import ast
import json
import re
import subprocess
import sys
from mlx_lm import load, stream_generate

import os

MODEL = os.environ.get("ORNATE_MODEL", "mlx-community/Qwen3-30B-A3B-4bit")
# ORNATE_THINK=1: always think. ORNATE_THINK=0: never think.
# Not set: think only after a tool that needs careful work.
THINK_MODE = {"1": "always", "0": "never"}.get(os.environ.get("ORNATE_THINK"), "auto")
THINK = THINK_MODE == "always"
THINK_AFTER = {"load_skill", "web_search"}
print("loading", MODEL)
model, tokenizer = load(MODEL)

SYSTEM = "You are Ornate, a helpful assistant."
SYSTEM_TOOLS = SYSTEM + (
    " You have a run_python tool. Only use it when a question needs calculation or running code; for everything else, answer directly."
    " For math, first reason through the problem in words and decide how to solve it."
    " Then use run_python to do the arithmetic, not to replace your reasoning."
    " Before giving your final answer, check that the result makes sense for the question."
    " If it does not, find the mistake and fix it."
)

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

# which Python function runs each tool. Other files can add more with add_tool.
TOOL_FUNCS = {"run_python": lambda args: run_python(args["code"])}

def add_tool(spec, func):
    TOOLS.append(spec)
    TOOL_FUNCS[spec["function"]["name"]] = func
    
def ask_model(messages, use_tools, show, think=None):
    prompt = tokenizer.apply_chat_template(
        messages,
        tools=TOOLS if use_tools else None,
        add_generation_prompt=True,
        enable_thinking=THINK if think is None else think,
    )
    reply = ""
    shown = 0
    for chunk in stream_generate(model, tokenizer, prompt=prompt, max_tokens=4000):
        reply += chunk.text
        if show:
            # hide everything between <think> and </think>, print only what's new
            visible = re.sub(r"<think>.*?(</think>|$)", "(thinking) ", reply, flags=re.DOTALL)
            if "<think>" in reply and "</think>" not in reply:
                continue
            print(visible[shown:], end="", flush=True)
            shown = len(visible)
    if show:
        if "<think>" in reply and "</think>" not in reply:
        # the model never closed its thinking, so show what it wrote
            print(reply.split("<think>")[-1].strip(), end="")
        print()
    return reply

def respond(messages, use_tools=True, show=True):
    """Run the agent loop on a conversation and return the final reply."""
    reply = ""
    think = THINK  # new: start with thinking off unless forced on
    for _ in range(5):
        reply = ask_model(messages, use_tools, show, think)
        messages.append({"role": "assistant", "content": reply})
        call = re.search(r"<tool_call>(.*?)</tool_call>", reply, re.DOTALL)
        if not call:
            break
        try:
            data = json.loads(call.group(1))
            name = data["name"]
            output = TOOL_FUNCS[name](data["arguments"])
        except Exception as e:
            name, output = "tool error", f"Error: bad tool call ({e})"
        if show:
            preview = output if name in ("run_python", "web_search") else (output.splitlines() or [""])[0]
            print(f"\n[{name}] {preview}\n")
        messages.append({"role": "tool", "content": output})
        if THINK_MODE == "auto" and name in THINK_AFTER:  # new
            think = True  # new: the hard part starts now, so think from here on
    if messages[-1]["role"] == "tool":
        reply = ask_model(messages, False, show, think)
        messages.append({"role": "assistant", "content": reply})
    return reply