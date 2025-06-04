import streamlit as st
import uuid
import os
import re
import logging
from dotenv import load_dotenv

# Third-party imports with error handling
try:
    from document_parser import parse_document
    from masking_agent import mask_text
    from agents import run_crew
    from pymongo import MongoClient
    import google.generativeai as genai
except ImportError as e:
    st.error(f"Import error: {e}")
    print(f"Import error: {e}")
    st.stop()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    filename="app_logs.txt",
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

print("Environment variables loaded:", "GOOGLE_API_KEY" in os.environ)

# Initialize MongoDB connection
try:
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client["ats_system"]
    resume_collection = db["resumes"]
    print("MongoDB connection successful.")
except Exception as e:
    st.error(f"MongoDB connection failed: {e}")
    logger.error(f"MongoDB connection failed: {e}")
    print(f"MongoDB connection failed: {e}")
    st.stop()

# Configure Google Gemini API
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    print("Google Gemini API configured successfully.")
except Exception as e:
    st.error(f"Failed to configure Gemini API: {e}")
    logger.error(f"Failed to configure Gemini API: {e}")
    print(f"Failed to configure Gemini API: {e}")
    st.stop()

# Set Streamlit page config to enforce a light theme
st.set_page_config(
    page_title="ATS Pro Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
    page_icon="🎯",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": None
    }
)


