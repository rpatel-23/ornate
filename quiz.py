import json
import random
import re
from harness import respond
from files import read_file

FORMAT = """Write {n} multiple-choice questions about: {topic}
{material}
Reply with ONLY a JSON list and no other text. Each item must look like this:
{{"topic": "short tag", "question": "the question", "correct": "the right answer", "wrong": ["wrong answer", "wrong answer", "wrong answer"], "why": "why the right answer is right", "trap": "the most tempting wrong answer and why it is wrong"}}"""

def make_questions(topic, n, material=""):
    """Ask the model for questions as JSON. Returns a list, or [] if it could not."""
    rules = read_file("skills/quiz.md")
    if material:
        material = "Use only this material:\n" + material + "\n"
    for attempt in range(2):
        messages = [
            {"role": "system", "content": "You write quiz questions.\n\n" + rules},
            {"role": "user", "content": FORMAT.format(n=n, topic=topic, material=material)},
        ]
        reply = respond(messages, use_tools=False, show=False)
        reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).replace("<think>", "")
        found = re.search(r"\[.*\]", reply, re.DOTALL)
        try:
            questions = json.loads(found.group(0))
        except Exception:
            continue
        # keep only questions that have every part
        good = [
            q for q in questions
            if isinstance(q, dict)
            and all(q.get(k) for k in ("question", "correct", "wrong", "why"))
            and isinstance(q["wrong"], list) and len(q["wrong"]) == 3
        ]
        if good:
            return good[:n]
    return []

def run_quiz(topic, n=5, material=""):
    """Run a quiz in the terminal. Code handles turns and score; the model only wrote the questions."""
    print("writing questions...")
    questions = make_questions(topic, n, material)
    if not questions:
        print("couldn't write a quiz for that. try rewording the topic.")
        return ""

    score = 0
    missed = []
    for i, q in enumerate(questions, 1):
        # shuffle here so the right answer is not always the same letter
        choices = [q["correct"]] + q["wrong"]
        random.shuffle(choices)
        right = "ABCD"[choices.index(q["correct"])]

        print(f"\nQuestion {i} of {len(questions)} ({q.get('topic', topic)})")
        print(q["question"])
        for letter, choice in zip("ABCD", choices):
            print(f"  {letter}) {choice}")

        answer = ""
        while answer not in ("A", "B", "C", "D"):
            answer = input("your answer (A-D): ").strip().upper()[:1]

        if answer == right:
            score += 1
            print("Correct.", q["why"])
        else:
            picked = choices["ABCD".index(answer)]
            missed.append({"n": i, "topic": q.get("topic", topic), "question": q["question"], "picked": picked, "correct": q["correct"]})
            print(f"Not quite. The answer is {right}) {q['correct']}.", q["why"])
            if q.get("trap"):
                print("Watch out:", q["trap"])
        print(f"Score: {score} of {i}")

    print(f"\nFinal score: {score} of {len(questions)}")
    if missed:
        print("Missed:", ", ".join(f"#{m['n']} {m['topic']}" for m in missed))
    else:
        print("Missed: nothing")

    # a summary the chat can remember, so follow-up questions work
    summary = f"Quiz on {topic}: scored {score} of {len(questions)}."
    for m in missed:
        summary += f"\nMissed #{m['n']} ({m['topic']}): {m['question']} I put: {m['picked']}. Correct: {m['correct']}."
    return summary
