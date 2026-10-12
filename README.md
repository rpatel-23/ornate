# Ornate

A local study assistant that runs entirely on a MacBook. It explains practice questions I got wrong in the format I review with, quizzes me, reads files I attach, and runs Python to check its own math. The agent loop, skills, and evals are written from scratch with no agent framework, and the project started with a small GPT built by hand to understand what is inside the model.

Runs on Apple Silicon with [MLX](https://github.com/ml-explore/mlx). No cloud, no API keys.

Built and tested on a MacBook Pro with an Apple M1 Max and 64 GB of memory, macOS 26.6.2. All speeds and timings in this repo come from that machine.

![Ornate reading an attached PDF, then using its Python tool for a calculation](demo.png)

One session: a question answered from an attached PDF, then a calculation it hands to the Python tool.

## What I found

- **Giving a model a calculator can make it worse.** A 14B model scored 48/50 on math problems by reasoning alone and 46/50 with a Python tool. Told to use code for any calculation, it stopped thinking, wrote quick wrong scripts, and reported impossible answers such as a 30 mph average for legs driven at 50 and 75 mph.
- **My tool was quietly broken, and the score hid it.** Models often end code with a bare variable, like a notebook cell. My tool returned nothing for that, and the model retried until it ran out of turns. Fixing it took the 8B from 45/50 to 49/50. I only found it by reading transcripts.
- **A prompt that fixed every failure on one test did not hold up on a new one.** A "reason first, then check your answer" prompt took the 14B from 46/50 to 50/50. On 45 fresh problems it tied on the 8B and gained one question on the 30B, at 50% more time. Most of the gain was the prompt fitting the test it was written for.
- **Thinking mode, not better instructions, let it find my mistakes.** Three rewrites of the instructions could not get the model to work out how I reached a wrong answer. Turning on its reasoning mode could: it named the right mistake on 8 of 9 new problems, against 6 of 9 without it.
- **Some jobs belong in code, not the model.** Asked to run a quiz itself, the model showed every question at once and reported a score of 1 of 3 when I had 0. Moving turn-taking and scoring into Python fixed it completely.
- **The biggest model cost nothing in speed.** Qwen3 30B-A3B only runs about 3B of its parameters per token, so it matched the 8B's speed and scored higher on every test.

Full numbers, transcripts, and caveats are in [EVALS.md](EVALS.md).

## What is built

| Part | Files | Status |
|---|---|---|
| Tiny GPT from scratch | `tokenizer.py`, `data.py`, `bigram.py`, `gpt.py` | Done |
| Local chat with streaming | `chat.py` | Done |
| Agent loop with a Python tool | `harness.py`, `agent.py` | Done |
| File attachments (text and PDF) | `files.py` | Done |
| Math evals with saved transcripts | `eval_math.py`, `eval_hard.py`, `results/` | Done |
| Skills, picked automatically | `skills/`, `agent.py` | Done (two skills) |
| Quizzes run by code | `quiz.py` | Done |
| Optional thinking mode | `harness.py` | Done |
| Skill eval (missed questions, hand-graded) | `eval_skill.py`, `problems_slips.json` | Done |
| Routing test for skill picking | | Next |
| Web search tool | | Next |
| Web app, then desktop app | | Planned |
| Search over class notes (RAG) | | Planned |
| Memory across chats | | Planned |
| Reading photos of worksheets | | Planned |
| Fine-tuning with before/after evals | | Planned |

## Run it

Requires a Mac with Apple Silicon.

```
git clone https://github.com/rpatel-23/ornate.git
cd ornate
python3 -m venv .venv && source .venv/bin/activate
pip install mlx mlx-lm numpy sympy pypdf
python agent.py
```

The first run downloads Qwen3 30B-A3B (17 GB, needs about 17 GB of memory). For a smaller machine, use the 5 GB model:

```
ORNATE_MODEL=mlx-community/Qwen3-8B-4bit python agent.py
```

In the chat:

| Command | What it does |
|---|---|
| `/file <path>` | Attaches a text file or PDF to your next message |
| `/quiz <topic>` or `/quiz 3 <topic>` | Runs a quiz, using any attached file as the material |
| `q` | Quits |

To let the model reason before it answers, start it with `ORNATE_THINK=1 python agent.py`. It is slower, and the reasoning is hidden behind a `(thinking)` marker.

Other entry points:

```
python gpt.py          # train the tiny GPT (a few minutes)
python eval_hard.py    # run the 50-problem math eval
```

## How it works

### Agent loop

A language model can only produce text. To let it run code, `harness.py` describes a `run_python` tool in the prompt. When the model replies with a tool call, the harness runs the code in a separate process, adds the output to the conversation, and asks the model again. This repeats for up to five rounds, then the model gets one final turn to answer.

The tool prints a bare last value the way a notebook does. It runs model-written code directly on the machine with a 10-second timeout and is not sandboxed yet.

### File attachments

`files.py` reads plain text directly and extracts text from PDFs with `pypdf`. The text is added to the user's message, so to the model an attachment is just more text. Files over 30,000 characters are cut off with a note. Scanned PDFs and images are not supported yet.

### Tiny GPT

A character-level transformer trained on the complete works of Shakespeare (about 1.1M characters), written to understand each part of a language model.

| Model | Parameters | Train loss | Val loss |
|---|---|---|---|
| Random guessing | n/a | 4.17 | 4.17 |
| Bigram | 4,225 | ~2.4 | not measured |
| Tiny GPT | 816,705 | ~1.45 | 1.62 |

Settings: 4 layers, 4 heads, 128-dim embeddings, 64-character context, 5,000 steps, batch size 32, AdamW at 1e-3. The bigram and the GPT share the same data and training loop. The only difference is attention.

Sample from the tiny GPT after a few minutes of training:

```
Nurse:
Why so-heart, I merry age greelized: yet you common me
too this death.
```

### Skills

A skill is a Markdown file of instructions in `skills/`. The system prompt lists each skill with one line saying when to use it. When a message matches, the model calls a `load_skill` tool, the harness returns the full file, and the model follows it. After the answer, the harness removes the skill text from the conversation so it does not leak into later, unrelated messages.

`missed-question` explains a practice question I got wrong: correct answer, my answer, the skill tested, the method, the exact slip with the wrong calculation written out, a miss type, a rule to remember, and a Desmos check. The format comes from how I already review SAT practice. It works best with thinking mode on.

### Quizzes

`quiz.py` asks the model once for questions as JSON (question, correct answer, three wrong answers, explanation, and the tempting trap). Plain Python then runs the quiz: one question at a time, shuffled choices, a running score, and a list of what was missed. The model can start a quiz on its own through a `start_quiz` tool, and the results go back into the chat so follow-up questions work.

How each of these was debugged and tested is in [EVALS.md](EVALS.md#4-skills-and-quizzes).

## Limits

- The evals are small (45 to 50 problems) and only cover math. Gaps of one or two questions are not meaningful.
- The missed-question skill has been checked on 9 hand-graded problems, and automatic skill picking only on a handful of messages.
- An 8B to 30B local model is well below frontier models, especially on long multi-step tasks.
- Nothing is fine-tuned yet. The models are stock Qwen3 weights from [mlx-community](https://huggingface.co/mlx-community).

## Notes

Built as a learning project, using Claude as a tutor to explain concepts, write parts of the code, and review mine.
