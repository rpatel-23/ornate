# Ornate: notes for Claude

Ornate is Rishabh's local AI agent, built from scratch as a learning and portfolio project. It runs Qwen3 30B-A3B-Instruct-2507 (4-bit, MLX; "Baroque") on his MacBook Pro (M1 Max, 64 GB). Public repo: github.com/rpatel-23/ornate. It is on his resume and in internship emails, so the README and EVALS must stay accurate.

## How Rishabh works

- High school junior. Python level: can follow along. **He wants to understand every line.** Explain each change in plain words before or right after making it; don't change many files silently.
- Prefers concise answers. Casual, playful tone is fine.
- Sessions: about an hour on weekdays, longer on weekends.
- He tests in the browser and terminal himself; ask him to try things and paste results.

## Running things

```
source .venv/bin/activate
uvicorn server:app --port 8000      # web app at http://localhost:8000 (restart after Python changes)
python agent.py                     # terminal chat
python test_checks.py               # code-side memory checks, no model, < 1 s
python eval_routing.py              # 30 messages, ~1.5 min (--tests routing_file_tests.json / routing_text_tests.json: with a file)
python eval_memory.py               # 13 forget/memory messages on a fake memory list (never touches memory.json)
python eval_hard.py / eval_skill.py # math and missed-question evals
python eval_math500.py --mode tools # MATH-500 (data/math500.jsonl, graded by math_grader.py): 2 to 5 hours; --limit N, --rerun-cut OLD_LIMIT; resumes after a crash
python eval_coding.py               # 15 write-and-run tasks (coding_tests.json), ~2 to 7 min
python eval_multiturn.py            # 11 conversations on a fake memory file, ~2 min
```

**Run one model at a time.** Each 30B model is ~17 GB; three at once (server + two evals) ran the GPU out of memory on 10-31. Keep the web server off while evals run.

`ORNATE_MODEL=...` picks the starting model. The web app also has a picker (`MODELS` in harness.py): Baroque = Qwen3-30B-A3B-Instruct-2507 (since 10-31; no thinking mode, was Qwen3-30B-A3B), Filigree = Qwen3 8B, Mosaic = Qwen3-30B-A3B-Thinking-2507 (always thinks, 32,768-token limit), Art Deco = Qwen3-Coder-30B-A3B (XML tool calls, repetition penalty 1.05); switching unloads the old model first. A `MODELS` entry can set `max_tokens` and `repetition_penalty`; the default reply limit is 16,384. `ORNATE_THINK=1/0` forces thinking on/off (default auto); only Filigree has a thinking switch now. Page-only changes need a hard refresh (cmd+shift+R), not a server restart.

## Files

