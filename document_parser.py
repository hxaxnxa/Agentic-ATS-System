import logging
from io import BytesIO
import re
from typing import Dict, List
import docx2txt
import PyPDF2

logging.basicConfig(level=logging.INFO, filename='logs.txt', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_document(file: BytesIO, filename: str) -> Dict:
    """
    Parse a PDF or DOCX file and extract structured content.
    Returns a dictionary with full_text and projects (if applicable).
    """
    try:
        full_text = ""
        projects = []

        if filename.endswith('.pdf'):
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text = page.extract_text() or ""
                full_text += text + "\n"
            logger.info(f"Extracted {len(full_text)} characters from PDF {filename}")

        elif filename.endswith('.docx'):
            full_text = docx2txt.process(file)
            logger.info(f"Successfully extracted {len(full_text)} characters from DOCX {filename}")

        else:
            logger.error(f"Unsupported file format: {filename}")
            raise ValueError("Unsupported file format. Only PDF and DOCX are supported.")

        # Basic structuring of the document
        structured_text = "[SECTION: General]\n" + full_text

        # Extract projects (mainly for resumes, may not apply to job descriptions)
        project_section = re.search(r'(?:Projects|Experience|Work\s+History)(.*?)(?=\n[A-Z][a-zA-Z\s]+:|\Z)', full_text, re.DOTALL | re.IGNORECASE)
        if project_section:
            project_text = project_section.group(1).strip()
            project_entries = re.split(r'\n\s*(?=[A-Za-z0-9\s\-]+(?:\s*\d{4}\s*(?:[-–]\s*(?:Present|\d{4}))?)?\s*(?=\n\s*[-•]))', project_text)
            structured_text += "\n[SECTION: Projects]\n"
            
            for entry in project_entries:
                entry = entry.strip()
                if entry:
                    structured_text += f"PROJECT ENTRY: {entry}\n"
                    # Extract project details
                    lines = entry.split('\n')
                    name_line = lines[0].strip()
                    name_match = re.match(r'^(.*?)(?:\s*[-–]\s*\d{4}(?:\s*[-–]\s*(?:Present|\d{4}))?)?$', name_line)
                    project_name = name_match.group(1).strip() if name_match else "Unnamed Project"
                    description = "\n".join(line.strip() for line in lines[1:] if line.strip())
                    
                    # Extract skills from description
                    skill_keywords = [
                        'Python', 'Java', 'JavaScript', 'React', 'Node.js', 'AWS', 'Docker', 'Kubernetes',
                        'GCP', 'Azure', 'Terraform', 'CI/CD', 'Git', 'SQL', 'MongoDB', 'Redis',
                        'GraphQL', 'Microservices', 'DevOps', 'Machine Learning', 'TensorFlow', 'PyTorch'
                    ]
                    skills = []
                    for line in lines[1:]:
                        for skill in skill_keywords:
                            if re.search(rf'\b{skill}\b', line, re.IGNORECASE) and skill not in skills:
                                skills.append(skill)
                    
                    projects.append({
                        "name": project_name,
                        "description": description,
                        "skills": skills
                    })

        # Extract skills section (if present)
        skills_section = re.search(r'Skills(.*?)(?=\n[A-Z][a-zA-Z\s]+:|\Z)', full_text, re.DOTALL | re.IGNORECASE)
        if skills_section:
            structured_text += "\n[SECTION: Skills]\n" + skills_section.group(1).strip()

        # Extract experience section for years of experience
        experience_section = re.search(r'Experience(.*?)(?=\n[A-Z][a-zA-Z\s]+:|\Z)', full_text, re.DOTALL | re.IGNORECASE)
        if experience_section:
            structured_text += "\n[SECTION: Experience]\n" + experience_section.group(1).strip()

        return {
            "full_text": structured_text,
            "projects": projects
        }

    except Exception as e:
        logger.error(f"Error parsing document {filename}: {e}")
        raise