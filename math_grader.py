"""Grading for MATH-500: is the model's \\boxed{} answer the same as the answer key?
Step 1 cleans formatting that doesn't change the value and compares text.
Step 2 turns both into sympy expressions and checks they are equal as math."""
import re
import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application, convert_xor

def last_boxed(text):
    """The contents of the last \\boxed{...} in the text, counting braces so nested { } work. None if there is none."""
    start = text.rfind("\\boxed")
    if start == -1:
        return None
    i = text.find("{", start)
    if i == -1:
        return None
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j]
    return None

def _braced(s, i):
    """If s[i] is '{', return (contents, index after the matching '}'). Else the single next character."""
    if i < len(s) and s[i] == "{":
        depth = 0
        for j in range(i, len(s)):
            depth += {"{": 1, "}": -1}.get(s[j], 0)
            if depth == 0:
                return s[i + 1:j], j + 1
    return (s[i], i + 1) if i < len(s) else ("", i)

def clean(s):
    """Remove formatting that doesn't change an answer's value."""
    s = s.strip().strip("$").strip()
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    s = re.sub(r"\\(left|right|displaystyle|!|,|;|:)", "", s)
    s = s.replace("\\ ", "")
    s = re.sub(r"\^\s*\{?\\circ\}?", "", s)                    # 90^\circ -> 90
    s = s.replace("\\%", "").replace("%", "").replace("\\$", "")
    s = re.sub(r"(?<=[\d}])\s*\\(text|mbox)\{\s*[a-zA-Z ]+\}(\^\d)?$", "", s)   # 864 \mbox{ inches}^2 -> 864 (a unit after the number)
    s = re.sub(r"\\(text|textbf|mbox|mathrm)\{([^{}]*)\}", r"\2", s)   # \text{Evelyn} -> Evelyn
    s = re.sub(r"^(\d+)_\{?\d+\}?$", r"\1", s)                  # 2516_8 -> 2516 (the base is already in the question)
    s = re.sub(r"^[a-zA-Z]\s*(=|\\in)\s*", "", s)               # x = 5 -> 5, x \in [-2,7] -> [-2,7] (only a single variable in front)
    s = re.sub(r"^(\d+)\^\{?(st|nd|rd|th)\}?$", r"\1", s)       # 12^{th} -> 12 (after \mathrm{th} became th)
    s = re.sub(r"^(\d+)\s*\\frac", r"\1+\\frac", s)             # 15 \frac{39}{40} -> 15+\frac{39}{40} (a mixed number)
    s = re.sub(r"\\(sin|cos|tan|cot|sec|csc|ln|log)\s*([a-zA-Z0-9])", r"\\\1(\2)", s)   # \cos x -> \cos(x), before spaces go
    s = re.sub(r"\s+", "", s)
    s = s.rstrip(".")
    s = re.sub(r"(?<![\d])\.(\d)", r"0.\1", s)                  # .5 -> 0.5
    s = re.sub(r"\\sqrt(\w)", r"\\sqrt{\1}", s)                 # \sqrt2 -> \sqrt{2}
    s = re.sub(r"\\frac(\d)(\d)", r"\\frac{\1}{\2}", s)         # \frac12 -> \frac{1}{2}
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", s):          # 13,535 -> 13535 (a thousands comma, not a list)
        s = s.replace(",", "")
    return s

def to_python(s):
    """Turn simple LaTeX into a Python-style expression for sympy: \\frac, \\sqrt, \\pi, ^, \\cdot."""
    out, i = "", 0
    while i < len(s):
        if s.startswith("\\frac", i):
            top, i = _braced(s, i + 5)
            bottom, i = _braced(s, i)
            out += f"(({to_python(top)})/({to_python(bottom)}))"
        elif s.startswith("\\sqrt[", i):
            j = s.index("]", i)
            n = s[i + 6:j]
            inner, i = _braced(s, j + 1)
            out += f"(({to_python(inner)})**(1/({n})))"
        elif s.startswith("\\sqrt", i):
            inner, i = _braced(s, i + 5)
            out += f"sqrt({to_python(inner)})"
        elif s[i] in "{}":
            out += "(" if s[i] == "{" else ")"
            i += 1
        else:
            out += s[i]
            i += 1
    out = out.replace("\\pi", "pi").replace("\\cdot", "*").replace("\\times", "*").replace("^", "**")
    out = re.sub(r"\\infty", "oo", out)
    out = re.sub(r"\\(sin|cos|tan|cot|sec|csc|ln|log)", r"\1", out)   # \cos x -> cos x
    return out

