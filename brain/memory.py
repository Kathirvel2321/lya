"""LYA's Brain — long-term memory stored in SQLite, FULLY ENCRYPTED at rest.
Every fact, conversation, and the admin identity are encrypted with AES-256
before touching the disk (security/vault.py). A stolen lya_brain.db is
gibberish without your Windows account's DPAPI key."""
import sqlite3, json, datetime, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security import vault

DB = os.path.join(os.path.dirname(__file__), "lya_brain.db")

# Migrate old unencrypted DB if it exists
if os.path.exists(DB):
    try:
        c = sqlite3.connect(DB)
        c.execute("SELECT count(*) FROM memory").fetchone()
        c.close()
        vault.encrypt_file(DB)          # old DB -> lya_brain.db.lya
    except sqlite3.DatabaseError:
        pass                            # already encrypted

def _conn():
    """Open the encrypted DB: decrypt to a private temp file, use, shred it."""
    tmp = DB + ".working"
    if os.path.exists(DB + ".lya"):
        with open(tmp, "wb") as f:
            f.write(vault.decrypt_file(DB + ".lya"))
    c = sqlite3.connect(tmp)
    c.execute("PRAGMA journal_mode=OFF")   # no stray WAL plaintext
    c.execute("""CREATE TABLE IF NOT EXISTS memory(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT,           -- 'fact' | 'preference' | 'conversation' | 'skill' | 'correction'
        key TEXT,            -- short name / topic
        value TEXT,          -- the content
        importance REAL DEFAULT 1.0,
        created TEXT,
        hits INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS admin(
        id INTEGER PRIMARY KEY CHECK (id=1),
        name TEXT, face_encoding TEXT, voice_path TEXT)""")
    return c

def _close(c):
    """Commit, close, re-encrypt to the real vault file, shred the plaintext copy."""
    c.commit(); c.close()
    tmp = DB + ".working"
    with open(tmp, "rb") as f:
        data = f.read()
    with open(DB + ".lya", "wb") as f:
        f.write(vault.encrypt(data))
    vault.secure_delete(tmp)          # plaintext working copy gone forever
    # shred any journal leftovers
    for suffix in ("-journal", "-wal", "-shm"):
        p = tmp + suffix
        if os.path.exists(p):
            vault.secure_delete(p)

def remember(kind, key, value, importance=1.0):
    c = _conn()
    c.execute("INSERT INTO memory(kind,key,value,importance,created) VALUES(?,?,?,?,?)",
              (kind, vault.encrypt_text(key), vault.encrypt_text(value),
               importance, datetime.datetime.now().isoformat()))
    _close(c)

def recall(key=None, kind=None, limit=10):
    """Search memory — encrypted LIKE works on encrypted blobs, so we decrypt-scan.
    For a personal-scale brain (thousands of rows) this is instant."""
    c = _conn()
    q, args = "SELECT kind, key, value, importance, hits, created FROM memory WHERE 1=1", []
    if kind:
        q += " AND kind=?"; args.append(kind)
    q += " ORDER BY importance DESC, hits DESC, id DESC"
    rows = []
    for kind_, k_enc, v_enc, imp, hits, created in c.execute(q, args):
        k, v = vault.decrypt_text(k_enc), vault.decrypt_text(v_enc)
        if key and key.lower() not in k.lower() and key.lower() not in v.lower():
            continue
        rows.append((k, v, kind_, hits))
        if len(rows) >= limit:
            break
    _close(c)
    return rows

def touch(key):
    """Every time LYA uses a memory it gets stronger (she favors what she uses)."""
    c = _conn()
    for id_, k_enc in c.execute("SELECT id, key FROM memory").fetchall():
        if key.lower() in vault.decrypt_text(k_enc).lower():
            c.execute("UPDATE memory SET hits=hits+1 WHERE id=?", (id_,))
    _close(c)

def think(prompt):
    """Before answering, LYA 'thinks' — pulls relevant memories about you."""
    results = recall(key=prompt.split()[0] if prompt else None)
    for k, v, *_ in results:
        touch(k)
    return results

def set_admin(name, face_encoding=None, voice_path=None):
    c = _conn()
    c.execute("DELETE FROM admin")
    c.execute("INSERT INTO admin(id,name,face_encoding,voice_path) VALUES(1,?,?,?)",
              (vault.encrypt_text(name),
               vault.encrypt_text(json.dumps(face_encoding)) if face_encoding is not None else None,
               vault.encrypt_text(voice_path) if voice_path else None))
    _close(c)

def get_admin():
    c = _conn()
    row = c.execute("SELECT name, face_encoding, voice_path FROM admin WHERE id=1").fetchone()
    _close(c)
    if not row: return None
    return {"name": vault.decrypt_text(row[0]),
            "face_encoding": json.loads(vault.decrypt_text(row[1])) if row[1] else None,
            "voice_path": vault.decrypt_text(row[2]) if row[2] else None}
