"""Saved chats for the web app. Each chat is one JSON file in chats/ (git-ignored, personal).
Folders are just names in chats/folders.json; a chat stores the name of the folder it is in."""
import json
import os
import re
import time
import uuid

DIR = "chats"
FOLDERS = os.path.join(DIR, "folders.json")
os.makedirs(DIR, exist_ok=True)

def path(chat_id):
    # ids are made by new_id() below; refuse anything else so a request can't read files outside chats/
    if not re.fullmatch(r"[0-9a-f]{12}", chat_id):
        raise ValueError("bad chat id")
    return os.path.join(DIR, chat_id + ".json")

def new_id():
    return uuid.uuid4().hex[:12]   # 12 random hex letters, e.g. "3f9a0c1b7d2e"

def load(chat_id):
    with open(path(chat_id)) as f:
        return json.load(f)

def save(chat, touch=True):
    # touch=True for a new message: newest chats go to the top of the sidebar.
    # Pinning, renaming or moving uses touch=False, so the chat keeps its place.
    if touch or "updated" not in chat:
        chat["updated"] = time.time()
    with open(path(chat["id"]), "w") as f:
        json.dump(chat, f, indent=1)

def delete(chat_id):
    os.remove(path(chat_id))

def list_all():
    """Every chat without its messages (the sidebar only needs these fields), newest first."""
    out = []
    for name in os.listdir(DIR):
        if name.endswith(".json") and name != "folders.json":
            c = load(name[:-5])
            out.append({k: c.get(k) for k in ("id", "title", "folder", "pinned", "updated")})
    return sorted(out, key=lambda c: c["updated"], reverse=True)

def make_title(text):
    # first line of the first message, cut to 40 letters. Code makes it, so it costs no model time.
    line = text.strip().splitlines()[0] if text.strip() else "New chat"
    return line if len(line) <= 40 else line[:40].rstrip() + "…"

def folders():
    if not os.path.exists(FOLDERS):
        return []
    with open(FOLDERS) as f:
        return json.load(f)

def save_folders(names):
    with open(FOLDERS, "w") as f:
        json.dump(names, f, indent=1)

def set_folder_for_all(old, new):
    """Renaming or deleting a folder: update every chat that was in it (new=None takes them out)."""
    for c in list_all():
        if c["folder"] == old:
            chat = load(c["id"])
            chat["folder"] = new
            save(chat, touch=False)
