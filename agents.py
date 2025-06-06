import logging
import os
import re
import json
from dotenv import load_dotenv
import google.generativeai as genai

logging.basicConfig(level=logging.DEBUG, filename='logs.txt', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Configure Gemini API
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    llm = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}")
    raise

def fallback_ats_score(resume_text, job_description, required_experience):
    """
    Fallback scoring logic if LLM fails.
    """
    score = 50
    pain_points = []
    summary = "Basic candidate with some relevant skills but limited details available."
    # Improved regex to detect experience more flexibly
    experience_match = re.search(r'(\d+\.?\d*)\s*(?:year|yr|yrs|years)?\s*(?:of\s*)?(?:experience)?', resume_text, re.IGNORECASE)
    candidate_years = float(experience_match.group(1)) if experience_match else 0
    if candidate_years < required_experience:
        gap = required_experience - candidate_years
        score -= 10 * gap
        pain_points.append(f"Insufficient experience: {candidate_years} years vs {required_experience} required.")
    elif candidate_years > required_experience + 5:
        score -= 5
        pain_points.append("Potential overqualification: significantly more experience than required.")
    skills = ['Python', 'GCP', 'AWS', 'Kubernetes', 'Terraform', 'CI/CD', 'Java', 'Go', 'C++']
    for skill in skills:
        if skill.lower() in job_description.lower() and skill.lower() not in resume_text.lower():
            score -= 5
            pain_points.append(f"Missing skill: {skill}.")
    score = max(0, min(100, score))
    status = "Shortlisted" if score > 80 else "Under Consideration" if score >= 60 else "Rejected"
    pain_points = pain_points or ["No specific gaps identified."]
    logger.info(f"Fallback ATS score: {score}, Status: {status}, Pain points: {pain_points}")
    return {
        "score": score,
        "pain_points": pain_points,
        "summary": summary,
        "status": status
    }

def analyze_resume(resume_text, job_description, required_experience):
    """
    Analyze resume using Gemini 1.5 Flash with improved ATS logic.
    """
    try:
        prompt = f"""
        **Resume Text:**
        {resume_text}
        
        **Job Description:**
        {job_description}
        
        **Required Experience:** {required_experience} years
        
        **Instructions:**
        
        **1. Calculate ATS Score (0-100) using this exact methodology:**
        
        **Technical Skills Match (40 points):**
        - Identify all technical skills mentioned in the job description
        - Count how many of these skills are present in the resume
        - Calculate: (Skills Found / Total Required Skills) × 40
        - Round to nearest integer
        
        **Experience Match (30 points):**
        - Extract years of relevant experience from resume
        - If experience >= required: award full 30 points
        - If experience < required: calculate (Actual Experience / Required Experience) × 30
        - Round to nearest integer
        
        **Soft Skills & Certifications (20 points):**
        - Identify soft skills and certifications mentioned in job description
        - Count matches in resume
        - Award points proportionally up to 20 points maximum
        
        **Education & Additional Factors (10 points):**
        - Relevant degree: 5 points
        - Project relevance: 3 points
        - Industry experience: 2 points
        - Award points based on presence of these factors
        
        **Final Score:** Sum all components (maximum 100)
        
        **2. Identify ALL Pain Points:**
        List every significant gap or concern, including:
        - Missing technical skills (be specific)
        - Experience gaps (quantify the shortage)
        - Missing certifications
        - Education mismatches
        - Lack of relevant projects
        - Industry experience gaps
        - Any other notable deficiencies
        
        **3. Provide Summary (100-150 words):**
        Write a balanced assessment covering:
        - Key strengths and relevant experience
        - Major skill gaps and weaknesses
        - Overall fit for the role
        - Potential for growth or training needs
        
        **Output Requirements:**
        - Return ONLY a valid JSON object
        - Include exactly these keys: "score", "pain_points", "summary"
        - Score must be an integer between 0-100
        - Pain_points must be an array of strings
        - Summary must be 100-150 words
        - Do NOT include "status" or any other fields
        
        **Example Format:**
        {{
            "score": 75,
            "pain_points": [
                "Missing React.js experience (required skill)",
                "Only 2 years Python experience vs 3+ required",
                "No AWS certification mentioned"
            ],
            "summary": "Candidate shows strong foundation in software development with solid experience in Python and database management. However, lacks specific React.js frontend experience which is critical for this role. The 2 years of Python experience falls short of the 3+ years requirement, though the quality of projects demonstrates good technical competency. Missing AWS certification could impact cloud deployment responsibilities. Strong problem-solving skills and relevant project portfolio suggest potential for growth with proper training."
        }}
        """
        response = llm.generate_content(prompt)
        output = response.text.strip()
        logger.info(f"Raw LLM output for resume analysis: {output}")

        # Handle potential code block markers
        if output.startswith("```json"):
            output = output[len("```json"):].rstrip("```").strip()
            logger.info(f"LLM output after stripping markers: {output}")
        elif output.startswith("```"):
            output = output[3:].rstrip("```").strip()
            logger.info(f"LLM output after stripping plain code markers: {output}")

        # Parse JSON output
        try:
            result = json.loads(output)
            required_keys = ["score", "pain_points", "summary"]
            if not all(key in result for key in required_keys):
                missing_keys = [key for key in required_keys if key not in result]
                logger.error(f"LLM output missing required keys: {missing_keys}")
                raise ValueError(f"Missing required keys in LLM output: {missing_keys}")
            if not isinstance(result["score"], int) or result["score"] < 0 or result["score"] > 100:
                logger.error(f"Invalid score in LLM output: {result['score']}")
                raise ValueError(f"Invalid score: {result['score']}")
            if not isinstance(result["pain_points"], list) or not result["pain_points"]:
                logger.warning("No pain points provided by LLM, setting default")
                result["pain_points"] = ["No specific gaps identified."]
            if not isinstance(result["summary"], str) or len(result["summary"]) < 50:
                logger.warning("Invalid or short summary provided by LLM, setting default")
                result["summary"] = "No summary provided."
            
            # Assign status based on score
            score = result["score"]
            result["status"] = (
                "Shortlisted" if score > 70 else
                "Under Consideration" if 50 < score <= 70 else
                "Rejected"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM output as JSON: {e}, output: {output}")
            return fallback_ats_score(resume_text, job_description, required_experience)
        except ValueError as e:
            logger.error(f"Validation error in LLM output: {e}")
            return fallback_ats_score(resume_text, job_description, required_experience)

        logger.info(f"Analysis result: {result}")
        return result
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        return fallback_ats_score(resume_text, job_description, required_experience)