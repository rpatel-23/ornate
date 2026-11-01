"""Coding eval: 15 "write code and run it" requests with Ornate's real prompt and tools (coding_tests.json).
Everything is decided by code, not the model's words:
  ran      - the model called run_python at least once
  ran_ok   - its last run_python finished without an error (Python's exit code, via the crash note)
  looped   - the loop guard had to stop the answer
  answer   - the expected answer appears in the final reply (rough: short answers like "the" can match by accident)
Run: python eval_coding.py      (ORNATE_MODEL=... picks the model)"""
import json
import os
import re
import time
from assistant import SYSTEM_PROMPT
from harness import respond, MODEL

CRASH_NOTE = "(The code raised an error."   # run_python adds this when the code crashes
LOOP_NOTE = "(stopped: the answer started repeating itself)"

tests = json.load(open("coding_tests.json"))
start = time.time()
records = []
for n, t in enumerate(tests, 1):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": t["message"]}]
    t0 = time.time()
    reply = respond(messages, show=False)
    outputs = [m["content"] for m in messages if m["role"] == "tool"]
    ran = bool(outputs)
    ran_ok = ran and CRASH_NOTE not in outputs[-1]
    looped = any(LOOP_NOTE in m["content"] for m in messages if m["role"] == "assistant")
    final = re.sub(r"(?<=\d),(?=\d{3})", "", reply.split("</think>")[-1])   # 832,040 -> 832040
    answer = re.search(r"(?<![\w.])" + re.escape(t["answer"]) + r"(?![\w])", final) is not None
    ok = ran_ok and answer and not looped
    print(f"{'PASS' if ok else 'FAIL'} {n}/{len(tests)} | ran {ran} | ran ok {ran_ok} | looped {looped} | answer {answer} "
          f"| {round(time.time() - t0)}s | {t['message'][:60]}", flush=True)
    records.append({**t, "ran": ran, "ran_ok": ran_ok, "looped": looped, "answer_found": answer, "correct": ok,
                    "messages": messages[1:]})

total = len(records)
count = lambda key: sum(r[key] for r in records)
os.makedirs("results", exist_ok=True)
path = f"results/coding__{MODEL.split('/')[-1]}.json"
with open(path, "w") as f:
    json.dump({"model": MODEL, "score": count("correct"), "total": total, "seconds": round(time.time() - start),
               "records": records}, f, indent=1)
print(f"\nmodel: {MODEL}")
print(f"all four ok: {count('correct')}/{total} | called run_python: {count('ran')}/{total} | ran without error: {count('ran_ok')}/{total}"
      f" | looped: {count('looped')}/{total} | answer in reply: {count('answer_found')}/{total} | {round(time.time() - start)}s")
print("saved to", path)
