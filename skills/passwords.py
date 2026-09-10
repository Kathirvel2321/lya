"""Password vault skill — AES-256 encrypted at rest, DPAPI-bound.

Storage is delegated to security/vault.py (Fernet + Windows DPAPI), the same
layer that protects the memory brain and face templates. Nothing here ever
touches the disk as plaintext.

Admin can save/list passwords by voice or text. Read-only for secondary users.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security import vault

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VAULT = os.path.join(_ROOT, "security", "passwords.lya")

# Pre-fix location: plaintext JSON. Migrated and shredded on first load.
_LEGACY_PLAINTEXT = os.path.join(_ROOT, "memory", "vault.json")


def _migrate_legacy():
    """One-time rescue of the old plaintext vault.json, then secure-delete it.
    Runs before every load so an old file dropped in later is still caught."""
    if not os.path.exists(_LEGACY_PLAINTEXT):
        return
    try:
        with open(_LEGACY_PLAINTEXT, "r", encoding="utf-8") as f:
            legacy = json.load(f)
    except Exception:
        legacy = None
    if legacy:
        merged = _read()
        merged.update(legacy)      # legacy entries win; they are the newer edit
        _write(merged)
        print(f"[LYA] Migrated {len(legacy)} password(s) from plaintext into the "
              f"encrypted vault.")
    vault.secure_delete(_LEGACY_PLAINTEXT)
    print(f"[LYA] Shredded the old plaintext vault at {_LEGACY_PLAINTEXT}")


def _read():
    """Decrypt the vault. A corrupt/unreadable vault raises — it must never
    silently look empty, or save() would overwrite real passwords with {}."""
    if not os.path.exists(_VAULT):
        return {}
    return json.loads(vault.decrypt_file(_VAULT).decode())


def _write(data):
    os.makedirs(os.path.dirname(_VAULT), exist_ok=True)
    with open(_VAULT, "wb") as f:
        f.write(vault.encrypt(json.dumps(data).encode()))


def _load():
    _migrate_legacy()
    return _read()


def save(site, password):
    """Store a password for a site/app. Overwrites silently."""
    data = _load()
    data[site.strip().lower()] = password
    _write(data)
    return f"Saved the password for {site.strip()}."


def list_sites():
    """Site names only — safe to speak aloud. Prefer this over list_all()."""
    return sorted(_load().keys())


def list_all():
    """Return [(site, password), ...]. Caller is responsible for the fact that
    this returns live secrets — do not speak these through a TTS engine in a
    room you do not control."""
    return sorted(_load().items())


def get(site):
    return _load().get(site.strip().lower())


def forget(site):
    data = _load()
    if data.pop(site.strip().lower(), None) is None:
        return f"I have no password saved for {site.strip()}."
    _write(data)
    return f"Deleted the password for {site.strip()}."


if __name__ == "__main__":
    # Self-check: round-trip through real encryption, verify the file on disk
    # is genuinely unreadable as plaintext, then restore the original vault.
    import shutil, tempfile
    backup = None
    if os.path.exists(_VAULT):
        backup = tempfile.mktemp(suffix=".lya")
        shutil.copy2(_VAULT, backup)
    try:
        os.path.exists(_VAULT) and os.remove(_VAULT)
        save("example.com", "hunter2-correct-horse")
        assert get("example.com") == "hunter2-correct-horse", "round-trip failed"
        assert get("EXAMPLE.COM ") == "hunter2-correct-horse", "site key not normalised"

        raw = open(_VAULT, "rb").read()
        assert b"hunter2" not in raw, "PASSWORD FOUND IN PLAINTEXT ON DISK"
        assert raw.startswith(b"gAAAAA"), "not a Fernet token"

        assert list_sites() == ["example.com"], "list_sites wrong"
        assert "Deleted" in forget("example.com"), "forget failed"
        assert get("example.com") is None, "still present after forget"
        print("passwords.py self-check PASSED - encrypted at rest, no plaintext leak")
    finally:
        os.path.exists(_VAULT) and os.remove(_VAULT)
        if backup:
            shutil.copy2(backup, _VAULT)
            os.remove(backup)
