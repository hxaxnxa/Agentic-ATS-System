import PyPDF2
import docx
import logging
import re
from io import BytesIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_document(file, filename):
    """
    Parse document (PDF or DOCX) using python-docx for DOCX and PyPDF2 for PDF.
    Returns extracted text or raises an exception on failure.
    """
    file.seek(0)
    if filename.endswith(".docx"):
        try:
            doc = docx.Document(file)
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            if text and text.strip():
                return text.strip()
            raise ValueError("python-docx returned empty content")
        except Exception as e:
            logger.error(f"python-docx parsing failed: {e}")
            raise ValueError("Failed to parse DOCX")
    elif filename.endswith(".pdf"):
        try:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text() or ""
                # Preserve line breaks and normalize spaces
                page_text = re.sub(r'\s+', ' ', page_text)
                page_text = re.sub(r'\n\s*\n', '\n', page_text)
                text += page_text + "\n"
            if text and text.strip():
                return text.strip()
            raise ValueError("PyPDF2 returned empty content")
        except Exception as e:
            logger.error(f"PyPDF2 parsing failed: {e}")
            raise ValueError("Failed to parse PDF")
    else:
        raise ValueError("Unsupported file format")