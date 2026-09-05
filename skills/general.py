"""GENERAL SKILL — the all-rounder fallback: reminders, math, time, weather,
translations, jokes, small talk. LYA's everyday brain when no specialist skill
matches."""
import datetime, random, webbrowser

import skills.device as device

_JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "There are 10 types of people: those who understand binary and those who don't.",
    "I told my computer I needed a break — it said 'why, are you not running well?'",
    "Why did the developer go broke? Because he used up all his cache.",
    "404: joke not found... oh wait, here's one: I'd tell you a UDP joke but you might not get it.",
]

_AFFIRM = ["you've got this", "one step at a time — and I'm with you",
           "every expert was once a beginner", "small progress is still progress"]


def match(text):
    return True  # fallback: always matches


def reply(text, say, ask):
    low = text.lower()

    # time / date
    if any(w in low for w in ("time ", "what time", "the date", "today date", "what day")):
        now = datetime.datetime.now()
        return now.strftime("It's %I:%M %p on %A, %d %B %Y.").lstrip("0")

    # simple math
    if any(w in low for w in ("calculate", "what is ", "how much is", "plus", "minus", "times", "divided")):
        return _math(low)

    # weather
    if "weather" in low:
        city = low.split("in", 1)[-1].strip(" ?.") or ""
        device.search_web(f"weather {city}".strip())
        return f"Weather{' in ' + city if city else ''} is on your screen."

    # translate
    if "translate" in low:
        device.search_web(text)
        return "Translation is open in your browser."

    # joke / mood
    if "joke" in low:
        return random.choice(_JOKES)
    if any(w in low for w in ("sad", "tired", "stressed", "motivate", "encourage")):
        return random.choice(_AFFIRM) + ". Want to talk about it?"

    # generic search
    if low.startswith(("search", "google", "look up", "find")):
        device.search_web(low.split(" ", 1)[-1])
        return "Here's what I found."

    return ("I'm here — ask me anything: tasks, tech help, cooking, learning, "
            "or say 'help' to see everything I can do.")


def _math(low):
    try:
        expr = (low.replace("what is", "").replace("calculate", "").replace("how much is", "")
                   .replace("plus", "+").replace("minus", "-").replace("times", "*")
                   .replace("multiplied by", "*").replace("divided by", "/")
                   .replace("x", "*").replace("?", "").strip())
        allowed = set("0123456789+-*/(). ")
        if not expr or not set(expr) <= allowed:
            return "I couldn't parse that math — keep it simple like 12*7."
        return f"That's {eval(expr)}."  # noqa: S307 — input whitelisted above
    except Exception:
        return "Hmm, that math didn't work out. Try like 25*4."
