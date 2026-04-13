import re
import fitz  # PyMuPDF


def clean_text(text: str) -> str:
    text = text.encode("utf-8", "ignore").decode("utf-8")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[•●▪▶▸►✔✓]", "- ", text)
    text = re.sub(r"[^a-zA-Z0-9,.!?@\-:/\n ]", "", text)
    text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", text)
    return text


def extract_text_from_pdf_file(file_obj) -> str:
    """Extract and clean text from a Flask file upload object."""
    try:
        data = file_obj.read()
        doc = fitz.open(stream=data, filetype="pdf")
        raw = "\n".join(page.get_text("text") for page in doc)
        doc.close()
        return clean_text(raw) if raw.strip() else "No text found in the PDF."
    except Exception as e:
        return f"Error extracting PDF: {str(e)}"
    finally:
        # Rewind so the same file can be re-read if needed
        try:
            file_obj.seek(0)
        except Exception:
            pass
