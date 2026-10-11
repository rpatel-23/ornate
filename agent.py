import json
import re
import subprocess
import sys
from mlx_lm import load, stream_generate

model, tokenizer = load("mlx-community/Qwen3-8B-4bit")

# describe the tool so the model knows it exists
tools = [{
    "type": "function",
    "function": {
        "name": "run_python",
        "description": "Run Python code and return what it prints. Use this for any math or calculation instead of doing it in your head.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code. Use print() to show the result."}
            },
            "required": ["code"],
        },
    },
}]

def run_python(code):
    try:
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=10
        )
        return (result.stdout + result.stderr).strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: code took longer than 10 seconds"

def ask_model(messages):
    prompt = tokenizer.apply_chat_template(
        messages, tools=tools, add_generation_prompt=True, enable_thinking=False
    )
    reply = ""
    for chunk in stream_generate(model, tokenizer, prompt=prompt, max_tokens=2000):
        print(chunk.text, end="", flush=True)
        reply += chunk.text
    print()
    return reply

messages = [{
    "role": "system",
    "content": "You are Ornate, a helpful assistant. For any calculation, use the run_python tool.",
}]

while True:
    user = input("\nyou: ")
    if user.strip().lower() in ("q", "quit"):
        break
    messages.append({"role": "user", "content": user})

    # agent loop: keep going until the model answers without calling a tool
    for _ in range(5):
        print("\nornate: ", end="")
        reply = ask_model(messages)
        messages.append({"role": "assistant", "content": reply})

        call = re.search(r"<tool_call>(.*?)</tool_call>", reply, re.DOTALL)
        if not call:
            break
        try:
            code = json.loads(call.group(1))["arguments"]["code"]
            output = run_python(code)
        except Exception as e:
            output = f"Error: bad tool call ({e})"
        print(f"\n[tool output] {output}")
        messages.append({"role": "tool", "content": output})