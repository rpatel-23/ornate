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

### Rerun after "save only when asked"

Both evals were rerun on the 30B-A3B with thinking off after these changes.

| Eval | Before | After |
|---|---|---|
| Routing, model alone | 27/30 | 30/30 in 99s |
| Routing, with fake-save check | 28/30 | 30/30 |
| Memory | 9/10 | 8/10 in 31s |

Routing: the code check caught nothing, because the model got everything right on its own. Part of the gain comes from the key, not the model: "btw im taking AP Gov" and "im a junior..." now expect no tool, and the model never saved those anyway. "Quickly explain standard deviation" went back to answering directly.

The routing eval checks only the model's first move and does not run tools. So a `remember` call on a message that is not a save request would still count as a fail here, even though the code would refuse it.

Memory: the basketball miss is unchanged (it still sends "Plays soccer."). The new miss is worse. "What do you know about me?" called `forget` with all five saved facts. In the app, that only queues the facts, and nothing is deleted unless the next message is a yes. But the model would ask "are you sure you want me to forget everything?" in reply to a harmless question. The forget instructions in the prompt changed between runs (confirm in chat instead of y/n), which is likely what moved it, the same way adding a tool moved the standard deviation message.

### Fixing "what do you know about me?"

It was not one message. Three more ways of asking were tried against several versions of the prompt. Each version below changes one thing from the current prompt. Each cell counts how many of the 4 questions called `forget` on every saved fact:

| Prompt | Calls forget |
|---|---|
| Current prompt | 4 of 4 |
| Forget rule from before the web app | 2 of 4 |
| Current prompt, earlier date | 3 of 4 |
| Memory list titled "Saved facts" instead of "What you know about the user" | 1 of 4 |
| Forget rule removed | 0 of 4 |

So the earlier 9/10 was partly luck: the old prompt also failed "what do you remember about me?", which the test did not include. Even the date at the top of the prompt changes the result, so rewording the prompt cannot be relied on. The forget rule ("If the user asks you to forget or delete something you know about them...") reads a lot like the question.

Two fixes:

1. **Code check.** `forget` now refuses unless the user's message says forget, delete, remove, erase, clear, or wipe, not counting "don't forget". It queues nothing and tells the model to answer normally. `test_checks.py` covers it with 10 messages.
2. **Prompt.** The forget rule was removed. The tool's own description and its replies already explain how to delete and confirm.

The three new questions were added to `memory_tests.json`. They were found while debugging this bug, so they are not a held-out test.

| Eval | Model alone | With code check |
|---|---|---|
| Memory (13 messages) | 12/13 | 12/13 |
| Routing (30 messages) | 30/30 | 30/30 |

Removing the rule changed no routing answers. With the rule gone, the model no longer calls `forget` on these questions, so the code check catches nothing in this run. It is there for the next time a prompt change shifts the model.

Two more bugs turned up while testing this in the web app, both in code checks:

- **"orget that i take ap stats"** (a typo). The check correctly refused the delete, but the reply left AP Stats out of the list, as if it had been deleted. The refusal now tells the model not to act as if anything was deleted, and to say so if the user seems to want a delete.
- **"what do u rmbr about me"** with an empty memory replied "Got it, I'll remember that." and saved the question itself as a fact. The save check matched "rmbr" anywhere in the message. Questions like "do you / do u / did you remember" no longer count as save requests, and `test_checks.py` has 4 new cases. No eval message changed: the only one the new rule matches, "what do you remember about me?", already did not count.

The basketball miss remains: "forget that i play basketball" is a real request to delete, so the check lets it through, and only the "are you sure?" step stops "Plays soccer." from being deleted.

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

## 8. Base model vs Ornate, a retry note for crashed code, and files

All on the 30B-A3B, thinking off, run 2026-10-30.

### Same model, with and without the harness

`eval_hard.py --problems problems_holdout.json`, the 45 problems the prompt was never tuned on. "No tools" gives the model only "You are Ornate, a helpful assistant." and no tools: essentially the stock model.

| | Held-out math |
|---|---|
| Qwen3 30B-A3B, no tools | 34/45 |
| Ornate (same model, reasoning prompt and Python tool) | 44/45 |

