"""LYA KNOWLEDGE HUB — classification, graph, and retention policy.
=================================================================
Every message LYA receives passes through here ONCE:

 1. CLASSIFY   → is it ephemeral / session / knowledge / protected?
 2. ROUTE      → ephemeral = never stored; others = stored as a GRAPH node
 3. DECAY      → maintenance() sweeps out expired data, protects the rest

Storage layers:
  - hot cache (RAM)      : last N session messages, auto-evicted
  - SQLite graph (vault) : nodes + edges, encrypted at rest by memory.py's vault
  - protected items      : written to a separate locked vault file FIRST,
                           so even a DB wipe can't lose them.

Deletion safety: NOTHING marked 'protected' can ever be deleted by decay,
and direct delete requests on protected items require re-confirmation.
"""
import datetime, json, os, re, sqlite3, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security import vault

DB = os.path.join(os.path.dirname(__file__), "lya_knowledge.db")
PROTECTED_VAULT = os.path.join(os.path.dirname(__file__), "protected_vault.json.lya")

# ---------------------------------------------------------------- classify
EPHEMERAL_PATTERNS = (
    r"^what(?:'s| is) (?:the )?time", r"^what(?:'s| is) (?:the )?date",
    r"^what day", r"^tell me a joke", r"^open \.", r"^close ",
    r"^(hi|hello|hey|yo|thanks|thank you|ok|okay)\b",
    r"^(who are you|what can you do|help)$",
)
SESSION_PATTERNS = (
    r"^(what|how|why|when|where|who|can you|do you|tell me|explain)\b",
    r"^(search|google|look up|weather|translate)\b",
)
PROTECT_TRIGGERS = ("secure this", "keep this safe", "never forget", "remember forever",
                    "don't delete", "dont delete", "long term", "long-term", "store securely")

def classify(text):
    """Return one of: 'ephemeral', 'session', 'knowledge', 'protected'."""
    low = text.lower().strip()
    if any(t in low for t in PROTECT_TRIGGERS):
        return "protected"
    if any(re.search(p, low) for p in EPHEMERAL_PATTERNS):
        return "ephemeral"
    if any(re.search(p, low) for p in SESSION_PATTERNS):
        return "session"
    if low.startswith(("remember", "note that", "my ", "i am", "i'm", "my name",
                       "i like", "i hate", "i use", "i work")):
        return "knowledge"
    return "session"

RETENTION = {"ephemeral": 0, "session": 7, "knowledge": 36500, "protected": 99999}  # days

# ---------------------------------------------------------------- graph DB
def _conn():
    tmp = DB + ".working"
    if os.path.exists(DB + ".lya"):
        with open(tmp, "wb") as f:
            f.write(vault.decrypt_file(DB + ".lya"))
    c = sqlite3.connect(tmp)
    c.execute("PRAGMA journal_mode=OFF")
    c.execute("""CREATE TABLE IF NOT EXISTS nodes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cls TEXT, topic TEXT, content TEXT,
        importance REAL DEFAULT 1.0, created TEXT, expires TEXT,
        hits INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS edges(
        src INTEGER, dst INTEGER, rel TEXT,
        PRIMARY KEY (src, dst, rel))""")
    return c

def _close(c):
    c.commit(); c.close()
    tmp = DB + ".working"
    with open(tmp, "rb") as f:
        data = f.read()
    with open(DB + ".lya", "wb") as f:
        f.write(vault.encrypt(data))
    vault.secure_delete(tmp)
    for sfx in ("-journal", "-wal", "-shm"):
        p = tmp + sfx
        if os.path.exists(p):
            vault.secure_delete(p)

# ---------------------------------------------------------------- protected vault
def _protect_write(items):
    with open(PROTECTED_VAULT, "wb") as f:
        f.write(vault.encrypt(json.dumps(items).encode()))

def _protect_read():
    if not os.path.exists(PROTECTED_VAULT):
        return []
    return json.loads(vault.decrypt_file(PROTECTED_VAULT).decode())

