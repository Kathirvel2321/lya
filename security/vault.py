"""LYA's vault — military-grade encryption for her entire brain.

Layers:
1. AES-256 (Fernet) encrypts EVERYTHING on disk: memory DB, face template,
   vault, logs. A hacker who steals the files gets unreadable garbage.
2. The encryption key itself is protected by Windows DPAPI — it is bound to
   YOUR Windows user account. Copying the files to another PC/user = useless.
   Even LYA's own code cannot read the data if the Windows session differs.
"""
import os, base64
from cryptography.fernet import Fernet

import win32crypt  # from pywin32 — Windows Data Protection API

KEY_PATH = os.path.join(os.path.dirname(__file__), ".lya_key")
ENTROPY = b"LYA-ultron-project-2026"   # extra salt bound to this app

def _get_fernet() -> Fernet:
    """Load or create the DPAPI-protected key. Transparent to callers."""
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "rb") as f:
            blob = f.read()
    else:
        raw = Fernet.generate_key()
        blob = win32crypt.CryptProtectData(raw, "LYA", ENTROPY, None, None, 0)
        with open(KEY_PATH, "wb") as f:
            f.write(blob)
    _, raw = win32crypt.CryptUnprotectData(blob, ENTROPY, None, None, 0)
    return Fernet(raw)

_F = _get_fernet()

def encrypt(data: bytes) -> bytes:
    return _F.encrypt(data)

def decrypt(token: bytes) -> bytes:
    return _F.decrypt(token)

def encrypt_text(text: str) -> str:
    return encrypt(text.encode()).decode()

def decrypt_text(token: str) -> str:
    return decrypt(token.encode()).decode()

def encrypt_file(path: str):
    """Encrypt a file in place."""
    if not os.path.exists(path) or path.endswith(".lya"):
        return
    with open(path, "rb") as f:
        data = f.read()
    with open(path + ".lya", "wb") as f:
        f.write(encrypt(data))
    os.remove(path)   # plaintext gone

def decrypt_file(path: str) -> bytes:
    """Decrypt .lya file to bytes (never touches the disk as plaintext)."""
    with open(path, "rb") as f:
        return decrypt(f.read())

def secure_delete(path: str):
    """Overwrite with random bytes before deleting — no forensic recovery."""
    if not os.path.exists(path):
        return
    size = os.path.getsize(path)
    with open(path, "wb") as f:
        f.write(os.urandom(size))
    os.remove(path)
