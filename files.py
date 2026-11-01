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

def attach(name, text):
    """How a file goes into a message (web app, /file and the routing eval). It goes before the typed words, in document tags.
    With "[File: essay.txt]" after the request, the model ran Python on writing tasks and tried to open() the file:
    24/30 right about Python that way, 27/30 this way (EVALS.md section 10)."""
    return f'The user attached a file. Its full text is already below, so there is nothing to open.\n<document name="{name}">\n{text}\n</document>\n\n'

def read_file(path):
    with open(path, "rb") as f:
        return text_from(path, f.read())
