# Evals

All runs use 4-bit Qwen3 models through `mlx-lm` on an M1 MacBook Pro with thinking mode off. Each question gets a fresh conversation. The grader reads only the final `ANSWER:` line. Full transcripts are in `results/`.

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

## Caveats

- 45 to 50 problems per set. A gap of one or two questions is noise.
- Only math. Nothing here measures explanation quality, coding, or reading files.
- The tool prompt changed again after these runs, adding "only use the tool when a question needs calculation." The numbers above have not been rerun with that wording.
- The grader requires an `ANSWER:` line. One 8B miss on the held-out set had the correct value but no answer line.
