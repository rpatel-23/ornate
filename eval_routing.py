import argparse
import json
import os
import re
import time
from assistant import SYSTEM_PROMPT, add_memory_hint, check_missed_save, load_skill
from harness import ask_model, MODEL, THINK, find_tool_call
from files import read_file

# --tests routing_file_tests.json runs the messages that come with a file attached
parser = argparse.ArgumentParser()
parser.add_argument("--tests", default="routing_tests.json", help="which test file to use")
args = parser.parse_args()

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

with open(args.tests) as f:
    tests = json.load(f)

start = time.time()
records = []
for t in tests:
    # a test can attach a file; it is added the same way the web app and /file do it
    attached = f"\n\n[File: {os.path.basename(t['file'])}]\n{read_file(t['file'])}" if "file" in t else ""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": add_memory_hint(t["message"], attached)}]
    # only the model's first reply matters here, so no tools are actually run
    reply = ask_model(messages, use_tools=True, show=False)
    got = first_action(reply)
    raw = got   # what the model did on its own, before any code check
    # same one-time check the chat uses: if it claimed a save without calling remember, it gets one retry
    note = check_missed_save(reply, messages) if got == "none" else None
    if note:
        messages += [{"role": "assistant", "content": reply}, {"role": "user", "content": note}]
        reply = ask_model(messages, use_tools=True, show=False)
        got = first_action(reply)
    # same gate the chat uses: if a skill refuses to load, the model sees the refusal and makes its next move
    if got == "missed-question":
        result = load_skill({"name": got})
        if result.startswith("Not loaded"):
            messages += [{"role": "assistant", "content": reply}, {"role": "tool", "content": result}]
            reply = ask_model(messages, use_tools=True, show=False)
            got = first_action(reply)
    # "expect" is one right answer, or a list when more than one first move is reasonable
    allowed = t["expect"] if isinstance(t["expect"], list) else [t["expect"]]
    ok = got in allowed
    print("PASS" if ok else "FAIL", f"| expected {' or '.join(allowed):<22} got {got:<16} | {t['message']}" + (f"  [{t['file']}]" if "file" in t else "") + (f"  (caught by check, model first said {raw})" if raw != got else ""))
    records.append({**t, "got": got, "raw": raw, "correct": ok, "raw_correct": raw in allowed, "reply": reply})

score = sum(r["correct"] for r in records)
raw_score = sum(r["raw_correct"] for r in records)
os.makedirs("results", exist_ok=True)
name = "routing" if args.tests == "routing_tests.json" else "routing_files"   # don't overwrite the main routing results
path = f"results/{name}__{MODEL.split('/')[-1]}__think{'1' if THINK else '0'}.json"
with open(path, "w") as f:
    json.dump({"model": MODEL, "thinking": THINK, "score": score, "raw_score": raw_score, "records": records}, f, indent=2)
print(f"\nmodel alone: {raw_score}/{len(records)} | with code check: {score}/{len(records)}")
print(f"{score}/{len(records)} routed correctly in {round(time.time() - start)}s | thinking {'on' if THINK else 'off'} | saved to {path}")
