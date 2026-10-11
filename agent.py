from harness import respond, SYSTEM_TOOLS

messages = [{"role": "system", "content": SYSTEM_TOOLS}]

while True:
    user = input("\nyou: ")
    if user.strip().lower() in ("q", "quit"):
        break
    messages.append({"role": "user", "content": user})
    print("\nornate: ", end="")
    respond(messages)