from pypdf import PdfReader

MAX_CHARS = 30000  # roughly 15 pages; keeps big files from overflowing the model

def read_file(path):
    if path.lower().endswith(".pdf"):
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        with open(path) as f:
            text = f.read()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n[file cut off here because it is too long]"
    return text