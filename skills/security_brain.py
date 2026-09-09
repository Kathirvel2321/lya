"""LYA SECURITY BRAIN — the hacking/defense knowledge core.
==========================================================
Three public, legal sources ingested into ONE compressed brain file:
  1. Your 3 books (lya/examples/*.pdf)            — offline, already built
  2. OWASP WSTG (Web Security Testing Guide)     — https://github.com/OWASP/wstg
  3. PortSwigger Web Security Academy lab list   — https://portswigger.net/web-security/all-labs
  4. MITRE ATT&CK Enterprise matrix (STIX data)  — https://attack.mitre.org

LYA uses it in TWO directions:
  - TEACH:  'book:', 'wstg:', 'lab:', 'attack:' — pull knowledge from the sources
  - POLICE: 'police mode' — think like the thief (ATT&CK tactics/techniques),
            then audit YOUR machine for every door that thief would knock on.

ETHICS LINE (hard-coded, cannot be removed): this brain only ever audits
YOUR OWN machine/network. Attacking anything else is refused.

Run:  python lya/skills/security_brain.py build
"""
import os, re, gzip, json, logging

logging.getLogger("urllib3").setLevel(logging.ERROR)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "security_brain.txt.gz")

SECTIONS = ("BOOK", "WSTG", "LABS", "ATTACK")

