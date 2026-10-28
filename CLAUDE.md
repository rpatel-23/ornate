# Ornate: notes for Claude

Ornate is Rishabh's local AI agent, built from scratch as a learning and portfolio project. It runs Qwen3 30B-A3B (4-bit, MLX) on his MacBook Pro (M1 Max, 64 GB). Public repo: github.com/rpatel-23/ornate. It is on his resume and in internship emails, so the README and EVALS must stay accurate.

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
python eval_routing.py              # 30 messages, ~1.5 min
python eval_memory.py               # 10 forget requests on a fake memory list (never touches memory.json)
python eval_hard.py / eval_skill.py # math and missed-question evals
```

`ORNATE_MODEL=...` switches model. `ORNATE_THINK=1/0` forces thinking on/off (default auto). Page-only changes need a hard refresh (cmd+shift+R), not a server restart.

## Files

- `harness.py`: model loading, `ask_model` (streaming, optional `emit` for the web), `respond` (agent loop, up to 5 tool rounds, optional `check` retry), `find_tool_call` (also accepts a bare `name {json}` call), `add_tool` registry, `run_python`.
- `assistant.py`: tools (`load_skill`, `start_quiz`, `web_search`, `remember`, `forget`), skill menu, system prompt, memory rules (`is_save_request`, `add_memory_hint`, `clear_memory_hints`, `check_missed_save`, `handle_delete_reply`).
- `memory.py`: facts in `memory.json` (git-ignored, personal, never commit it).
- `agent.py`: terminal chat and slash commands. `server.py` + `static/index.html`: FastAPI web app (NDJSON streaming, lock, queue, memory popup, copy). `quiz.py`, `files.py`, `skills/`, `styles/`.
- `tokenizer.py`, `data.py`, `bigram.py`, `gpt.py`: the tiny GPT from the start of the project.
- `EVALS.md`: every eval with numbers and findings. `results/`: saved transcripts.

## Rules we settled on

- **Code decides anything that matters, not the model.** Quiz scoring is in Python. `remember` refuses unless the user's latest message is an explicit save request. `forget` only queues facts; the model asks "are you sure", and code deletes only if the next user message is a yes. Never base a check on the model's own words (the "energy is stored in glucose" bug).
- **Read transcripts before blaming the model or changing the prompt.** Several "model failures" were harness bugs.
- **Rerun the relevant evals after any prompt or tool change**, since adding a tool shifted routing on unrelated messages. Report "model alone" and "with code check" separately.
- **Don't tune prompts to pass a specific test** (no test wording in the prompt). Don't relabel a failing test unless the key was wrong.
- **README and EVALS numbers must be measured.** No claims of fine-tuning or training; models are stock Qwen3.
- Keep personal info out of the repo and screenshots.

## Known state

- Routing and memory evals have not been rerun since memory became "save only when asked" (routing_tests.json now expects `none` for "btw im taking AP Gov" and "im a junior...").
- Multi-turn behavior isn't covered by any eval (all routing tests are single messages).
- `run_python` is not sandboxed. LaTeX math shows raw in the web app. One conversation at a time, no saved chats.
- The 30B MoE beat a dense 32B (same or better scores, ~8x faster), so Ornate stays on the 30B.

## Next up

1. Rerun eval_routing.py and eval_memory.py; update EVALS.md.
2. Web app: sidebar with saved chats, then a design pass (blue accent, LaTeX rendering, drag-and-drop files).
3. New web screenshot for demo.png (no personal info).
4. Then: vision, RAG over class notes, multi-language code runner with a sandbox, fine-tuning with before/after evals, Windows port (RTX 4070, 8 GB VRAM).
