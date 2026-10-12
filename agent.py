import os
import re
from assistant import SYSTEM_PROMPT, system_prompt, respond, unload_skills, read_file, run_quiz

messages = [{"role": "system", "content": SYSTEM_PROMPT}]
attached = ""  # file text waiting to go out with your next message
style = "plain"

while True:
    user = input("\nyou: ")
    if user.strip().lower() in ("q", "quit"):
        break

    # "/style name" switches personality for the rest of the chat; "/style" lists them
    if user.strip() == "/style" or user.startswith("/style "):
        name = user[6:].strip()
        if not name:
            print("styles:", ", ".join(f[:-3] for f in sorted(os.listdir("styles")) if f.endswith(".md")))
            continue
        try:
            messages[0]["content"] = system_prompt(name)
            style = name
            print("style:", name)
        except Exception as e:
            print("couldn't load that style:", e)
        continue

    # "/quiz topic" or "/quiz 3 topic" runs a quiz; uses any attached file as the material
    if user.startswith("/quiz "):
        words = user[6:].split()
        count = int(words.pop(0)) if words and words[0].isdigit() else 5
        summary = run_quiz(" ".join(words), count, attached)
        attached = ""
        if summary:
            messages.append({"role": "user", "content": summary})
        continue

    # "/file path" attaches a file instead of sending a message
    if user.startswith("/file "):
        path = user[6:].strip().strip("'\"").replace("\\ ", " ")
        try:
            attached += f"\n\n[File: {path}]\n{read_file(path)}"
            print("attached", path)
        except Exception as e:
            print("couldn't read that file:", e)
        continue

    # if the user tells it to stop joking, switch to plain style in code, not just by asking the model
    if style != "plain" and re.search(r"\b(chill|relax|stop joking|no jokes|stop roasting)\b", user.lower()):
        messages[0]["content"] = system_prompt("plain")
        style = "plain"
        print("(switched to plain style)")

    messages.append({"role": "user", "content": user + attached})
    attached = ""
    print("\nornate: ", end="")
    respond(messages)
    unload_skills(messages)