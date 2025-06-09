from flask import Flask, request, render_template, jsonify, send_from_directory
import uuid
import os
import logging
import re
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from document_parser import parse_document
from masking_agent import mask_text
from agents import analyze_resume
from pymongo import MongoClient
import google.generativeai as genai

app = Flask(__name__, static_folder='frontend/build/static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    filename="app_logs.txt",
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded: GOOGLE_API_KEY present=%s", "GOOGLE_API_KEY" in os.environ)

# Initialize MongoDB connection
try:
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client["ats_system"]
    resume_collection = db["resumes"]
    logger.info("MongoDB connection successful.")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    exit(1)

# Configure Google Gemini API
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    logger.info("Google Gemini API configured successfully.")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}")
    exit(1)

def extract_required_experience(job_description: str) -> int:
    """
    Extract required years of experience from the job description using regex.
    Looks for patterns like 'X years of experience', 'X+ years', etc.
    Returns 0 if no experience requirement is found.
    """
    # Regex to match patterns like '3 years', '5+ years', '3-5 years', etc.
    patterns = [
        r'(\d+)\s*(?:\+|-)?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience)',  # e.g., '3 years of experience', '5+ years'
        r'(\d+)-(\d+)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience)'         # e.g., '3-5 years of experience'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, job_description, re.IGNORECASE)
        if match:
            if pattern == patterns[1]:  # Range like '3-5 years'
                lower, upper = int(match.group(1)), int(match.group(2))
                return lower  # Take the lower bound as the minimum requirement
            else:  # Single value like '3 years'
                return int(match.group(1))
    
    logger.warning("No experience requirement found in job description, defaulting to 0 years.")
    return 0

def store_resume_in_mongo(resume_id: str, masked_text: str, mappings: dict, collection_id: str) -> dict:
    resume_data = {
        "resume_id": resume_id,
        "masked_text": masked_text,
        "pii_mappings": mappings,
        "pii_collection_id": collection_id,
    }
    resume_collection.insert_one(resume_data)
    logger.info(f"Stored resume with ID: {resume_id}")
    return resume_data

def get_candidate_name(masked_text: str) -> str:
    try:
        prompt = (
            "You are an expert in resume analysis. The following text is a resume with sensitive information masked (e.g., [ADDRESS], [PHONE], [EMAIL]). "
            "Your task is to identify and extract only the candidate's full name (first and last name, and optionally middle name or initial). "
            "The name is typically found at the top of the resume or in a 'Name' field. "
            "Do not extract any other information, such as job titles, technical terms, or masked data. "
            "If no clear name is found, return 'Unknown Candidate'. "
            "Return only the name as a string, nothing else.\n\n"
            f"{masked_text[:2000]}"
        )
        response = model.generate_content(prompt)
        candidate_name = response.text.strip()
        if not candidate_name or len(candidate_name.split()) < 2 or len(candidate_name) > 30:
            logger.warning("No valid candidate name found by LLM, using 'Unknown Candidate'")
            return "Unknown Candidate"
        logger.info(f"Candidate name extracted via LLM: {candidate_name}")
        return candidate_name
    except Exception as e:
        logger.error(f"Error extracting name with LLM: {e}")
        return "Unknown Candidate"

@app.route('/')
def index():
    logger.info("Attempting to render index.html")
    template_path = os.path.join(app.template_folder, 'index.html')
    if not os.path.exists(template_path):
        logger.error(f"Template not found at: {template_path}")
        return jsonify({"error": "Template index.html not found"}), 500
    
    js_files = []
    css_files = []
    static_js_path = os.path.join(app.static_folder, 'js')
    static_css_path = os.path.join(app.static_folder, 'css')
    
    if os.path.exists(static_js_path):
        js_files = [f for f in os.listdir(static_js_path) if f.endswith('.js') and 'main.' in f]
    if os.path.exists(static_css_path):
        css_files = [f for f in os.listdir(static_css_path) if f.endswith('.css') and 'main.' in f]
    
    if not js_files:
        logger.error("No main.js file found in static/js")
        return jsonify({"error": "No main.js file found"}), 500
    
    import time
    cache_buster = int(time.time())
    js_files = [f"{f}?v={cache_buster}" for f in js_files]
    css_files = [f"{f}?v={cache_buster}" for f in css_files]
    
    return render_template('index.html', js_files=js_files, css_files=css_files)

@app.route('/analyze', methods=['POST'])
def analyze_resumes():
    try:
        if 'resumes' not in request.files or not request.form.get('job_description'):
            return jsonify({"error": "Missing resumes or job description"}), 400

        resumes = request.files.getlist('resumes')
        job_description = request.form['job_description']
        # Extract required experience from job description
        required_experience = extract_required_experience(job_description)
        results = []

        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        for resume in resumes:
            if resume and resume.filename.endswith(('.pdf', '.docx')):
                filename = secure_filename(resume.filename)
                resume_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                resume.save(resume_path)
                logger.info(f"Processing resume: {filename}")
                
                with open(resume_path, 'rb') as f:
                    resume_text = parse_document(f, filename)
                masked_text, mappings, collection_id = mask_text(resume_text)
                candidate_name = get_candidate_name(masked_text)
                resume_id = str(uuid.uuid4())
                store_resume_in_mongo(resume_id, masked_text, mappings, collection_id)
                result = analyze_resume(masked_text, job_description, required_experience)
                
                results.append({
                    "resume_name": filename,
                    "candidate_name": candidate_name,
                    "score": result["score"],
                    "pain_points": result["pain_points"],
                    "summary": result["summary"],
                    "status": result["status"],
                    "resume_path": f"/uploads/{filename}"
                })

        return jsonify(results)
    except Exception as e:
        logger.error(f"Error in analyze_resumes: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/uploads/<filename>')
def download_resume(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/static/<path:path>')
def serve_static(path):
    response = send_from_directory(app.static_folder, path)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    logger.info(f"Serving static file: {path}")
    return response

if __name__ == '__main__':
    app.run(debug=True)