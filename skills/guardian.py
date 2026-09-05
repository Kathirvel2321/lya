"""LYA's conscience — the Ultron safety layer.
Action logs are encrypted so a snooper can't see what commands were run."""
import datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security import vault

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
    enc = os.path.join(os.path.dirname(__file__), "lya_actions.log.lya")
    entry = f"{datetime.datetime.now().isoformat()} | {'ALLOWED' if allowed else 'BLOCKED'} | {cmd}\n"
    history = vault.decrypt_file(enc).decode() if os.path.exists(enc) else ""
    with open(enc, "wb") as f:
        f.write(vault.encrypt((history + entry).encode()))
