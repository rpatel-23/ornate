import ast
import json
import re
import subprocess
import sys
from mlx_lm import load, stream_generate

import os

MODEL = os.environ.get("ORNATE_MODEL", "mlx-community/Qwen3-8B-4bit")
print("loading", MODEL)
model, tokenizer = load(MODEL)

SYSTEM = "You are Ornate, a helpful assistant."
SYSTEM_TOOLS = SYSTEM + " For any calculation, use the run_python tool."

TOOLS = [{
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

def print_last_value(code):
    # models often end with a bare value like a notebook cell; make that print
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    if not tree.body or not isinstance(tree.body[-1], ast.Expr):
        return code
    last = ast.unparse(tree.body[-1].value)
    rest = ast.unparse(ast.Module(body=tree.body[:-1], type_ignores=[]))
    return rest + f"\n_last = {last}\nif _last is not None:\n    print(_last)"

def run_python(code):
    try:
        result = subprocess.run(
            [sys.executable, "-c", print_last_value(code)], capture_output=True, text=True, timeout=10
        )
        return (result.stdout + result.stderr).strip() or "(no output. Use print() to show the result.)"
    except subprocess.TimeoutExpired:
        return "Error: code took longer than 10 seconds"
    
def ask_model(messages, use_tools, show):
    prompt = tokenizer.apply_chat_template(
        messages,
        tools=TOOLS if use_tools else None,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    reply = ""
    for chunk in stream_generate(model, tokenizer, prompt=prompt, max_tokens=2000):
        if show:
            print(chunk.text, end="", flush=True)
        reply += chunk.text
    if show:
        print()
    return reply

def respond(messages, use_tools=True, show=True):
    """Run the agent loop on a conversation and return the final reply."""
    reply = ""
    for _ in range(5):
        reply = ask_model(messages, use_tools, show)
        messages.append({"role": "assistant", "content": reply})
        call = re.search(r"<tool_call>(.*?)</tool_call>", reply, re.DOTALL)
        if not call:
            break
        try:
            code = json.loads(call.group(1))["arguments"]["code"]
            output = run_python(code)
        except Exception as e:
            output = f"Error: bad tool call ({e})"
        if show:
            print(f"\n[tool output] {output}\n")
        messages.append({"role": "tool", "content": output})
    return reply