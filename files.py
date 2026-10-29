import io
from pypdf import PdfReader

MAX_CHARS = 30000  # roughly 15 pages; keeps big files from overflowing the model

def text_from(name, data):
    """Turn a file's bytes into text. Used by /file in the terminal and by drag-and-drop in the web app."""
    if name.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            # not text (an image, a Word file, ...): say so instead of feeding the model garbage
            raise ValueError(f"Can't read {name}: only text files and PDFs work for now.")
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n[file cut off here because it is too long]"
    return text

def read_file(path):
    with open(path, "rb") as f:
        return text_from(path, f.read())
