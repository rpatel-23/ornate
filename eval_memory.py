"""Tests forget (and not-forget) with a fake memory list, so your real memory.json is never touched."""
import json
import os
import tempfile
import time
import memory
from assistant import system_prompt, add_memory_hint, is_delete_request
from harness import ask_model, MODEL, THINK, find_tool_call

with open("memory_tests.json") as f:
    data = json.load(f)

# point memory at a temporary file holding the fake list
memory.PATH = os.path.join(tempfile.mkdtemp(), "memory.json")
memory.save(data["memory"])
prompt = system_prompt()   # built with the fake memories

def norm(facts):
    return sorted(f.strip().lower().rstrip(".") for f in facts)

start = time.time()
records = []
for t in data["tests"]:
    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": add_memory_hint(t["message"])}]
    reply = ask_model(messages, use_tools=True, show=False)
    try:
        call = find_tool_call(reply)
    except Exception:
        call = {"name": "bad tool call", "arguments": {}}
    got = call["name"] if call else "none"
    allowed = t["expect"] if isinstance(t["expect"], list) else [t["expect"]]
    ok = got in allowed
    note = ""
    # for a forget, the exact facts matter too: deleting the wrong one is a fail
    if ok and got == "forget":
        sent = call["arguments"].get("facts") or []
        sent = [sent] if isinstance(sent, str) else sent
        ok = norm(sent) == norm(t["facts"])
        if not ok:
            note = f"  (wanted {t['facts']}, sent {sent})"
    # with the code check: forget refuses unless the user's message asks to delete, so nothing gets queued
    checked_ok = ok or (got == "forget" and not is_delete_request(t["message"]) and "none" in allowed)
    caught = "  (caught by check)" if checked_ok and not ok else ""
    print("PASS" if ok else "FAIL", f"| expected {' or '.join(allowed):<17} got {got:<10} | {t['message']}{note}{caught}")
    records.append({**t, "got": got, "correct": ok, "checked_correct": checked_ok, "reply": reply})

score = sum(r["correct"] for r in records)
checked = sum(r["checked_correct"] for r in records)
os.makedirs("results", exist_ok=True)
path = f"results/memory__{MODEL.split('/')[-1]}__think{'1' if THINK else '0'}.json"
with open(path, "w") as f:
    json.dump({"model": MODEL, "thinking": THINK, "score": score, "checked_score": checked, "records": records}, f, indent=2)
print(f"\nmodel alone: {score}/{len(records)} | with code check: {checked}/{len(records)}")
print(f"{score}/{len(records)} correct in {round(time.time() - start)}s | saved to {path}")
