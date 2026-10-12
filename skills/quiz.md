# Quiz me

Use this when the user asks to be quizzed, tested, or given practice questions on a topic or on an attached file.

The quiz itself is run by code in quiz.py, which asks one question at a time, checks answers, and keeps score. These are the rules for writing the questions.

## Question rules

- If material is provided, write questions only from that material. Do not add outside facts.
- Prefer scenario questions ("A researcher does X. What is this an example of?") over definition questions ("What is X?").
- Each question must have exactly one correct answer that a teacher would not argue with. If a scenario could reasonably be labeled two ways, rewrite it until it cannot.
- Make the three wrong answers plausible. Use the mistakes a student would really make, such as mixing up two similar terms.
- Do not reuse the same four choices for every question.
- No "all of the above", "none of the above", or "both A and B".
- "why" explains in one or two sentences why the correct answer is right.
- "trap" names the most tempting wrong answer and says in one sentence why it is wrong.
- "topic" is a 2 to 4 word tag naming the specific concept this one question tests, such as "stratified vs cluster". Never use the overall quiz topic as the tag, and never give two questions the same tag.
- Use the exact terms the course uses. For AP Statistics, a teacher measuring only their own class is a "convenience sample", not "sampling bias".
- For math, the correct answer must be computed, not estimated.