The one miss with tools is a sample standard deviation: the code ran, but used the wrong formula (79.28 instead of 9.09). This set scored 45/45 in section 3; code has changed since then, and one problem is within noise.

### A note when Python crashes

In the web app, "solve 2x^2+3x+2=" ran `math.sqrt` on a negative discriminant. The code crashed, and the model wrote "Let's calculate the complex solutions" and stopped. `run_python` now adds "(The code raised an error. Fix the code and call run_python again.)" whenever the code exits with an error (decided by Python's exit code, not by the model's words), and turns off Python 3.14's color codes, which reached the model as junk like `[35m`. Replaying that chat, the model then retried with `cmath`.

| Python tool | Before | After |
|---|---|---|
| Held-out, 45 | 44/45 | 44/45 |
| Hard, 50 | 50/50 | 50/50 |

The same 3 problems crashed in both runs, and the model recovered on all of them even without the note. So these sets can't show a gain: the note fixes the case that was seen and costs nothing here.

### Routing with a file attached

"summarize this pdf" with a resume attached loaded the missed-question skill in the web app. No routing test had a file, so `routing_file_tests.json` adds 17 messages with made-up files in `test_files/` (resume, notes, article, essay, cover letter, scores, practice test), written before any fix. `eval_routing.py --tests routing_file_tests.json` attaches each file the same way the web app does.

The fix is a code gate, like the one on `remember`: missed-question loads only when the user's typed words say they missed a question ("I put", "I answered", "marked wrong", "the key says"...). The attached file never counts. When it refuses, the model is told to answer directly. No prompt change.

| | Model alone | With code check |
|---|---|---|
| With a file, 17 messages | 13/17 | 15/17 |
| Original routing test, 30 messages | 30/30 | 30/30 |

Fixed: "make me a study guide from these notes" and "explain number 2 to me" (with the practice test) both loaded missed-question; with the gate the model answered directly. All three real missed questions with a file still loaded the skill. Still failing: "summarize this article in 3 bullet points" and "fix the grammar in my essay" called `run_python`. That is a different problem and is not fixed yet.

## 9. MATH-500, a newer model, and two specialist models

Run 2026-10-30 to 10-31. "Current" is Qwen3-30B-A3B (Baroque). "2507" is Qwen3-30B-A3B-Instruct-2507, Qwen's newer version of the same model, with thinking split off into a separate model.

### MATH-500

