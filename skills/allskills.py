"""LYA ALL-ROUNDER SKILL ROUTER
==============================
One entry point main.py calls:  allskills.reply(text, say, ask)
Routes any request to the right skill:

  - cooking     : recipes, steps, kitchen help, substitutes
  - guiding     : directions, travel, etiquette, life-advice
  - teaching    : explain like a teacher, homework help, study plans
  - techno      : smart technical person — fix, install, troubleshoot, code
  - hacker      : (SAFE / ETHICAL ONLY) scan, recon on OWN devices, learn hacking
  - autonomous  : "LYA open chrome and install x" — she does it hands-free

KALI NOTE: teach mode — say "kali about", "kali roadmap", "kali lesson 1",
  "kali command nmap", "kali quiz" to learn the ethical hacker's OS.

Returns the spoken reply, or None if no skill matched (so main.py falls through).
"""
import re

from skills import cooking, guiding, teaching, techno, hacker, autonomous, kali, learnhack

_SKILLS = (
    (cooking.match,    cooking.reply),
    (guiding.match,    guiding.reply),
    (teaching.match,   teaching.reply),
    (techno.match,     techno.reply),
    (hacker.match,     hacker.reply),
    (learnhack.match,  learnhack.reply),
    (kali.match,       kali.reply),
    (autonomous.match, autonomous.reply),
)


def reply(text, say, ask):
    """Return a string reply if a skill handled it, else None."""
    for matcher, handler in _SKILLS:
        try:
            if matcher(text):
                return handler(text, say, ask)
        except Exception as e:
            return f"That skill hit a snag: {e}"
    return None
