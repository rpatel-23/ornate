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

## 5. Routing and web search

### Routing test

`eval_routing.py` sends each message in `routing_tests.json` once and checks only the model's first move: load a skill, start a quiz, run Python, search, or answer directly. No tools are run, so it takes about a minute. Some messages are traps, such as "I put my phone in rice after it got wet" (contains "I put", the phrase the prompt names as a missed-question signal) and "I got a 1410 on the SAT, is that good?"

| Setup | Correct first move | Time |
|---|---|---|
| 18 messages, thinking off | 18/18 | 36s |
| 18 messages, thinking on | 17/18 | 110s |
| 22 messages with web search added, thinking off | 21/22, then 22/22 after fixing the key | 52s |

With thinking on, the one miss was a tip question. Its reasoning worked out the student's mistake correctly, then decided to verify the arithmetic with Python and never loaded the skill.

After web search was added, "is a 1410 a good SAT score?" triggered a search where the key said to answer directly. Looking up current percentiles is reasonable, so the key now accepts either. When a test fails, the answer key is one of the things to check.

### Web search

Question: who won the most recent Super Bowl? (Super Bowl LX, February 2026: Seahawks 29, Patriots 13.)

| Setup | Query it wrote | Answer |
|---|---|---|
| No date in prompt, thinking off | "who won the most recent superbowl" | Chiefs won Super Bowl LIX (wrong game and wrong winner) |
| Date in prompt, told to prefer the newest result, thinking off | same | Same wrong answer, with the correct result shown fifth in its own search results |
| Date in prompt, thinking on | "who won the most recent Super Bowl in 2026" | Correct |

The wrong answer came from a cut-off snippet describing the Chiefs as the "two-time defending champion" going into Super Bowl LIX. With thinking on, the model used the date in its query, so most results were about the right game. Both the query and the reading changed at once, so this does not show how much each one mattered.

On a later question (most recent NBA champion), with adaptive thinking, the results included both the 2025 and 2026 Finals. The model answered with 2026 and pointed out the conflict. Both are single questions, not a test.

## 6. Memory

Ornate saves facts about the user to `memory.json` (git-ignored) with a `remember` tool and deletes them with a `forget` tool. Saved facts go into the system prompt at the start of every turn. `/memory` and `/forget` let the user check and delete facts directly.

### Routing with memory tools

`eval_routing.py` grew from 22 to 30 messages: 4 where the user mentions a lasting fact, 3 where they ask to save something ("rmbr that...", "dont forget..."), a one-time fact that should not be saved (a test tomorrow), and a trap where "remember" is not a save request ("i cant remember the quadratic formula").

| Run | Score |
|---|---|
| First run with `remember` | 26/30 |
| After fixing the tool call parser | 29/30 |
| After adding `forget` and a "don't claim a save" prompt rule | 27/30 |
| Same, plus a code check for fake saves | model alone 27/30, with check 28/30 |

All 22 original messages kept passing until the last two runs, when "can you quickly explain standard deviation" flipped from answering to running Python. The model's output is deterministic, so adding a tool to the prompt was enough to change its behavior on an unrelated message.

What the transcripts showed:

- **Correct calls scored as misses.** Two "fails" were the model calling `remember` correctly but without the `<tool_call>` tags. The harness did not see a tool call, so nothing was saved and the eval scored "none". The fix was in the parser (`find_tool_call`), which now also accepts a bare tool name followed by JSON, but only when that is the whole reply and the name is a real tool. Same lesson as the 45 to 49 bug: read the transcript before changing the prompt.
- **Claiming a save without making one.** After the tool changed shape, "btw im taking AP Gov this year" got the reply "remembered." with no tool call. A prompt rule against this changed nothing. A code check now catches replies that say saved/remembered/noted with no `remember` call in that turn and gives the model one retry. The eval reports both scores, so the check does not hide what the model does on its own.
- **Several facts in one.** Told "one fact per call", the model still saved "Takes AP Stats and AP Pre Calc, likes short answers" as one fact, so deleting one deleted all three. Changing the tool's input from one string to a list of strings fixed it.
- **Still missed:** a fact mentioned alongside a question ("im a junior and want to major in CS. what classes should i take?"). Asking explicitly to remember is reliable; mentioning something in passing is not.

