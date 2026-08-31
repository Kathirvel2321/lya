"""LYA's Brain — long-term memory stored in SQLite.
Every conversation, fact, preference, and skill gets remembered here.
LYA becomes smarter every day because everything is recalled before answering."""
import sqlite3, json, datetime, os

DB = os.path.join(os.path.dirname(__file__), "lya_brain.db")

def _conn():
    c = sqlite3.connect(DB)
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

def remember(kind, key, value, importance=1.0):
    c = _conn()
    c.execute("INSERT INTO memory(kind,key,value,importance,created) VALUES(?,?,?,?,?)",
              (kind, key, value, importance, datetime.datetime.now().isoformat()))
    c.commit(); c.close()

def recall(key=None, kind=None, limit=10):
    """Search memory — most important + most-reused first."""
    c = _conn()
    q = "SELECT key, value, kind, hits FROM memory WHERE 1=1"
    args = []
    if key:
        q += " AND (key LIKE ? OR value LIKE ?)"; args += [f"%{key}%", f"%{key}%"]
    if kind:
        q += " AND kind=?"; args.append(kind)
    q += " ORDER BY importance DESC, hits DESC, id DESC LIMIT ?"; args.append(limit)
    rows = c.execute(q, args).fetchall()
    c.close()
    return rows

def touch(key):
    """Every time LYA uses a memory it gets stronger (she favors what she uses)."""
    c = _conn()
    c.execute("UPDATE memory SET hits = hits+1 WHERE key LIKE ?", (f"%{key}%",))
    c.commit(); c.close()

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
              (name, json.dumps(face_encoding) if face_encoding is not None else None, voice_path))
    c.commit(); c.close()

def get_admin():
    c = _conn()
    row = c.execute("SELECT name, face_encoding, voice_path FROM admin WHERE id=1").fetchone()
    c.close()
    if not row: return None
    return {"name": row[0],
            "face_encoding": json.loads(row[1]) if row[1] else None,
            "voice_path": row[2]}
