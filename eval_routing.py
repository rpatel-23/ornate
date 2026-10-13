import json
import os
import re
import time
from assistant import SYSTEM_PROMPT, add_memory_hint
from harness import ask_model, MODEL, THINK, find_tool_call

# what each expected label means as a first action
def first_action(reply):
    """Return the model's first move: a skill name, 'quiz', 'python', or 'none'."""
    try:
        data = find_tool_call(reply)
    except Exception:
        return "bad tool call"
    if data is None:
        return "none"
    name = data.get("name")
    if name == "load_skill":
        return data.get("arguments", {}).get("name", "load_skill")
    if name == "start_quiz":
        return "quiz"
    if name == "run_python":
        return "python"
    return name

with open("routing_tests.json") as f:
    tests = json.load(f)

start = time.time()
records = []
for t in tests:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": add_memory_hint(t["message"])}]
    # only the model's first reply matters here, so no tools are actually run
    reply = ask_model(messages, use_tools=True, show=False)
    got = first_action(reply)
    # "expect" is one right answer, or a list when more than one first move is reasonable
    allowed = t["expect"] if isinstance(t["expect"], list) else [t["expect"]]
    ok = got in allowed
    print("PASS" if ok else "FAIL", f"| expected {' or '.join(allowed):<22} got {got:<16} | {t['message']}")
    records.append({**t, "got": got, "correct": ok, "reply": reply})

score = sum(r["correct"] for r in records)
os.makedirs("results", exist_ok=True)
path = f"results/routing__{MODEL.split('/')[-1]}__think{'1' if THINK else '0'}.json"
with open(path, "w") as f:
    json.dump({"model": MODEL, "thinking": THINK, "score": score, "records": records}, f, indent=2)
print(f"\n{score}/{len(records)} routed correctly in {round(time.time() - start)}s | thinking {'on' if THINK else 'off'} | saved to {path}")
