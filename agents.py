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
    Fallback scoring logic if LLM fails - focused on technical assessment.
    """
    score = 50
    pain_points_list = []
    summary = "Technical assessment limited due to processing constraints."
    
    # Enhanced technical experience detection
    experience_patterns = [
        r'(\d+\.?\d*)\s*(?:year|yr|yrs|years)?\s*(?:of\s*)?(?:experience|exp)',
        r'(\d+\.?\d*)\+?\s*(?:year|yr|yrs|years)',
        r'over\s*(\d+\.?\d*)\s*(?:year|yr|yrs|years)',
        r'(\d+\.?\d*)\s*to\s*\d+\.?\d*\s*(?:year|yr|yrs|years)'
    ]
    
    candidate_years = 0
    for pattern in experience_patterns:
        match = re.search(pattern, resume_text, re.IGNORECASE)
        if match:
            candidate_years = max(candidate_years, float(match.group(1)))
    
    if candidate_years < required_experience:
        gap = required_experience - candidate_years
        score -= min(20, gap * 5)  # Cap penalty at 20 points
        pain_points_list.append(f"Technical experience gap: {candidate_years} years vs {required_experience} required")
    
    # Enhanced technical skills assessment
    technical_skills = {
        'critical': ['Python', 'Java', 'JavaScript', 'React', 'Node.js', 'AWS', 'Docker', 'Kubernetes'],
        'important': ['GCP', 'Azure', 'Terraform', 'CI/CD', 'Git', 'SQL', 'MongoDB', 'Redis'],
        'preferred': ['GraphQL', 'Microservices', 'DevOps', 'Machine Learning', 'TensorFlow', 'PyTorch']
    }
    
    critical_missing = 0
    important_missing = 0
    
    for skill in technical_skills['critical']:
        if skill.lower() in job_description.lower() and skill.lower() not in resume_text.lower():
            critical_missing += 1
            score -= 8
            pain_points_list.append(f"Missing critical technical skill: {skill}")
    
    for skill in technical_skills['important']:
        if skill.lower() in job_description.lower() and skill.lower() not in resume_text.lower():
            important_missing += 1
            score -= 4
            pain_points_list.append(f"Missing important technical skill: {skill}")
    
    # Technical depth assessment
    technical_indicators = ['API', 'database', 'algorithm', 'system design', 'architecture', 'scalability', 'performance']
    technical_depth = sum(1 for indicator in technical_indicators if indicator.lower() in resume_text.lower())
    
    if technical_depth < 3:
        score -= 10
        pain_points_list.append("Limited technical depth indicators in resume")
    
    score = max(0, min(100, score))
    status = "Shortlisted" if score > 70 else "Under Consideration" if score >= 50 else "Rejected"
    
    # Categorize pain points for technical assessment
    pain_points = {
        "critical": [p for p in pain_points_list if "Missing critical" in p or "experience gap" in p],
        "major": [p for p in pain_points_list if "Missing important" in p or "Limited technical depth" in p],
        "minor": [p for p in pain_points_list if p not in pain_points["critical"] and p not in pain_points["major"]] or ["Technical assessment requires more detailed evaluation"]
    }
    
    mandatory_skills_gap = bool(pain_points["critical"])
    
    # Technical-focused summary
    summary_parts = [
        f"Technical screening assessment based on available resume data shows {candidate_years} years of experience.",
        f"Score of {score} indicates {'strong technical alignment' if score > 70 else 'moderate technical fit' if score >= 50 else 'significant technical gaps'}.",
    ]
    
    if critical_missing > 0:
        summary_parts.append(f"Critical technical skills missing: {critical_missing} key technologies not demonstrated.")
    
    if important_missing > 0:
        summary_parts.append(f"Important technical capabilities gap: {important_missing} preferred skills absent.")
    
    summary_parts.append("Recommend technical interview to validate hands-on experience and assess problem-solving capabilities.")
    
    summary = " ".join(summary_parts)
    
    result = {
        "score": score,
        "mandatory_skills_gap": mandatory_skills_gap,
        "pain_points": pain_points,
        "summary": summary,
        "status": status
    }
    
    logger.info(f"Technical fallback assessment result: {result}")
    return result

def analyze_resume(resume_text, job_description, required_experience):
    """
    Technical-focused resume analysis using Gemini 1.5 Flash for post-HR screening.
    """
    try:
        prompt = f"""
            **CONTEXT:** This is a TECHNICAL SCREENING analysis for a candidate who has already passed initial HR screening. Focus exclusively on technical competency, hands-on experience, and job-specific technical requirements.

            **MASKED RESUME DATA:**
            {resume_text}

            **JOB TECHNICAL REQUIREMENTS:**
            {job_description}

            **TECHNICAL ANALYSIS INSTRUCTIONS:**

            **1. TECHNICAL SKILLS ASSESSMENT (60 points total):**

            **Mandatory Technical Skills (35 points):**
                - Extract MANDATORY technical skills from job description (keywords: "required", "must have", "essential", "mandatory")
                - Score: (Mandatory Skills Present / Total Mandatory Skills) × 35
                - Each missing mandatory skill = -8 points penalty
                - Focus on: Programming languages, frameworks, cloud platforms, databases, tools
                - Only count skills EXPLICITLY mentioned in resume

            **Core Technical Competencies (25 points):**
                - Identify important technical skills (preferred/nice-to-have)
                - Include: DevOps tools, testing frameworks, architectural patterns, methodologies
                - Score: (Core Skills Present / Total Core Skills) × 25
                - Each missing core skill = -3 points penalty

            **2. TECHNICAL EXPERIENCE DEPTH (25 points):**

            **Hands-on Experience Assessment (15 points):**
                - Extract required years from job description
                - Compare with candidate's technical experience
                - Award full points if experience >= required
                - Proportional scoring if below requirement
                - Consider project complexity and technical leadership

            **Technical Project Quality (10 points):**
                - Assess technical project descriptions and complexity
                - Look for: System design, scalability, performance optimization
                - Architecture decisions, technical challenges solved
                - Open source contributions, technical leadership

            **3. TECHNICAL CERTIFICATIONS & CONTINUOUS LEARNING (15 points):**
                - Relevant technical certifications (up to 8 points)
                - Advanced degrees in technical fields (up to 4 points)
                - Recent technical learning/courses (up to 3 points)
                - Only award if explicitly mentioned

            **TECHNICAL PAIN POINTS IDENTIFICATION:**

            **CRITICAL Technical Issues (Immediate Concerns):**
                - Missing mandatory programming languages/frameworks
                - Insufficient hands-on experience in core tech stack
                - No experience with required cloud platforms/databases
                - Missing essential technical certifications
                - Lack of system design/architecture experience

            **MAJOR Technical Issues (Training Required):**
                - Limited experience with important technologies
                - Outdated technology versions or practices
                - Missing DevOps/CI-CD experience
                - Limited exposure to scalable systems
                - Weak evidence of technical problem-solving

            **MINOR Technical Issues (Growth Opportunities):**
                - Missing nice-to-have technical skills
                - Limited exposure to emerging technologies
                - Could benefit from additional certifications
                - Room for improvement in technical leadership

            **TECHNICAL SUMMARY REQUIREMENTS:**
            Write exactly 130-160 words focusing on:
                - Technical readiness for the specific role
                - Depth of hands-on experience in required technologies
                - Technical problem-solving capabilities demonstrated
                - Ability to work with complex technical systems
                - Potential for handling technical challenges
                - Specific technical training needs
                - Clear recommendation for technical interview focus areas

            **For high-scoring candidates (70+):** Emphasize technical strengths while noting specific areas for validation in technical interview.
            **For moderate candidates (50-69):** Focus on technical gaps and required upskilling.
            **For low-scoring candidates (<50):** Highlight major technical deficiencies and extensive training needs.

            **OUTPUT FORMAT - Return ONLY valid JSON:**
            {{
                "score": <integer 0-100>,
                "mandatory_skills_gap": <boolean>,
                "pain_points": {{
                    "critical": [<list of critical technical issues>],
                    "major": [<list of major technical concerns>],
                    "minor": [<list of minor technical improvements>]
                }},
                "summary": "<130-160 words technical assessment>"
            }}

            **ANALYSIS GUIDELINES:**
                - Focus ONLY on technical competencies and job-specific requirements
                - Assess hands-on experience over theoretical knowledge
                - Prioritize current technology stack experience
                - Consider technical complexity of past projects
                - Evaluate potential for technical growth and learning
                - Be specific about technology gaps and training needs
                - Provide actionable insights for technical interview planning
                - Base assessment strictly on resume content provided
                - Do not infer or assume unlisted technical skills
        """

        response = llm.generate_content(prompt)
        output = response.text.strip()
        logger.info(f"Technical LLM analysis output: {output}")

        # Handle potential code block markers
        if output.startswith("```json"):
            output = output[len("```json"):].rstrip("```").strip()
        elif output.startswith("```"):
            output = output[3:].rstrip("```").strip()

        # Parse and validate JSON output
        try:
            result = json.loads(output)
            logger.debug(f"Parsed technical analysis: {result}")

            # Validate required fields
            required_keys = ["score", "mandatory_skills_gap", "pain_points", "summary"]
            if not all(key in result for key in required_keys):
                missing_keys = [key for key in required_keys if key not in result]
                logger.error(f"Technical analysis missing keys: {missing_keys}")
                raise ValueError(f"Missing required keys: {missing_keys}")

            # Validate and normalize score
            if not isinstance(result["score"], (int, float)) or result["score"] < 0 or result["score"] > 100:
                logger.error(f"Invalid technical score: {result['score']}")
                raise ValueError(f"Invalid score: {result['score']}")
            result["score"] = max(0, min(100, int(result["score"])))

            # Validate mandatory_skills_gap
            if not isinstance(result["mandatory_skills_gap"], bool):
                logger.warning(f"Invalid mandatory_skills_gap: {result['mandatory_skills_gap']}")
                result["mandatory_skills_gap"] = bool(result.get("pain_points", {}).get("critical", []))

            # Validate and normalize pain_points
            if not isinstance(result["pain_points"], dict):
                logger.warning("Invalid pain_points structure, using default")
                result["pain_points"] = {
                    "critical": ["Technical assessment data incomplete"],
                    "major": ["Requires detailed technical evaluation"],
                    "minor": ["Technical interview recommended for validation"]
                }
            else:
                for severity in ["critical", "major", "minor"]:
                    if severity not in result["pain_points"]:
                        result["pain_points"][severity] = []
                    elif not isinstance(result["pain_points"][severity], list):
                        result["pain_points"][severity] = [str(result["pain_points"][severity])]
                    else:
                        result["pain_points"][severity] = [str(item) for item in result["pain_points"][severity] if item]

                # Ensure at least one category has content
                if not any(result["pain_points"][severity] for severity in ["critical", "major", "minor"]):
                    result["pain_points"]["minor"] = ["Technical evaluation completed - interview recommended"]

            # Validate and enhance summary
            if not isinstance(result["summary"], str):
                logger.warning("Invalid summary format")
                result["summary"] = self._generate_technical_summary(result["score"], result["pain_points"])
            else:
                word_count = len(result["summary"].split())
                if word_count < 120 or word_count > 170:
                    logger.warning(f"Technical summary length {word_count} outside target range")
                    # Keep original but ensure it's technical-focused
                    if word_count < 120:
                        result["summary"] += " Technical interview should focus on validating hands-on experience, problem-solving approach, and specific technology implementation details to confirm technical readiness."

            # Assign technical screening status
            score = result["score"]
            if score > 70:
                result["status"] = "Shortlisted"
            elif score >= 50:
                result["status"] = "Under Consideration"  
            else:
                result["status"] = "Rejected"

            logger.info(f"Final technical analysis: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in technical analysis: {e}")
            return fallback_ats_score(resume_text, job_description, required_experience)
        except ValueError as e:
            logger.error(f"Validation error in technical analysis: {e}")
            return fallback_ats_score(resume_text, job_description, required_experience)

    except Exception as e:
        logger.error(f"Technical LLM analysis failed: {e}")
        return fallback_ats_score(resume_text, job_description, required_experience)

def _generate_technical_summary(score, pain_points):
    """Generate a technical-focused summary based on score and pain points."""
    summary_parts = []
    
    if score > 75:
        summary_parts.append("Candidate demonstrates strong technical competency with solid alignment to role requirements.")
    elif score >= 60:
        summary_parts.append("Candidate shows moderate technical alignment with some skill gaps requiring attention.")
    else:
        summary_parts.append("Candidate exhibits significant technical gaps that may impact role performance.")
    
    if pain_points.get("critical"):
        summary_parts.append(f"Critical technical concerns: {'; '.join(pain_points['critical'][:2])}.")
    
    if pain_points.get("major"):
        summary_parts.append(f"Major technical areas for development: {'; '.join(pain_points['major'][:2])}.")
    
    summary_parts.append("Technical interview recommended to validate hands-on experience, assess problem-solving capabilities, and determine specific training needs for optimal role performance.")
    
    return " ".join(summary_parts)