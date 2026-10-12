# Evals

All runs use 4-bit Qwen3 models through `mlx-lm` on a MacBook Pro (Apple M1 Max, 64 GB memory, macOS 26.6.2) with thinking mode off. Each question gets a fresh conversation. The grader reads only the final `ANSWER:` line. Full transcripts are in `results/`.

The models pick the most likely token every time, so the same question always gives the same answer. Rerunning does not add information.

## 1. First eval: 20 calculation questions

`eval_math.py`, Qwen3 8B.

| Setup | Correct |
|---|---|
| No tools | 18/20 |
| Python tool | 19/20 |

Too small to show that the tool helps. It did show that the two setups fail differently:

- Without tools, the model slipped a digit in a long multiplication. On a remainder question it stated a made-up answer while describing work it never did.
- With the tool, it wrote buggy code for a prime-counting question and reported 198 primes below 200 without noticing that was impossible.

The first version of the grader accepted the right number anywhere in the reply. It scored both setups 19/20 and hid the no-tools failures.

## 2. Harder eval: 50 problems, three models

`eval_hard.py` with `problems_hard.json`: word problems, geometry, statistics, probability, number theory. Every answer in the key was computed with code.

| Model | No tools | Python tool | Time for both runs |
|---|---|---|---|
| Qwen3 8B | 44/50 | 49/50 | about 9 min |
| Qwen3 14B | 48/50 | 46/50 | about 17 min |
| Qwen3 30B-A3B | 48/50 | 50/50 | about 9 min |

These use the original one-line tool prompt: "For any calculation, use the run_python tool."

**The tool bug.** Before the fix, the 8B scored 45/50 with the tool in 421s. Three of its five misses ended on a tool call whose last line was a bare variable. The tool ran it as a script and returned no output. Printing a bare last value raised the score to 49/50 and cut the run to 276s.

**The 14B's four tool misses**, all of which it answered correctly without the tool:

| Problem | What its code did |
|---|---|
| Average speed over two 150-mile legs | Divided the full 300 miles by each speed, giving 30 mph |
| Largest of three consecutive odd integers | Returned 676, an even number |
| Arrangements of MISSISSIPPI | Counted M as four letters |
| Rectangle area | Imported `sympy`, which was not installed, and retried the same import |

The 14B run happened before `sympy` was installed, so its tool score is understated by about one. The 14B result file in `results/` was later overwritten by the prompt test below; the 46/50 run is in the git history.

## 3. Does a better tool prompt help?

New prompt: reason through the problem in words first, use code only for the arithmetic, check that the result makes sense, and fix it if not.

On the 50 problems above, the 14B went from 46/50 to 50/50, with the tool run taking 814s compared with 555s. Two things changed at once (the prompt and installing `sympy`), and the prompt was written after reading those exact failures.

### Held-out test

45 new problems the prompt was never tuned against (`problems_holdout.json`), tool runs only.

| Model | Old prompt | New prompt | Extra time |
|---|---|---|---|
| Qwen3 8B | 42/45 | 42/45 | +53% |
| Qwen3 30B-A3B | 44/45 | 45/45 | +50% |

The 8B tied. The new prompt fixed three problems and broke three others, including one where it followed "reason in words first" so literally that it worked 74 steps by hand, never called the tool, and ran out of tokens.

The 30B's old-prompt score was first measured as 43/45. One miss was a harness bug: it computed the right answer on its fifth tool call and was cut off by the round limit. After the loop was changed to give the model a final turn, it scored 44/45.

Conclusion: on new problems the prompt gained at most one question for 50% more time.

### What is left

The remaining mistakes look plausible, so a "does this make sense" check cannot catch them:

- 355 where the answer is 356 (rounded where it should have rounded down)
- The 49th Fibonacci number where the 50th was asked for
- A regression slope of 1.125 where the answer is 0.9 (mixed a sample covariance with a population variance)
- A deposit counted at the start of each month where the problem said the end

## 4. Skills and quizzes

These are judged by reading the output, not by an automatic grader, because "did it name the right mistake" is a judgment call.

### Missed-question skill

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

## Caveats

- 45 to 50 problems per set. A gap of one or two questions is noise.
- Sections 1 to 3 cover only math. Section 4 is hand-graded and small. Nothing here measures coding or reading files yet.
- The tool prompt changed again after these runs, adding "only use the tool when a question needs calculation." The numbers above have not been rerun with that wording.
- The grader requires an `ANSWER:` line. One 8B miss on the held-out set had the correct value but no answer line.
