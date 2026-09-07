"""LYA HACKER TRAINER — she teaches AND hacks with you (DUO edition).
====================================================================
Not a link list. A real training co-pilot for BOTH of you (owner + Kaching).
Each learner gets their own progress; LYA remembers whose turn it is.

Say to LYA:
  "learn hacking"          -> overview + BOTH learners' progress bars
  "hacker lesson 1..8"     -> a lesson she TEACHES the active learner
  "hacker mission 1..8"    -> she runs the real tools on YOUR machine, live
  "hacker curriculum"      -> the full 8-lesson roadmap
  "switch to kaching"      -> hand the keyboard to Kaching (own progress)
  "switch to me"           -> take it back
  "kaching lesson 2"       -> teach/run directly for Kaching
  "our progress"           -> the duo scoreboard
  "hacking plan"           -> 8-week study plan (race each other!)
  "hacking channels"       -> free YouTube teachers
  "hacking labs"           -> legal practice ranges
  "hacking courses"        -> free full courses

Every mission uses the tools she already has (hacker.py) and only ever
targets YOUR OWN machine / network. That's the legal line and she holds it.
"""
import os
import re
import gzip
from skills import hacker

# ------------------------------------------------------- BOOK KNOWLEDGE BASE
# Your 3 ethical-hacking books (PDFs in lya/examples/) are ingested ONCE by
# build_knowledge.py into book_knowledge.txt.gz. LYA searches them to answer
# "book: <topic>" questions — the books become HER memory.
KB_FILE = os.path.join(os.path.dirname(__file__), "book_knowledge.txt.gz")
_kb_cache = None

def _load_kb():
    """Return the full book text, building it from the PDFs on first use."""
    global _kb_cache
    if _kb_cache is not None:
        return _kb_cache
    if not os.path.exists(KB_FILE):
        try:
            from skills import build_knowledge
            build_knowledge.build()
        except Exception:
            pass
    try:
        with gzip.open(KB_FILE, "rt", encoding="utf-8") as f:
            _kb_cache = f.read()
    except Exception:
        _kb_cache = ""
    return _kb_cache

