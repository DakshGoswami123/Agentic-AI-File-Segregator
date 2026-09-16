"""
Content extraction for each supported file type.

Every extractor has the same contract: given a Path, return the best
extracted text as a string, or "" if nothing could be extracted.
Extractors never raise — failures are logged and treated as "no text
found" so that one unreadable file can never crash the agent.
"""

import logging
from pathlib import Path

import PyPDF2
from docx import Document
from PIL import Image
import pytesseract

logger = logging.getLogger("file_segregator")


def extract_text_from_pdf(file_path: Path) -> str:
    try:
        text_parts = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as error:
        logger.warning("Could not read PDF %s: %s", file_path.name, error)
        return ""


def extract_text_from_docx(file_path: Path) -> str:
    try:
        document = Document(file_path)
        return "\n".join(p.text for p in document.paragraphs)
    except Exception as error:
        logger.warning("Could not read DOCX %s: %s", file_path.name, error)
        return ""


def extract_text_from_txt(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as error:
        logger.warning("Could not read TXT %s: %s", file_path.name, error)
        return ""


def extract_text_from_image(file_path: Path) -> str:
    try:
        with Image.open(file_path) as image:
            return pytesseract.image_to_string(image)
    except Exception as error:
        logger.warning("Could not OCR image %s: %s", file_path.name, error)
        return ""


_EXTRACTORS = {
    ".pdf": extract_text_from_pdf,
    ".docx": extract_text_from_docx,
    ".txt": extract_text_from_txt,
    ".png": extract_text_from_image,
    ".jpg": extract_text_from_image,
    ".jpeg": extract_text_from_image,
    ".tiff": extract_text_from_image,
    ".bmp": extract_text_from_image,
}


def extract_text(file_path: Path) -> str:
    """Dispatch to the right extractor based on file extension."""
    extractor = _EXTRACTORS.get(file_path.suffix.lower())
    if extractor is None:
        return ""
    return extractor(file_path)
