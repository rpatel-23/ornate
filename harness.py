import ast
import json
import re
import subprocess
import sys
from mlx_lm import load, stream_generate

import gc
import os
import mlx.core as mx

# the models you can pick in the web app. Names follow "Ornate": styles of decorative art.
# Both scored about the same time on the math eval (EVALS.md section 2); the 8B's win is memory, not speed.
MODELS = {
    "baroque":  {"name": "Baroque",  "repo": "mlx-community/Qwen3-30B-A3B-4bit",
                 "about": "30B · smartest"},
    "filigree": {"name": "Filigree", "repo": "mlx-community/Qwen3-8B-4bit",
                 "about": "8B · lighter on memory"},
}

# ORNATE_THINK=1: always think. ORNATE_THINK=0: never think.
# Not set: think only after a tool that needs careful work.
THINK_MODE = {"1": "always", "0": "never"}.get(os.environ.get("ORNATE_THINK"), "auto")
THINK = THINK_MODE == "always"
THINK_AFTER = {"load_skill", "web_search"}

MODEL = model = tokenizer = None

def use_model(repo):
    """Switch to another model. The old one is unloaded first, so only one is ever in memory."""
    global MODEL, model, tokenizer
    if repo == MODEL:
        return
    model = tokenizer = None   # drop the old model...
    gc.collect()               # ...let Python free it...
    mx.clear_cache()           # ...and hand MLX's freed memory back to the Mac
    print("loading", repo)
    try:
        model, tokenizer = load(repo)
    except Exception:
        if MODEL:   # couldn't load the new one: put the old one back so Ornate still works, then report the error
            model, tokenizer = load(MODEL)
        raise
    MODEL = repo

use_model(os.environ.get("ORNATE_MODEL", MODELS["baroque"]["repo"]))

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
    # PYTHON_COLORS / NO_COLOR: plain error text. Python 3.14 can add terminal color codes like [35m, which are junk to the model.
    env = {**os.environ, "PYTHON_COLORS": "0", "NO_COLOR": "1"}
    try:
        result = subprocess.run(
            [sys.executable, "-c", print_last_value(code)], capture_output=True, text=True, timeout=10, env=env
        )
        output = (result.stdout + result.stderr).strip() or "(no output. Use print() to show the result.)"
        if result.returncode != 0:
            # the code crashed (decided by Python's exit code, not the model's words). Without this note the model
            # sometimes says "Let's calculate..." and stops (seen on 2x^2+3x+2=0, where math.sqrt hit a negative).
            output += "\n(The code raised an error. Fix the code and call run_python again.)"
        return output
    except subprocess.TimeoutExpired:
        return "Error: code took longer than 10 seconds"

# which Python function runs each tool. Other files can add more with add_tool.
TOOL_FUNCS = {"run_python": lambda args: run_python(args["code"])}

def add_tool(spec, func):
    TOOLS.append(spec)
    TOOL_FUNCS[spec["function"]["name"]] = func
    
def ask_model(messages, use_tools, show, think=None, emit=None):
    prompt = tokenizer.apply_chat_template(
        messages,
        tools=TOOLS if use_tools else None,
        add_generation_prompt=True,
        enable_thinking=THINK if think is None else think,
    )
    reply = ""
    shown = 0
    sent = 0   # how much visible text has gone to emit
    for chunk in stream_generate(model, tokenizer, prompt=prompt, max_tokens=4000):
        reply += chunk.text
        if emit:
            # for the web page: no thinking, and stop before any tool call text
            clean = re.sub(r"<think>.*?(</think>|$)", "", reply, flags=re.DOTALL).split("<tool_call>")[0].lstrip()
            if len(clean) > sent:
                emit({"type": "text", "text": clean[sent:]})
                sent = len(clean)
        if show:
            # hide everything between <think> and </think>, print only what's new
            visible = re.sub(r"<think>.*?(</think>|$)", "(thinking) ", reply, flags=re.DOTALL)
            if "<think>" in reply and "</think>" not in reply:
                continue
            print(visible[shown:], end="", flush=True)
            shown = len(visible)
    if emit and sent == 0 and "<think>" in reply and "</think>" not in reply and "<tool_call>" not in reply:
        # the model sometimes writes its whole answer inside a thinking block it never closes.
        # The page hides thinking, so it would get nothing ("(no reply)"); send what it wrote instead, like the terminal does.
        inside = reply.split("<think>")[-1].strip()
        if inside:
            emit({"type": "text", "text": inside})
    if show:
        if "<think>" in reply and "</think>" not in reply:
        # the model never closed its thinking, so show what it wrote
            print(reply.split("<think>")[-1].strip(), end="")
        print()
    return reply

def find_tool_call(reply):
    """Return the tool call in a reply as {"name": ..., "arguments": ...}, or None if there isn't one."""
    call = re.search(r"<tool_call>(.*?)</tool_call>", reply, re.DOTALL)
    if call:
        return json.loads(call.group(1))
    # backup: sometimes the model writes the call without its tags, like
    #   remember
    #   {"fact": "Hates long explanations."}
    bare = re.fullmatch(r"\s*(\w+)\s*(\{.*\})\s*", reply.split("</think>")[-1], re.DOTALL)
    if bare and bare.group(1) in TOOL_FUNCS:
        return {"name": bare.group(1), "arguments": json.loads(bare.group(2))}
    return None

def respond(messages, use_tools=True, show=True, check=None, emit=None):
    """Run the agent loop on a conversation and return the final reply."""
    reply = ""
    think = THINK  # new: start with thinking off unless forced on
    for _ in range(5):
        reply = ask_model(messages, use_tools, show, think, emit)
        messages.append({"role": "assistant", "content": reply})
        try:
            data = find_tool_call(reply)
            if data is None:
                # optional code check on the final answer; if it returns a note, send it back and let the model fix itself once
                note = check(reply, messages) if check else None
                if note:
                    check = None   # only one retry, so it can never loop
                    messages.append({"role": "user", "content": note})
                    continue
                break
            name = data["name"]
            if emit:
                emit({"type": "tool_start", "name": name})
            output = TOOL_FUNCS[name](data["arguments"])
        except Exception as e:
            name, output = "tool error", f"Error: bad tool call ({e})"
        if show:
            preview = output if name in ("run_python", "web_search") else (output.splitlines() or [""])[0]
            print(f"\n[{name}] {preview}\n")
        messages.append({"role": "tool", "content": output})
        if emit:
            emit({"type": "tool", "name": name, "output": output[:300]})   # the page decides what to show from the result   # lets the page show "searching the web..." etc.
        if THINK_MODE == "auto" and name in THINK_AFTER:  # new
            think = True  # new: the hard part starts now, so think from here on
    if messages[-1]["role"] == "tool":
        reply = ask_model(messages, False, show, think, emit)
        messages.append({"role": "assistant", "content": reply})
    return reply