def _book_pages(kb, topic, n=3):
    """Find pages in the books that mention the topic (case-insensitive)."""
    topic = topic.strip().lower()
    if not topic or not kb:
        return []
    blocks = re.split(r"\[p\d+\]", kb)
    hits = []
    terms = [w for w in re.findall(r"\w+", topic) if len(w) > 3]
    for b in blocks:
        bl = b.lower()
        score = sum(1 for w in terms if w in bl)
        if score >= max(1, len(terms) // 2):
            hits.append((score, b.strip()))
    hits.sort(key=lambda x: -x[0])
    return [h[1][:1200] for h in hits[:n]]

def books_reply(text):
    """'book <topic>' / 'search books <topic>' — LYA answers from YOUR books."""
    t = text.lower()
    for pre in ("search books", "search book", "book:", "book ", "in the books",
                "from the books", "what do the books say about"):
        if t.startswith(pre) or pre in t:
            topic = text[re.search(re.escape(pre), text, re.I).end():].strip() or text
            kb = _load_kb()
            if not kb:
                return ("📚 I couldn't load the books yet. Put your 3 PDFs in "
                        "lya/examples/ and run:  python lya/skills/build_knowledge.py")
            pages = _book_pages(kb, topic)
            if not pages:
                return (f"📚 I searched all 3 books for '{topic}' — nothing solid "
                        "came up. Try a shorter keyword, like 'buffer overflow'.")
            out = [f"📚 From YOUR books — '{topic}':"]
            for i, p in enumerate(pages, 1):
                out.append(f"\n— excerpt {i} —\n{p}")
            out.append("\nWant me to turn this into a lesson? Say 'hacker lesson on "
                       + topic + "' and I'll teach it properly.")
            return "\n".join(out)
    return None

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

# ------------------------------------------------------------- EXTRA CONTENT
PLAN = [
    "Week 1 — Recon: lessons 1–3 (scanning, LAN mapping, system fingerprinting)",
    "Week 2 — Vulnerabilities: lesson 4 + risky-service hunting on your own PC",
    "Week 3 — Passwords & crypto: lessons 5–6 (hashing, Base64, strength audits)",
    "Week 4 — Defense: lesson 7 hardening, re-run until every check is green",
    "Weeks 5–6 — Kali track: 'kali lesson 1..12' with LYA, one lesson a day",
    "Weeks 7–8 — TryHackMe beginner path, then PortSwigger Web Security Academy",
]
CHANNELS = [
    "NetworkChuck — networking & hacking, very beginner-friendly",
    "John Hammond — malware analysis & CTF walkthroughs",
    "The Cyber Mentor / TCM Security — full ethical-hacking courses",
    "David Bombal — networking, Kali, WiFi security",
    "LiveOverflow — deep, how-exploits-really-work series",
    "InsiderPhD — weekly CTF solutions, gentle learning curve",
]
LABS = [
    "TryHackMe — guided rooms, best starting point (free tier)",
    "PortSwigger Web Security Academy — free web-hacking labs",
    "Hack The Box Starting Point — real machines, free tier",
    "OverTheWire Bandit — Linux/command-line wargames (SSH)",
    "DVWA / Metasploitable — vulnerable VMs to run on YOUR machine",
    "PicoCTF — Carnegie Mellon's free beginner CTF",
]
COURSES = [
    "TCM Security 'Practical Ethical Hacking' — cheap, excellent",
    "Cybrary — free intro security courses",
    "Stanford CS155 — computer & network security (free lectures)",
    "OpenSecurityTraining2 — free deep-dive architecture/reversing",
    "PortSwigger Academy — the free web-security textbook-in-labs",
]

# ------------------------------------------------------------- DUO STATE
def _load_state():
    """Returns ({'me': set(), 'kaching': set()}, active_name)."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = f.read().splitlines()
        active = data[0].strip() if data else "me"
        sets = {"me": set(), "kaching": set()}
        for line in data[1:]:
            parts = line.split(":")
            if len(parts) == 2 and parts[0] in sets:
                sets[parts[0]] = set(int(x) for x in parts[1].split() if x.isdigit())
        return sets, (active if active in sets else "me")
    except Exception:
        return {"me": set(), "kaching": set()}, "me"

def _save_state(sets, active):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write(active + "\n")
            for who in ("me", "kaching"):
                f.write(f"{who}: " + " ".join(str(x) for x in sorted(sets[who])) + "\n")
    except Exception:
        pass

def _load_progress():
    sets, active = _load_state()
    return sets[active]

def _save_progress(done):
    sets, active = _load_state()
    sets[active] = set(done)
    _save_state(sets, active)

def _bar(done, total):
    return "█" * done + "░" * (total - done)

def _active_name():
    return "Kaching" if _load_state()[1] == "kaching" else "You"

def switch_to(who):
    sets, _ = _load_state()
    _save_state(sets, "kaching" if "kaching" in who.lower() else "me")
    name = "Kaching" if "kaching" in who.lower() else "you"
    done = sets["kaching" if name == "Kaching" else "me"]
    return (f"🔄 Keyboard handed to {name}. Progress: {_bar(len(done), 8)} "
            f"{len(done)}/8.\nSay 'hacker lesson {min(set(LESSONS) - done, default=1)}' "
            "to continue where you left off.")

def scoreboard():
    sets, active = _load_state()
    return ("🏆 DUO SCOREBOARD\n"
            f"  You     {_bar(len(sets['me']), 8)} {len(sets['me'])}/8\n"
            f"  Kaching {_bar(len(sets['kaching']), 8)} {len(sets['kaching'])}/8\n\n"
            f"Next up: {active}. Race responsibly. 😄")

def overview():
    sets, active = _load_state()
    done = sets[active]
    who = "Kaching's turn" if active == "kaching" else "Your turn"
    lines = [
        "🔥 HACKER TRAINER — I teach, you learn, we hack YOUR machine together.",
        f"{who}. Progress: {_bar(len(done), 8)} {len(done)}/8 lessons done.",
        "",
        "Say 'hacker lesson 1' (I teach) or 'hacker mission 1' (I run the tools live).",
        "Also: 'switch to kaching' / 'switch to me' / 'our progress' — or 'hacking plan'.",
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
    return (f"⚔️ MISSION {n} ({_active_name()}): {L['title']}\n\n"
            + (result or "(tool returned nothing)") + "\n\n"
            f"💬 {L['explain']}\n\n"
            + (f"🏆 Lesson {n} complete! {_bar(len(done), 8)} {len(done)}/8"
               if len(done) < 8 else "🏆 ALL 8 DONE — you graduate to TryHackMe next. 🎓"))

# ------------------------------------------------------------- ROUTER
def match(text):
    """True if this is a trainer command (allskills.py calls this)."""
    t = text.lower().strip()
    if t.startswith("kali") or "kali linux" in t:
        return False
    if "hacker lesson" in t or "hacker mission" in t:
        return True
    if t in ("learn hacking", "hacking lessons", "hacker curriculum", "teach me hacking",
             "hacking", "hacking plan", "hacker plan", "hacking channels",
             "hacker channels", "hacking labs", "hacker labs", "hacking courses",
             "hacker courses", "our progress", "hacker progress"):
        return True
    if t.startswith("switch to kaching") or t.startswith("switch to me"):
        return True
    return False

def reply(text, say=None, ask=None):
    t = text.lower().strip()
    if t.startswith("switch to kaching") or t.startswith("switch to me"):
        return switch_to("kaching" if "kaching" in t else "me")
    if "plan" in t:
        return ("🗓️ 8-week hacking plan — lessons → labs → certs:\n"
                + "\n".join("  " + p for p in PLAN)
                + "\n\nSay 'hacker lesson 1' to start week 1.")
    if "channel" in t:
        return ("📺 YouTube channels worth your time:\n"
                + "\n".join("  • " + c for c in CHANNELS))
    if "lab" in t:
        return ("🧪 Legal practice labs (hack ONLY these):\n"
                + "\n".join("  • " + l for l in LABS))
    if "course" in t:
        return ("🎓 Courses, free first:\n"
                + "\n".join("  • " + c for c in COURSES))
    if "our progress" in t:
        return scoreboard()
    m = re.search(r"(lesson|mission)\s*(\d+)", t)
    if m:
        n = int(m.group(2))
        return lesson(n) if m.group(1) == "lesson" else mission(n)
    return overview()