[MATH-500](https://huggingface.co/datasets/HuggingFaceH4/MATH-500) is 500 competition problems from the MATH benchmark, levels 1 to 5, with answers in LaTeX. `eval_math500.py --mode tools` gives each problem to Ornate (the reasoning prompt and the Python tool) with "Put your final answer in \boxed{}." Replies were capped at 4,000 tokens, Ornate's limit at the time.

`math_grader.py` takes the last `\boxed{}` and compares it to the key: first as cleaned-up text, then as math with sympy, so `\frac{1}{2}` matches `0.5` and `(b+2)(a+5)` matches `(a+5)(b+2)`. Before any model ran, it graded all 500 official solutions as correct and rejected a set of wrong answers.

| Level | Current | 2507 |
|---|---|---|
| 1 | 42/43 | 42/43 |
| 2 | 85/90 | 89/90 |
| 3 | 96/105 | 99/105 |
| 4 | 106/128 | 114/128 |
| 5 | 73/134 | 96/134 |
| **Total** | **402/500 (80.4%)** | **440/500 (88.0%)** |

Most of the 2507's lead is on level 5. With 500 problems, one run has a margin of about ±2 points, so a 7-point gap is real; a 1 or 2 point gap would not be. The two runs overlapped and the Mac's battery ran down during the second one, so their times are not comparable.

**Grader fixes.** Reading every FAIL turned up right answers marked wrong: a base subscript (`2516` for `2516_8`), units (`864` for `864 \mbox{ inches}^2`), `\cot x` written as `\frac{\cos x}{\sin x}`, vectors written with `\frac` or a factor in front, a mixed number (`15 \frac{39}{40}` for `\frac{639}{40}`), `12^{th}`, `x \in [-2,7]`, and multiple-choice letters with extra text. Each fix is a general rule, tested on wrong answers too, and the official solutions still grade 500/500. One of my rules first rejected `\text{C}` for `\text{(C)}`, which I caught because a right answer flipped to wrong. A `\pm` rule came later: `1 \pm \sqrt{19}` means the two answers `1+\sqrt{19}, 1-\sqrt{19}`. A separate Claude model, given only each problem, key, and answer, judged every flipped answer it saw, 22 different ones, correct except one: `-3.35889894354067, 5.35889894354067` for `1 \pm \sqrt{19}`, a decimal, not the exact roots. The grader had been accepting any number within 0.000001, so that answer passed. It now accepts that only when neither answer is a decimal, and this caught one more: `0.00199` for `\frac{2}{1005}`, which the first grader had marked right. Regrading the saved answers (no model calls) moved the current model from 388 to 402 and the 2507 from 429 to 440.

**Where the misses come from.** 51 of the 2507's 60 misses never gave an answer: every one hit the 4,000-token limit while still working. The current model had 12 replies with no answer: 6 hit the limit (some repeating one line until they ran out), 5 used all 5 tool rounds, and 1 stopped early. The current model called Python on 241 problems, the 2507 on 179.

**Harness bugs this run found:**

- **A 9-hour freeze.** On problem 151 (`intermediate_algebra/964`), the model's code recursed until Python's limit, and the whole traceback went back into the conversation: 144,721 tokens, past the model's 131,072. The run sat on it all night until macOS killed the job. `run_python` now returns at most 2,000 characters, the start and the end (where errors are), with a note saying how much was cut. Rerun, the problem took under a minute (still wrong: 4 instead of 1).
- **A missing closing tag.** The 2507 once wrote `<tool_call>` and its code, then stopped before `</tool_call>`, so the code never ran. That was its one miss on the hard set (LCM of 84, 126, 220). It happened once in about 800 saved tool calls. `find_tool_call` now accepts a call missing its closing tag at the very end of a reply.
- **Lost progress.** A crash used to lose the whole run. Results are now saved after every problem.

Both runs above used both harness fixes.

### A bigger reply limit: 4,000 to 16,384 tokens

Since most of the 2507's misses ran out of room, Ornate's default reply limit went to 16,384 tokens (Qwen's suggestion for this model). Generation always picks the most likely token, so a bigger limit can only change replies that hit the old one. `eval_math500.py --rerun-cut 4000` reruns just those, plus 5 that did not as a check. All 5 checks came back word for word the same.

| | 4,000 tokens | 16,384 tokens |
|---|---|---|
| Current | 402/500 (80.4%) | 402/500 (80.4%) |
| 2507 | 440/500 (88.0%) | **475/500 (95.0%)** |

The 2507 got 35 more right and none fewer, mostly level 4 and 5 (by level: 42/43, 89/90, 104/105, 125/128, 115/134). Its long replies were real work that needed room; 6 still end without an answer. The current model's 6 long replies were loops, repeating the same lines, and more room did not help: the loop guard (below) stopped all 6, and in the 4,000-token run the same replies had repeated their endings 9 to 64 times. Most of the 2507 rerun ran before the loop guard existed and the current model's ran with it; since the guard only stopped replies that were already looping, it does not change either score.

### The 2507 on the other evals

First run before the output cap and the closing-tag fix; rerun on 10-31 with all of this section's harness changes, for both models.

| Eval | Current | 2507, first run | 2507, rerun |
|---|---|---|---|
| Held-out math, 45 | 44/45 | 45/45 | 45/45 |
| Hard math, 50 | 50/50 | 49/50 | 50/50 |
| Routing, 30 | 30/30 | 29/30 | 29/30 |
| File routing, 17: model alone / with code check | 13/17 / 15/17 | 14/17 / 16/17 | 14/17 / 16/17 |
| Memory, 13 | 12/13 (see below) | 12/13 | 12/13 |

The 2507's hard-math miss in the first run was the missing closing tag; with the fix it is 50/50. Its routing miss: "btw im taking AP Gov this year" calls `remember`, which the save gate refuses, since the message doesn't ask to save. Its file-routing miss is "fix the grammar in my essay" calling `run_python`, the same as the current model.

The current model's rerun matched its old scores on every eval but memory, which fell to 10/13 (11/13 with the code check): "what do you remember about me?" called `remember` and "whats in your memory" called `forget` (the forget gate stopped it). Rerun with only the date in the prompt set back to October 28, it scored 12/13 again. So the date at the top of the prompt, not this section's harness changes, flips those two messages, like the forget bug in section 6. The gates keep either call from saving or deleting anything, but the first move is still wrong.

### Thinking and code models in the picker

Two more models joined the picker: **Mosaic** (Qwen3-30B-A3B-Thinking-2507), which always reasons before answering, and **Art Deco** (Qwen3-Coder-30B-A3B-Instruct), trained mostly on code. Each needed harness changes:

- Mosaic's chat template writes the opening `<think>` into the prompt, so its reply only contains `</think>`. `ask_model` adds the opening tag back, so its thinking is hidden like every other model's. It gets a 32,768-token limit, Qwen's suggestion for it.
- Art Deco writes tool calls as XML (`<function=run_python><parameter=code>...`), not JSON. `find_tool_call` reads both, and turns numbers and lists back into numbers and lists using each tool's spec.

Mosaic has only a quick test so far (sum of the divisors of 360: 1170, using Python, in 25 s). Art Deco was measured.

**Art Deco wrote the same function 24 times.** Asked in the web app to write a function and test it, it wrote the code, said "Let me run this code to see the results:", and pasted the same code as text instead of calling the tool, 23 times. To find the cause, I gave it the same first message with different parts of Ornate's prompt:

| Prompt | Calls the tool? |
|---|---|
| Tool rules only | yes |
| Tool rules + skills note | yes |
| Tool rules + style | yes |
| Tool rules + date + skills note | yes |
| Tool rules + date | yes, but stopped before `</tool_call>` |
| Tool rules + skills note + style | no, loops |
| Tool rules + date + style | no, loops |
| The full prompt (what the web app uses) | no, loops |

No single part is the cause: small changes flip it either way. Since rewording would just be tuning to one example, I left the prompt alone and fixed what code can fix:

- **A loop guard.** If the last 300 characters of an answer already appear twice before, code stops the answer and adds "(stopped: the answer started repeating itself)". On the 24-copy answer it stops at 2,400 characters instead of 22,934, and it never triggered on `EVALS.md` or `harness.py`.
- **A repetition penalty of 1.05** for Art Deco, from its own `generation_config.json`. It still picks the top token, so answers stay repeatable. It did not break this loop.
- **Tags that go missing.** The routing transcripts showed Art Deco calling the right tool but writing `<function=...>` with no `<tool_call>` around it (7 of its routing misses), so nothing ran. `find_tool_call` now accepts that too, and the page hides it.

| Art Deco | First run | After reading bare `<function=...>` calls | Current model |
|---|---|---|---|
| Routing, 30 | 17/30 | 23/30 | 30/30 |
| File routing, 17 | 13/17 | 14/17 | 15/17 |
| Memory, 13 | 9/13 | 11/13 | 12/13 |

What is left is the model's own choices: it often skips the missed-question skill and just solves the problem, plus a few tool calls it didn't need.

**Switching models mid-chat.** Testing the web app end to end, a chat that started on Baroque and switched to Art Deco got stuck: Art Deco wrote 7 lines of "Let me try a simpler approach" and never answered. `respond` now logs every bad tool call to the server's output, and the log showed why. With Baroque's JSON tool calls earlier in the chat, Art Deco copied that format instead of its own XML, and wrote `{"name": "run_python", "code": "..."}`, with the arguments at the top level instead of inside `"arguments"`. Each call failed, and the model kept "fixing" code that was fine. `find_tool_call` now reads that form too. Replayed, the same chat ran the code on its second try (the first had a real error, an unescaped quote) and answered correctly.

### Coding: 15 write-and-run tasks

The routing tests have only 4 messages that expect `run_python`, so `eval_coding.py` adds 15 tasks like "write a function that counts the vowels in a string, then run it on ..." (`coding_tests.json`, answers computed in Python). Each runs with Ornate's full prompt and tools. Code checks four things: it called `run_python`, its last run had no error (Python's exit code), the loop guard didn't fire, and the expected answer is in the final reply.

| | All four | Called Python | No error | Looped | Time |
|---|---|---|---|---|---|
| Current | 15/15 | 15/15 | 15/15 | 0 | 226 s |
| 2507 | 15/15 | 15/15 | 15/15 | 0 | 101 s |
| Art Deco | 14/15 | 14/15 | 14/15 | 0 | 295 s |

Art Deco's miss is the same pattern as above: on "sum all the primes below 100", it wrote the code as text and never ran it. A second miss was the grader's: it answered "832,040" and the check wanted "832040", so the check now ignores thousands commas. These tasks are easy enough that the two general models are perfect, so they show that the code model is less reliable at running code in Ornate, not which model writes better code. The answer check is rough: short answers like "the" or "True" could match by accident.

### All four picker models, side by side

Rerun 10-31 with all of this section's harness changes. Mosaic always thinks before answering, so it is much slower. Times are for the whole set, one model running at a time.

| | Baroque (30B-A3B) | 2507 Instruct | Mosaic (2507 Thinking) | Art Deco (Coder) |
|---|---|---|---|---|
| Held-out math, 45 | 44/45 (327 s) | 45/45 (515 s) | 45/45 (1,804 s) | not run |
| Hard math, 50 | 50/50 (328 s) | 50/50 (365 s) | 50/50 (1,172 s) | not run |
| Routing, 30 | 30/30 | 29/30 | 27/30 | 23/30 |
| File routing, 17: model alone / with code check | 13/17 / 15/17 | 14/17 / 16/17 | 15/17 / 15/17 | 14/17 / 14/17 |
| Memory, 13 | 10/13 / 11/13 (12/13 with the 10-28 date) | 12/13 | 12/13 | 11/13 |
| Coding, 15 | 15/15 (226 s) | 15/15 (101 s) | 15/15 (424 s) | 14/15 (295 s); 15/15 after the `<code>` fix below |
| MATH-500, 500 | 402 (80.4%) | 475 (95.0%) | first 100 only: 95 (see below) | not run |

**Mosaic on MATH-500.** A full run would take about 5 hours, so Mosaic ran the first 100 problems (same reply limits as the others' 16,384-token runs, but its own 32,768). On those 100: Mosaic 95, 2507 94, Baroque 88, with Mosaic taking 73 minutes. 3 of its 5 misses were right answers in the wrong format: it wrote `<answer>5</answer>` or `<final_answer>0</final_answer>` instead of the `\boxed{}` the prompt asks for. Those stay wrong, since the instruction was part of the task.

Mosaic's routing misses are its own choices: it checked 3³ in Python instead of loading the missed-question skill, wrote 4 practice questions itself instead of calling `start_quiz`, and searched the web for "what classes should I take senior year". On files it wrote a quiz itself and answered one real missed question directly; it never called `run_python` on the article or the essay, which the other models do. Thinking first did not make it better at choosing tools; on these sets it matches the 2507 Instruct on math and takes 2 to 4 times as long.

### Baroque is now the 2507

Since the 2507 matched or beat the original 30B-A3B on everything but one routing message, Baroque now loads Qwen3-30B-A3B-Instruct-2507. It has no thinking mode (Qwen moved thinking into the separate Thinking model, which is Mosaic), so Ornate's adaptive thinking does nothing on Baroque now. Three results the README cites had only been measured on the original model, so they were rerun on the 2507:

| | Original 30B-A3B | 2507 |
|---|---|---|
| Held-out math, no tools or prompt | 34/45 | 39/45 |
| Held-out math, Ornate | 44/45 | 45/45 |
| Hard math, no tools | 48/50 | 50/50 |
| Naming the slip, 9 problems (graded by reading) | 6/9 thinking off, 8/9 on | 7/9 (no thinking mode) |

The harness still adds 6 points on the held-out set, all on arithmetic: a sum of primes, compound interest, a binomial probability, an angle, a standard deviation, and a digit sum that turned into a loop. The hard set no longer shows anything: the 2507 gets all 50 without tools.

Slips, by the same standard as section 4: 7 found. On two (a mean, and order of operations) it first tried paths that don't give my answer, noticed, and kept going until one did; the original model with thinking off described a path to 67 for an answer of 28 and didn't notice. Missed: on the distribution problem it blamed a division (−10 ÷ −5) instead of distributing −3 wrong, and on the bias question it said the right answer was selection bias, not voluntary response bias.

### MATH-500 without tools

The held-out set says the harness adds 6 points, so the same check ran on MATH-500: Baroque (the 2507) with no tools and the plain "You are Ornate, a helpful assistant." prompt, 16,384-token limit.

| | MATH-500 |
|---|---|
| Ornate (reasoning prompt and Python tool) | 475/500 (95.0%) |
| Same model, no tools or prompt | **481/500 (96.2%)** |

By level, no tools: 42/43, 90/90, 104/105, 122/128, 123/134. 466 problems were right both ways, 9 only with tools, 15 only without, and 10 neither. 15 against 9 is within what one run of each can tell apart, so the honest reading is that on MATH-500 the tools make no measurable difference for this model. 10 of the 15 no-tools-only wins never called Python in the tools run, so the difference there came from the prompt, not the tool, and 4 were tools-run replies with no answer at all.

That fits the held-out result instead of contradicting it: those 45 problems are mostly arithmetic (sums of primes, compound interest, standard deviations), where Python fixes the model's slips, while MATH-500 is reasoning that this model already does well in its head. The original 30B-A3B was not run without tools on MATH-500.

### Multi-turn conversations

Every test above is a single message, so some of Ornate's most important rules were never measured: a delete happens only after "yes" in the *next* message, a skill is unloaded after the answer, and a save shouldn't repeat on later turns. `eval_multiturn.py` runs 11 short conversations (`multiturn_tests.json`) the same way `server.py` runs each turn (refresh the prompt, settle any pending delete, answer, unload skills, clear the save hint), on a fake memory list in a temporary file. Code checks the memory list at the end, which tools each turn called, and words in each reply. The conversations were written from Ornate's rules before the first run.

| | Baroque (2507) | Art Deco |
|---|---|---|
| First run | 10/11 | |
| After the fix below | **11/11** | 10/11 |

**A note from the app caused the one failure.** "forget that i take ap precalculus", then "wait no, forget that i play soccer instead": the second message isn't a yes, so `handle_delete_reply` correctly cancelled the first delete, and added a note telling the model "If they said no, tell them in one short sentence, like 'Okay, I'll keep it.'" The model did exactly that and ignored the new request. When the reply is itself a delete request (`is_delete_request`), the note now says the earlier delete was cancelled and to handle this as a new one. Deleting still needs its own "are you sure" and a yes: rerun, Baroque asks "Are you sure you want me to forget: Plays soccer.?" and the memory list is unchanged. Art Deco's one miss: it solved the missed question with Python instead of loading the skill, its usual choice.

### Art Deco's code never ran: a `<code>` tag

Every saved result was searched for tool calls that came back as "bad tool call". 18 were in Art Deco's coding eval, all the same: `<function=run_python><code>...</code></function>`, a `<code>` tag where the template uses `<parameter=code>`. With no `code` found, `run_python` crashed, so none of that code ran. `xml_tool_call` now also reads a plain `<name>...</name>` tag, but only for the tool's own argument names, so other tags in the text can't be misread. All 18 saved calls parse with the fix. (The other 4 bad calls were Baroque's original model writing invalid JSON, its own mistake.) Art Deco rerun on 11-01:

| Art Deco | 10-31 | 11-01, with the fix |
|---|---|---|
| Coding, 15 | 14/15 (295 s) | **15/15** (180 s) |
| Routing, 30 | 23/30 | 21/30 |
| File routing, 17 | 14/17 | 12/17 |
| Memory, 13 | 11/13 | 10/13 |

Coding is the only eval where the fix changes anything, and it took 40% less time without the crashed rounds. The other three moved the other way, but the transcripts show proper tool calls, parsed correctly, that the model chose differently: on the amendment question it now calls `remember` to save a fact about the First Amendment, and on the Super Bowl it no longer searches. The only thing that changed in its prompt is the date, so like Baroque's memory eval (above), Art Deco's tool choices move with the calendar.

### For context

The DeepSeek-R1 paper (January 2025) lists MATH-500 scores of 74.6% for GPT-4o, 78.3% for Claude 3.5 Sonnet, 90.0% for o1-mini, and 96.4% for o1. Those were measured without tools, with each lab's own prompt and grading, so they are not directly comparable to the numbers above. MATH has also been public for years, so these problems may be in any model's training data.

## 10. Writing tasks on a file: where the file goes

On 11-01 the only file-routing miss left on Baroque was "fix the grammar in my essay", which called `run_python` with code like `text.replace("is", "are")`. That replaces "is" inside every word too ("This" becomes "Thare"), so it isn't a harmless miss. One test is too few to fix against, so before changing anything I wrote 13 new tests (`routing_text_tests.json`): 10 writing tasks on the made-up files in `test_files/` (rewrite, make formal, shorten, translate, outline, title, tone...) that should get no tool, and 3 counting tasks (word count, how often a word appears, how many scores are above 80) that should call `run_python`, to catch a fix that goes too far.

Baseline: **7/13** model alone, 8/13 with the code check. Five writing tasks called Python; for "translate this article into spanish" it imported `googletrans` (not installed) and tried to `open('article.txt')`, a file that isn't on disk.

**A prompt rule didn't help.** Adding "When the answer is writing (new or changed text), write it yourself" (in general terms, not the tests' wording) left the new tests at 7/13 and dropped file routing from 16/17 to 15/17. It was removed.