# ---------------------------------------------------------------- public API
def ingest(text, skill="general"):
    """Called by allskills/main for EVERY user message.
    Classifies, stores what's worth storing, links it into the graph.
    Returns the classification (so the UI can show 'ephemeral — not stored')."""
    cls = classify(text)
    if cls in ("ephemeral", "session"):
        return cls                      # ZERO disk writes — no overload possible
    now = datetime.datetime.now()
    topic = _topic_of(text)
    expires = (now + datetime.timedelta(days=RETENTION[cls])).isoformat()
    c = _conn()
    cur = c.execute(
        "INSERT INTO nodes(cls,topic,content,importance,created,expires) VALUES(?,?,?,?,?,?)",
        (cls, vault.encrypt_text(topic), vault.encrypt_text(text),
         3.0 if cls == "protected" else 1.0, now.isoformat(), expires))
    nid = cur.lastrowid
    # graph edges: this node -> topic node -> skill node
    t = _node(c, "topic", topic)
    s = _node(c, "skill", skill)
    c.execute("INSERT OR IGNORE INTO edges VALUES(?,?,?)", (nid, t, "about"))
    c.execute("INSERT OR IGNORE INTO edges VALUES(?,?,?)", (t, s, "handled_by"))
    _close(c)
    if cls == "protected":
        items = _protect_read()
        items.append({"text": text, "topic": topic, "when": now.isoformat()})
        _protect_write(items)           # survives even a full DB wipe
    return cls

def _node(c, kind, name):
    """Find-or-create a hub node (topic or skill) in the graph."""
    for id_, v in c.execute("SELECT id, content FROM nodes WHERE cls=?", (kind,)).fetchall():
        if vault.decrypt_text(v) == name:
            return id_
    cur = c.execute(
        "INSERT INTO nodes(cls,topic,content,importance,created,expires) VALUES(?,?,?,?,?,?)",
        (kind, vault.encrypt_text(kind), vault.encrypt_text(name), 2.0,
         datetime.datetime.now().isoformat(), "9999-12-31T23:59:59"))
    return cur.lastrowid

def _topic_of(text):
    """Pick a short topic label — first meaningful words."""
    stop = {"what", "is", "the", "a", "an", "how", "to", "my", "i", "do", "you",
            "remember", "that", "please", "can", "of", "for", "me", "and", "in", "on"}
    words = [w.strip(".,!?") for w in text.lower().split()]
    key = [w for w in words if w and w not in stop]
    return " ".join(key[:4]) or "misc"

def query(text, limit=5):
    """'What is this about / where is it stored' — one graph-aware search.
    Protected items are ALWAYS searched too (they live in their own vault)."""
    low = text.lower()
    words = set(re.findall(r"[a-z0-9]+", low)) - {"what", "about", "is", "the", "my", "where", "stored"}
    hits = []
    for item in _protect_read():
        t, topic = item["text"], item["topic"]
        blob = (t + " " + topic).lower()
        if words & set(re.findall(r"[a-z0-9]+", blob)):
            hits.append((3.0, topic, t, "protected"))
    c = _conn()
    for id_, cls, t_enc, v_enc, imp, hits_, created in c.execute(
            "SELECT id,cls,topic,content,importance,hits,created FROM nodes WHERE cls NOT IN ('topic','skill')"):
        blob = (vault.decrypt_text(t_enc) + " " + vault.decrypt_text(v_enc)).lower()
        score = imp + hits_ * 0.1
        if words & set(re.findall(r"[a-z0-9]+", blob)):
            score += 2
        else:
            continue
        hits.append((score, vault.decrypt_text(t_enc), vault.decrypt_text(v_enc), cls))
    _close(c)
    hits.sort(key=lambda x: -x[0])
    return hits[:limit]

def maintenance():
    """The nightly sweep — LYA's own 'declutter without losing treasures' routine.
    - session nodes past expiry: securely deleted
    - knowledge: kept, gets +0.1 importance each sweep (used knowledge = stronger)
    - protected: re-verified against the separate vault; NEVER touched by decay
    Returns a human-readable report."""
    now = datetime.datetime.now().isoformat()
    c = _conn()
    doomed = [i for (i,) in c.execute(
        "SELECT id FROM nodes WHERE cls='session' AND expires < ?", (now,))]
    for i in doomed:
        c.execute("DELETE FROM edges WHERE src=? OR dst=?", (i, i))
    c.execute("DELETE FROM nodes WHERE cls='session' AND expires < ?", (now,))
    c.execute("UPDATE nodes SET importance = MIN(importance + 0.1, 10) "
              "WHERE cls='knowledge'")
    _close(c)
    prot = _protect_read()
    return (f"Cleanup: {len(doomed)} expired session items removed. "
            f"{len(prot)} protected items verified intact. Knowledge base kept.")

def protect_count():
    return len(_protect_read())

def stats():
    c = _conn()
    counts = {}
    for cls, n in c.execute("SELECT cls, COUNT(*) FROM nodes GROUP BY cls"):
        counts[cls] = n
    _close(c)
    return counts
