import argparse
import json
import os
import re
import time

# options, so one script covers every experiment
parser = argparse.ArgumentParser()
parser.add_argument("--problems", default="problems_hard.json", help="which problem file to use")
parser.add_argument("--mode", choices=["both", "tools", "no_tools"], default="both")
parser.add_argument("--prompt", choices=["reason", "simple"], default="reason", help="which tool prompt to test")
args = parser.parse_args()

from harness import respond, SYSTEM, SYSTEM_TOOLS, MODEL

# the original one-line tool prompt, kept so old and new can be compared
SIMPLE_TOOLS = SYSTEM + " For any calculation, use the run_python tool."
TOOL_PROMPT = SYSTEM_TOOLS if args.prompt == "reason" else SIMPLE_TOOLS

with open(args.problems) as f:
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
    # small answers like probabilities need a tighter match than big ones
    tolerance = 0.01 if abs(expected) >= 1 else 0.0001
    return abs(value - expected) <= tolerance

def run(use_tools):
    system = TOOL_PROMPT if use_tools else SYSTEM
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

runs = {"both": ["no_tools", "python_tool"], "tools": ["python_tool"], "no_tools": ["no_tools"]}[args.mode]
results = {"model": MODEL, "problems": args.problems, "prompt": args.prompt}
for name in runs:
    print(f"\n=== {name} ===")
    start = time.time()
    score, records = run(use_tools=(name == "python_tool"))
    results[name] = {"score": score, "total": len(PROBLEMS), "seconds": round(time.time() - start), "records": records}

os.makedirs("results", exist_ok=True)
set_name = os.path.basename(args.problems).replace(".json", "")
path = f"results/{MODEL.split('/')[-1]}__{set_name}__{args.prompt}.json"
with open(path, "w") as f:
    json.dump(results, f, indent=2)

print(f"\nmodel: {MODEL} | problems: {args.problems} | tool prompt: {args.prompt}")
for name in runs:
    r = results[name]
    print(f"{name}: {r['score']}/{r['total']} in {r['seconds']}s")
print("transcripts saved to", path)
