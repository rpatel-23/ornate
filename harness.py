import ast
import json
import re
import subprocess
import sys
import threading
from mlx_lm import load, stream_generate
from mlx_lm.sample_utils import make_logits_processors

import gc
import os
import mlx.core as mx

# the models you can pick in the web app. Names follow "Ornate": styles of decorative art.
# Baroque was Qwen3-30B-A3B until 10-31; the 2507 version beat it (MATH-500 95.0% vs 80.4%, EVALS.md section 9).
# It can't think (Qwen moved thinking to a separate model, Mosaic), so the thinking setting does nothing on it.
MODELS = {
    "baroque":  {"name": "Baroque",  "repo": "mlx-community/Qwen3-30B-A3B-Instruct-2507-4bit",
                 "about": "30B · best all-round"},
    "filigree": {"name": "Filigree", "repo": "mlx-community/Qwen3-8B-4bit",
                 "about": "8B · lighter on memory"},
    # always thinks before answering, often 5,000+ words, so it gets a much bigger reply limit (Qwen suggests 32,768)
    "mosaic":   {"name": "Mosaic",   "repo": "mlx-community/Qwen3-30B-A3B-Thinking-2507-4bit",
                 "about": "30B · thinks first, slow", "max_tokens": 32768},
    # trained mostly on code; never thinks, and writes tool calls as XML (see find_tool_call).
    # repetition_penalty 1.05 is from the model's own generation_config.json: without it, it wrote one function 24 times.
    "artdeco":  {"name": "Art Deco", "repo": "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
                 "about": "30B · code", "repetition_penalty": 1.05},
}
DEFAULT_MAX_TOKENS = 16384  # longest reply for models without their own max_tokens (Qwen's suggestion for 2507 Instruct).
                            # It was 4000: on MATH-500 that cut off 51 of the 2507 model's 60 misses before they reached an answer.

def setting(key, default=None):
    """A setting from the current model's MODELS entry, like max_tokens; default if it has none."""
    return next((m.get(key, default) for m in MODELS.values() if m["repo"] == MODEL), default)

def max_tokens():
    return setting("max_tokens", DEFAULT_MAX_TOKENS)

# ORNATE_THINK=1: always think. ORNATE_THINK=0: never think.
# Not set: think only after a tool that needs careful work.
THINK_MODE = {"1": "always", "0": "never"}.get(os.environ.get("ORNATE_THINK"), "auto")
THINK = THINK_MODE == "always"
THINK_AFTER = {"load_skill", "web_search"}

MODEL = model = tokenizer = None
STOP = threading.Event()   # the web page's Stop button sets this; the answer ends at the next word

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

MAX_OUTPUT = 2000   # characters of run_python output the model gets back

def run_python(code):
    # PYTHON_COLORS / NO_COLOR: plain error text. Python 3.14 can add terminal color codes like [35m, which are junk to the model.
    env = {**os.environ, "PYTHON_COLORS": "0", "NO_COLOR": "1"}
    try:
        result = subprocess.run(
            [sys.executable, "-c", print_last_value(code)], capture_output=True, text=True, timeout=10, env=env
        )
        output = (result.stdout + result.stderr).strip() or "(no output. Use print() to show the result.)"
        if len(output) > MAX_OUTPUT:
            # a huge print once made a 144,000-token prompt (past the model's limit) and froze MATH-500 for 9 hours.
            # Keep the start and the end (where errors show up) and say how much was cut.
            half = MAX_OUTPUT // 2
            output = (output[:half] + f"\n... ({len(output) - MAX_OUTPUT} characters cut. Print less, e.g. just the final answer.) ...\n"
                      + output[-half:])
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
    # Thinking-2507's template writes the opening <think> into the prompt itself, so the reply only has </think>.
    # Put it back, so the code below can hide the thinking the same way for every model.
    # (the prompt is a list of token numbers, so decode its last few to check)
    reply = "<think>\n" if tokenizer.decode(prompt[-4:]).endswith("<think>\n") else ""
    shown = 0
    sent = 0   # how much visible text has gone to emit
    # a repetition penalty makes recent words a little less likely; it still picks the top word, so answers stay repeatable
    penalty = setting("repetition_penalty")
    extra = {"logits_processors": make_logits_processors(repetition_penalty=penalty)} if penalty else {}
    for chunk in stream_generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens(), **extra):
        if STOP.is_set():
            break
        reply += chunk.text
        if len(reply) > 2000 and len(reply) % 50 < len(chunk.text) and reply.count(reply[-300:]) >= 3:
            # the same 300 characters 3 times: the model is stuck in a loop (Art Deco wrote one function 24 times
            # saying "Let me run this code" but never calling the tool). Code ends it, not the model.
            reply += "\n\n(stopped: the answer started repeating itself)"
            if emit:
                emit({"type": "text", "text": "\n\n(stopped: the answer started repeating itself)"})
            break
        if emit:
            # for the web page: no thinking, and stop before any tool call text
            clean = re.sub(r"<think>.*?(</think>|$)", "", reply, flags=re.DOTALL).split("<tool_call>")[0].split("<function=")[0].lstrip()
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

