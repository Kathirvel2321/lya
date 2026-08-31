"""LYA's conscience — the Ultron safety layer.
Before any destructive/secure action, LYA checks herself AND re-verifies
your face + voice. If you ask her to do something harmful, she refuses
and explains why — like you asked."""
import datetime
from vision import face_auth

DANGEROUS = ["format", "del /", "rm -rf", "rmdir", "shutdown", "reg delete",
             "diskpart", "cipher /w", "vssadmin delete", "bcdedit"]

PASSWORDS_FILE = "lya_vault.txt"  # never accessed without verification

def is_dangerous(command):
    low = command.lower()
    return any(d in low for d in DANGEROUS)

def guard(command, action):
    """Returns (allowed, message). Secure + dangerous actions need re-verification."""
    if not is_dangerous(command):
        return True, action()
    if face_auth.verify():
        result = action()
        return True, f"Verified. {result}"
    return False, "That's a dangerous command and I could not verify you. I won't do it."

def correct_user(text):
    """LYA is allowed to push back when you're wrong — you asked for this."""
    notes = {
        "delete": "Heads up: that deletes things permanently. Sure you want it? Say 'confirm' to proceed.",
        "shutdown": "You'll lose unsaved work. Say 'confirm' if you really mean it.",
    }
    for k, msg in notes.items():
        if k in text.lower():
            return msg
    return None

def log_action(cmd, allowed):
    with open("lya_actions.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat()} | {'ALLOWED' if allowed else 'BLOCKED'} | {cmd}\n")