- `harness.py`: `MODELS` and `use_model` (load/switch, one model in memory at a time), `ask_model` (streaming, optional `emit` for the web, `STOP` flag for the Stop button, loop guard), `respond` (agent loop, up to 5 tool rounds, optional `check` retry), `find_tool_call` (JSON or XML calls, with or without `<tool_call>` tags, a missing closing tag, arguments at the top level, or a bare `name {json}`; `respond` logs bad tool calls to stderr), `add_tool` registry, `run_python` (output capped at 2,000 characters).
- `math_grader.py`, `eval_math500.py`, `eval_coding.py`, `coding_tests.json`, `data/math500.jsonl` (MIT, from HuggingFaceH4/MATH-500). `eval_multiturn.py` + `multiturn_tests.json`: 11 short conversations run the way the server runs turns, on a fake memory file.
- `assistant.py`: tools (`load_skill`, `start_quiz`, `web_search`, `remember`, `forget`), skill menu, system prompt, memory rules (`is_save_request`, `is_delete_request`, `add_memory_hint`, `clear_memory_hints`, `check_missed_save`, `handle_delete_reply`).
- `memory.py`: facts in `memory.json` (git-ignored, personal, never commit it).
- `agent.py`: terminal chat and slash commands. `server.py` + `static/index.html`: FastAPI web app (NDJSON streaming, lock, queue, memory popup, copy, edit a sent message, sidebar, settings panel: theme in the browser, thinking mode on the server until restart; KaTeX math from a CDN; files by drag-and-drop or paperclip, sent as base64 and read by `files.text_from`; the open chat's id sits in the URL after #, so a refresh keeps it). `chats.py`: saved chats as JSON files in `chats/` (git-ignored, personal), folders in `chats/folders.json`. `quiz.py`, `files.py`, `skills/`, `styles/`.
- `tokenizer.py`, `data.py`, `bigram.py`, `gpt.py`: the tiny GPT from the start of the project.
- `EVALS.md`: every eval with numbers and findings. `docs/findings.md`: the full "What I found" list (the README keeps 5 short highlights). `results/`: saved transcripts.

## Rules we settled on

- **Code decides anything that matters, not the model.** Quiz scoring is in Python. `remember` refuses unless the user's latest message is an explicit save request. `forget` refuses unless the user's latest message asks to delete, and then only queues facts; the model asks "are you sure", and code deletes only if the next user message is a yes. Never base a check on the model's own words (the "energy is stored in glucose" bug).
- **Read transcripts before blaming the model or changing the prompt.** Several "model failures" were harness bugs.
- **Rerun the relevant evals after any prompt or tool change**, since adding a tool shifted routing on unrelated messages. Report "model alone" and "with code check" separately.
- **Don't tune prompts to pass a specific test** (no test wording in the prompt). Don't relabel a failing test unless the key was wrong.
- **README and EVALS numbers must be measured.** No claims of fine-tuning or training; models are stock Qwen3.
- Keep personal info out of the repo and screenshots.
- **Never add Claude as a co-author or contributor.** No `Co-Authored-By` lines, no "Generated with Claude Code" footers, and no Claude attribution in commit messages, PR descriptions, or files. Rishabh writes and makes his own commits; the README's Notes section already says Claude was used as a tutor, and that is the only mention.

## Known state

- Evals rerun 2026-10-28: routing 30/30, memory 12/13 (model alone and with code check). `forget` now refuses unless the user's message asks to delete (`is_delete_request`), and the forget rule was removed from the prompt because it made "what do you know about me?" call forget. Remaining memory miss: "forget that i play basketball" deletes "Plays soccer." (stopped only by the "are you sure").
- Multi-turn: `eval_multiturn.py` (11 conversations, 11-01): Baroque 11/11, Art Deco 10/11. It found that "wait no, forget X instead" was answered "Okay, I'll keep it" because `handle_delete_reply`'s note said to; a reply that is itself a delete request now gets a note to handle it as a new request.
- 2026-10-30 (EVALS.md section 8): held-out math 44/45 for Ornate vs 34/45 for the same model with no tools. `run_python`'s crash note ("Fix the code and call run_python again") and no-color env: before/after 44/45 and 50/50 both, no change. File routing: `routing_file_tests.json` (17 messages, made-up files in `test_files/`, run with `eval_routing.py --tests routing_file_tests.json`): 13/17 model alone, 15/17 with the missed-question gate (`is_missed_question` on the typed text only, in `load_skill`); original 30 routing still 30/30. Still failing: "summarize this article in 3 bullet points" and "fix the grammar in my essay" call run_python.
- The web page used to show "(no reply)" when the model wrote its answer inside a thinking block it never closed (seen after the missed-question skill). `ask_model` now sends that text to the page, like the terminal does.
- `run_python` is not sandboxed. Math needs internet once per page load (KaTeX from a CDN), else it shows raw. Web files: text and PDF only; an edited message keeps its files. Saved chats: the model still sees one chat at a time (switching loads it from disk); a chat's title is its first message, cut to 40 letters.
- Model picker, measured 2026-10-28 (one 200-word answer each): Baroque 22.8 words/s, Filigree 19.7 words/s; server memory 16 GB vs 4.9 GB; switching takes 1 to 3 s once files are cached. The 8B's win is memory, not speed. Routing and memory evals have only been run on the 30B.
- The 30B MoE beat a dense 32B (same or better scores, ~8x faster), so Ornate stays on the 30B.
- 10-31 (EVALS.md section 9): MATH-500 with tools, 16,384-token limit: Baroque 402/500 (80.4%), Qwen3-30B-A3B-Instruct-2507 475/500 (95.0%; 440 at 4,000 tokens). The grader was fixed for 26 right answers marked wrong (all confirmed). The 2507 matches or beats Baroque on every eval except routing 29/30 ("btw im taking AP Gov" calls remember; the gate refuses). Rishabh made it Baroque on 10-31; rerun on it: held-out no tools 39/45 (Ornate 45/45), hard no tools 50/50, slips 7/9 by reading. Mosaic: math 45/45 and 50/50, MATH-500 first 100: 95 (2507 94, Baroque 88) but ~3x slower, routing 27/30. Art Deco: routing 23/30, coding 14/15; its tool use flips with small prompt changes and it sometimes writes "Let me run this code" then pastes code instead of calling the tool (the loop guard stops repeats). Coding eval: Baroque, 2507, Mosaic 15/15.
- Baroque's memory eval depends on the prompt's date: 10/13 on 10-31, 12/13 with the date set to 10-28 (what do you remember / whats in your memory call remember / forget; gates stop both).
- 11-01: MATH-500 no tools on Baroque 481/500 (96.2%) vs Ornate 475/500: the tools don't help on competition math (they do on the arithmetic held-out set, 39 -> 45). Art Deco wrote `<code>` instead of `<parameter=code>` 18 times in the coding eval, so its code never ran; `xml_tool_call` reads plain argument tags now, and it scores 15/15 coding. Art Deco's routing/files/memory move with the date (21/30, 12/17, 10/13 on 11-01). Web app tested end to end on port 8001 (Stop, scrolling, starters, Mosaic hiding its thinking).
- 11-01 (EVALS.md section 10): files now go before the typed words in `<document>` tags (`files.attach`, used by server, `/file` and `eval_routing.py`). New `routing_text_tests.json` (10 writing + 3 counting tasks on a file): 7/13 -> 8/13 alone, 10/13 with check; file routing 17/17 with check (15/17 alone). A prompt rule ("write it yourself") didn't help and was removed. Routing 30 is 28/30 on 11-01 with old and new code alike (date). Still calling Python: shorten, translate, outline.
- Web app 10-31: Stop button (`POST /stop`), scrolling up during an answer stays put, new chat shows the box centered with starter ideas.

## Next up

1. Auto-picking the model (Rishabh wants picker first, auto later): measure before building.
2. The 3 writing tasks that still call run_python (shorten, translate, outline in routing_text_tests.json); maybe a fresh test set too.
3. Windows port (laptop with RTX 4070, 8 GB VRAM). MLX is Mac-only, so harness.py needs a second engine: llama-cpp-python with CUDA and GGUF files, picked by platform, keeping the Baroque/Filigree names. Filigree (8B, ~5 GB at 4-bit) fits in VRAM; Baroque (30B MoE, ~17 GB) needs its expert layers kept in system RAM, so check the laptop's RAM first.
4. Then: fine-tuning (LoRA on MLX) with before/after evals on data it never trained on, vision, RAG over class notes, multi-language code runner with a sandbox.