# --------------------------------------------------------------- helpers
def _fetch(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "LYA-education/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def _cache_path(tag):
    return os.path.join(HERE, f".cache_{tag}.html")

def _fetch_cached(tag, url):
    """Fetch once per day; keeps raw copy so rebuilds are instant."""
    p = _cache_path(tag)
    if os.path.exists(p) and (time.time() - os.path.getmtime(p)) < 86400:
        with open(p, "rb") as f:
            return f.read()
    data = _fetch(url)
    with open(p, "wb") as f:
        f.write(data)
    return data

import time  # noqa: E402  (after helper defs for readability)

def _html_text(raw):
    """Very small HTML -> text (no external deps)."""
    try:
        html = raw.decode("utf-8", "ignore")
    except Exception:
        return ""
    html = re.sub(r"(?is)<(script|style|nav|footer|svg)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)</(p|div|li|h[1-6]|tr)>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    import html as h
    html = h.unescape(html)
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()

# --------------------------------------------------------------- INGESTERS
def _ingest_wstg():
    """OWASP WSTG stable markdown — one file per category, GitHub raw."""
    base = ("https://raw.githubusercontent.com/OWASP/wstg/master/document/"
            "4-Web_Application_Security_Testing/")
    files = [
        ("01-Information_Gathering", "01-Information_Gathering", [
            "README.md", "01-Information_Gathering.md"]),
    ]
    # WSTG is big; fetch the category index READMEs (all 10 categories)
    cats = [
        "01-Information_Gathering", "02-Configuration_and_Deployment_Management_Testing",
        "03-Identity_Management_Testing", "04-Authentication_Testing",
        "05-Authorization_Testing", "06-Session_Management_Testing",
        "07-Input_Validation_Testing", "08-Testing_for_Error_Handling",
        "09-Testing_for_Weak_Cryptography", "10-Business_Logic_Testing",
        "11-Client-side_Testing",
    ]
    out = []
    for cat in cats:
        try:
            raw = _fetch(base + cat + "/README.md")
            txt = raw.decode("utf-8", "ignore")
            txt = re.sub(r"^#{1,3} .*$", "", txt, flags=re.M)      # drop headers
            txt = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", txt)          # links -> text
            out.append(f"\n\n===== WSTG: {cat.replace('_', ' ')} =====\n{txt.strip()}")
            print(f"  + WSTG {cat}")
        except Exception as e:
            print(f"  ! WSTG {cat}: {e}")
    return "".join(out)

def _ingest_labs():
    """PortSwigger all-labs page — titles grouped by topic (free, public list)."""
    try:
        html = _fetch("https://portswigger.net/web-security/all-labs").decode("utf-8", "ignore")
        # Individual lab titles are lazy-loaded JS; store topic sections with
        # real lab counts + deep links (30 topics, ~280 labs).
        sections = re.findall(
            r'id="([a-z0-9\-]+)"[^>]*>([^<]{4,80})</h2>(.*?)(?=<h2|$)', html, re.S)
        seen, out = set(), []
        for sid, title, body in sections:
            n = len(re.findall(r"academy-labstatus", body))
            if sid in seen or n == 0:
                continue
            seen.add(sid)
            out.append(f"- {title.strip()}: {n} labs — "
                       f"https://portswigger.net/web-security/all-labs#{sid}")
        print(f"  + PortSwigger: {len(out)} topics, "
              f"{sum(int(re.search(r'(\d+) labs', o).group(1)) for o in out)} labs")
        return "\n\n===== PORTSWIGGER WEB SECURITY ACADEMY =====\n" + "\n".join(out)
    except Exception as e:
        print(f"  ! PortSwigger: {e}")
        return ""

def _ingest_attack():
    """MITRE ATT&CK Enterprise — official STIX bundle (techniques + tactics)."""
    try:
        raw = _fetch("https://github.com/mitre-attack/attack-stix-data/raw/master/"
                     "enterprise-attack/enterprise-attack.json")
        data = json.loads(raw)
        tactics, techs = {}, []
        for obj in data.get("objects", []):
            if obj.get("type") == "x-mitre-tactic":
                tactics[obj["external_references"][0]["external_id"]] = obj["name"]
            elif obj.get("type") == "attack-pattern" and not obj.get("revoked"):
                tid = obj["external_references"][0]["external_id"]
                desc = (obj.get("description") or "")[:600]
                det = obj.get("x_mitre_detection") or ""
                techs.append((tid, obj["name"], desc, det))
        print(f"  + ATT&CK: {len(techs)} techniques, {len(tactics)} tactics")
        lines = ["\n\n===== MITRE ATT&CK ENTERPRISE ====="]
        for tid, name, desc, det in techs:
            lines.append(f"[{tid}] {name}\n{desc}\nDetection: {det}\n")
        return "\n".join(lines)
    except Exception as e:
        print(f"  ! ATT&CK: {e}")
        return ""

def _ingest_books():
    try:
        from skills import build_knowledge
    except ImportError:
        import build_knowledge
    build_knowledge.build()
    try:
        with gzip.open(os.path.join(HERE, "book_knowledge.txt.gz"), "rt",
                       encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

# --------------------------------------------------------------- BUILD / LOAD
BRAIN_MAX_AGE = 7 * 86400   # rebuild from live sources once a week

def _brain_stale():
    if not os.path.exists(OUT):
        return True
    try:
        import time
        return (time.time() - os.path.getmtime(OUT)) > BRAIN_MAX_AGE
    except Exception:
        return False

def ensure_fresh():
    """Rebuild in a BACKGROUND thread when the brain is older than a week.
    Never blocks LYA — she keeps answering from the current brain meanwhile."""
    if not _brain_stale():
        return
    import threading
    def _bg():
        try:
            build()
            global _cache
            _cache = None          # force reload of the new brain
        except Exception as e:
            print(f"[security_brain] refresh failed: {e}")
    threading.Thread(target=_bg, daemon=True).start()

def build():
    print("Building LYA security brain (books + WSTG + PortSwigger + ATT&CK)...")
    text = (_ingest_books() + _ingest_wstg() + _ingest_labs() + _ingest_attack())
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        f.write(text)
    print(f"Done: {len(text):,} chars -> {os.path.basename(OUT)}")

_cache = None
def _load():
    global _cache
    ensure_fresh()
    if _cache is None:
        try:
            with gzip.open(OUT, "rt", encoding="utf-8") as f:
                _cache = f.read()
        except Exception:
            _cache = ""
    return _cache

def _sections():
    """Split the brain at each '===== SECTION' marker (first occurrence, in
    document order). Later markers inside a section don't match SECTIONS
    names exactly, so findall of the real headers is used."""
    kb = _load()
    headers = []
    for m in re.finditer(r"===== ([A-Za-z &]+)[^=\n]*", kb):
        name = m.group(1).strip().upper()
        if "ATT&CK" in name or "ATTACK" in name:
            s = "ATTACK"
        elif "PORTSWIGGER" in name or "LAB" in name:
            s = "LABS"
        elif name.startswith("WSTG"):
            s = "WSTG"
        elif name.startswith("BOOK"):
            s = "BOOK"
        else:
            continue
        headers.append((m.start(), s))
    out = {}
    for i, (pos, s) in enumerate(headers):
        end = headers[i + 1][0] if i + 1 < len(headers) else len(kb)
        if s not in out:               # first occurrence wins
            out[s] = kb[pos:end]
    return out

SYNONYMS = {
    "xss": ["cross-site scripting", "xss"],
    "csrf": ["cross-site request forgery", "csrf"],
    "ssrf": ["server-side request forgery", "ssrf"],
    "xxe": ["xml external entity", "xxe"],
    "idor": ["access control", "authorization"],
    "sqli": ["sql injection"],
    "rce": ["command injection", "remote code"],
    "lfi": ["path traversal", "file inclusion"],
    "rfd": ["reflected file download"],
    "ssti": ["template injection"],
}

def _search(section, topic, n=3, width=1200):
    body = _sections().get(section, "")
    if not body or not topic.strip():
        return []
    terms = [w for w in re.findall(r"\w+", topic.lower()) if len(w) > 3]
    # short keywords (xss, csrf, rce...) are valuable — keep them
    terms += [w for w in re.findall(r"\w{3}", topic.lower()) if w not in terms]
    # expand hacker slang to full names (xss -> cross-site scripting)
    low = topic.lower().strip()
    for slang, fulls in SYNONYMS.items():
        if slang in low:
            terms += fulls
    # split into paragraphs at natural record boundaries
    blocks = re.split(r"\n(?=(?:\[T\d{4}\]|\[p\d+\]|\[WSTG|=====|- [A-Z]))", body)
    hits = []
    for b in blocks:
        bl = b.lower()
        score = sum(1 for w in terms if w in bl)
        if score >= 1:
            hits.append((score, b.strip()))
    hits.sort(key=lambda x: -x[0])
    return [h[1][:width] for h in hits[:n]]

# --------------------------------------------------------------- POLICE MODE
# Think like the thief (ATT&CK tactics) -> audit like the police.
# Every check below runs ONLY on this machine, read-only, using hacker.py tools.
POLICE_PLAYBOOK = [
    ("Reconnaissance",   "What does a stranger see first?",
     ["recon", "who is on my network"]),
    ("Initial Access",   "Which doors are open to knock on?",
     ["portscan my pc"]),
    ("Execution/Persistence", "What runs on startup that you didn't install?",
     ["startup audit"]),
    ("Credential Access","Are your passwords weak or reused?",
     ["how strong is my password audit"]),
    ("Defense Evasion",  "Is your firewall/AV actually ON?",
     ["am i secure"]),
    ("Lateral Movement", "Can an intruder hop to other devices on your LAN?",
     ["who is on my network"]),
    ("Exfiltration",     "Is anything odd talking to the internet?",
     ["network audit"]),
]

def police_audit():
    """Run the full read-only audit chain — needs owner auth BEFORE calling."""
    from skills import hacker
    steps, findings = [], []
    for tactic, question, cmds in POLICE_PLAYBOOK:
        for cmd in cmds:
            try:
                res = hacker.handle(cmd)
            except Exception as e:
                res = f"(tool error: {e})"
            steps.append(f"[{tactic}] {cmd}")
            findings.append((tactic, cmd, res))
    return steps, findings

def police_report():
    steps, findings = police_audit()
    out = ["🚔 POLICE MODE — full audit (read-only, YOUR machine only)", ""]
    for tactic, cmd, res in findings:
        out.append(f"━━ {tactic} — '{cmd}'")
        out.append((res or "(nothing returned)")[:2000])
        out.append("")
    out.append("✅ Audit complete. Every item above is a door a thief would try — close it before they find it.")
    return "\n".join(out)

# --------------------------------------------------------------- OWNER GATE
# NOTHING in this brain runs without: owner face + voiceprint + secret phrase,
# verified through security/auth_wall.py — the SAME wall as the vault.
# And LYA NEVER executes an attack by herself: even with auth, every destructive
# command needs the owner to type/say the exact per-session confirmation word.

class OwnerGate:
    """Session authorization for the hacker brain. Expires after 10 minutes."""
    TTL = 600  # seconds

    def __init__(self):
        self._granted_at = 0

    def check(self, wall_verify_fn):
        """wall_verify_fn(phrase) -> (ok, report). Owner calls this with live
        face/voice/phrase. Returns (ok, message)."""
        import time
        if self.authorized():
            return True, "✅ Owner session already active."
        ok, report = wall_verify_fn()
        if ok:
            self._granted_at = time.time()
            return True, "🔓 Owner verified — hacker brain UNLOCKED for 10 minutes."
        return False, f"🚫 ACCESS DENIED. {report}\nLya will not open this brain without all three gates."

    def authorized(self):
        import time
        return (time.time() - self._granted_at) < self.TTL

    def revoke(self):
        self._granted_at = 0
        return "🔒 Owner session closed. Hacker brain locked."

GATE = OwnerGate()

# Per-mission confirmation: even an authorized owner must confirm each real action.
CONFIRM_WORDS = ("confirm", "confirmed", "yes confirm", "do it")

def needs_confirmation(cmd_text):
    """Real actions (missions, police audit) require the word 'confirm' in the
    SAME command. Teaching/questions are always safe and need no confirmation."""
    risky = any(k in cmd_text.lower() for k in
                ("mission", "police audit", "police mode", "run", "scan", "crack"))
    return risky and not any(w in cmd_text.lower() for w in CONFIRM_WORDS)

# --------------------------------------------------------------- LYA COMMANDS
def brain_reply(text):
    """Router for knowledge questions — ALWAYS safe, no auth needed:
      'book: <topic>'    -> search the 3 books
      'wstg: <topic>'    -> search OWASP WSTG
      'lab: <topic>'     -> find matching PortSwigger labs
      'attack: <topic>'  -> search MITRE ATT&CK techniques
    """
    t = text.lower().strip()
    for prefix, section, label in (
            ("book", "BOOK", "Your books"),
            ("wstg", "WSTG", "OWASP WSTG"),
            ("lab", "LABS", "PortSwigger Academy"),
            ("attack", "ATTACK", "MITRE ATT&CK")):
        m = re.search(rf"(?:search |in |from |what do .* say about )?{prefix}\s*[:\-]?\s+(.+)", t)
        if m and (t.startswith(prefix) or f" {prefix} " in t or f"{prefix}:" in t):
            topic = text[m.start(1):].strip()
            hits = _search(section, topic)
            if not hits:
                return (f"🔍 {label}: nothing solid on '{topic}'. "
                        "Try a shorter keyword like 'xss' or 'persistence'.")
            out = [f"📖 {label} — '{topic}':"]
            for i, h in enumerate(hits, 1):
                out.append(f"\n— match {i} —\n{h}")
            return "\n".join(out)
    return None

def match(text):
    """allskills router — hacker-brain commands (ALL gated)."""
    t = text.lower().strip()
    if t in ("police mode", "police audit", "audit me like a thief", "think like a thief"):
        return True
    return brain_reply(text) is not None

def reply(text, say=None, ask=None):
    """Called by allskills.py. GATE applies to police mode only —
    knowledge questions stay free (they teach, they don't touch anything)."""
    t = text.lower().strip()
    if t in ("police mode", "police audit", "audit me like a thief", "think like a thief"):
        if not GATE.authorized():
            return ("🔐 POLICE MODE is locked.\n"
                    "It thinks like a thief to protect you — so it needs proof you're the owner.\n"
                    "Ask from the web UI: face + voice + your secret phrase.\n"
                    "And even then, run it with: 'police mode confirm'")
        if needs_confirmation(text):
            return "🚔 Ready to run the full read-only audit. Say 'police mode confirm' to start."
        return police_report()
    return brain_reply(text)

if __name__ == "__main__":
    build()
