# Ornate

A local AI agent that runs entirely on a MacBook. It chats, runs Python to check its math, searches the web when it needs current information, reads files I attach, remembers facts about me across chats, and loads skills on its own for specific jobs, such as working out exactly how I got a practice question wrong or running an interactive quiz. The agent loop, skills, and evals are written from scratch with no agent framework, and the project started with a small GPT built by hand to understand what is inside the model.

Runs on Apple Silicon with [MLX](https://github.com/ml-explore/mlx). Everything runs offline except the optional web search, and nothing needs an API key.

Built and tested on a MacBook Pro with an Apple M1 Max and 64 GB of memory, macOS 26.6.2. All speeds and timings in this repo come from that machine.

![Ornate loading its missed-question skill, thinking, and naming the exact mistake behind a wrong answer of $26](demo.png)

I put $26 on a discount-and-tax problem. Ornate picks the missed-question skill on its own, turns on thinking, and finds the exact mistake: both percentages taken off the original price, $40 - $10 - $4 = $26.

## What I found

- **Giving a model a calculator can make it worse.** A 14B model scored 48/50 on math problems by reasoning alone and 46/50 with a Python tool. Told to use code for any calculation, it stopped thinking, wrote quick wrong scripts, and reported impossible answers such as a 30 mph average for legs driven at 50 and 75 mph.
- **My tool was quietly broken, and the score hid it.** Models often end code with a bare variable, like a notebook cell. My tool returned nothing for that, and the model retried until it ran out of turns. Fixing it took the 8B from 45/50 to 49/50. I only found it by reading transcripts.
- **A prompt that fixed every failure on one test did not hold up on a new one.** A "reason first, then check your answer" prompt took the 14B from 46/50 to 50/50. On 45 fresh problems it gained at most one question, at 50% more time. Most of the gain came from fitting the prompt to the test it was written for.
- **Thinking helps hard work and hurts quick decisions.** With its reasoning mode on, the model found how I reached a wrong answer on 8 of 9 new problems, against 6 of 9 without it. But it picked the right tool slightly less often (17/18 against 18/18) and took three times as long. So Ornate decides with thinking off and turns it on only after it loads a skill or runs a search.
- **Search found the right answer, and the model ignored it.** Asked who won the most recent Super Bowl, the correct result was in the search results, and the model still answered with an older game and the wrong winner. Adding today's date to the prompt and thinking after the search fixed it: the model wrote a better query and, on a later question, noticed and explained conflicting results.
- **Some jobs belong in code, not the model.** Asked to run a quiz itself, the model showed every question at once and reported a score of 1 of 3 when I had 0. Moving turn-taking and scoring into Python fixed it completely.

Full numbers, transcripts, and caveats are in [EVALS.md](EVALS.md).

## What is built

| Part | Files | Status |
|---|---|---|
| Tiny GPT from scratch | `tokenizer.py`, `data.py`, `bigram.py`, `gpt.py` | Done |
| Agent loop with tools | `harness.py`, `assistant.py`, `agent.py` | Done |
| Python tool for math | `harness.py` | Done |
| File attachments (text and PDF) | `files.py` | Done |
| Skills, picked automatically | `skills/`, `assistant.py` | Done (two skills) |
| Quizzes run by code | `quiz.py` | Done |
| Web search | `assistant.py` | Done |
| Adaptive thinking | `harness.py` | Done |
| Math evals | `eval_math.py`, `eval_hard.py` | Done |
| Skill and routing tests | `eval_skill.py`, `eval_routing.py` | Done |
| Personality styles | `styles/`, `agent.py` | Done (plain and roast) |
| Memory across chats | `memory.py`, `assistant.py` | Done |
| Web app, then desktop app | | Planned |
| Search over class notes (RAG) | | Planned |
| Reading photos of worksheets | | Planned |
| Fine-tuning with before/after evals | | Planned |

## Run it

Requires a Mac with Apple Silicon.

```
git clone https://github.com/rpatel-23/ornate.git
cd ornate
python3 -m venv .venv && source .venv/bin/activate
pip install mlx mlx-lm numpy sympy pypdf ddgs
python agent.py
```

The first run downloads Qwen3 30B-A3B (17 GB, needs about 17 GB of memory). It only runs about 3B of its parameters for each token, so it is as fast as an 8B model and scored higher on every test here. For a smaller machine, use the 5 GB model:

```
ORNATE_MODEL=mlx-community/Qwen3-8B-4bit python agent.py
```

Just type normally. Ornate decides on its own whether to explain a missed question, start a quiz, run Python, search the web, save or delete a memory, or answer directly. A few commands are also available:

| Command | What it does |
|---|---|
| `/file <path>` | Attaches a text file or PDF to your next message |
| `/quiz <topic>` or `/quiz 3 <topic>` | Runs a quiz, using any attached file as the material |
| `/style roast`, `/style plain`, `/style` | Switches personality for the rest of the chat, or lists the styles |
| `/memory` | Lists what Ornate remembers about you |
| `/forget <number>` | Deletes a memory by its number in `/memory` |
| `q` | Quits |

Thinking is automatic by default. `ORNATE_THINK=1` keeps it on for every answer, and `ORNATE_THINK=0` turns it off.

Tests:

```
python eval_routing.py   # does it pick the right first move? (22 messages, about 1 minute)
python eval_hard.py      # 50 math problems, with and without the Python tool
python eval_skill.py     # 9 missed questions, graded by reading the output
python gpt.py            # train the tiny GPT (a few minutes)
```

## How it works

**Agent loop.** A language model can only produce text. `harness.py` describes the available tools in the prompt. When the model replies with a tool call, the harness runs it, adds the result to the conversation, and asks again, for up to five rounds, then gives the model one final turn to answer. Tools are registered with `add_tool`, so adding one is a single function.

**Tools.** `run_python` runs model-written code in a separate process with a 10-second timeout (not sandboxed yet) and prints a bare last value the way a notebook does. `web_search` returns five results from DuckDuckGo, labeled as website text so the model treats them as information and not as instructions. `load_skill` and `start_quiz` are described below.

**Skills.** A skill is a Markdown file of instructions in `skills/`. The system prompt lists each skill with one line saying when to use it. When a message matches, the model calls `load_skill`, gets the full file, and follows it. After the answer, the harness removes the skill text from the conversation so it does not leak into later messages. `missed-question` gives the correct answer, my answer, the skill tested, the method, the exact slip with the wrong calculation written out, a miss type, a rule to remember, and a Desmos check. The format comes from how I already review SAT practice.

**Quizzes.** `quiz.py` asks the model once for questions as JSON: the question, the correct answer, three wrong answers, an explanation, and the most tempting trap. Plain Python then runs the quiz one question at a time with shuffled choices, a running score, and a list of what was missed. The results go back into the chat so follow-up questions work.

**Adaptive thinking.** Each answer starts with thinking off, so choosing what to do stays fast. If the model loads a skill or searches the web, thinking turns on for the rest of that answer. Today's date is in the system prompt so "most recent" means something.

**Styles.** A style is a Markdown file in `styles/` added to the end of the system prompt, and unlike a skill it stays on for the whole chat. `plain` is the default: concise, no emojis, no sign-offs. `roast` is a teasing, deadpan tutor voice with rules for reading the room: match the user's energy, drop the jokes when they sound stressed, and keep every fact and skill format exactly as in plain style. Telling it to "chill" or "relax" switches back to plain in code, because the model kept joking one message after agreeing to stop.

**File attachments.** `files.py` reads plain text and extracts text from PDFs with `pypdf`. The text is added to the message, so to the model an attachment is just more text. Files over 30,000 characters are cut off with a note.

**Tiny GPT.** A character-level transformer trained on the complete works of Shakespeare (about 1.1M characters), written to understand each part of a language model.

| Model | Parameters | Train loss | Val loss |
|---|---|---|---|
| Random guessing | n/a | 4.17 | 4.17 |
| Bigram | 4,225 | ~2.4 | not measured |
| Tiny GPT | 816,705 | ~1.45 | 1.62 |

Settings: 4 layers, 4 heads, 128-dim embeddings, 64-character context, 5,000 steps, batch size 32, AdamW at 1e-3. The bigram and the GPT share the same data and training loop. The only difference is attention.

## Limits

- The math evals have 45 to 50 problems, the skill test 9, and the routing test 22, and I wrote the tests as well as the prompts. Gaps of one or two are not meaningful.
- Style instructions are followed only loosely. The model still adds emojis and sign-offs in plain style, and in roast style it tends to copy its example jokes rather than write new ones.
- Search depends on an unofficial package, needs internet, and only sees short snippets. A small model can still misread them.
- An 8B to 30B local model is well below frontier models, especially on long multi-step tasks.
- Memories are saved to `memory.json` on your machine, which is git-ignored so personal facts never reach GitHub. Ornate sometimes misses a fact mentioned in passing alongside a question, so saying "remember" is the reliable way.
- Nothing is fine-tuned yet. The models are stock Qwen3 weights from [mlx-community](https://huggingface.co/mlx-community).

## Notes

Built as a learning project, using Claude as a tutor to explain concepts, write parts of the code, and review mine.
