"""Fast checks for the code-side safety nets. No model needed: python test_checks.py"""
import re
src = open("assistant.py").read()
exec(src[src.index("SAVE_REQUEST = "):src.index("last_user_text = ")])
exec(src[src.index("CLAIMS_SAVE = "):src.index("def called_remember")])
exec(src[src.index("MISSED_QUESTION = "):src.index("# replies that claim a save")])

# is the user's message an explicit request to save something?
CASES = {
    "rmbr that i take ap gov": True,
    "remember that my SAT is on december 5": True,
    "save this in your memory: i like bullet points": True,
    "dont forget i hate long explanations": True,
    "for future reference i like short answers": True,
    "keep in mind im a junior": True,
    # not requests: must never cause a save
    "explain photosynthesis in detail": False,
    "btw im taking AP Gov this year": False,
    "i cant remember the quadratic formula": False,
    "i don't remember how to do this": False,
    "who won the most recent super bowl": False,
    "what do u rmbr about me": False,
    "do you remember my sat date?": False,
    "what did you remember from last time": False,
    "can you remember that i like bullet points": True,
}
fails = 0
for text, want in CASES.items():
    got = is_save_request(text)
    if got != want:
        fails += 1
        print(f"FAIL wanted {want}, got {got}: {text}")
print(f"{len(CASES) - fails}/{len(CASES)} save-request checks passed")

# does the model's answer claim a save? (used only to catch a false claim)
CLAIMS = {
    "Remembered.": True,
    "Okay, I've saved that you take AP Gov.": True,
    "Got it, I'll remember that.": True,
    "During photosynthesis, energy is stored in glucose.": False,
    "The file is saved to disk.": False,
    "Nice! Good luck this season.": False,
}
cfails = 0
for text, want in CLAIMS.items():
    got = bool(CLAIMS_SAVE.search(text))
    if got != want:
        cfails += 1
        print(f"FAIL wanted {want}, got {got}: {text}")
print(f"{len(CLAIMS) - cfails}/{len(CLAIMS)} save-claim checks passed")

# is the user's message a request to delete something? (forget refuses otherwise)
DELETES = {
    "forget that i take ap stats": True,
    "i quit soccer, delete that from your memory": True,
    "can you remove my SAT date": True,
    "clear my memory": True,
    # not requests: must never queue a delete
    "dont forget my sat is on december 5": False,
    "don't forget i hate long explanations": False,
    "i forgot my calculator at home lol": False,
    "what do you know about me?": False,
    "what do you remember about me?": False,
    "whats in your memory": False,
}
dfails = 0
for text, want in DELETES.items():
    got = is_delete_request(text)
    if got != want:
        dfails += 1
        print(f"FAIL wanted {want}, got {got}: {text}")
print(f"{len(DELETES) - dfails}/{len(DELETES)} delete-request checks passed")

# does the user's typed message say they missed a question? (missed-question refuses to load otherwise)
MISSED = {
    "If 5x + 3 = 28, what is 10x? I put 5.": True,
    "I got this wrong on my practice test: a 15% tip on a $40 meal. I said $4. Why is that wrong?": True,
    "my teacher marked my answer of 81 wrong for 3 to the power of 3. what did I mess up?": True,
    "Which amendment protects free speech? I answered the 2nd and it said incorrect.": True,
    "The mean of 4, 8, and 12 is what? I wrote 24 but the answer key says 8.": True,
    "I got number 3 wrong on this, I put A. why?": True,
    "i put 3 for question 1 and it was wrong": True,
    "my answer for #4 was 6 but the key says 3, what did i do wrong": True,
    # not reports of a miss: the skill must not load (a file attached to these never counts)
    "summarize this pdf": False,
    "summarize this": False,
    "what's this document about?": False,
    "explain number 2 to me": False,
    "quiz me on these notes": False,
    "make me a study guide from these notes": False,
    "what does the mitochondria do?": False,
}
mfails = 0
for text, want in MISSED.items():
    got = is_missed_question(text)
    if got != want:
        mfails += 1
        print(f"FAIL wanted {want}, got {got}: {text}")
print(f"{len(MISSED) - mfails}/{len(MISSED)} missed-question checks passed")
