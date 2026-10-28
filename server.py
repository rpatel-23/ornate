"""Ornate as a web server: the same agent as agent.py, reached over HTTP instead of the terminal.
Run:  uvicorn server:app --port 8000
Test: curl -X POST localhost:8000/chat -H "Content-Type: application/json" -d '{"message": "hi"}'"""
import re
import threading
from fastapi import FastAPI
from pydantic import BaseModel
import memory
from assistant import system_prompt, respond, unload_skills, add_memory_hint, check_fake_save

app = FastAPI()

# one conversation for now; saved chats come later
messages = [{"role": "system", "content": system_prompt()}]
lock = threading.Lock()   # the model can only answer one request at a time

class ChatIn(BaseModel):
    message: str

@app.post("/chat")
def chat(body: ChatIn):
    with lock:
        messages[0]["content"] = system_prompt()   # refresh, so new or deleted memories are current
        messages.append({"role": "user", "content": add_memory_hint(body.message)})
        reply = respond(messages, show=False, check=check_fake_save)
        unload_skills(messages)
    # hide the model's thinking, same as the terminal does
    answer = re.sub(r"<think>.*?(</think>|$)", "", reply, flags=re.DOTALL).strip()
    return {"reply": answer}

@app.get("/memory")
def get_memory():
    return {"facts": memory.load()}

@app.post("/reset")
def reset():
    with lock:
        del messages[1:]   # keep the system prompt, drop the chat
    return {"ok": True}