TRIG = {name: getattr(sympy, name) for name in ["sin", "cos", "tan", "cot", "sec", "csc", "log"]} | {"ln": sympy.log}
TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)

def as_sympy(s):
    expr = to_python(s)
    if "\\" in expr:          # leftover LaTeX we can't read: don't guess
        return None
    expr = re.sub(r"(?<![a-zA-Z])i(?![a-zA-Z])", "I", expr)   # the imaginary unit
    try:
        return parse_expr(expr, transformations=TRANSFORMS, local_dict={"pi": sympy.pi, "I": sympy.I, "sqrt": sympy.sqrt, "oo": sympy.oo, **TRIG})
    except Exception:
        return None

def same_value(a, b):
    x, y = as_sympy(a), as_sympy(b)
    if x is None or y is None:
        return False
    try:
        if sympy.simplify(x - y) == 0:
            return True
        # close-enough numbers only when both are exact forms sympy couldn't simplify (like nested square roots).
        # A decimal never stands in for an exact answer: 5.35889894354067 is not 1+\sqrt{19}. (0.5 vs \frac{1}{2} still
        # matches above, since they are exactly equal.)
        if re.search(r"\d\.\d", a + b):
            return False
        return abs(complex(sympy.N(x)) - complex(sympy.N(y))) < 1e-6
    except Exception:
        return False

def wraps(s):
    """True if the first bracket closes at the very end: '(3,4]' yes, '(a+5)(b+2)' no."""
    depth = 0
    for i, ch in enumerate(s):
        depth += (ch in "([{") - (ch in ")]}")
        if depth == 0 and i < len(s) - 1:
            return False
    return True

def split_top(s):
    """Split '1,-2' or '(3,\\frac{\\pi}{2})' into items at commas that aren't inside brackets."""
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur); cur = ""
        else:
            cur += ch
    return parts + [cur]

def matrix_entries(s):
    """'\\begin{pmatrix}1\\\\2\\end{pmatrix}' -> ['1', '|', '2']: entries with '|' between rows, so shapes must match. None if not a matrix."""
    s = re.sub(r"^[^=]*=", "", s.strip().strip("$")).strip()     # drop "\mathbf{v} =" in front
    m = re.fullmatch(r"(.*?)\\begin\{[pbv]matrix\}(.*)\\end\{[pbv]matrix\}", s, re.DOTALL)
    if not m:
        return None
    scale = m.group(1).strip()      # a number in front, like \frac{8}{49} \begin{pmatrix}..., multiplies every entry
    out = []
    for row in m.group(2).split("\\\\"):
        out += [f"({clean(scale)})({clean(x)})" if scale else clean(x) for x in row.split("&")] + ["|"]
    return out

def expand_pm(s):
    """'1\\pm\\sqrt{19}' -> '1+\\sqrt{19},1-\\sqrt{19}'. Only one \\pm, and only outside brackets, so it can't misread anything bigger."""
    if s.count("\\pm") != 1 or re.search(r"[\[(]", s.split("\\pm")[0]):
        return s
    return s.replace("\\pm", "+") + "," + s.replace("\\pm", "-")

def is_correct(model_answer, key):
    if model_answer is None:
        return False
    a, b = clean(model_answer), clean(key)
    if a == b:
        return True
    # 1 \pm \sqrt{19} means two answers: 1+\sqrt{19}, 1-\sqrt{19}
    a, b = expand_pm(a), expand_pm(b)
    # multiple choice: the key is a letter like (B), and the answer is B, or starts with (B)
    if re.fullmatch(r"\([A-E]\)", b):
        return a == b[1] or a.startswith(b)
    # matrices and vectors: same shape, then every entry equal, in order (-1/3 matches -\frac{1}{3})
    ma, mb = matrix_entries(model_answer), matrix_entries(key)   # raw text: clean() would eat a backslash from "\\ \frac"
    if ma or mb:
        return bool(ma and mb) and len(ma) == len(mb) and all(p == q or same_value(p, q) for p, q in zip(ma, mb))
    # points and intervals like (3, pi/2): same brackets, then compare inside
    if a[:1] in "([" and b[:1] == a[:1] and a[-1:] == b[-1:] and wraps(a) and wraps(b):
        a, b = a[1:-1], b[1:-1]
    pa, pb = split_top(a), split_top(b)
    if len(pa) != len(pb):
        return False
    if len(pa) > 1:   # a list of answers: same items, in any order
        return all(any(p == q or same_value(p, q) for q in pb) for p in pa) and \
               all(any(p == q or same_value(p, q) for p in pa) for q in pb)
    return same_value(a, b)
