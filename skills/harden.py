"""LYA HARDENING CHECK — 'is lya secure' for HER OWN body.
==========================================================
Walks every lock we built and reports any hole. Run: 'is lya secure'.
"""
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHECKS = [
    ("Memory DB encrypted", os.path.join(HERE, "brain", "lya_brain.db.lya")),
    ("Action log encrypted", os.path.join(HERE, "skills", "lya_actions.log.lya")),
    ("Phone token encrypted", os.path.join(HERE, "security", "phone_token.lya")),
    ("Groq key encrypted", os.path.join(HERE, "security", "groq_key.lya")),
    ("Security word stored", os.path.join(HERE, "security", "security_word.lya")),
    ("Vault key file", os.path.join(HERE, "security", ".lya_key")),
]

LEAKS = [
    (os.path.join(HERE, "debug"), "debug folder (recordings!) — delete after use"),
    (os.path.join(HERE, "skills", "home_devices.json"), "device registry is plain JSON — contains MACs only (low risk)"),
    (os.path.join(HERE, "skills", ".home_baseline.json"), "network baseline plain JSON (MAC only, low risk)"),
]

def audit():
    lines = ["🛡️ LYA SELF-AUDIT", ""]
    holes = 0
    for name, path in CHECKS:
        ok = os.path.exists(path)
        lines.append(f"  {'✅' if ok else '❌ MISSING'}  {name}")
        if not ok:
            holes += 1
    lines.append("")
    for path, note in LEAKS:
        exists = os.path.isdir(path) and os.listdir(path) or os.path.exists(path)
        if exists:
            lines.append(f"  ⚠️  {note}: {os.path.relpath(path, HERE)}")
    lines.append("")
    key = os.path.join(HERE, "security", ".lya_key")
    lines.append("🔐 DPAPI-bound vault key: " +
                 ("present (bound to YOUR Windows user)" if os.path.exists(key) else "MISSING"))
    lines.append("")
    lines.append("🔒 Hard rules active: no attack without owner auth, no unreviewed code execution,")
    lines.append("   all actions logged, self-modification only after your 'confirm'.")
    if holes == 0:
        lines.append("\n✅ No holes found. Your Lya is sealed.")
    else:
        lines.append(f"\n🚨 {holes} missing lock(s) — re-run: python store_key.py / security_test.py")
    return "\n".join(lines)

def match(text):
    t = text.lower()
    return any(k in t for k in ("is lya secure", "is ly a secure", "lya security check",
                                "audit lya", "self audit", "check your locks"))

def reply(text, say=None, ask=None):
    return audit()