### Forgetting

`eval_memory.py` gives the model a fake memory list in a temp file, so the real `memory.json` is never touched. A forget passes only if the model sends exactly the right facts.

Result: 9/10. All 5 real forgets sent the right facts, including two at once. "dont forget...", "i forgot my calculator", and questions about saved facts did not trigger a delete.

The miss: "forget that i play basketball", with nothing about basketball saved, deleted "Plays soccer." instead.

How deleting changed:

1. **By number.** Facts were numbered in the prompt and the model deleted by number. In a live test, "forget that i take ap stats" deleted AP Precalc. The model counted from a list it had written earlier in the chat, not the current one.
2. **By exact text.** The code deletes only on an exact match, and a miss deletes nothing and returns the real list. This fixed the stale numbers but not the basketball case, because "Plays soccer." really is saved. Code can check that a fact exists, not that it is the one the user meant.
3. **Confirm in code.** The `forget` tool now shows the facts and asks the user y/n before deleting. The model cannot skip it. The eval still counts the basketball case as a fail, because it measures the model, and the model is still wrong.

### Later changes to memory

Using Ornate in the web app turned up a bug the evals missed. "Explain photosynthesis in detail" came back as "Already saved." The fake-save check scanned the model's answer for words like "stored", found "energy is stored in glucose", and told the model to call `remember`. Every memory test used memory-related messages, so nothing tested an ordinary answer that happens to contain those words.

After that, memory changes are decided only by the user's message:

- `remember` refuses unless the latest message is an explicit request ("rmbr", "save this", "don't forget"). Ornate no longer saves facts mentioned in passing, so "btw im taking AP Gov" and "im a junior..." now expect no tool in the routing test.
- `forget` holds the facts and the model asks "are you sure?". Code deletes them only if the next message is a yes. This replaced the y/n prompt, which had stopped working in the web app because it waited for input in the server's terminal.
- `test_checks.py` runs these checks without the model: 11 messages for "is this a save request" and 6 answers for "does this claim a save", including the photosynthesis sentence.

The routing and memory evals have not been rerun since these changes.

## 7. A bigger model: 32B dense vs 30B MoE

Qwen3-30B-A3B is a mixture-of-experts model: 30B parameters in total, but only about 3B run for each token. Qwen3-32B is dense, so all 32B run for every token. Same 4-bit size on disk (about 17 to 18 GB), same prompts, same evals; only the model changed.

| | 30B-A3B (MoE) | 32B (dense) |
|---|---|---|
| Memory test | 9/10 in 30s | 7/10 in 238s |
| Routing, model alone | 27/30 in 97s | 27/30 in 749s |
| Routing, with fake-save check | 28/30 | 27/30 |

The dense model was about 8 times slower and no more accurate.

Where they differed:

- **Better on two things.** The 32B actually called `remember` for "btw im taking AP Gov this year" instead of replying "remembered." with no save, and it answered "quickly explain standard deviation" without running Python.
- **Worse on skills.** It missed two missed-question messages that the 30B passed on every run: it ran Python for "I put 81 for 3 to the power of 3" and answered the free speech question directly without loading the skill.
- **Worse deletes.** Asked to delete "everything about my classes", it also deleted every other saved fact. Asked "dont forget my SAT is on December 5", it saved the date and then deleted it. Both were scored as bad tool calls because it put two calls in one block, but reading both calls would have been worse.
- **Same mistakes.** Both models deleted "Plays soccer." when asked to forget basketball, and both missed the fact mentioned alongside a question ("im a junior and want to major in CS..."). Since a bigger model made the same mistakes, these look like design problems, which supports handling them in code (the y/n confirm on deletes) rather than waiting for a smarter model.

Ornate keeps the 30B-A3B: same or better accuracy, at a speed that works for chat.

## Caveats

- 45 to 50 problems per set. A gap of one or two questions is noise.
- Sections 1 to 3 cover only math. Section 4 is hand-graded and small. The routing test is 30 messages, the memory test 10, and the search results are single questions. Nothing here measures coding or reading files yet.
- The tool prompt changed again after these runs, adding "only use the tool when a question needs calculation." The numbers above have not been rerun with that wording.
- The grader requires an `ANSWER:` line. One 8B miss on the held-out set had the correct value but no answer line.
