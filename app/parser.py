import os
import fitz  # PyMuPDF
import docx


def extract_text_from_pdf(filepath):
    """Extract full raw text from a PDF file using PyMuPDF."""
    text_parts = []
    try:
        with fitz.open(filepath) as doc:
            for page in doc:
                text_parts.append(page.get_text())
        return "\n".join(text_parts).strip()
    except Exception as e:
        print(f"Error extracting PDF text from {filepath}: {e}")
        return ""


def extract_text_from_docx(filepath):
    """Extract full raw text from a DOCX file using python-docx."""
    text_parts = []
    try:
        doc = docx.Document(filepath)
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text)
        return "\n".join(text_parts).strip()
    except Exception as e:
        print(f"Error extracting DOCX text from {filepath}: {e}")
        return ""


def extract_resume_text(filepath):
    """Extract text from supported resume formats (.pdf or .docx)."""
    if not filepath or not os.path.exists(filepath):
        return ""

    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(filepath)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(filepath)
    return ""