# Apply modern UI styling
st.markdown(
    """
    <style>
    /* General App Styling */
    .stApp {
        background: #ffffff;
        color: #000000 !important;
    }
    .stApp * {
        color: #000000 !important;
    }

    /* Main Card Styling */
    .main-card {
        background: #ffffff;
        border-radius: 20px;
        padding: 0.5rem;
        margin: 1rem auto;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
        max-width: 1200px;
    }

    /* Metric Card Styling */
    .metric-card {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: #000000 !important;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 0.5rem 0;
    }
    .metric-card h3 {
        color: #000000 !important;
        margin-bottom: 0.5rem;
    }
    .metric-card div {
        color: #000000 !important;
    }

    /* Score Card Styling */
    .score-card {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
    }
    .score-card h4 {
        color: #000000 !important;
    }
    .score-high {
        color: #000000 !important;
        font-size: 2.5rem;
        font-weight: bold;
    }
    .score-medium {
        color: #000000 !important;
        font-size: 2.5rem;
        font-weight: bold;
    }
    .score-low {
        color: #000000 !important;
        font-size: 2.5rem;
        font-weight: bold;
    }

    /* Pain Point Styling */
    .pain-point {
        background: rgba(255, 255, 255, 0.7);
        padding: 0.5rem 1rem;
        border-radius: 10px;
        margin: 0.3rem 0;
        border-left: 4px solid #4facfe;
        color: #000000 !important;
    }

    /* Typography */
    .header-title {
        color: #000000 !important;
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 1rem;
    }
    .section-title {
        color: #000000 !important;
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .job-desc-section {
        color: #000000 !important;
        margin-bottom: 1rem;
        text-align: left;
        padding-left: 1rem;
    }
    .job-desc-section p,
    .job-desc-section div {
        color: #000000 !important;
    }
    .job-desc-header {
        color: #000000 !important;
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .stMarkdown,
    .stMarkdown p,
    .stMarkdown div,
    .stMarkdown h1,
    .stMarkdown h2,
    .stMarkdown h3,
    .stMarkdown h4,
    .stMarkdown h5,
    .stMarkdown h6 {
        color: #000000 !important;
    }

    /* Button Styling */
    .stButton > button {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: #000000 !important;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        border: none;
        font-weight: 500;
        transition: opacity 0.3s;
    }
    .stButton > button:hover {
        opacity: 0.9;
    }

    /* Form Input Styling */
    .stTextArea textarea,
    .stNumberInput input {
        border: 1px solid #d1d5db;
        border-radius: 5px;
        padding: 0.5rem;
        background-color: #ffffff;
        color: #000000 !important;
    }
    .stTextArea label,
    .stNumberInput label,
    .stForm label {
        color: #000000 !important;
    }

    /* File Uploader Styling */
    div[data-testid="stFileUploader"] div[data-testid="stFileUploaderDropzone"],
    div[data-testid="stFileUploader"] div[data-testid="stFileUploaderDropzone"] > div,
    div[data-testid="stFileUploader"] div[role="button"],
    div[data-testid="stFileUploader"] div.uploadedFile,
    div.stFileUploader > div > div {
        background-color: #f3f4f6 !important;
    }
    div[data-testid="stFileUploader"] div[data-testid="stFileUploaderDropzone"] {
        border: 2px dashed #d1d5db !important;
    }
    div[data-testid="stFileUploader"] div[data-testid="stFileUploaderDropzone"]:hover {
        background-color: #f3f4f6 !important;
        border-color: #9ca3af !important;
    }
    div[data-testid="stFileUploader"] div[role="button"]:hover,
    div.stFileUploader > div > div:hover {
        background-color: #f3f4f6 !important;
    }
    
    div[data-testid="stFileUploader"] label,
    div[data-testid="stFileUploader"] p,
    div[data-testid="stFileUploader"] div,
    div[data-testid="stFileUploader"] div[data-testid="stFileUploaderFileName"],
    div[data-testid="stFileUploader"] div[data-testid="stFileUploaderFileName"] * {
        color: #000000 !important;
    }

    div[data-testid="stFileUploader"] span {
        color: #f3f4f6 !important;
    }

    /* Number Input Styling */
    div[data-testid="stNumberInput"] button,
    .stNumberInput button,
    div[data-testid="stNumberInput"] div[role="spinbutton"] + div button,
    div[data-testid="stNumberInput"] div[class*="step"] button,
    div[data-testid="stNumberInput"] button[aria-label*="increment"],
    div[data-testid="stNumberInput"] button[aria-label*="decrement"] {
        background-color: #f3f4f6 !important;
        color: #000000 !important;
        border: 1px solid #d1d5db !important;
    }
    div[data-testid="stNumberInput"] button:hover,
    .stNumberInput button:hover {
        background-color: #e5e7eb !important;
    }

    /* Spinner Styling */
    div[data-testid="stSpinner"],
    div[data-testid="stSpinner"] *,
    [class*="SpinnerMessage"] {
        color: #000000 !important;
    }

    /* Error Message Styling */
    div[data-testid="stAlert"],
    div[data-testid="stAlert"][kind="error"],
    div[data-testid="stAlert"] *,
    [class*="AlertMessage"] {
        color: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def store_resume_in_mongo(resume_id: str, masked_text: str, mappings: dict, collection_id: str) -> dict:
    """
    Store the masked resume data in MongoDB.

    Args:
        resume_id (str): Unique identifier for the resume.
        masked_text (str): Resume text with sensitive information masked.
        mappings (dict): Mapping of masked data to original data.
        collection_id (str): Identifier for the PII collection.

    Returns:
        dict: The stored resume data.
    """
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
    """
    Extract candidate name using LLM from masked resume text.

    Args:
        masked_text (str): Resume text with sensitive information masked.

    Returns:
        str: Candidate's full name, or "Unknown Candidate" if not found.
    """
    try:
        prompt = (
            "You are an expert in resume analysis. The following text is a resume with sensitive information masked (e.g., [ADDRESS], [PHONE], [EMAIL]). "
            "Your task is to identify and extract only the candidate's full name (first and last name, and optionally middle name or initial). "
            "The name is typically found at the top of the resume or in a 'Name' field. "
            "Do not extract any other information, such as job titles, technical terms, or masked data. "
            "If no clear name is found, return 'Unknown Candidate'. "
            "Return only the name as a string, nothing else.\n\n"
            f"{masked_text[:2000]}"  # Limit to avoid token overflow
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

def extract_job_title(jd_text: str) -> str:
    """
    Extract job title from the first non-empty, non-bulleted, non-placeholder line.

    Args:
        jd_text (str): Job description text.

    Returns:
        str: Extracted job title, or "Software Engineer" as a default.
    """
    lines = jd_text.split("\n")
    for line in lines:
        line = line.strip()
        if (
            line
            and not re.match(r"^[\*\-•\[]", line)
            and not re.search(r"\[insert|job description:", line, re.IGNORECASE)
        ):
            job_title = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            if len(job_title.split()) <= 10 and not job_title.lower().startswith(
                "we are seeking"
            ):
                return job_title.strip()
    return "Software Engineer"

def format_job_description(jd_text: str) -> dict:
    """
    Clean job description and extract sections.

    Args:
        jd_text (str): Raw job description text.

    Returns:
        dict: Formatted job description with description, responsibilities, and qualifications.
    """
    lines = jd_text.split("\n")
    skip_sections = ["job description:", "job summary:", "about ", "[insert"]
    in_responsibilities = False
    in_qualifications = False
    responsibilities = []
    qualifications = []
    description = []

    for line in lines:
        line = line.strip()
        if any(section.lower() in line.lower() for section in skip_sections):
            continue
        if line.lower().startswith("responsibilities:"):
            in_responsibilities = True
            in_qualifications = False
            continue
        if line.lower().startswith("qualifications:"):
            in_responsibilities = False
            in_qualifications = True
            continue
        if in_responsibilities and line:
            responsibilities.append(f"• {line}")
        elif in_qualifications and line:
            qualifications.append(f"• {line}")
        elif line:
            description.append(line)

    return {
        "description": "\n".join(description).strip() or "No description provided",
        "responsibilities": responsibilities,
        "qualifications": qualifications,
    }

def format_pain_points(pain_points_text: str) -> list:
    """
    Format pain points into a list of individual bullet points.

    Args:
        pain_points_text (str): Raw pain points text.

    Returns:
        list: List of formatted pain points.
    """
    if not pain_points_text or pain_points_text.lower() == "none":
        return ["None identified"]

    points = re.split(r"\n\s*[\*\-•]\s*", pain_points_text)
    formatted_points = []

    for point in points:
        point = point.strip()
        if point:
            point = re.sub(r"\*\*(.*?)\*\*", r"\1", point)
            point = re.sub(r"\*+$", "", point)
            point = re.sub(r"^\s*", "", point)
            point = re.sub(r"\s+", " ", point)
            if point and point[0].islower():
                point = point[0].upper() + point[1:]
            if point and point[-1] not in ".!?":
                point += "."
            if len(point.strip()) >= 10:
                formatted_points.append(point)

    return formatted_points if formatted_points else ["No valid points identified"]

def parse_crew_output(result) -> tuple:
    """
    Parse CrewAI output, handling string or CrewOutput objects.

    Args:
        result: CrewAI output, either as a string or CrewOutput object.

    Returns:
        tuple: (score1, pain_points1, generated_jd, score2, pain_points2, full_jd_text)
    """
    score1 = pain_points1 = generated_jd = score2 = pain_points2 = full_jd_text = "N/A"

    if isinstance(result, str):
        logger.info("Parsing CrewAI result as string")
        lines = result.split("\n")
        task1_start = task2_start = -1

        for i, line in enumerate(lines):
            if "ATS Score:" in line and "Generated Job Description:" not in result[: result.find(line)]:
                task1_start = i
            elif "Generated Job Description:" in line:
                task2_start = i
                break

        if task1_start != -1:
            task1_text = "\n".join(lines[task1_start:task2_start if task2_start != -1 else None])
            score1_match = re.search(r"ATS Score:\s*(\d+)", task1_text)
            pain1_match = re.search(r"Pain Points:\s*(.*?)(?=\n\n|\Z)", task1_text, re.DOTALL)
            if score1_match:
                score1 = score1_match.group(1)
                logger.info(f"Task 1 ATS Score: {score1}")
            if pain1_match:
                pain_points1 = format_pain_points(pain1_match.group(1).strip())
                logger.info("Task 1 Pain Points extracted")

        if task2_start != -1:
            task2_text = "\n".join(lines[task2_start:])
            jd_match = re.search(r"Generated Job Description:\s*(.*?)(?=\n\s*ATS Score:)", task2_text, re.DOTALL)
            if jd_match:
                full_jd_text = format_job_description(jd_match.group(1).strip())
                generated_jd = extract_job_title(jd_match.group(1).strip())
                logger.info(f"Task 2 Job Description extracted: {generated_jd}")
            else:
                jd_lines = []
                in_jd_section = False
                for line in lines[task2_start:]:
                    if "Generated Job Description:" in line:
                        in_jd_section = True
                        continue
                    elif "ATS Score:" in line and in_jd_section:
                        break
                    elif in_jd_section:
                        jd_lines.append(line)
                if jd_lines:
                    full_jd_text = format_job_description("\n".join(jd_lines).strip())
                    generated_jd = extract_job_title("\n".join(jd_lines).strip())
                    logger.info(f"Task 2 Job Description extracted via fallback: {generated_jd}")

            score2_match = re.search(r"ATS Score:\s*(\d+)", task2_text)
            pain2_match = re.search(r"Pain Points:\s*(.*?)(?=\n\n|\Z)", task2_text, re.DOTALL)
            if score2_match:
                score2 = score2_match.group(1)
                logger.info(f"Task 2 ATS Score: {score2}")
            if pain2_match:
                pain_points2 = format_pain_points(pain2_match.group(1).strip())
                logger.info("Task 2 Pain Points extracted")

    else:
        try:
            if hasattr(result, "tasks_output") and len(result.tasks_output) >= 2:
                task1_output = str(result.tasks_output[0].raw)
                task2_output = str(result.tasks_output[1].raw)
                logger.info("Parsing CrewAI result as CrewOutput object")

                score1_match = re.search(r"ATS Score:\s*(\d+)", task1_output)
                pain1_match = re.search(r"Pain Points:\s*(.*?)(?=\n\n|\Z)", task1_output, re.DOTALL)
                if score1_match:
                    score1 = score1_match.group(1)
                    logger.info(f"Task 1 ATS Score: {score1}")
                if pain1_match:
                    pain_points1 = format_pain_points(pain1_match.group(1).strip())
                    logger.info("Task 1 Pain Points extracted")

                jd_match = re.search(r"Generated Job Description:\s*(.*?)(?=\n\s*ATS Score:)", task2_output, re.DOTALL)
                score2_match = re.search(r"ATS Score:\s*(\d+)", task2_output)
                pain2_match = re.search(r"Pain Points:\s*(.*?)(?=\n\n|\Z)", task2_output, re.DOTALL)
                if jd_match:
                    full_jd_text = format_job_description(jd_match.group(1).strip())
                    generated_jd = extract_job_title(jd_match.group(1).strip())
                    logger.info(f"Task 2 Job Description extracted: {generated_jd}")
                if score2_match:
                    score2 = score2_match.group(1)
                    logger.info(f"Task 2 ATS Score: {score2}")
                if pain2_match:
                    pain_points2 = format_pain_points(pain2_match.group(1).strip())
                    logger.info("Task 2 Pain Points extracted")
        except AttributeError as e:
            logger.error(f"Error parsing CrewOutput: {e}")
            pass

    return score1, pain_points1, generated_jd, score2, pain_points2, full_jd_text

def get_score_class(score: str) -> str:
    """
    Determine the CSS class for the score based on the score value.

    Args:
        score (str): The score value as a string.

    Returns:
        str: CSS class based on the score range.
    """
    try:
        score = int(score)
        if score >= 80:
            return "score-high"
        elif score >= 50:
            return "score-medium"
        else:
            return "score-low"
    except (ValueError, TypeError):
        return "score-low"

def main():
    """Main function to run the ATS Pro Dashboard application."""

    # Initialize session state
    if "analyzing" not in st.session_state:
        st.session_state.analyzing = False
    if "results" not in st.session_state:
        st.session_state.results = None

    # Header
    st.markdown('<div class="header-title">🎯 ATS Pro Dashboard</div>', unsafe_allow_html=True)

    # Main Input Card
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📋 Resume Analysis</div>', unsafe_allow_html=True)

    with st.form(key="ats_form"):
        col1, col2 = st.columns([2, 1])
        with col1:
            uploaded_file = st.file_uploader(
                "📄 Upload Resume (PDF/DOCX)",
                type=["pdf", "docx"],
                help="Upload a PDF or DOCX resume file",
            )
            job_description = st.text_area(
                "💼 Job Description", height=100, help="Enter the job description for analysis"
            )
        with col2:
            required_experience = st.number_input(
                "⏱️ Years of Experience Required",
                min_value=0,
                step=1,
                help="Specify minimum years of experience",
            )
            submit_button = st.form_submit_button("🚀 Analyze Resume")

    st.markdown("</div>", unsafe_allow_html=True)

    if submit_button:
        if not os.getenv("GOOGLE_API_KEY"):
            st.error("Gemini API key not found in .env file")
            logger.error("Gemini API key not found")
            st.stop()

        try:
            if not uploaded_file or not job_description or required_experience < 0:
                raise ValueError(
                    "Please upload a resume, provide a job description, and specify valid years of experience."
                )

            st.session_state.analyzing = True
            with st.spinner("🔍 Analyzing resume..."):
                logger.info("Parsing resume")
                resume_text = parse_document(uploaded_file, uploaded_file.name)
                logger.info("Masking resume text")
                masked_text, mappings, collection_id = mask_text(resume_text)
                logger.info("Extracting candidate name")
                candidate_name = get_candidate_name(masked_text)
                resume_id = str(uuid.uuid4())
                store_resume_in_mongo(resume_id, masked_text, mappings, collection_id)
                logger.info("Running CrewAI")
                result = run_crew(masked_text, job_description, required_experience)
                score1, pain_points1, generated_jd, score2, pain_points2, full_jd_text = parse_crew_output(
                    result
                )
                st.session_state.results = {
                    "candidate_name": candidate_name,
                    "score1": score1,
                    "pain_points1": pain_points1,
                    "generated_jd": generated_jd,
                    "score2": score2,
                    "pain_points2": pain_points2,
                    "full_jd_text": full_jd_text,
                    "required_experience": required_experience,
                }
            st.session_state.analyzing = False

        except Exception as e:
            st.session_state.analyzing = False
            st.error(f"❌ Error: {str(e)}")
            logger.error(f"Error in main: {e}")

    # Display results if available
    if st.session_state.results:
        results = st.session_state.results
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-title">👤 Analysis Results for {results["candidate_name"]}</div>',
            unsafe_allow_html=True,
        )

        # Split into Left (HR) and Right (AI) sections with equal width
        col1, col2 = st.columns([1, 1])

        # Left Side: HR Agent-Generated Results
        with col1:
            st.markdown('<div class="section-title">🔍 HR Agent-Generated Results</div>', unsafe_allow_html=True)

            # HR Score
            st.markdown(
                f"""
                <div class="metric-card">
                    <h3>HR Job Match</h3>
                    <div class="{get_score_class(results["score1"])}">{results["score1"]}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # HR Pain Points
            st.markdown('<div class="score-card">', unsafe_allow_html=True)
            st.markdown("<h4>HR Job Issues</h4>", unsafe_allow_html=True)
            for point in results["pain_points1"]:
                st.markdown(f'<div class="pain-point">• {point}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Right Side: AI-Generated Results
        with col2:
            st.markdown('<div class="section-title">✨ AI-Generated Results</div>', unsafe_allow_html=True)

            # AI Score
            st.markdown(
                f"""
                <div class="metric-card">
                    <h3>AI Generated Match</h3>
                    <div class="{get_score_class(results["score2"])}">{results["score2"]}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Job Title
            st.markdown('<div class="job-desc-section">', unsafe_allow_html=True)
            st.markdown('<div class="job-desc-header">Job Title</div>', unsafe_allow_html=True)
            st.markdown(f"{results['generated_jd']}", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # Experience Required
            st.markdown('<div class="job-desc-section">', unsafe_allow_html=True)
            st.markdown('<div class="job-desc-header">Experience Required</div>', unsafe_allow_html=True)
            st.markdown(f"{results['required_experience']}+ years", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # Job Description
            st.markdown('<div class="job-desc-section">', unsafe_allow_html=True)
            st.markdown('<div class="job-desc-header">Job Description</div>', unsafe_allow_html=True)
            st.markdown(f"{results['full_jd_text']['description']}", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # Qualifications
            if results["full_jd_text"]["qualifications"]:
                st.markdown('<div class="job-desc-section">', unsafe_allow_html=True)
                st.markdown('<div class="job-desc-header">Qualifications</div>', unsafe_allow_html=True)
                for qual in results["full_jd_text"]["qualifications"]:
                    st.markdown(f'<div class="pain-point">{qual}</div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # Responsibilities
            if results["full_jd_text"]["responsibilities"]:
                st.markdown('<div class="job-desc-section">', unsafe_allow_html=True)
                st.markdown('<div class="job-desc-header">Responsibilities</div>', unsafe_allow_html=True)
                for resp in results["full_jd_text"]["responsibilities"]:
                    st.markdown(f'<div class="pain-point">{resp}</div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # AI Pain Points
            st.markdown('<div class="score-card">', unsafe_allow_html=True)
            st.markdown("<h4>AI Generated Issues</h4>", unsafe_allow_html=True)
            for point in results["pain_points2"]:
                st.markdown(f'<div class="pain-point">• {point}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()