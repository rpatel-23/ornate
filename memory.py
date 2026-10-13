"""Ornate's long-term memory: facts about the user, saved in memory.json."""
import json
import os

PATH = "memory.json"

def load():
    if not os.path.exists(PATH):   # first run: no memories yet
        return []
    with open(PATH) as f:
        return json.load(f)

def save(facts):
    with open(PATH, "w") as f:
        json.dump(facts, f, indent=2)

def add(fact):
    facts = load()
    fact = fact.strip()
    if fact.lower() in (f.lower() for f in facts):   # skip exact repeats
        return "Already saved."
    facts.append(fact)
    save(facts)
    return "Saved."

def remove(n):
    facts = load()
    if n < 1:                 # 0 or negatives would count from the end of the list
        raise IndexError
    gone = facts.pop(n - 1)   # users count from 1, lists count from 0
    save(facts)
    return gone

def remove_text(fact):
    """Delete the fact that matches this text exactly (ignoring case and a final period). Returns it, or None."""
    facts = load()
    key = fact.strip().lower().rstrip(".")
    for i, f in enumerate(facts):
        if f.lower().rstrip(".") == key:
            gone = facts.pop(i)
            save(facts)
            return gone
    return None

def as_prompt():
    """The memory section that goes into the system prompt."""
    facts = load()
    if not facts:
        return ""
    return "\n\nWhat you know about the user from past chats:\n" + "\n".join(f"- {f}" for f in facts)