"""LYA CLOUD EDITION — runs on Render/Hugging Face free tier.
Your iPhone reaches her from ANYWHERE, even with your laptop off.

Architecture:
- Brain: Groq API (free) — same as home
- Memory: Supabase free Postgres (persistent, survives restarts)
- Encryption: AES-256 (Fernet) with a key derived from YOUR secret passphrase.
  Even Supabase/Render staff see only encrypted blobs.
- Auth: phone token (LYA_PHONE_TOKEN) + passphrase-encrypted memory

Deploy guide: see cloud/README.md
"""
import os, sys, json, hashlib, base64
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
from urllib import request as urlreq
from cryptography.fernet import Fernet

# ---------- encryption (passphrase-based; DPAPI not available in cloud) ----------
SECRET = os.environ.get("LYA_PASSPHRASE", "")
if not SECRET:
    raise SystemExit("Set LYA_PASSPHRASE env var — the passphrase that encrypts your memories.")
F = Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET.encode()).digest()))

def enc(t): return F.encrypt(t.encode()).decode()
def dec(t): return F.decrypt(t.encode()).decode()

# ---------- Supabase memory (free Postgres, via REST — no SDK needed) ----------
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_KEY", "")

def sb_request(method, path, payload=None, query=""):
    req = urlreq.Request(f"{SB_URL}/rest/v1/{path}{query}", method=method,
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"},
        data=json.dumps(payload).encode() if payload else None)
    with urlreq.urlopen(req, timeout=15) as r:
        return json.loads(r.read() or b"[]")

def remember(kind, key, value, importance=1.0):
    sb_request("POST", "memories", {"kind": kind, "ekey": enc(key), "evalue": enc(value),
                                    "importance": importance})

def recall(limit=10, kind=None):
    q = "?select=*&order=importance.desc,created.desc&limit=200"
    rows = sb_request("GET", "memories", query=q)
    out = []
    for r in rows:
        if kind and r["kind"] != kind: continue
        try:
            out.append((dec(r["ekey"]), dec(r["evalue"]), r["kind"], r.get("hits", 0)))
        except Exception:
            continue   # row encrypted with a different passphrase — skip
        if len(out) >= limit: break
    return out

# ---------- the brain (same as home: Groq) ----------
def groq_reply(user_text):
    from brain.mind import HEADERS  # reuse browser-like headers
    key = os.environ.get("GROQ_API_KEY", "")
    facts = "\n".join(f"- ({k}) {v}" for k, v, *_ in recall(limit=15)) or "(still learning)"
    sys_prompt = (f"You are LYA, the admin's personal AI assistant — loyal, sharp, honest.\n"
                  f"You know these things about your admin:\n{facts}\n"
                  "If asked something unwise or harmful, say so and suggest the right way.")
    body = json.dumps({"model": "openai/gpt-oss-20b",
                       "messages": [{"role": "system", "content": sys_prompt},
                                    {"role": "user", "content": user_text}],
                       "max_tokens": 500}).encode()
    req = urlreq.Request("https://api.groq.com/openai/v1/chat/completions", data=body,
                         headers={**HEADERS, "Authorization": f"Bearer {key}"})
    with urlreq.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]

def lyas_answer(q):
    low = q.lower()
    if "remember" in low:
        fact = low.replace("remember", "").strip()
        remember("fact", fact.split()[0] if fact else "note", fact, 2)
        return "Stored in my cloud memory. I won't forget."
    if "what do you know" in low:
        rows = recall(limit=5)
        return "Here's what I remember: " + "; ".join(v for _, v, *_ in rows)
    reply = groq_reply(q)
    remember("conversation", low[:30], low)
    return reply


# ---------- LEVEL 3+4: TOP-LEVEL biometric wall (InsightFace + Resemblyzer) ----------
# Stored in the encrypted memories table under special kinds:
#   'biometric_face'   -> enrolled selfie (base64 jpeg, encrypted)
#   'biometric_voice'  -> enrolled voice sample (base64 audio, encrypted)
#   'biometric_phrase' -> the spoken secret keyword (encrypted text)
# Security: security/auth_wall.py — ArcFace face match + voiceprint match + keyword.

def get_biometric(kind):
    rows = sb_request("GET", "memories", query=f"?kind=eq.{kind}&select=evalue&limit=1")
    return dec(rows[0]["evalue"]) if rows else None

import base64 as b64mod
from security.auth_wall import AuthWall, face_embedding, voice_embedding, face_match, voice_match, keyword_match

def _wall():
    """Build the auth wall from enrolled templates (cached)."""
    global _WALL
    if _WALL is None:
        sf = b64mod.b64decode(get_biometric("biometric_face"))
        sv = b64mod.b64decode(get_biometric("biometric_voice"))
        _WALL = AuthWall(sf, sv)
    return _WALL
_WALL = None

def vault_unlock_check(selfie_b64=None, voice_b64=None):
    """Return (ok, message). Face + voiceprint + keyword must ALL pass."""
    stored_face = get_biometric("biometric_face")
    stored_voice = get_biometric("biometric_voice")
    stored_phrase = get_biometric("biometric_phrase")
    if not (stored_face and stored_voice and stored_phrase):
        return False, "No biometrics enrolled yet. Enroll first (from a trusted session)."
    if not selfie_b64: return False, "Live selfie required for vault access."
    if not voice_b64:  return False, "Speak your secret keyword for vault access."
    try:
        ok, report = _wall().verify(b64mod.b64decode(selfie_b64),
                                    b64mod.b64decode(voice_b64),
                                    dec(stored_phrase))
    except Exception as e:
        return False, f"Verification error: {e}"
    return ok, ("IDENTITY CONFIRMED - ArcFace face + voiceprint + keyword verified. Vault unlocked. [" + report + "]"
                if ok else f"Vault stays locked. [{report}]")

# ---------- reminder watcher: fires even when the laptop is off ----------
import threading

def _remind(topic, text):
    """Push a notification to the admin's phone via ntfy.sh (free)."""
    if not topic:
        return
    try:
        req = urlreq.Request(f"https://ntfy.sh/{topic}", data=text.encode(),
                             headers={"Title": "LYA reminder", "Priority": "high",
                                      "Tags": "bell"})
        urlreq.urlopen(req, timeout=10)
    except Exception:
        pass

def _watch_reminders(every=30):
    topic = os.environ.get("NTFY_TOPIC", "")
    from brain.sync import pull_due_cloud   # passphrase-based decryption, no DPAPI
    while True:
        try:
            for rid, what in pull_due_cloud():
                msg = (f"Reminder: {what}. That's happening now — "
                       f"you asked me not to let you forget.")
                _remind(topic, msg)
        except Exception:
            pass
        threading.Event().wait(every)

threading.Thread(target=_watch_reminders, daemon=True).start()

# ---------- the same lightweight phone UI ----------
from web_server import HTML   # identical interface, reuse it

TOKEN = os.environ.get("LYA_PHONE_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set LYA_PHONE_TOKEN env var — your private access token.")

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.end_headers(); self.wfile.write(body.encode())

    def _json(self, code, obj):
        self._send(code, json.dumps(obj), "application/json")

    def do_GET(self): self._send(200, HTML)

    def do_POST(self):
        self._json(503, {"error": "Legacy cloud actions are disabled until the shared identity protocol is configured."})

    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"LYA cloud edition live on port {port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
