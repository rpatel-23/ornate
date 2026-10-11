import json
import os
import re
from harness import respond, SYSTEM_TOOLS, MODEL
from files import read_file

SKILL = "missed-question"
thinking = os.environ.get("ORNATE_THINK") == "1"

skill_text = read_file(f"skills/{SKILL}.md")
with open("problems_slips.json") as f:
    problems = json.load(f)

records = []
for i, p in enumerate(problems, 1):
    messages = [
        {"role": "system", "content": SYSTEM_TOOLS + "\n\n" + skill_text},
        {"role": "user", "content": f"{p['question']} I put {p['wrong']}."},
    ]
    reply = respond(messages, show=False)
    # drop hidden thinking, then pull out just the "Your slip" line
    # remove finished thinking blocks; if the model never closed one, keep its text
    final = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).replace("<think>", "").strip()
    found = re.search(r"\*\*Your slip:\*\*(.*?)(?=\n\*\*|\Z)", final, re.DOTALL)
    slip = found.group(1).strip() if found else "(no 'Your slip' line found)"
    used_tool = any(m["role"] == "tool" for m in messages)

    print(f"\n--- {i}. {p['question']}  (put {p['wrong']}, correct {p['correct']})")
    print("EXPECTED SLIP:", p["slip"])
    print("MODEL'S SLIP: ", slip)
    records.append({**p, "model_slip": slip, "used_tool": used_tool, "final": final, "messages": messages[1:]})

os.makedirs("results", exist_ok=True)
path = f"results/skill_{SKILL}__{MODEL.split('/')[-1]}__think{'1' if thinking else '0'}.json"
with open(path, "w") as f:
    json.dump({"model": MODEL, "thinking": thinking, "records": records}, f, indent=2)
print(f"\n{len(records)} problems | thinking {'on' if thinking else 'off'} | saved to {path}")
print("Not auto-graded: compare each MODEL'S SLIP to the EXPECTED SLIP by reading them.")
