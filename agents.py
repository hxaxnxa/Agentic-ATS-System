import logging
import os
import re
import json
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Dict, List

# Setup logging
logging.basicConfig(level=logging.DEBUG, filename='logs.txt', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Gemini API
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    llm = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}")
    raise

def fallback_ats_score(resume_text: str, job_description: str, required_experience: int, projects: List[Dict]) -> Dict:
    """
    Fallback scoring logic if LLM fails - adjusted for new scoring weights.
    Scoring: 70% projects, 10% technical skills, 10% good-to-have skills, 10% experience.
    """
    score = 0
    pain_points_list = []

    # Extract skills from job description
    # Mandatory skills
    mandatory_skills_raw = re.findall(r'(?:required|must have|essential|mandatory)\s*[:\s]*(.*?)(?=\n[A-Z][a-zA-Z\s]+:|\Z)', job_description, re.IGNORECASE | re.DOTALL)
    mandatory_skills = []
    for skill_block in mandatory_skills_raw:
        lines = [line.strip() for line in skill_block.split('\n') if line.strip()]
        for line in lines:
            # Remove verbose prefixes
            line = re.sub(r'^(Proficiency in|Strong|Experience with|Understanding of)\s+', '', line, flags=re.IGNORECASE)
            # Extract skills in parentheses
            paren_skills = re.findall(r'\((.*?)\)', line)
            if paren_skills:
                for skill_group in paren_skills:
                    skills = [s.strip() for s in skill_group.split(',') if s.strip()]
                    mandatory_skills.extend(skills)
            # Remove parentheses and their content for the remaining text
            line = re.sub(r'\s*\([^()]*\)', '', line)
            # Split by 'and' or commas
            skills = re.split(r',\s*|\s+and\s+', line, flags=re.IGNORECASE)
            skills = [skill.strip() for skill in skills if skill.strip()]
            mandatory_skills.extend(skills)
    # Remove duplicates and non-specific terms
    non_specific_terms = {'programming skills', 'Generative AI frameworks', 'ML libraries', 'data analysis', 'visualization tools', 'cloud platforms'}
    mandatory_skills = list(set(skill for skill in mandatory_skills if skill and skill not in non_specific_terms))
    logger.debug(f"Extracted mandatory skills: {mandatory_skills}")

    # Good-to-have skills
    good_to_have_skills = re.findall(r'(?:preferred|nice to have|good to have)\s*[:\s]*(.*?)(?=\n[A-Z][a-zA-Z\s]+:|\Z)', job_description, re.IGNORECASE | re.DOTALL)
    good_to_have_skills_list = []
    for skill_block in good_to_have_skills:
        lines = [line.strip() for line in skill_block.split('\n') if line.strip()]
        for line in lines:
            line = re.sub(r'^(Experience with|Familiarity with|Knowledge of)\s+', '', line, flags=re.IGNORECASE)
            skills = re.split(r',\s*|\s+and\s+', line, flags=re.IGNORECASE)
            skills = [skill.strip() for skill in skills if skill.strip()]
            good_to_have_skills_list.extend(skills)
    good_to_have_skills = list(set(skill for skill in good_to_have_skills_list if skill))
    logger.debug(f"Extracted good-to-have skills: {good_to_have_skills}")

    # 70% Project Skills
    project_skills = []
    for project in projects:
        project_skills.extend(project.get("skills", []))
    project_skills = list(set(project_skills))  # Remove duplicates
    logger.debug(f"Project skills: {project_skills}")

    matched_project_skills = sum(1 for skill in mandatory_skills if any(re.search(rf'\b{skill}\b', ps, re.IGNORECASE) for ps in project_skills))
    matched_skills = [skill for skill in mandatory_skills if any(re.search(rf'\b{skill}\b', ps, re.IGNORECASE) for ps in project_skills)]
    logger.debug(f"Matched mandatory skills in projects: {matched_skills}")
    project_score = (matched_project_skills / max(len(mandatory_skills), 1)) * 70 if mandatory_skills else 0
    score += project_score
    if matched_project_skills < len(mandatory_skills):
        missing_skills = [skill for skill in mandatory_skills if not any(re.search(rf'\b{skill}\b', ps, re.IGNORECASE) for ps in project_skills)]
        pain_points_list.append(f"Missing mandatory project skills: {', '.join(missing_skills)}")

    # 10% Technical Skills (non-project)
    skills_section = re.search(r'\[SECTION: Skills\](.*?)(?=\[SECTION:|\Z)', resume_text, re.DOTALL)
    technical_skills = []
    if skills_section:
        skills_text = skills_section.group(1).strip()
        for skill in skills_text.split('\n'):
            skill = skill.strip()
            if skill and skill not in project_skills:  # Exclude project skills
                technical_skills.append(skill)
    matched_tech_skills = sum(1 for skill in mandatory_skills if any(re.search(rf'\b{skill}\b', ts, re.IGNORECASE) for ts in technical_skills))
    tech_score = (matched_tech_skills / max(len(mandatory_skills), 1)) * 10 if mandatory_skills else 0
    score += tech_score

    # 10% Good-to-Have Skills
    all_skills = project_skills + technical_skills
    matched_good_to_have = sum(1 for skill in good_to_have_skills if any(re.search(rf'\b{skill}\b', s, re.IGNORECASE) for s in all_skills))
    good_to_have_score = (matched_good_to_have / max(len(good_to_have_skills), 1)) * 10 if good_to_have_skills else 0
    score += good_to_have_score
    if matched_good_to_have < len(good_to_have_skills):
        missing_good_to_have = [skill for skill in good_to_have_skills if not any(re.search(rf'\b{skill}\b', s, re.IGNORECASE) for s in all_skills)]
        pain_points_list.append(f"Missing good-to-have skills: {', '.join(missing_good_to_have)}")

    # 10% Experience
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
    experience_score = 10  # Default to max score if no requirement
    if required_experience > 0:  # Align with Flask's logic (0 means no requirement)
        experience_score = min(10, (candidate_years / required_experience * 10))
        if candidate_years < required_experience:
            gap = required_experience - candidate_years
            experience_score -= min(2 * gap, experience_score)  # Deduct 2 points per year below
            pain_points_list.append(f"Experience gap: {candidate_years} years vs {required_experience} required")
    score += max(0, experience_score)

    # Finalize score
    score = max(0, min(100, score))
    status = "Shortlisted" if score > 70 else "Under Consideration" if score >= 50 else "Rejected"

    # Categorize pain points
    pain_points = {
        "critical": [p for p in pain_points_list if "Missing mandatory project skills" in p],
        "major": [p for p in pain_points_list if "Experience gap" in p],
        "minor": [p for p in pain_points_list if "Missing good-to-have skills" in p] or ["Needs further evaluation in interview"]
    }

    # Generate summary
    summary = (
        f"Candidate scored {score} based on project alignment, skills, and experience. "
        f"Projects cover {matched_project_skills}/{len(mandatory_skills)} mandatory skills, contributing {project_score:.1f}/70 points. "
        f"Non-project technical skills match {matched_tech_skills}/{len(mandatory_skills)} mandatory skills, adding {tech_score:.1f}/10 points. "
        f"Good-to-have skills match {matched_good_to_have}/{len(good_to_have_skills)} skills, adding {good_to_have_score:.1f}/10 points. "
        f"Experience of {candidate_years} years vs {required_experience} required adds {experience_score:.1f}/10 points. "
        f"{'Strong project alignment; recommend technical interview to validate skills.' if score > 70 else 'Moderate fit; interview to assess gaps.' if score >= 50 else 'Significant gaps; may require extensive training.'}"
    )

    # Add relevance to projects
    for project in projects:
        project_skills = project.get("skills", [])
        relevant_skills = [skill for skill in mandatory_skills if any(re.search(rf'\b{skill}\b', ps, re.IGNORECASE) for ps in project_skills)]
        project["relevance"] = f"Matches {', '.join(relevant_skills)} requirements" if relevant_skills else "No direct match to mandatory skills"

    result = {
        "score": int(score),
        "pain_points": pain_points,
        "summary": summary,
        "status": status,
        "projects": projects
    }

    logger.info(f"Fallback assessment result: {result}")
    return result

