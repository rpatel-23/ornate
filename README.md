# Ornate

A local AI assistant that runs entirely on a MacBook. It chats, reads files I attach, and runs Python to check its own math. The agent loop and the evals are written from scratch with no agent framework, and the project started with a small GPT built by hand to understand what is inside the model.

Runs on Apple Silicon with [MLX](https://github.com/ml-explore/mlx). No cloud, no API keys.

Built and tested on a MacBook Pro with an Apple M1 Max and 64 GB of memory, macOS 26.6.2. All speeds and timings in this repo come from that machine.

![Ornate reading an attached PDF, then using its Python tool for a calculation](demo.png)

One session: a question answered from an attached PDF, then a calculation it hands to the Python tool.

## What I found

- **Giving a model a calculator can make it worse.** A 14B model scored 48/50 on math problems by reasoning alone and 46/50 with a Python tool. Told to use code for any calculation, it stopped thinking, wrote quick wrong scripts, and reported impossible answers such as a 30 mph average for legs driven at 50 and 75 mph.
- **My tool was quietly broken, and the score hid it.** Models often end code with a bare variable, like a notebook cell. My tool returned nothing for that, and the model retried until it ran out of turns. Fixing it took the 8B from 45/50 to 49/50. I only found it by reading transcripts.
- **A prompt that fixed every failure on one test did not hold up on a new one.** A "reason first, then check your answer" prompt took the 14B from 46/50 to 50/50. On 45 fresh problems it tied on the 8B and gained one question on the 30B, at 50% more time. Most of the gain was the prompt fitting the test it was written for.
- **The biggest model cost nothing in speed.** Qwen3 30B-A3B only runs about 3B of its parameters per token, so it matched the 8B's speed and scored higher on every test.

Full numbers and caveats are in [EVALS.md](EVALS.md).

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
| Memory | | Next |
| Fine-tuning with before/after evals | | Planned |
| Desktop app | | Planned |

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

A skill is a Markdown file of instructions in `skills/`. The system prompt lists each skill with one line describing when to use it. When a message matches, the model calls a `load_skill` tool, the harness hands back the full file, and the model follows it. After the answer, the harness removes the skill text from the conversation, so it does not leak into later, unrelated messages.

The first one, `missed-question`, explains a practice question I got wrong in a fixed format: correct answer, my answer, the skill tested, the method, the exact slip, a miss type, a rule to remember, and a Desmos check. The format comes from how I already review SAT practice.

Getting it to name the slip took four tries on one test problem ($40 shirt, 25% off, then 10% tax, wrong answer $26):

| Version | What it said the slip was |
|---|---|
| First draft | "You may have calculated the discount incorrectly or skipped the tax" |
| Told to test wrong methods in code | A path that gives $27 |
| Told to write out the wrong calculation | A path that gives $34, published anyway |
| Same skill with thinking mode on | Adding 25% and 10% and taking 35% off: $40 - $14 = $26 |

Two things caused the early failures. The skill told the model to run tests first and also to output nothing but the final block, so it skipped the tests. And working backward from a wrong answer needs room to try ideas and throw them out, which the model only had with thinking on.

That was one problem run several times, so I tested the skill on 9 new missed questions, each with a wrong answer that comes from a known mistake (`eval_skill.py`, `problems_slips.json`). There is no automatic grader for "did it name the right mistake," so each answer was read and judged by hand.

| Thinking | Found the slip |
|---|---|
| Off | 6 of 9, plus 1 partial |
| On | 8 of 9, plus 1 that named a different mistake that also produces the wrong answer |

Thinking mode fixed both clear misses and broke none of the ones that already worked. With it off, the model would describe a mistake that leads to a different number than the one I put (a path to 67 for an answer of 28) and not notice.

Two flaws this test showed in my own work: one problem had two different mistakes that give the same wrong answer, so it could not tell them apart, and my script hid a correct answer because the model never closed its thinking tag.

Nine problems, graded by reading, is enough to turn thinking on for this skill and not enough to quote a percentage.

### Quizzes: the model writes, code keeps score

The first quiz skill asked the model to run the whole quiz itself. It showed all the questions at once, skipped feedback, and reported 1 of 3 correct when the answer was 0. Keeping score and taking turns is bookkeeping, and code does that perfectly while models do not.

So `quiz.py` asks the model once for the questions as JSON (question, correct answer, three wrong answers, explanation, the tempting trap), then plain Python runs the quiz: one question at a time, shuffled choices, a running score, and a list of what was missed. The model can start a quiz on its own through a `start_quiz` tool, and the results are added to the chat so follow-up questions work.

### Picking skills automatically

On a first check, a missed-question message went straight to the Python tool and skipped the skill. Moving the skill check to the front of the system prompt fixed that. A second problem was that a loaded skill stayed in the conversation, so a later plain question ("what does photosynthesis produce?") came back in the missed-question format. Removing skill text after each answer fixed that.

On four fresh messages in one chat (a missed fraction problem, a plain question, a quiz request, a plain question), the model chose correctly every time. That is a spot check, not a test; a routing test with marked answers is next. Style instructions such as "no emojis, no sign-offs" are still followed only loosely.

## Limits

- The evals are small (45 to 50 problems) and only cover math. Gaps of one or two questions are not meaningful.
- The missed-question skill has been checked on 9 hand-graded problems, and automatic skill picking only on a handful of messages.
- An 8B to 30B local model is well below frontier models, especially on long multi-step tasks.
- Nothing is fine-tuned yet. The models are stock Qwen3 weights from [mlx-community](https://huggingface.co/mlx-community).

## Notes

Built as a learning project, using Claude as a tutor to explain concepts, write parts of the code, and review mine.
