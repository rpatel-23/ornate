import os
import re
from assistant import system_prompt, respond, unload_skills, read_file, run_quiz, add_memory_hint, check_missed_save, clear_memory_hints
import memory

messages = [{"role": "system", "content": system_prompt()}]
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

    # "/memory" lists saved facts; "/forget 2" deletes fact #2
    if user.strip() == "/memory":
        facts = memory.load()
        print("\n".join(f"{i}. {f}" for i, f in enumerate(facts, 1)) or "no memories yet")
        continue
    if user.startswith("/forget "):
        try:
            print("forgot:", memory.remove(int(user[8:])))
            messages[0]["content"] = system_prompt(style)   # rebuild the prompt without it
        except (ValueError, IndexError):
            print("usage: /forget <number from /memory>")
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

    messages[0]["content"] = system_prompt(style)   # refresh, so memories saved or deleted last turn are current
    messages.append({"role": "user", "content": add_memory_hint(user) + attached})
    attached = ""
    print("\nornate: ", end="")
    respond(messages, check=check_missed_save)
    unload_skills(messages)
    clear_memory_hints(messages)