**The file's place in the message did.** The app put the file after the request: `fix the grammar in my essay` then `[File: essay.txt]` and the text. A scratch test on all 30 file messages, counting only "Python or not" right:

| How the file is attached | Right about Python |
|---|---|
| Request, then `[File: essay.txt]` and the text (before) | 24/30 |
| `[File: essay.txt]` and the text, then the request | 25/30 |
| A line saying the full text is already here, the text in `<document name="essay.txt">` tags, then the request | **27/30** |

The third is now `files.attach`, used by the web app, `/file` in the terminal, and `eval_routing.py`, so the eval sends exactly what the app sends. Full evals after the change:

| Eval | Before | After |
|---|---|---|
| Writing and counting on a file, 13 | 7/13 alone, 8/13 with check | **8/13** alone, **10/13** with check |
| File routing, 17 | 14/17 alone, 16/17 with check | **15/17** alone, **17/17** with check |
| Routing, 30 (no files) | 29/30 on 10-31 | 28/30 |

The routing drop is the date, not this change: those 30 messages have no files, and the committed code from before the change also scored 28/30 on 11-01 (new miss: "I got a 1410 on the SAT. is that a good score?" picks the missed-question skill).

Still failing: "shorten my cover letter to one paragraph", "translate this article into spanish" and "turn these notes into an outline" call Python. The 3 counting tasks still call Python, as they should. The new tests were written by me and looked at while choosing the format, so a fresh set would be a fairer check.

## Caveats

- 45 to 50 problems per set, except MATH-500. A gap of one or two questions is noise.
- Sections 1 to 3 cover only math. Section 4 is hand-graded and small. The routing test is 30 messages, the memory test 13, the multi-turn test 11 conversations, and the search results are single questions. Section 9's coding tasks are simple, and MATH-500 is public, so the models may have seen it.
- Sections 1 to 8 were run before section 9's harness changes (output cap, loop guard, 16,384-token limit, XML tool calls). The 30B-A3B's held-out, hard, routing, file-routing, and memory evals were rerun with them (section 9) and matched, except memory, which moved with the date; the skill, search, and other-model results were not rerun.
- The tool prompt changed again after these runs, adding "only use the tool when a question needs calculation." The numbers above have not been rerun with that wording.
- The grader requires an `ANSWER:` line. One 8B miss on the held-out set had the correct value but no answer line.
