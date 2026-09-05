"""TEACHING SKILL — explain like a teacher, study plans, quiz mode."""
import random

_QUE = ("teach me", "explain", "what is", "what are", "how does", "why is",
        "why does", "define", "study plan", "quiz me", "homework")

_PLAN = ("Here's a 7-day plan: days 1-2 read and take notes, day 3 make a "
         "mind-map, day 4 practice problems, day 5 teach it back to me out loud, "
         "day 6 revision, day 7 mock test.")


def match(text):
    return any(q in text for q in _QUE)


_QUIZ_BANK = [
    ("What does CPU stand for?", "central processing unit"),
    ("What does HTTP stand for?", "hypertext transfer protocol"),
    ("Binary 1010 in decimal?", "10"),
    ("What does RAM stand for?", "random access memory"),
    ("Capital of Japan?", "tokyo"),
]


def _quiz(ask):
    q, a = random.choice(_QUIZ_BANK)
    ans = (ask(f"QUIZ — {q} ") or "").lower().strip()
    if a in ans:
        return f"Correct! {q.title()} — {a}."
    return f"Not quite — the answer is: {a}. Say 'quiz me' again for another."


def reply(text, say, ask):
    low = text.lower()
    if "quiz me" in low:
        return _quiz(ask)
    if "study plan" in low:
        return _PLAN
    topic = (low.split("teach me", 1)[-1].split("explain", 1)[-1]
                .split("what is", 1)[-1].split("what are", 1)[-1]
                .split("how does", 1)[-1].split("why", 1)[-1]
                .split("define", 1)[-1].strip(" ?.,"))
    if not topic:
        return "Tell me the topic and I'll teach it step by step."
    say(f"Teaching mode: {topic}.")
    # Feynman-style scaffolding, then open a trusted source
    try:
        import skills.techno as techno
        web = techno._web_summary(topic)
    except Exception:
        web = ""
    return (f"Let's learn {topic} the simple way. Step 1: the core idea in one "
            f"line. {web} Step 2: an example. Step 3: you explain it back to me — "
            f"that's how you know you truly got it.")
