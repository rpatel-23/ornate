"""Ornate as a web server: the same agent as agent.py, reached over HTTP instead of the terminal.
Run:  uvicorn server:app --port 8000
Test: curl -X POST localhost:8000/chat -H "Content-Type: application/json" -d '{"message": "hi"}'"""
import json
import queue
import re
import threading
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import memory
import chats
from typing import Optional
from assistant import system_prompt, respond, unload_skills, add_memory_hint, check_missed_save, clear_memory_hints, pending_delete

app = FastAPI()

# the chat the model is working on right now. Others wait on disk in chats/ until opened.
messages = [{"role": "system", "content": system_prompt()}]
lock = threading.Lock()   # the model can only answer one request at a time
file_lock = threading.Lock()   # chat files: so a rename and a save never write the same file at once
turn_starts = []   # where each user turn starts in messages, so an edit knows where to cut
current = None     # the open chat's info (id, title, folder, pinned, turns), or None before the first message

class ChatIn(BaseModel):
    message: str
    chat_id: Optional[str] = None   # which saved chat this message is for; None starts a new one
    edit: Optional[int] = None   # set when the user edits an earlier message: which of their messages (0 = first)

def open_chat(chat_id):
    """Make chat_id the conversation the model sees (loading it from disk if needed)."""
    global current
    if chat_id and current and current["id"] == chat_id:
        return   # already open
    pending_delete.clear()   # an "are you sure?" from another chat must not be answered here
    if chat_id:
        current = chats.load(chat_id)
        messages[1:] = current.pop("messages")
        turn_starts[:] = current.pop("turn_starts")
    else:
        current = {"id": chats.new_id(), "title": None, "folder": None, "pinned": False, "turns": []}
        del messages[1:]
        turn_starts.clear()

def save_current():
    with file_lock:
        try:
            # pin, folder and title may have changed in the sidebar while the model was answering; keep those
            on_disk = chats.load(current["id"])
            for k in ("title", "folder", "pinned"):
                current[k] = on_disk[k]
        except FileNotFoundError:
            pass   # first save of a new chat
        chats.save({**current, "messages": messages[1:], "turn_starts": turn_starts})

@app.get("/")
def page():
    return FileResponse("static/index.html")   # the chat page

@app.post("/chat")
def chat(body: ChatIn):
    """Streams the answer as it is written: one JSON object per line (text pieces and tool events)."""
    q = queue.Queue()

    shown = {"text": ""}   # the answer as the page shows it, so a reopened chat looks the same

    def emit(event):
        # same rule as the page: text before a tool call is replaced by the answer after it
        if event["type"] == "text":
            shown["text"] += event["text"]
        elif event["type"] == "tool_start":
            shown["text"] = ""
        q.put(event)

    def run():
        with lock:
            opened = False
            try:
                open_chat(body.chat_id)
                opened = True   # only save the turn if its own chat is the one open
                if current["title"] is None:
                    current["title"] = chats.make_title(body.message)
                q.put({"type": "chat", "id": current["id"], "title": current["title"]})   # page learns the new chat's id
                if body.edit is not None and body.edit < len(turn_starts):
                    # editing: drop that message and everything after it, then answer the new text as if it were sent then
                    del messages[turn_starts[body.edit]:]
                    del turn_starts[body.edit:]
                    del current["turns"][body.edit:]
                    pending_delete.clear()   # an old "are you sure?" must not be answered by an edited message
                messages[0]["content"] = system_prompt()   # refresh, so new or deleted memories are current
                turn_starts.append(len(messages))
                messages.append({"role": "user", "content": add_memory_hint(body.message)})
                respond(messages, show=False, check=check_missed_save, emit=emit)
                unload_skills(messages)
                clear_memory_hints(messages)
            except Exception as e:
                emit({"type": "error", "text": str(e)})
                shown["text"] += "\n(error: " + str(e) + ")"
            if opened:
                current["turns"].append({"user": body.message, "bot": shown["text"]})
                save_current()
            q.put({"type": "done"})

    # the model runs in a background thread; this loop hands each piece to the browser as it arrives
    threading.Thread(target=run, daemon=True).start()

    def events():
        while True:
            event = q.get()
            yield json.dumps(event) + "\n"
            if event["type"] == "done":
                break

    return StreamingResponse(events(), media_type="application/x-ndjson")

@app.get("/memory")
def get_memory():
    return {"facts": memory.load()}

@app.delete("/memory/{n}")
def delete_memory(n: int):
    """Delete a fact by its number (from 1), for the delete button in the memory popup."""
    with lock:
        try:
            gone = memory.remove(n)
        except IndexError:
            return {"ok": False}
    return {"ok": True, "deleted": gone}

# ---- saved chats and folders, for the sidebar ----

@app.get("/chats")
def list_chats():
    return {"chats": chats.list_all(), "folders": chats.folders()}

@app.get("/chats/{chat_id}")
def get_chat(chat_id: str):
    c = chats.load(chat_id)
    return {"id": c["id"], "title": c["title"], "turns": c["turns"]}

class ChatEdit(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None
    folder: Optional[str] = None   # "" takes the chat out of its folder

@app.patch("/chats/{chat_id}")
def edit_chat(chat_id: str, body: ChatEdit):
    """Rename, pin/unpin, or move a chat to a folder."""
    with file_lock:
        c = chats.load(chat_id)
        if body.title is not None and body.title.strip():
            c["title"] = body.title.strip()
        if body.pinned is not None:
            c["pinned"] = body.pinned
        if body.folder is not None:
            c["folder"] = body.folder or None
        chats.save(c, touch=False)
    return {"ok": True}

@app.delete("/chats/{chat_id}")
def delete_chat(chat_id: str):
    global current
    with lock, file_lock:   # wait for any answer to finish, so it can't save the chat again after this
        chats.delete(chat_id)
        if current and current["id"] == chat_id:
            current = None
            del messages[1:]
            turn_starts.clear()
    return {"ok": True}

class FolderIn(BaseModel):
    name: str

@app.post("/folders")
def create_folder(body: FolderIn):
    name = body.name.strip()
    with file_lock:
        names = chats.folders()
        if name and name not in names:
            chats.save_folders(names + [name])
    return {"ok": True}

@app.patch("/folders/{name}")
def rename_folder(name: str, body: FolderIn):
    new = body.name.strip()
    with file_lock:
        names = chats.folders()
        if new and name in names and new not in names:
            chats.save_folders([new if n == name else n for n in names])
            chats.set_folder_for_all(name, new)
    return {"ok": True}

@app.delete("/folders/{name}")
def delete_folder(name: str):
    """Deletes the folder only. Its chats move back to the main list; none are deleted."""
    with file_lock:
        chats.save_folders([n for n in chats.folders() if n != name])
        chats.set_folder_for_all(name, None)
    return {"ok": True}
