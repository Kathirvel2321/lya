"""GUIDING SKILL — directions, travel, etiquette, life advice."""
import urllib.parse

import skills.device as device

_QUE = ("guide me", "how do i get to", "directions", "route to", "how to reach",
        "where is", "nearest", "advice", "should i", "help me decide", "tips")


def match(text):
    return any(q in text for q in _QUE)


_LIFE_RULES = (
    ("interview", "Dress one level above the role, arrive ten minutes early, "
     "and prepare three stories about your wins."),
    ("presentation", "Open with a hook, one idea per slide, and rehearse out "
     "loud at least twice."),
    ("angry", "Breathe four seconds in, hold four, out four. Respond, don't react."),
    ("study", "Pomodoro: 25 minutes focus, 5 minutes break. Phone in another room."),
    ("sleep", "No screens thirty minutes before bed and keep the room cool and dark."),
)


def reply(text, say, ask):
    low = text.lower()
    for key, advice in _LIFE_RULES:
        if key in low:
            return advice
    if any(q in low for q in ("how do i get to", "directions", "route to", "how to reach")):
        dest = low.split("to", 1)[-1].strip(" ?.")
        say(f"Opening directions to {dest}.")
        device.search_web(f"directions to {dest}")
        return f"Route to {dest} is on screen."
    if "where is" in low or "nearest" in low:
        device.search_web(text)
        return "Here's what I found on screen."
    return ("Tell me the situation in one line and I'll guide you — "
            "travel, decisions, etiquette, anything.")
