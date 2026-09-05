"""LYA HACKER TRAINER — she teaches AND hacks with you
=====================================================
Not a link list. A real training co-pilot:

  "learn hacking"       -> overview + your progress
  "hacker lesson 1..8"  -> a lesson she TEACHES you
  "hacker mission 1..8" -> she runs the real tools on YOUR machine, live
  "hacker curriculum"   -> the full 8-lesson roadmap

Every mission uses the tools she already has (hacker.py) and only ever
targets YOUR OWN machine / network. That's the legal line and she holds it.
"""
import os
import re
from skills import hacker

# ------------------------------------------------------------- CURRICULUM
LESSONS = {
    1: {
        "title": "How hackers think — recon first",
        "teach": (
            "Every hack starts with RECON: learning what exists before touching anything.\n"
            "A real pentest goes: 1) map the target, 2) find open doors (ports/services),\n"
            "3) probe those doors for weaknesses, 4) report and FIX them.\n"
            "Rule one of the trade: never attack blind. Information first, action later.\n"
            "Your mission: I scan your own PC like an attacker would — open ports tell\n"
            "a stranger exactly where to knock."
        ),
        "mission": "portscan my pc",
        "explain": "I just ran a TCP connect scan on your own machine. Every open port is a door — close the ones you don't use.",
    },
    2: {
        "title": "Networks — who is on your LAN",
        "teach": (
            "Before touching a single port, a hacker maps the NETWORK: which devices exist,\n"
            "which IPs they hold. I use the ARP table — think of it as your router's guest list.\n"
            "Any device on your LAN can reach the others, so an unknown device is a real finding.\n"
            "Mission: I pull your ARP table and we audit every device on it."
        ),
        "mission": "who is on my network",
        "explain": "Check each device: if you can't name it (your PC, phone, TV, router), change your WiFi password tonight.",
    },
    3: {
        "title": "Know your fortress — system recon",
        "teach": (
            "You can't defend what you don't know. Recon means listing your OS version,\n"
            "your IPs, your LAN-facing address — exactly what an attacker sees first.\n"
            "The LAN-facing IP is the address other devices use to reach you.\n"
            "Mission: I fingerprint your machine — the same first step an attacker takes."
        ),
        "mission": "recon",
        "explain": "Now you know your exposed surface. Attackers see this too — that's why we harden next.",
    },
    4: {
        "title": "Risky services — what attracts attackers",
        "teach": (
            "Some ports are famous for being unsafe when exposed: 445 SMB (WannaCry's door),\n"
            "3389 RDP (remote desktop — brute-force magnet), 23 Telnet (no encryption at all).\n"
            "If your scan shows one open and you don't need it, that IS the vulnerability.\n"
            "Mission: rescan your PC and let's hunt risky services together."
        ),
        "mission": "port scan my pc",
        "explain": "Close unneeded services (services.msc). Needed ones? Keep them — but firewall them away from the internet.",
    },
    5: {
        "title": "Passwords — hashing, strength and cracking",
        "teach": (
            "Systems never store your password — they store a HASH: a one-way fingerprint.\n"
            "Cracking = guessing inputs until a hash matches. Fast hashes fall in seconds;\n"
            "long random ones take centuries. That's the whole game: LENGTH beats cleverness.\n"
            "Mission: I generate a cryptographically strong password for you."
        ),
        "mission": "generate a password",
        "explain": "12+ chars, mixed everything. Test one of yours: say 'how strong is my password <yours>'.",
    },
    6: {
        "title": "Crypto basics — Caesar and Base64",
        "teach": (
            "Base64 is NOT encryption — it's encoding, reversible by anyone. Yet it hides\n"
            "passwords in configs everywhere. Caesar shifts letters by N — ancient, broken,\n"
            "but it teaches the core idea: keys and alphabets.\n"
            "Mission: I encode and decode a secret with you so you see it with your own eyes."
        ),
        "mission": "base64 encode hello hacker",
        "explain": "See? Encoding is a costume, not a lock. Real crypto is AES — and the key is the only secret.",
    },
    7: {
        "title": "Hardening — turning the scoreboard green",
        "teach": (
            "Offense finds holes, defense closes them. Hardening = firewall ON, real-time AV ON,\n"
            "risky ports closed, updates applied. The deliverable of every real pentest is not\n"
            "the exploit — it's the fix.\n"
            "Mission: full security posture check on your machine."
        ),
        "mission": "am i secure",
        "explain": "Anything OFF in that report is your homework. Fix it, re-run until everything is green.",
    },
    8: {
        "title": "Graduation — legal practice ranges",
        "teach": (
            "You have the fundamentals now. To practice on REAL targets legally, use ranges\n"
            "built for it: TryHackMe (guided rooms), PortSwigger Web Security Academy (web),\n"
            "Hack The Box Starting Point (real machines). Hacking anything else without\n"
            "written permission is a crime — same skill, the target decides the law.\n"
            "You're ready. Keep your ethics sharper than your tools."
        ),
        "mission": "recon",
        "explain": "Final sweep. From here: TryHackMe -> PortSwigger labs -> Hack The Box. I guide you through every room.",
    },
}

