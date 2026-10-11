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

An earlier version of the grader accepted the right number anywhere in the reply and scored both setups 19/20, hiding the no-tools failures. Next step is a larger, harder problem set with saved transcripts.

## Run it

```
git clone https://github.com/rpatel-23/ornate.git
cd ornate
python3 -m venv .venv && source .venv/bin/activate
pip install mlx mlx-lm numpy
python gpt.py
```

Requires a Mac with Apple Silicon.

## Notes

Built as a learning project, using Claude as a tutor to explain concepts and review code.
