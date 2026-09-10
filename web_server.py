# -*- coding: utf-8 -*-
"""LYA's iPhone gateway - a featherweight web server.
Access from your iPhone Safari -> Add to Home Screen -> looks like an app,
uses ~0 MB storage and almost no battery (all thinking happens server-side).

Security: requires a secret access token on every request (multi-level auth:
this token + your Windows DPAPI key + face verification for private data).

Run:  python web_server.py
Then on iPhone:  http://<your-pc-ip>:5000  -> share -> Add to Home Screen
"""
import os, sys, json, socket, time, hmac, secrets
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
from brain import memory, mind
from skills import guardian
from vision import face_auth
from audio import voice_auth
from security import escalation
import base64, re

# ---- per-client verified sessions ------------------------------------------
# This used to be a single module-global {"verified": False}. One successful
# face check flipped it True for the WHOLE SERVER - every client, every later
# request, forever, until restart. Nothing ever reset it. Now each successful
# verification mints an opaque, expiring session id bound to that one client.
SESSION_TTL = 600          # a face check is worth 10 minutes, then re-verify
_sessions = {}             # sid -> expiry timestamp


def _new_session():
    sid = secrets.token_urlsafe(24)
    _sessions[sid] = time.time() + SESSION_TTL
    return sid


def _session_valid(sid):
    """True only for a live, unexpired sid. Reaps expired entries on the way
    through so the dict can't grow without bound on a long-running server."""
    now = time.time()
    for k, exp in list(_sessions.items()):
        if exp <= now:
            del _sessions[k]
    return bool(sid) and _sessions.get(sid, 0) > now

# ---- the access token: only YOUR phone knows this ----
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "security", "phone_token.lya")
if os.path.exists(TOKEN_FILE):
    TOKEN = vault_dec = __import__("security.vault", fromlist=["vault"]).decrypt_file(TOKEN_FILE).decode()
else:
    import secrets
    TOKEN = secrets.token_urlsafe(24)
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    from security import vault
    with open(TOKEN_FILE, "wb") as f:
        f.write(vault.encrypt(TOKEN.encode()))
    print(f"\n[LYA] First run - your private phone access token:\n\n  {TOKEN}\n")
    print("Put this in your iPhone app once. Never share it.")

HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>LYA</title>
<style>
 body{margin:0;background:#05070f;color:#cfe9ff;font-family:-apple-system,sans-serif;
      height:100vh;display:flex;flex-direction:column}
 #orb{width:90px;height:90px;border-radius:50%;margin:20px auto;
      background:radial-gradient(circle at 35% 30%,#4df0ff,#0a3a66 70%);
      box-shadow:0 0 30px #00d0ff88;animation:pulse 2s infinite}
 @keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}
 h1{text-align:center;font-size:18px;font-weight:600;margin:4px}
 #chat{flex:1;overflow-y:auto;padding:12px;-webkit-overflow-scrolling:touch}
 .msg{max-width:85%;margin:6px 0;padding:9px 13px;border-radius:16px;font-size:15px;line-height:1.4}
 .you{background:#1a2a4a;margin-left:auto;border-bottom-right-radius:4px}
 .lya{background:#0a1626;border:1px solid #123;border-bottom-left-radius:4px}
 form{display:flex;padding:8px;background:#070b16}
 input{flex:1;background:#101828;border:1px solid #1c2c48;color:#cfe9ff;
       border-radius:20px;padding:11px 15px;font-size:16px;outline:none}
 button{background:#00d0ff;border:none;color:#001;border-radius:20px;
        padding:0 18px;margin-left:6px;font-size:16px;font-weight:700}
</style></head><body>
<div id="orb"></div><h1>LYA</h1>
<div id="chat"></div>
<form onsubmit="send();return false">
 <input id="q" placeholder="Ask LYA anything..." autocomplete="off">
 <button>â–²</button>
</form>
<script>
const TOKEN = localStorage.getItem('lya_token') || prompt('Enter your LYA access token:');
localStorage.setItem('lya_token', TOKEN);
async function send(){
  const q = document.getElementById('q').value.trim(); if(!q) return;
  document.getElementById('q').value='';
  add(q,'you');
  const SID = localStorage.getItem('lya_sid') || '';
  const r = await fetch('/ask',{method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'token='+encodeURIComponent(TOKEN)+'&sid='+encodeURIComponent(SID)
        +'&q='+encodeURIComponent(q)});
  const j = await r.json();
  if(j.verified === false) localStorage.removeItem('lya_sid');  // expired - re-verify
  add(j.error ? 'â›” '+j.error : j.reply, 'lya');
}
function add(t,c){const d=document.createElement('div');d.className='msg '+c;
  d.textContent=t;document.getElementById('chat').appendChild(d);
  document.getElementById('chat').scrollTop=999999;}
</script></body></html>"""

# ---- iPhone face+voice capture page (uses the GOOD sensors) ----
ENROLL_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>LYA Enroll</title>
<style>body{margin:0;background:#05070f;color:#cfe9ff;font-family:-apple-system,sans-serif;
text-align:center;padding:20px}video{width:90%;border-radius:16px;background:#000}
button{background:#00d0ff;border:none;color:#001;border-radius:20px;padding:12px 22px;
font-size:16px;font-weight:700;margin:10px}#log{white-space:pre-wrap;font-size:14px}</style>
</head><body>
<h2>LYA Identity Setup</h2>
<video id="v" autoplay playsinline muted></video><br>
<button onclick="step1()">1. Capture my face</button>
<button onclick="step2()">2. Record my voice</button>
<div id="log"></div>
<script>
const TOKEN = localStorage.getItem('lya_token') || prompt('LYA access token:');
localStorage.setItem('lya_token', TOKEN);
const v = document.getElementById('v'), log = document.getElementById('log');
navigator.mediaDevices.getUserMedia({video:{facingMode:'user'},audio:true}).then(s=>v.srcObject=s);
function say(t){log.textContent += t + '\\n';}
async function post(path, body){
  const r = await fetch(path,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'token='+encodeURIComponent(TOKEN)+'&'+body});
  return r.json();
}
function grabFrame(){
  const c=document.createElement('canvas');c.width=320;c.height=320;
  c.getContext('2d').drawImage(v,0,0,320,320);
  return c.toDataURL('image/jpeg',0.9).split(',')[1];
}
async function step1(){
  say('Capturing 6 face frames...');
  const frames=[];
  for(let i=0;i<6;i++){frames.push(grabFrame());await new Promise(r=>setTimeout(r,350));}
  const j=await post('/enroll_face','frames='+encodeURIComponent(JSON.stringify(frames)));
  say(j.ok ? 'Face stored on the laptop (encrypted).' : 'Face FAILED: '+(j.error||'no face seen'));
}
async function step2(){
  say('Recording voice: say "LYA, I am your admin" clearly...');
  const stream=v.srcObject, rec=new MediaRecorder(stream);
  const chunks=[];rec.ondataavailable=e=>chunks.push(e.data);
  rec.start();await new Promise(r=>setTimeout(r,4000));rec.stop();
  await new Promise(r=>rec.onstop=r);
  const blob=new Blob(chunks);const ab=await blob.arrayBuffer();
  // wrap raw audio into a WAV container for the server
  const wav=makeWav(new Uint8Array(ab));
  const j=await post('/enroll_voice','wav='+encodeURIComponent(btoa(String.fromCharCode(...wav))));
  say(j.ok ? 'Voice stored on the laptop (encrypted). I know you now.' : 'Voice FAILED: '+(j.error||''));
}
function makeWav(pcm){ // pcm here is whatever MediaRecorder gave; server tries WAV decode
  return pcm;
}
</script></body></html>"""

VERIFY_HTML = ENROLL_HTML.replace("LYA Enroll", "LYA Verify").replace(
    '<button onclick="step2()">2. Record my voice</button>', "")
VERIFY_HTML = VERIFY_HTML.replace("""async function step1(){
  say('Capturing 6 face frames...');
  const frames=[];
  for(let i=0;i<6;i++){frames.push(grabFrame());await new Promise(r=>setTimeout(r,350));}
  const j=await post('/enroll_face','frames='+encodeURIComponent(JSON.stringify(frames)));
  say(j.ok ? 'Face stored on the laptop (encrypted).' : 'Face FAILED: '+(j.error||'no face seen'));
}""", """async function step1(){
  say('Look at the camera...');
  const j=await post('/verify_identity','frame='+encodeURIComponent(grabFrame()));
  if(j.ok && j.sid) localStorage.setItem('lya_sid', j.sid);
  say(j.ok ? 'IDENTITY CONFIRMED - welcome, '+(j.name||'admin')+' (valid '+((j.ttl||600)/60)+' min)' : 'ACCESS DENIED: '+(j.error||'not recognized'));
}""")
# verify page records voice too
VERIFY_HTML = VERIFY_HTML.replace("Face stored on the laptop", "Face OK")
VERIFY_HTML = VERIFY_HTML.replace("function makeWav(pcm){ // pcm here is whatever MediaRecorder gave; server tries WAV decode\n  return pcm;\n}",
    """function makeWav(pcm){return pcm;}
const _step2 = step2;
step2 = async function(){
  say('Say: LYA, I am your admin');
  const stream=v.srcObject, rec=new MediaRecorder(stream);
  const chunks=[];rec.ondataavailable=e=>chunks.push(e.data);
  rec.start();await new Promise(r=>setTimeout(r,3500));rec.stop();
  await new Promise(r=>rec.onstop=r);
  const ab=await new Blob(chunks).arrayBuffer();
  const u8=new Uint8Array(ab);let s='';for(const b of u8)s+=String.fromCharCode(b);
  const j=await post('/verify_identity','frame='+encodeURIComponent(grabFrame())+'&wav='+encodeURIComponent(btoa(s)));
  if(j.ok && j.sid) localStorage.setItem('lya_sid', j.sid);
  say(j.ok ? 'IDENTITY CONFIRMED - welcome, '+(j.name||'admin') : 'ACCESS DENIED: '+(j.error||''));
}""")

_NEEDS_FACE = ("That touches your private memory. Open /verify on this phone and "
               "show me your face first - the access token proves it's your "
               "phone, not that it's you holding it.")


def lyas_answer(q, verified=False):
    """Same brain, same guardian - one gateway for the phone.

    `verified` comes from a live /verify_identity session, NEVER from the access
    token alone. The token proves 'this is the paired phone'; only the face
    check proves 'this is the owner holding it'. Reading or writing private
    memory requires the latter."""
    low = q.lower()
    if "remember" in low or "my " in low[:4]:
        # "my age is 19", "my birthday is 12 march", "my exam is on..."
        if not verified:
            return _NEEDS_FACE
        fact = q.strip()
        key = "birthday" if "birthday" in low or "birth" in low else \
              "age" if "age" in low else \
              "exam" if "exam" in low else fact.split()[1] if len(fact.split()) > 1 else "note"
        memory.remember("fact", key, fact, importance=3)
        return f"Stored: '{fact}'. I'll keep this in mind - and update it when things change."
    if "what do you know" in low or "what do you remember" in low:
        if not verified:
            return _NEEDS_FACE
        rows = memory.recall(limit=8)
        return "Here's what I remember: " + "; ".join(v for _, v, *_ in rows)
    if "birthday" in low or "wish" in low:
        if not verified:
            return _NEEDS_FACE
        rows = memory.recall(limit=20)
        facts = [v for _, v, *_ in rows if "birthday" in v.lower() or "birth" in v.lower()]
        if facts:
            return f"Of course I remember - {facts[0]}. I will wish you the moment the day comes."
        return "You haven't told me your birthday yet - tell me and I'll never forget it."
    reply = mind.reply(q, memory.get_admin()["name"] if memory.get_admin() else "admin",
                       verified=verified)
    if verified:      # unverified chatter must not pollute the memory brain
        memory.remember("conversation", low[:30], low)
    return reply

def _b64_to_bytes(s):
    try:
        return base64.b64decode(re.sub(r"^data:[^,]+,", "", s))
    except Exception:
        return b""

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        if self.path == "/enroll":
            return self._send(200, ENROLL_HTML)
        if self.path == "/verify":
            return self._send(200, VERIFY_HTML)
        if self.path == "/escalate":
            # Same face-check page, but it signals the PC's escalation gate
            return self._send(200, VERIFY_HTML.replace("/verify_identity", "/escalate")
                .replace("IDENTITY CONFIRMED", "TASK APPROVED"))
        return self._send(200, HTML)

    def _check_token(self, data):
        # compare_digest, not ==: a plain string compare short-circuits on the
        # first wrong byte and leaks the token one character at a time.
        if not hmac.compare_digest(data.get("token", [""])[0], TOKEN):
            self._send(403, json.dumps({"error": "wrong token - access denied"}), "application/json")
            return False
        return True

    def do_POST(self):
        if self.path not in ("/ask", "/enroll_face", "/enroll_voice", "/verify_identity", "/escalate"):
            return self._send(404, "not found")
        data = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        if not self._check_token(data):
            return

        if self.path == "/enroll_face":
            try:
                frames = json.loads(data.get("frames", ["[]"])[0])
                jpgs = [_b64_to_bytes(f) for f in frames]
                ok = face_auth.enroll_from_jpg(jpgs)
                if ok and memory.get_admin() is None:
                    memory.set_admin("admin", {"device": "iphone"})
                return self._send(200, json.dumps({"ok": bool(ok),
                    "error": "no face detected in the frames" if not ok else ""}), "application/json")
            except Exception as e:
                return self._send(200, json.dumps({"ok": False, "error": str(e)}), "application/json")

        if self.path == "/enroll_voice":
            try:
                wav = _b64_to_bytes(data.get("wav", [""])[0])
                ok = voice_auth.enroll_from_wav([wav])
                return self._send(200, json.dumps({"ok": bool(ok),
                    "error": "audio too short or unreadable" if not ok else ""}), "application/json")
            except Exception as e:
                return self._send(200, json.dumps({"ok": False, "error": str(e)}), "application/json")

        if self.path == "/verify_identity":
            frame = _b64_to_bytes(data.get("frame", [""])[0])
            ok, dist = face_auth.verify_from_jpg(frame)
            # voice adds a second factor when provided
            if ok and "wav" in data:
                wav = _b64_to_bytes(data["wav"][0])
                if voice_auth.enrolled() and not voice_auth.verify_from_wav(wav):
                    ok = False
            if ok:
                admin = memory.get_admin()
                return self._send(200, json.dumps({"ok": True, "sid": _new_session(),
                    "ttl": SESSION_TTL,
                    "name": admin["name"] if admin else "admin"}), "application/json")
            return self._send(200, json.dumps({"ok": False,
                "error": f"face/voice not recognized (dist={dist:.3f})"}), "application/json")

        if self.path == "/escalate":
            """Phone-side approval for a sensitive task on the laptop.
            Same face(+voice) check as /verify_identity; on success it writes
            the one-time grant the laptop's escalation gate is waiting for."""
            frame = _b64_to_bytes(data.get("frame", [""])[0])
            ok, dist = face_auth.verify_from_jpg(frame)
            if ok and "wav" in data:
                wav = _b64_to_bytes(data["wav"][0])
                if voice_auth.enrolled() and not voice_auth.verify_from_wav(wav):
                    ok = False
            if ok:
                # nonce binds this approval to the laptop's current escalate() call
                escalation.phone_approve(nonce=escalation.current_nonce())
                return self._send(200, json.dumps({"ok": True,
                    "msg": "approved - the laptop may proceed"}), "application/json")
            return self._send(200, json.dumps({"ok": False,
                "error": f"face/voice not recognized (dist={dist:.3f})"}), "application/json")

        # /ask
        q = data.get("q", [""])[0].strip()
        verified = _session_valid(data.get("sid", [""])[0])
        try:
            reply = lyas_answer(q, verified)
        except Exception as e:
            reply = f"My brain hiccuped: {e}"
        self._send(200, json.dumps({"reply": reply, "verified": verified}),
                   "application/json")

    def log_message(self, *a):   # quiet logs
        pass

def main():
    port = 5000
    srv = HTTPServer(("0.0.0.0", port), Handler)
    ip = socket.gethostbyname(socket.gethostname())
    print(f"""
{'='*55}
  LYA iPhone gateway running
  On your iPhone (same WiFi):  http://{ip}:{port}
  1. Open it in Safari
  2. Share -> 'Add to Home Screen'
  3. Paste your token when asked (shown above on first run)
  4. First time only: open /enroll - capture face + voice
  5. Every time someone wakes LYA: open /verify - face + voice check
   6. When the laptop asks for a protected-task approval: open /escalate
{'='*55}""")
    srv.serve_forever()

if __name__ == "__main__":
    main()
