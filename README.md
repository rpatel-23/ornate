# Ornate

A local-first AI assistant built from scratch on Apple Silicon. The project goes layer by layer: a tiny GPT written by hand, then a fine-tuned open model with measured results, then a custom agent harness with tools and memory.

Everything runs on a single MacBook using [MLX](https://github.com/ml-explore/mlx).

## Roadmap

- [x] Tiny GPT from scratch
- [x] Run a real open model locally
- [ ] LoRA fine-tune with before/after evals
- [ ] Agent harness (tools, memory, agent loop)
- [ ] UI and release

## Tiny GPT from scratch

A character-level transformer trained on the complete works of Shakespeare (about 1.1M characters, 65 unique characters). The goal was to understand every part of a language model by writing it myself.

### Files

| File | What it does |
|---|---|
| `tokenizer.py` | Maps each character to a number and back |
| `data.py` | Splits the text 90/10 into train/validation and serves random batches of (input, next-character) pairs |
| `bigram.py` | Baseline model that predicts the next character from only the previous one |
| `gpt.py` | Transformer with multi-head self-attention, position embeddings, and 4 stacked blocks |

### Results

| Model | Parameters | Train loss | Val loss |
|---|---|---|---|
| Random guessing | n/a | 4.17 | 4.17 |
| Bigram | 4,225 | ~2.4 | not measured |
| Tiny GPT | 816,705 | ~1.45 | 1.62 |

GPT settings: 4 layers, 4 heads, 128-dim embeddings, 64-character context, 5,000 steps, batch size 32, AdamW at 1e-3. Training takes a few minutes on an M1 MacBook Pro.

The bigram and the GPT use the same data and the same training loop. The only difference is attention, which lets each character look back at the ones before it.

### Sample output

Bigram, after training:

```
I he'l ngho oforienstheve no keeed.
RAnt---wit,
UKICEDULof-dity's brdunghosther ctert. m, o we owofravertog mierut;
```

Tiny GPT, after training:

```
Nirset:
First I saw, thou love itself to which countain,
Hath may frevinent off drown asked only,
And said weeping to my deserves to whundst have been.

Nurse:
Why so-heart, I merry age greelized: yet you common me
too this death.
```

## Local chat

`chat.py` is a terminal chat loop around Qwen3 8B (4-bit) running through `mlx-lm`. It keeps the conversation history, applies the model's chat template, and streams the reply as it is generated.

On an M1 MacBook Pro it runs at about 50 tokens per second and peaks under 5 GB of memory.

```
python chat.py
```

The first run downloads the model (about 5 GB).

## Agent with a Python tool

`harness.py` holds the agent loop. The model is told a `run_python` tool exists. When it replies with a tool call, the harness runs the code in a separate process, sends the output back, and lets the model continue, for up to five rounds per question. `agent.py` is the chat version.

```
python agent.py
```

The tool runs model-written code directly on the machine with a 10-second timeout. It is not sandboxed yet.

### First math eval

`eval_math.py` asks 20 calculation questions twice, once with no tools and once with the Python tool, and grades only the final `ANSWER:` line.

| Setup | Correct |
|---|---|
| No tools | 18/20 |
| Python tool | 19/20 |

A one-question gap on 20 questions is too small to mean anything, so this does not show that the tool improves accuracy. What it does show is that the two setups fail differently:

- Without tools, the model slipped a digit in a long multiplication, and on a remainder question it stated a made-up answer while describing work it never did.
- With the tool, both of those were fixed, but it wrote buggy code for a prime-counting question and reported the wrong output (198 primes below 200) without noticing it was impossible.

An earlier version of the grader accepted the right number anywhere in the reply and scored both setups 19/20, hiding the no-tools failures.

### Harder eval and model comparison

`eval_hard.py` runs 50 harder problems from `problems_hard.json` (word problems, geometry, statistics, probability, number theory). Every answer in the key was computed with code. Full transcripts are saved in `results/`.

| Model (4-bit) | No tools | Python tool | Time for both runs |
|---|---|---|---|
| Qwen3 8B | 44/50 | 49/50 | about 9 min |
| Qwen3 14B | 48/50 | 46/50 | about 17 min |
| Qwen3 30B-A3B | 48/50 | 50/50 | about 9 min |

What the transcripts showed:

- **The tool was broken for one coding style.** Models often end their code with a bare variable, like a notebook cell. The tool ran it as a script, returned nothing, and the model retried until it ran out of rounds. Making the tool print a bare last value took the 8B from 45/50 to 49/50 and cut the run from 421s to 276s.
- **A tool can make a stronger model worse.** The 14B scored lower with the tool than without it. Told to use Python for any calculation, it stopped reasoning, wrote quick wrong code, and reported impossible results (a 30 mph average for legs driven at 50 and 75 mph, an even number as an "odd integer").
- **Bigger helps reasoning, not arithmetic.** The 14B and 30B still slip on long calculations by hand. The tool fixes those.
- The 30B-A3B only activates about 3B of its parameters per token, so it runs as fast as the 8B. It is the model I use on the Mac.

The 14B was run before `sympy` was installed and one of its four tool misses was that missing import, so its tool score is slightly understated.

### Does a better tool prompt help? Held-out test

I replaced the one-line tool prompt with one that tells the model to reason in words first, use code only for the arithmetic, and check that the result makes sense. On the 50 problems above, the 14B went from 46/50 to 50/50.

That prompt was written after reading those exact failures, so I tested it on 45 new problems it had never been tuned against (`problems_holdout.json`), tool runs only:

| Model | Old prompt | New prompt | Extra time |
|---|---|---|---|
| Qwen3 8B | 42/45 | 42/45 | +53% |
| Qwen3 30B-A3B | 43/45 | 45/45 | +50% |

On new problems the prompt did not clearly help. The 8B tied, fixing three problems and breaking three others. The 30B gained two, but one of those was a harness bug and not the prompt: with the old prompt it computed the right answer on its fifth tool call and was cut off by the round limit before it could reply. After I fixed the loop to give the model one last turn to answer, the old prompt scored 44/45, so the prompt's real gain on the 30B is one question. Most of the earlier gain came from fitting the prompt to the test.

The remaining mistakes are off-by-one errors and formula mix-ups (355 instead of 356, the 49th Fibonacci number instead of the 50th) that look plausible, so a "does this make sense" check cannot catch them.

Limits of all of this: the problem sets are small (45 to 50 questions), each model gives the same answer every run, and gaps of one or two questions are not meaningful.

## Run it

```
git clone https://github.com/rpatel-23/ornate.git
cd ornate
python3 -m venv .venv && source .venv/bin/activate
pip install mlx mlx-lm numpy sympy
python gpt.py
```

Requires a Mac with Apple Silicon.

## Notes

Built as a learning project, using Claude as a tutor to explain concepts and review code.
