from harness import respond, SYSTEM_TOOLS
from files import read_file

messages = [{"role": "system", "content": SYSTEM_TOOLS}]
attached = ""  # file text waiting to go out with your next message

while True:
    user = input("\nyou: ")
    if user.strip().lower() in ("q", "quit"):
        break

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