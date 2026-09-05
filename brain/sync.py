"""brain/sync.py — one LYA, two bodies.

The laptop brain stores memories with DPAPI encryption; the cloud brain uses
your LYA_PASSPHRASE. They can never read each other's raw rows, so this module
keeps them in step by comparing DECRYPTED content and re-encrypting with the
destination's key. Everything crossing the internet is always ciphertext.

Env needed (only if you want cloud sync — everything is free):
    SUPABASE_URL, SUPABASE_KEY, LYA_PASSPHRASE   (same values as Render)

Usage:
    from brain import sync
    sync.sync_reminders()          # push due/pending reminders up + pull down
    sync.push_reminder(text, when) # called by skills/reminder.py on add()
    sync.sync_memories()           # laptop -> cloud memory backup (one way)
    sync.status()                  # quick health print
"""
import os, datetime, json, urllib.request

HOME = os.path.join(os.path.dirname(__file__), "..", "data", "reminders.db")


def _env():
    return (os.environ.get("SUPABASE_URL", "").rstrip("/"),
            os.environ.get("SUPABASE_KEY", ""))


def cloud_ready():
    u, k = _env()
    return bool(u and k)


def _sb(method, path, payload=None):
    """Minimal Supabase REST call — no SDK needed."""
    u, k = _env()
    req = urllib.request.Request(
        f"{u}/rest/v1/{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"apikey": k, "Authorization": f"Bearer {k}",
                 "Content-Type": "application/json", "Prefer": "return=representation"},
        method=method)
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read().decode()
    return json.loads(body) if body else []


# ---------------------------------------------------------------- reminders
def push_reminder(what, when):
    """Mirror one local reminder to the cloud (encrypted with the passphrase)."""
    if not cloud_ready():
        return False
    from security import vault
    try:
        from cloud.lya_cloud import enc
    except Exception:
        return False
    rows = _sb("GET", f"reminders?what=eq.{enc(what or 'reminder')}&done=eq.false&select=id")
    if rows:
        return True  # already there
    _sb("POST", "reminders", {"what": enc(what or "reminder"),
                              "when_iso": enc(when.isoformat()),
                              "fired": False})
    return True


def pull_due_cloud():
    """Cloud reminders that are due right now (used by the cloud watcher)."""
    from cloud.lya_cloud import dec
    now = datetime.datetime.now().isoformat(timespec="seconds")
    rows = _sb("GET", "reminders?fired=eq.false&done=eq.false&select=id,what,when_iso")
    out = []
    for r in rows:
        try:
            t = dec(r["when_iso"])
        except Exception:
            continue  # encrypted with a different passphrase — skip
        if t <= now:
            out.append((r["id"], dec(r["what"])))
            _sb("PATCH", f"reminders?id=eq.{r['id']}", {"fired": True})
    return out


def pull_future_cloud():
    """Bring cloud-created reminders down to the laptop brain."""
    from security import vault
    import sqlite3
    from cloud.lya_cloud import dec
    if not cloud_ready():
        return 0
    rows = _sb("GET", "reminders?fired=eq.false&done=eq.false&select=id,what,when_iso")
    c = sqlite3.connect(HOME)
    c.execute("""CREATE TABLE IF NOT EXISTS reminders(
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 what TEXT, when_iso TEXT, done INTEGER DEFAULT 0,
                 fired INTEGER DEFAULT 0, created TEXT)""")
    n = 0
    for r in rows:
        try:
            what, when = dec(r["what"]), dec(r["when_iso"])
        except Exception:
            continue
        dup = c.execute("SELECT what FROM reminders WHERE done=0").fetchall()
        have = any(what.lower() in vault.decrypt_text(w).lower()
                   for (_, w) in dup)
        if not have:
            c.execute("INSERT INTO reminders(what,when_iso,created) VALUES(?,?,?)",
                      (vault.encrypt_text(what), vault.encrypt_text(when),
                       datetime.datetime.now().isoformat()))
            n += 1
    c.commit(); c.close()
    return n


# ---------------------------------------------------------------- memories
def sync_memories(limit=500):
    """One-way backup: newest local memories -> cloud (encrypted there too)."""
    from security import vault
    if not cloud_ready():
        return 0
    existing = {r["ekey"] for r in _sb("GET", f"memories?select=ekey&order=id.desc&limit={limit * 3}")}
    import sqlite3
    mem_db = os.path.join(os.path.dirname(__file__), "..", "data", "memory.db")
    if not os.path.exists(mem_db):
        return 0
    c = sqlite3.connect(mem_db)
    rows = c.execute("SELECT kind, ekey, evalue, importance FROM memories "
                     "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    try:
        from cloud.lya_cloud import enc
    except Exception:
        return 0
    sent = 0
    for kind, ekey, evalue, imp in rows:
        try:
            plain_key = vault.decrypt_text(ekey)
            plain_val = vault.decrypt_text(evalue)
        except Exception:
            continue  # row belongs to a different machine user — skip
        ck = enc(plain_key)
        if ck in existing:
            continue
        _sb("POST", "memories", {"kind": kind, "ekey": ck,
                                 "evalue": enc(plain_val),
                                 "importance": imp or 1})
        sent += 1
    return sent


def status():
    if not cloud_ready():
        return "cloud sync not configured (SUPABASE_URL / SUPABASE_KEY missing)"
    n = len(_sb("GET", "memories?select=id&limit=1000"))
    m = len(_sb("GET", "reminders?select=id&limit=1000"))
    return f"cloud reachable — {n} memories, {m} reminders mirrored"
