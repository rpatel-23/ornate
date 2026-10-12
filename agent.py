from quiz import run_quiz
import os
from harness import respond, SYSTEM_TOOLS
from files import read_file

messages = [{"role": "system", "content": SYSTEM_TOOLS}]
attached = ""  # file text waiting to go out with your next message

while True:
    user = input("\nyou: ")
    if user.strip().lower() in ("q", "quit"):
        break

    # "/quiz topic" or "/quiz 3 topic" runs a quiz; uses any attached file as the material
    if user.startswith("/quiz "):
        words = user[6:].split()
        count = int(words.pop(0)) if words and words[0].isdigit() else 5
        summary = run_quiz(" ".join(words), count, attached)
        attached = ""
        if summary:
            messages.append({"role": "user", "content": summary})
        continue

    # "/skills" lists the skills that exist
    if user.strip() == "/skills":
        print("skills:", ", ".join(f[:-3] for f in os.listdir("skills") if f.endswith(".md")))
        continue

    # "/skill name" loads a skill's instructions into this chat
    if user.startswith("/skill "):
        name = user[7:].strip()
        try:
            text = read_file(f"skills/{name}.md")
            messages[0]["content"] += "\n\n" + text
            print("loaded skill:", name)
        except Exception as e:
            print("couldn't load that skill:", e)
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

    messages.append({"role": "user", "content": user + attached})
    attached = ""
    print("\nornate: ", end="")
    respond(messages)