STATE_FILE = os.path.join(os.path.dirname(__file__), "hacker_progress.txt")

# ------------------------------------------------------------- PROGRESS
def _load_progress():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(int(x) for x in f.read().split() if x.strip().isdigit())
    except Exception:
        return set()

def _save_progress(done):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write(" ".join(str(x) for x in sorted(done)))
    except Exception:
        pass

def _bar(done, total):
    return "█" * done + "░" * (total - done)

def overview():
    done = _load_progress()
    lines = [
        "🔥 HACKER TRAINER — I teach, you learn, we hack YOUR machine together.",
        f"Progress: {_bar(len(done), 8)} {len(done)}/8 lessons done.",
        "",
        "Say 'hacker lesson 1' (I teach) or 'hacker mission 1' (I run the tools live).",
        "",
    ]
    for n, L in LESSONS.items():
        mark = "✅" if n in done else f"{n}."
        lines.append(f"  {mark} {L['title']}")
    return "\n".join(lines)

def lesson(n):
    L = LESSONS.get(n)
    if not L:
        return f"No lesson {n}. Pick 1–{len(LESSONS)} — say 'hacker curriculum'."
    done = _load_progress()
    return (f"📖 LESSON {n}: {L['title']}\n\n{L['teach']}\n\n"
            f"Ready? Say 'hacker mission {n}' and I run it live with you.")

def mission(n):
    L = LESSONS.get(n)
    if not L:
        return f"No mission {n}. Pick 1–{len(LESSONS)}."
    result = hacker.handle(L["mission"])
    done = _load_progress()
    done.add(n)
    _save_progress(done)
    return (f"⚔️ MISSION {n}: {L['title']}\n\n"
            + (result or "(tool returned nothing)") + "\n\n"
            f"💬 {L['explain']}\n\n"
            + (f"🏆 Lesson {n} complete! {_bar(len(done), 8)} {len(done)}/8"
               if len(done) < 8 else "🏆 ALL 8 DONE — you graduate to TryHackMe next. 🎓"))

# ------------------------------------------------------------- ROUTER
def match(text):
    """True if this is a trainer command (allskills.py calls this)."""
    t = text.lower().strip()
    if "hacker lesson" in t or "hacker mission" in t:
        return True
    if t in ("learn hacking", "hacking lessons", "hacker curriculum", "teach me hacking"):
        return True
    return False

def reply(text, say=None, ask=None):
    t = text.lower().strip()
    m = re.search(r"(lesson|mission)\s*(\d+)", t)
    if m:
        n = int(m.group(2))
        return lesson(n) if m.group(1) == "lesson" else mission(n)
    return overview()
