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
from assistant import system_prompt, respond, unload_skills, add_memory_hint, check_missed_save, clear_memory_hints

app = FastAPI()

# one conversation for now; saved chats come later
messages = [{"role": "system", "content": system_prompt()}]
lock = threading.Lock()   # the model can only answer one request at a time

class ChatIn(BaseModel):
    message: str

@app.get("/")
def page():
    return FileResponse("static/index.html")   # the chat page

@app.post("/chat")
def chat(body: ChatIn):
    """Streams the answer as it is written: one JSON object per line (text pieces and tool events)."""
    q = queue.Queue()

    def run():
        with lock:
            try:
                messages[0]["content"] = system_prompt()   # refresh, so new or deleted memories are current
                messages.append({"role": "user", "content": add_memory_hint(body.message)})
                respond(messages, show=False, check=check_missed_save, emit=q.put)
                unload_skills(messages)
                clear_memory_hints(messages)
            except Exception as e:
                q.put({"type": "error", "text": str(e)})
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

@app.post("/reset")
def reset():
    with lock:
        del messages[1:]   # keep the system prompt, drop the chat
    return {"ok": True}
