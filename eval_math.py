import re
from harness import respond, SYSTEM, SYSTEM_TOOLS

# (question, correct answer)
PROBLEMS = [
    ("What is 4817 * 392?", 1888264),
    ("What is 987654 * 3210?", 3170369340),
    ("What is 2 to the power of 37?", 137438953472),
    ("What is 17 factorial divided by 15 factorial?", 272),
    ("What is the sum of all integers from 1 to 500?", 125250),
    ("What is the remainder when 123456789 is divided by 97?", 39),
    ("How many prime numbers are less than 200?", 46),
    ("What is 15% of 2340 plus 7.5% of 880?", 417),
    ("$2500 is invested at 4% interest compounded annually. What is it worth after 10 years, rounded to the nearest dollar?", 3701),
    ("What is the sum of the two solutions of 2x^2 - 3x - 12 = 0?", 1.5),
    ("What is the distance between the points (-3, 7) and (9, -9)?", 20),
    ("How many ways can you choose 6 items from 20?", 38760),
    ("What is the mean of 12, 15, 22, 9, 31, 18, 27, rounded to two decimal places?", 19.14),
    ("What is 13 to the power of 5?", 371293),
    ("What is the greatest common divisor of 1071 and 462?", 21),
    ("A right triangle has legs of length 119 and 120. How long is the hypotenuse?", 169),
    ("How many seconds are in 3.5 days?", 302400),
    ("What is the sum of the squares of the integers from 1 to 50?", 42925),
    ("A value of 82 comes from a distribution with mean 70 and standard deviation 8. What is its z-score?", 1.5),
    ("What is 999 * 999?", 998001),
]

def is_correct(reply, expected):
    # only grade the final ANSWER line, not numbers in the work
    found = re.findall(r"ANSWER:\**\s*\$?\s*(-?[\d,]*\.?\d+)", reply)
    if not found:
        return False
    return abs(float(found[-1].replace(",", "")) - expected) <= 0.01

def run(use_tools):
    system = SYSTEM_TOOLS if use_tools else SYSTEM
    score = 0
    for question, expected in PROBLEMS:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": question + "\nEnd your reply with a line in the form ANSWER: <number>"},
        ]
        reply = respond(messages, use_tools=use_tools, show=False)
        ok = is_correct(reply, expected)
        score += ok
        print("PASS" if ok else "FAIL", "-", question)
        if not ok:
            print("   reply ended with:", repr(reply[-200:]))
    return score

print("=== Without tools ===")
no_tools = run(use_tools=False)
print("\n=== With python tool ===")
with_tools = run(use_tools=True)

print(f"\nWithout tools: {no_tools}/{len(PROBLEMS)}")
print(f"With tools:    {with_tools}/{len(PROBLEMS)}")