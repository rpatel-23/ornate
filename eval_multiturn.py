"""Multi-turn eval: short conversations (multiturn_tests.json) run the same way the web app runs each turn,
on a fake memory list in a temporary file, so your real memory.json is never touched.
Everything is checked by code: the memory list at the end, which tools each turn called, and words in each reply.
Run: python eval_multiturn.py      (ORNATE_MODEL=... picks the model)"""
import json
import os
import tempfile
import time
import memory
from assistant import system_prompt, respond, unload_skills, add_memory_hint, check_missed_save, clear_memory_hints, pending_delete
from harness import MODEL, find_tool_call

data = json.load(open("multiturn_tests.json"))
memory.PATH = os.path.join(tempfile.mkdtemp(), "memory.json")

def norm(facts):
    return sorted(f.strip().lower().rstrip(".") for f in facts)

def tools_called(new_messages):
    """Names of the tools the model called in these messages (one turn)."""
    names = []
    for m in new_messages:
        if m["role"] == "assistant":
            try:
                call = find_tool_call(m["content"])
            except Exception:
                call = None
            if call:
                names.append(call["name"])
    return names

def check_memory(want, have):
    if want == "unchanged":
        return norm(have) == norm(data["memory"])
    if want == "plus one about chemistry":
        extra = [f for f in have if f not in data["memory"]]
        return len(have) == len(data["memory"]) + 1 and len(extra) == 1 and "chemistry" in extra[0].lower()
    return norm(have) == norm(want)

start = time.time()
records, passed = [], 0
for t in data["tests"]:
    memory.save(list(data["memory"]))   # fresh fake memory and no pending delete for every conversation
    pending_delete.clear()
    messages = [{"role": "system", "content": ""}]
    problems, log = [], []
    for i, turn in enumerate(t["turns"], 1):
        # the same steps as one turn in server.py: refresh the prompt, add the message, answer, clean up
        messages[0]["content"] = system_prompt()
        before = len(messages)
        messages.append({"role": "user", "content": add_memory_hint(turn["user"])})
        reply = respond(messages, show=False, check=check_missed_save)
        unload_skills(messages)
        clear_memory_hints(messages)
        called = tools_called(messages[before:])
        final = reply.split("</think>")[-1].lower()
        if "tool" in turn and turn["tool"] not in called:
            problems.append(f"turn {i}: expected {turn['tool']}, called {called or 'nothing'}")
        for name in turn.get("no_tool", []):
            if name in called:
                problems.append(f"turn {i}: called {name}, which it shouldn't")
        for word in turn.get("reply_has", []):
            if word not in final:
                problems.append(f"turn {i}: reply is missing {word!r}")
        for word in turn.get("reply_not", []):
            if word in final:
                problems.append(f"turn {i}: reply says {word!r}")
        log.append({"user": turn["user"], "tools": called, "reply": reply})
    have = memory.load()
    if not check_memory(t["memory_after"], have):
        problems.append(f"memory ended as {have}")
    ok = not problems
    passed += ok
    print(f"{'PASS' if ok else 'FAIL'} | {t['name']}" + "".join(f"\n     - {p}" for p in problems), flush=True)
    records.append({"name": t["name"], "correct": ok, "problems": problems, "memory_after": have, "turns": log, "messages": messages[1:]})

os.makedirs("results", exist_ok=True)
path = f"results/multiturn__{MODEL.split('/')[-1]}.json"
with open(path, "w") as f:
    json.dump({"model": MODEL, "score": passed, "total": len(records), "seconds": round(time.time() - start), "records": records}, f, indent=1)
print(f"\n{passed}/{len(records)} conversations passed in {round(time.time() - start)}s | saved to {path}")
