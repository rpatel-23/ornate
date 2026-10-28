"""Fast checks for the code-side safety nets. No model needed: python test_checks.py"""
import re
src = open("assistant.py").read()
exec(src[src.index("SAVE_REQUEST = "):src.index("last_user_text = ")])
exec(src[src.index("CLAIMS_SAVE = "):src.index("def called_remember")])

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
