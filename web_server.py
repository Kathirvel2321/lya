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

APPROVE_HTML = """<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Approve LYA task</title><style>body{font:18px system-ui;background:#10151c;color:#e6edf5;max-width:32rem;margin:auto;padding:24px}input,button{font:inherit;padding:12px;box-sizing:border-box;width:100%;margin:8px 0}video{width:100%}</style>
<h1>Approve laptop task</h1><p id="task">Load the pending task before approving.</p>
<input id="token" type="password" placeholder="Paired phone token" autocomplete="off">
<button onclick="loadTask()">Load pending task</button>
<video id="camera" autoplay muted playsinline></video>
<input id="phrase" type="password" placeholder="Owner security phrase" autocomplete="off">
<button id="approve" onclick="approveTask()" disabled>Verify and approve once</button><p id="status" role="status"></p>
<script>
let challenge=null,stream=null;
async function post(path,extra={}){const body=new URLSearchParams({token:document.getElementById('token').value,...extra});const r=await fetch(path,{method:'POST',body});return r.json()}
async function loadTask(){try{challenge=await post('/challenge');document.getElementById('task').textContent=challenge.task||challenge.error;if(!challenge.nonce)return;stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'}});document.getElementById('camera').srcObject=stream;document.getElementById('approve').disabled=false}catch(e){document.getElementById('status').textContent='Camera unavailable. Use trusted HTTPS and allow camera access.'}}
async function approveTask(){document.getElementById('approve').disabled=true;try{const v=document.getElementById('camera');const c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);const r=await post('/escalate',{nonce:challenge.nonce,frame:c.toDataURL('image/jpeg',.85).split(',')[1],phrase:document.getElementById('phrase').value});document.getElementById('status').textContent=r.msg||r.error}catch(e){document.getElementById('status').textContent='Approval failed. Reload the task.'}finally{document.getElementById('phrase').value='';if(stream)stream.getTracks().forEach(t=>t.stop())}}
</script>"""

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
        if self.path in ("/escalate", "/verify"):
            return self._send(200, APPROVE_HTML)
        if self.path == "/enroll":
            return self._send(403, "Enrollment is deferred.")
        return self._send(200, HTML)

    def _check_token(self, data):
        # compare_digest, not ==: a plain string compare short-circuits on the
        # first wrong byte and leaks the token one character at a time.
        if not hmac.compare_digest(data.get("token", [""])[0], TOKEN):
            self._send(403, json.dumps({"error": "wrong token - access denied"}), "application/json")
            return False
        return True

    def do_POST(self):
        if self.path not in ("/ask", "/challenge", "/escalate", "/verify_identity", "/enroll_face", "/enroll_voice"):
            return self._send(404, "not found")
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2_000_000:
                return self._send(413, "Invalid request size")
            data = parse_qs(self.rfile.read(size).decode())
            if not self._check_token(data):
                return
            if self.path.startswith("/enroll"):
                return self._send(403, json.dumps({"error": "Enrollment is deferred; a phone token cannot replace the owner."}), "application/json")
            if self.path == "/challenge":
                challenge = escalation.current_challenge()
                return self._send(200, json.dumps(challenge or {"error": "No pending task."}), "application/json")
            if self.path in ("/escalate", "/verify_identity"):
                import ssl
                if not isinstance(self.connection, ssl.SSLSocket):
                    return self._send(403, json.dumps({"error": "Phone verification requires HTTPS."}), "application/json")
                if escalation._locked_out():
                    return self._send(429, json.dumps({"error": "Verification is locked. Try later."}), "application/json")
                challenge = escalation.current_challenge()
                nonce = data.get("nonce", [""])[0]
                if not challenge or not hmac.compare_digest(nonce, challenge["nonce"]):
                    return self._send(403, json.dumps({"error": "Task expired or changed. Refresh its details."}), "application/json")
                from vision import identity
                phrase = data.get("phrase", [""])[0]
                ok = escalation.check_security_word(phrase) == "ok"
                if ok:
                    ok, detail = identity.verify_owner(_b64_to_bytes(data.get("frame", [""])[0]))
                if not ok:
                    escalation._record_failure()
                    return self._send(403, json.dumps({"error": "Verification failed; task remains blocked."}), "application/json")
                # Re-read after biometric processing: never approve a replacement task.
                current = escalation.current_challenge()
                if not current or not hmac.compare_digest(nonce, current["nonce"]):
                    return self._send(403, json.dumps({"error": "Task expired."}), "application/json")
                escalation.phone_approve(nonce=nonce)
                escalation._reset_attempts()
                return self._send(200, json.dumps({"ok": True, "msg": "Approved this task once."}), "application/json")
            q = data.get("q", [""])[0].strip()
            # Gateway chat has no private session and no executable skills.
            return self._send(200, json.dumps({"reply": lyas_answer(q, verified=False), "verified": False}), "application/json")
        except Exception:
            return self._send(400, json.dumps({"error": "Request failed; no approval issued."}), "application/json")

    def log_message(self, *a):   # quiet logs
        pass

def main():
    import ssl
    port = int(os.environ.get("LYA_PHONE_PORT", "5000"))
    cert, key = os.environ.get("LYA_TLS_CERT"), os.environ.get("LYA_TLS_KEY")
    if not cert or not key:
        raise SystemExit("Configure LYA_TLS_CERT and LYA_TLS_KEY for trusted HTTPS before phone approval. Enrollment remains deferred.")
    srv = HTTPServer((os.environ.get("LYA_PHONE_HOST", "127.0.0.1"), port), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, key)
    srv.socket = context.wrap_socket(srv.socket, server_side=True)
    print(f"LYA phone approval: HTTPS port {port}. Open /escalate on your paired phone.")
    srv.serve_forever()


if __name__ == "__main__":
    main()