def analyze_resume(resume_text: str, job_description: str, required_experience: int, projects: List[Dict]) -> Dict:
    """
    Technical-focused resume analysis using Gemini 1.5 Flash for post-HR screening.
    Scoring: 70% projects, 10% technical skills, 10% good-to-have skills, 10% experience.
    """
    try:
        # Construct LLM prompt
        prompt = f"""
            **CONTEXT:** This is a TECHNICAL SCREENING analysis for a candidate who has passed initial HR screening. 
            Focus on technical competency, emphasizing project skills (70% of score), with technical skills (10%), 
            good-to-have skills (10%), and experience (10%).

            **MASKED RESUME DATA:**
            {resume_text}

            **JOB TECHNICAL REQUIREMENTS:**
            {job_description}

            **REQUIRED YEARS OF EXPERIENCE:**
            {required_experience}

            **EXTRACTED PROJECTS:**
            {json.dumps(projects, indent=2) if projects else "No projects identified."}

            **TECHNICAL ANALYSIS INSTRUCTIONS:**

            **1. EXTRACT SKILLS FROM JOB DESCRIPTION:**
                - **Mandatory Skills:** Identified by keywords "required", "must have", "essential", "mandatory".
                  Extract specific skills, including tools mentioned in parentheses (e.g., "Generative AI frameworks (like GPT, BERT)" → "GPT", "BERT").
                  Remove verbose prefixes like "Proficiency in", "Strong", "Experience with".
                  Split skills by 'and' or commas (e.g., "Python and R" → "Python", "R").
                - **Good-to-Have Skills:** Identified by keywords "preferred", "nice to have", "good to have".
                - Examples: Programming languages, frameworks, cloud platforms, databases, tools.

            **2. SCORE THE CANDIDATE (0-100):**

                **Projects (70 points):**
                    - Match skills in projects to mandatory skills using exact, case-insensitive matching.
                    - Score = (Matched Project Skills / Total Mandatory Skills) × 70.
                    - Each missing mandatory skill = critical pain point.

                **Technical Skills (10 points):**
                    - Match non-project technical skills (e.g., from Skills section) to mandatory skills.
                    - Score = (Matched Technical Skills / Total Mandatory Skills) × 10.

                **Good-to-Have Skills (10 points):**
                    - Match any skills (from projects or elsewhere) to good-to-have skills.
                    - Score = (Matched Good-to-Have Skills / Total Good-to-Have Skills) × 10.

                **Experience (10 points):**
                    - Extract candidate's years of experience from resume.
                    - Compare with required years.
                    - If required years is 0, award full points (10).
                    - Otherwise, score = min(10, (Years Experience / Required Years) × 10).
                    - Deduct 2 points per year below required (minimum 0).

                - Cap total score at 100.

            **3. TECHNICAL PAIN POINTS IDENTIFICATION:**

                **Critical Issues (Immediate Concerns):**
                    - Missing mandatory skills not covered in projects.
                    - No relevant project experience matching job requirements.

                **Major Issues (Training Required):**
                    - Insufficient years of experience.
                    - Limited project experience in required technologies.

                **Minor Issues (Growth Opportunities):**
                    - Missing good-to-have skills.
                    - Could benefit from additional project exposure.

            **4. TECHNICAL SUMMARY REQUIREMENTS:**
                - Write 130-160 words focusing on:
                    - Project alignment with mandatory skills.
                    - Non-project technical skills and good-to-have skills.
                    - Experience fit and gaps.
                    - Recommendation for technical interview focus areas.
                - For high-scoring candidates (70+): Emphasize project strengths.
                - For moderate candidates (50-69): Highlight gaps and upskilling needs.
                - For low-scoring candidates (<50): Note significant deficiencies.

            **5. PROJECT ANALYSIS:**
                - For each project, list:
                    - Name
                    - Description
                    - Skills extracted
                    - Relevance to mandatory skills (e.g., "Matches Python and AWS requirements").
                - If no projects, note this and assess other sections.

            **6. ASSIGN STATUS:**
                - "Shortlisted" if score >= 70.
                - "Under Consideration" if score is 50–69.
                - "Rejected" if score < 50.

            **OUTPUT FORMAT - Return ONLY valid JSON:**
            {{
                "score": <integer 0-100>,
                "pain_points": {{
                    "critical": [<list of critical issues>],
                    "major": [<list of major concerns>],
                    "minor": [<list of minor improvements>]
                }},
                "summary": "<130-160 words technical assessment>",
                "status": "<Shortlisted|Under Consideration|Rejected>",
                "projects": [
                    {{
                        "name": "<project name>",
                        "description": "<description>",
                        "skills": [<list of skills>],
                        "relevance": "<relevance to mandatory skills>"
                    }},
                    ...
                ]
            }}

            **ANALYSIS GUIDELINES:**
                - Focus on technical competencies and job-specific requirements.
                - Prioritize project skills (70% weight).
                - Assess hands-on experience over theoretical knowledge.
                - Base assessment strictly on resume content provided.
                - Do not infer or assume unlisted skills.
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
            required_keys = ["score", "pain_points", "summary", "status", "projects"]
            if not all(key in result for key in required_keys):
                missing_keys = [key for key in required_keys if key not in result]
                logger.error(f"Technical analysis missing keys: {missing_keys}")
                raise ValueError(f"Missing required keys: {missing_keys}")

            # Validate and normalize score
            if not isinstance(result["score"], (int, float)) or result["score"] < 0 or result["score"] > 100:
                logger.error(f"Invalid technical score: {result['score']}")
                raise ValueError(f"Invalid score: {result['score']}")
            result["score"] = max(0, min(100, int(result["score"])))

            # Validate pain_points
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

            # Validate summary
            if not isinstance(result["summary"], str):
                logger.warning("Invalid summary format")
                result["summary"] = generate_technical_summary(result["score"], result["pain_points"])
            else:
                word_count = len(result["summary"].split())
                if word_count < 120 or word_count > 170:
                    logger.warning(f"Technical summary length {word_count} outside target range")
                    if word_count < 120:
                        result["summary"] += " Technical interview should focus on validating project experience and technical skills."

            # Validate status
            if result["status"] not in ["Shortlisted", "Under Consideration", "Rejected"]:
                logger.warning(f"Invalid status: {result['status']}, recalculating based on score")
                score = result["score"]
                result["status"] = "Shortlisted" if score >= 70 else "Under Consideration" if score >= 50 else "Rejected"

            # Validate projects
            if not isinstance(result["projects"], list):
                logger.warning("Invalid projects format, using provided projects")
                result["projects"] = projects
            else:
                for project in result["projects"]:
                    if not all(key in project for key in ["name", "description", "skills", "relevance"]):
                        logger.warning(f"Invalid project format: {project}")
                        project.update({
                            "name": project.get("name", "Unnamed Project"),
                            "description": project.get("description", "No description provided"),
                            "skills": project.get("skills", []),
                            "relevance": project.get("relevance", "Relevance not assessed")
                        })

            logger.info(f"Final technical analysis: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in technical analysis: {e}")
            return fallback_ats_score(resume_text, job_description, required_experience, projects)
        except ValueError as e:
            logger.error(f"Validation error in technical analysis: {e}")
            return fallback_ats_score(resume_text, job_description, required_experience, projects)

    except Exception as e:
        logger.error(f"Technical LLM analysis failed: {e}")
        return fallback_ats_score(resume_text, job_description, required_experience, projects)

def generate_technical_summary(score: int, pain_points: Dict) -> str:
    """
    Generate a technical-focused summary based on score and pain points.
    """
    summary_parts = []
    
    if score >= 70:
        summary_parts.append("Candidate demonstrates strong alignment with role requirements, particularly in project experience.")
    elif score >= 50:
        summary_parts.append("Candidate shows moderate fit with some gaps in project skills and experience.")
    else:
        summary_parts.append("Candidate exhibits significant gaps in project experience and required skills.")
    
    if pain_points.get("critical"):
        summary_parts.append(f"Critical issues: {'; '.join(pain_points['critical'][:2])}.")
    
    if pain_points.get("major"):
        summary_parts.append(f"Major concerns: {'; '.join(pain_points['major'][:2])}.")
    
    if pain_points.get("minor"):
        summary_parts.append(f"Minor improvements: {'; '.join(pain_points['minor'][:2])}.")
    
    summary_parts.append("Technical interview recommended to validate project experience, assess technical skills, and determine training needs.")
    
    return " ".join(summary_parts)