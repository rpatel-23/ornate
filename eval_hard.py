import json
import os
import re
import time
from harness import respond, SYSTEM, SYSTEM_TOOLS, MODEL

with open("problems_hard.json") as f:
    PROBLEMS = json.load(f)

def is_correct(reply, expected):
    # only grade the final ANSWER line; accepts 1.5, 1,500, -11, and fractions like 3/2
    found = re.findall(r"ANSWER:\**\s*\$?\s*(-?[\d,]*\.?\d+(?:\s*/\s*\d*\.?\d+)?)", reply)
    if not found:
        return False
    text = found[-1].replace(",", "").replace(" ", "")
    if "/" in text:
        top, bottom = text.split("/")
        if float(bottom) == 0:
            return False
        value = float(top) / float(bottom)
    else:
        value = float(text)
    return abs(value - expected) <= 0.01

def run(use_tools):
    system = SYSTEM_TOOLS if use_tools else SYSTEM
    score = 0
    records = []
    for p in PROBLEMS:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": p["question"] + "\nEnd your reply with a line in the form ANSWER: <number>"},
        ]
        reply = respond(messages, use_tools=use_tools, show=False)
        ok = is_correct(reply, p["answer"])
        score += ok
        print("PASS" if ok else "FAIL", "-", p["question"])
        if not ok:
            print("   expected", p["answer"], "| reply ended with:", repr(reply[-150:]))
        # keep the whole conversation so failures can be read later
        records.append({"question": p["question"], "expected": p["answer"], "correct": ok, "messages": messages[1:]})
    return score, records

results = {"model": MODEL}
for name, use_tools in [("no_tools", False), ("python_tool", True)]:
    print(f"\n=== {name} ===")
    start = time.time()
    score, records = run(use_tools)
    results[name] = {"score": score, "total": len(PROBLEMS), "seconds": round(time.time() - start), "records": records}

os.makedirs("results", exist_ok=True)
path = "results/" + MODEL.split("/")[-1] + ".json"
with open(path, "w") as f:
    json.dump(results, f, indent=2)

print("\nmodel:", MODEL)
for name in ("no_tools", "python_tool"):
    r = results[name]
    print(f"{name}: {r['score']}/{r['total']} in {r['seconds']}s")
print("transcripts saved to", path)
