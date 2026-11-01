"""MATH-500: 500 competition problems (levels 1 to 5) from the MATH benchmark, graded by math_grader.py.
Run:  python eval_math500.py --mode tools          (Ornate: reasoning prompt + Python tool)
      python eval_math500.py --mode no_tools       (the bare model)
      add --limit 100 to run only the first 100 problems.
      add --rerun-cut 4000 to rerun only the problems that hit an old 4000-token reply limit (after raising it).
ORNATE_MODEL=... picks the model, like everywhere else."""
import argparse
import json
import os
import time
from collections import defaultdict

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["tools", "no_tools"], default="tools")
parser.add_argument("--limit", type=int, default=500, help="only run the first N problems")
parser.add_argument("--rerun-cut", type=int, metavar="OLD_LIMIT",
                    help="rerun only the problems whose reply hit OLD_LIMIT tokens in the saved results, plus 5 that didn't as a check")
parser.add_argument("--only", metavar="IDS_JSON",
                    help="run only the problems listed in this JSON file (a list of ids), e.g. the ones another model missed")
args = parser.parse_args()

import harness
from harness import respond, SYSTEM, SYSTEM_TOOLS, MODEL
from math_grader import last_boxed, is_correct

rows = [json.loads(line) for line in open("data/math500.jsonl")][: args.limit]
os.makedirs("results", exist_ok=True)
path = f"results/math500__{MODEL.split('/')[-1]}__{args.mode}.json"

old = {}
if args.rerun_cut:
    # The model always picks its most likely next word, so a bigger limit can only change replies that hit the old one.
    # Rerun those, plus 5 that didn't: if the 5 come out word-for-word the same, the shortcut is fair.
    old = {r["id"]: r for r in json.load(open(path))["records"]}
    def was_cut(r):
        return any(len(harness.tokenizer.encode(m["content"])) >= args.rerun_cut - 10 for m in r["messages"] if m["role"] == "assistant")
    cut = {i for i, r in old.items() if was_cut(r)}
    control = [i for i, r in old.items() if i not in cut][:5]
    rows = [r for r in rows if r["unique_id"] in cut or r["unique_id"] in control]
    print(f"rerunning {len(cut)} cut-off problems and {len(control)} controls", flush=True)
    path = path.replace(".json", f"__rerun_cut{args.rerun_cut}.json")
if args.only:
    wanted = set(json.load(open(args.only)))
    rows = [r for r in rows if r["unique_id"] in wanted]
    path = path.replace(".json", f"__only_{os.path.basename(args.only).removesuffix('.json')}.json")   # its own file, so a full run isn't overwritten

# resume: if an earlier run of this same file stopped partway (crash, out of memory), keep what it saved and skip those problems
done_before = []
if os.path.exists(path):
    saved = json.load(open(path))
    if not saved.get("finished"):
        done_before = saved["records"]
        rows = [r for r in rows if r["unique_id"] not in {x["id"] for x in done_before}]
        print(f"resuming: {len(done_before)} problems already done, {len(rows)} left", flush=True)
use_tools = args.mode == "tools"
system = SYSTEM_TOOLS if use_tools else SYSTEM

def save(finished):
    # saved after every problem, so a crash keeps everything done so far ("finished": false marks a partial run)
    score = sum(x["correct"] for x in records)
    with open(path, "w") as f:
        json.dump({"model": MODEL, "mode": args.mode, "finished": finished, "score": score, "total": len(records),
                   "seconds": round(time.time() - start),
                   "by_level": {lvl: {"correct": c, "total": t} for lvl, (c, t) in sorted(by_level.items())}, "records": records}, f, indent=1)
    return score

start = time.time()
records = list(done_before)
by_level = defaultdict(lambda: [0, 0])   # level -> [correct, total]
for x in done_before:
    by_level[x["level"]][0] += x["correct"]
    by_level[x["level"]][1] += 1
for n, r in enumerate(rows, 1):
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": r["problem"] + "\n\nPut your final answer in \\boxed{}."}]
    reply = respond(messages, use_tools=use_tools, show=False)
    got = last_boxed(reply.split("</think>")[-1])
    ok = is_correct(got, r["answer"])
    by_level[r["level"]][0] += ok
    by_level[r["level"]][1] += 1
    done = sum(c for c, _ in by_level.values())
    if r["unique_id"] in old:
        same = old[r["unique_id"]]["messages"] == messages[1:]
        print("  same reply as before" if same else "  CHANGED from before", flush=True)
    print(f"{'PASS' if ok else 'FAIL'} {n}/{len(rows)} (score {done}) | level {r['level']} | key {r['answer']!r} | got {got!r}", flush=True)
    records.append({"id": r["unique_id"], "level": r["level"], "subject": r["subject"], "answer": r["answer"],
                    "got": got, "correct": ok, "messages": messages[1:]})
    save(finished=False)

score = save(finished=True)
seconds = round(time.time() - start)
print(f"\nmodel: {MODEL} | mode: {args.mode} | {score}/{len(records)} ({100 * score / len(records):.1f}%) in {seconds}s")
for lvl, (c, t) in sorted(by_level.items()):
    print(f"  level {lvl}: {c}/{t}")
print("saved to", path)