def xml_tool_call(text):
    """Qwen3-Coder's format: <function=run_python><parameter=code>print(1)</parameter></function>.
    Every value arrives as text, so numbers and lists are turned back into numbers and lists using the tool's own spec."""
    name = re.search(r"<function=([\w-]+)>", text).group(1)
    spec = next((t["function"]["parameters"]["properties"] for t in TOOLS if t["function"]["name"] == name), {})
    found = re.findall(r"<parameter=([\w-]+)>\n?(.*?)\n?</parameter>", text, re.DOTALL)
    # it also wrote <code>print(1)</code> instead of <parameter=code>: 18 times in the coding eval, so none of that code ran.
    # Only the tool's own argument names are looked for, so other tags in the text can't be misread.
    for key in spec:
        if key not in dict(found):
            plain = re.search(rf"<{key}>\n?(.*?)\n?</{key}>", text, re.DOTALL)
            if plain:
                found.append((key, plain.group(1)))
    args = {}
    for key, value in found:
        if spec.get(key, {}).get("type", "string") != "string":
            value = json.loads(value)   # "5" -> 5, "[1, 2]" -> [1, 2]
        args[key] = value
    return {"name": name, "arguments": args}

def json_tool_call(text):
    """A JSON call. Usually {"name": ..., "arguments": {...}}, but after another model's turns in the same chat
    Art Deco wrote {"name": "run_python", "code": "..."}, with the arguments at the top level. Both mean the same call."""
    data = json.loads(text)
    if "arguments" not in data:
        data = {"name": data["name"], "arguments": {k: v for k, v in data.items() if k != "name"}}
    return data

def find_tool_call(reply):
    """Return the tool call in a reply as {"name": ..., "arguments": ...}, or None if there isn't one."""
    call = re.search(r"<tool_call>(.*?)</tool_call>", reply, re.DOTALL)
    if call and "<function=" in call.group(1):
        return xml_tool_call(call.group(1))
    if call:
        return json_tool_call(call.group(1))
    # the 2507 model once stopped right after the JSON, before writing </tool_call> (LCM of 84, 126, 220), so the code never ran
    unclosed = re.search(r"<tool_call>\s*(\{.*\})\s*$", reply, re.DOTALL)
    if unclosed:
        return json_tool_call(unclosed.group(1))
    # same thing in Art Deco's XML format: it stopped right after </function>
    unclosed = re.search(r"<tool_call>(\s*<function=.*</function>)\s*$", reply, re.DOTALL)
    if unclosed:
        return xml_tool_call(unclosed.group(1))
    # and with no <tool_call> tags at all: on the routing evals Art Deco called remember, start_quiz and web_search
    # as a bare <function=...> 7 times, and none of them ran
    bare_xml = re.search(r"<function=[\w-]+>.*?</function>", reply, re.DOTALL)
    if bare_xml:
        return xml_tool_call(bare_xml.group(0))
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
        if STOP.is_set():
            break   # stopped: don't run a half-written tool call
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
            # the web page can't show this, so log it where the server's output goes, with the end of the reply that caused it
            print(f"[bad tool call] {e!r} | reply ended: {reply[-300:]!r}", file=sys.stderr, flush=True)
        if show:
            preview = output if name in ("run_python", "web_search") else (output.splitlines() or [""])[0]
            print(f"\n[{name}] {preview}\n")
        messages.append({"role": "tool", "content": output})
        if emit:
            emit({"type": "tool", "name": name, "output": output[:300]})   # the page decides what to show from the result   # lets the page show "searching the web..." etc.
        if THINK_MODE == "auto" and name in THINK_AFTER:  # new
            think = True  # new: the hard part starts now, so think from here on
    if messages[-1]["role"] == "tool" and not STOP.is_set():
        reply = ask_model(messages, False, show, think, emit)
        messages.append({"role": "assistant", "content": reply})
    return reply