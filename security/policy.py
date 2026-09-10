"""Explicit permissions. Model output and device tokens are never authority."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    role: str = "stranger"
    person: str = "guest"
    id: str = ""


PUBLIC = frozenset({"chat", "help", "time", "ui", "theme_preview", "stop"})
TRUSTED = frozenset({"open_app", "volume"})
OWNER = frozenset({"files", "theme_apply", "memory_read", "memory_write",
                   "memory_forget", "learn", "reminders", "screenshot",
                   "vault", "skill_draft", "council"})


def allowed(session, action, phone_approved=False):
    if action in PUBLIC:
        return True
    if action in TRUSTED:
        return session.role in {"admin", "friend", "secondary"}
    if action in OWNER:
        return session.role == "admin" and phone_approved
    return False  # new capabilities must deliberately join the policy


def require(session, action, phone_approved=False):
    if not allowed(session, action, phone_approved):
        raise PermissionError("This action requires an authorized session and, for private work, phone approval.")
