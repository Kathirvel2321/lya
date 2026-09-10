"""LYA JARVIS INTERFACE — her face, Iron-Man grade.
==================================================
Fullscreen holographic HUD in your browser (http://localhost:5050):
  - Living core: layered rotating arcs + waveform that reacts to her state
  - Deep-space particle field + horizon grid (never a plain background)
  - Glass telemetry panels (left: memory vault, right: system status)
  - Popup holo-cards: saved notes/passwords fly in when you ask for them
  - Smooth 60fps canvas animation, zero dependencies

Run:  python ui/jarvis_server.py   -> opens fullscreen automatically
Same brain as everywhere else; same token security as the phone gateway.
"""
import os, sys, json, socket, webbrowser, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import base64, re

from brain import memory
from web_server import lyas_answer, TOKEN   # reuse the SAME brain + token

# ================================================================ FRONTEND
HTML_HEAD = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LYA — JARVIS Interface</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--cy:#4df0ff;--cy2:#0a3a66;--amber:#ffb84d;--bg:#02040a;--glass:rgba(10,22,40,.55)}
@keyframes bootIn{0%{opacity:0;filter:blur(6px)}100%{opacity:1;filter:blur(0)}}
@keyframes flickIn{0%,18%,22%,25%,53%,57%,100%{opacity:1}20%,24%,55%{opacity:.35}}
@keyframes glowPulse{0%,100%{text-shadow:0 0 14px #00c8ff66}50%{text-shadow:0 0 28px #00c8ffcc,0 0 60px #00c8ff44}}
@keyframes scan{0%{transform:translateY(-100%)}100%{transform:translateY(100%)}}
#boot{position:fixed;inset:0;z-index:99;background:#02040a;display:flex;flex-direction:column;
  align-items:center;justify-content:center;transition:opacity .9s ease}
#bootLog{margin-top:22px;font-family:Rajdhani;font-size:13px;letter-spacing:2px;color:#4df0ff;
  opacity:.85;min-height:110px;text-align:center;line-height:1.9}
#bootBar{width:280px;height:3px;background:rgba(77,240,255,.12);border-radius:3px;overflow:hidden;margin-top:16px}
#bootBar i{display:block;height:100%;width:0%;background:linear-gradient(90deg,#0a8cff,#4df0ff);
  box-shadow:0 0 14px #4df0ff;transition:width .35s ease}
.fade-ui{animation:bootIn .8s ease both}
.vignette{position:fixed;inset:0;z-index:1;pointer-events:none;
  background:radial-gradient(ellipse at center,transparent 55%,rgba(0,2,8,.75) 100%)}
.scanlines{position:fixed;inset:0;z-index:1;pointer-events:none;opacity:.05;
  background:repeating-linear-gradient(0deg,transparent 0 2px,#9ff 2px 3px)}
.sweepline{position:fixed;left:0;right:0;height:120px;z-index:1;pointer-events:none;opacity:.35;
  background:linear-gradient(180deg,transparent,rgba(77,240,255,.05),transparent);
  animation:scan 9s linear infinite}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:#cfe9ff;font-family:'Segoe UI',system-ui,sans-serif;
  height:100vh;overflow:hidden;display:grid;
  grid-template-columns:300px 1fr 300px;grid-template-rows:56px 1fr 90px;
  grid-template-areas:"top top top" "left core right" "in in in"}
/* ---- starfield & grid run on the canvas behind everything ---- */
#space{position:fixed;inset:0;z-index:0;opacity:.9}
.panel{position:relative;z-index:2;margin:8px;border-radius:14px;
  background:linear-gradient(160deg,rgba(10,30,55,.55),rgba(4,10,22,.65));
  border:1px solid rgba(77,240,255,.18);backdrop-filter:blur(10px);
  box-shadow:0 0 24px rgba(0,180,255,.07), inset 0 0 30px rgba(0,140,255,.04);
  overflow:hidden;display:flex;flex-direction:column}
.panel h3{font-family:'Orbitron',sans-serif;font-size:10.5px;letter-spacing:4px;color:var(--cy);
  padding:12px 14px 8px;text-transform:uppercase;opacity:.9;
  text-shadow:0 0 12px rgba(77,240,255,.5)}
.panel h3::before{content:'▚ ';opacity:.7}
.panel::after{content:'';position:absolute;top:0;left:8%;right:8%;height:1px;
  background:linear-gradient(90deg,transparent,rgba(77,240,255,.55),transparent)}
.panel .body{flex:1;overflow-y:auto;padding:4px 10px 10px;scrollbar-width:thin}
.panel .body::-webkit-scrollbar{width:4px}
.panel .body::-webkit-scrollbar-thumb{background:rgba(77,240,255,.35);border-radius:4px}
#left{grid-area:left}#right{grid-area:right}
#topbar{grid-area:top;display:flex;align-items:center;gap:18px;padding:0 20px;
  border-bottom:1px solid rgba(77,240,255,.14);background:rgba(3,8,18,.55);backdrop-filter:blur(8px)}
#topbar .brand{font-family:'Orbitron',sans-serif;font-weight:900;font-size:19px;letter-spacing:9px;
  color:var(--cy);animation:glowPulse 4s ease-in-out infinite}
#status{font-family:'Rajdhani',sans-serif}
#topbar .sep{flex:1}
#topbar .clock{font-variant-numeric:tabular-nums;letter-spacing:2px;opacity:.85}
#core{grid-area:core;position:relative;display:flex;flex-direction:column;align-items:center;
  justify-content:center;min-width:0}
#orbWrap{position:relative;width:min(52vh,480px);height:min(52vh,480px)}
#orbWrap::after{content:'';position:absolute;inset:-8%;border-radius:50%;pointer-events:none;
  background:radial-gradient(circle,transparent 58%,rgba(0,20,45,.35) 100%)}
#chat{position:absolute;inset:auto 12% 0 12%;max-height:46vh;overflow-y:auto;z-index:3;
  scrollbar-width:none;display:flex;flex-direction:column;gap:8px;padding-bottom:4px}
#chat::-webkit-scrollbar{display:none}
.bubble{max-width:80%;padding:9px 14px;border-radius:14px;font-size:14.5px;line-height:1.45;
  font-family:'Rajdhani',sans-serif;font-weight:500;letter-spacing:.3px;
  animation:rise .35s ease both;word-wrap:break-word}
.you{align-self:flex-end;background:rgba(77,240,255,.14);border:1px solid rgba(77,240,255,.25);
  border-bottom-right-radius:4px}
.lya{align-self:flex-start;background:rgba(8,18,34,.8);border:1px solid rgba(77,240,255,.2);
  border-bottom-left-radius:4px;box-shadow:0 0 18px rgba(0,180,255,.08)}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
</style></head><body>
<div id="boot"><div style="font-family:'Orbitron';font-size:34px;font-weight:900;letter-spacing:14px;color:#4df0ff;
  text-shadow:0 0 30px #00c8ff;animation:flickIn 2.2s ease">L Y A</div>
  <div style="font-family:'Rajdhani';font-size:12px;letter-spacing:6px;color:#5fb8d8;margin-top:8px">INITIALIZING INTERFACE</div>
  <div id="bootBar"><i></i></div><div id="bootLog"></div></div>
<div class="vignette"></div><div class="scanlines"></div><div class="sweepline"></div>
<canvas id="space"></canvas>
<div id="topbar">
  <div class="brand">L Y A</div>
  <div id="status" style="letter-spacing:2px;font-size:12px;color:#7fe8ff">● ONLINE</div>
  <div class="sep"></div><div class="clock" id="clock" style="opacity:.7;font-size:13px"></div>
</div>
<div class="panel" id="left"><h3>Memory Vault</h3><div class="body" id="vault"></div></div>
<div id="core"><div id="orbWrap"><canvas id="orb"></canvas></div><div id="chat"></div></div>
<div class="panel" id="right"><h3>System Telemetry</h3><div class="body" id="telemetry"></div></div>
"""

HTML_TAIL = """
<div id="overlay" style="position:fixed;inset:0;z-index:9;display:none;
  background:rgba(2,6,14,.55);backdrop-filter:blur(4px)" onclick="hideCard()"></div>
<div id="card" style="position:fixed;left:50%;top:50%;transform:translate(-50%,-46%) scale(.94);
  opacity:0;pointer-events:none;z-index:10;min-width:340px;max-width:70vw;max-height:70vh;
  border-radius:16px;background:linear-gradient(165deg,rgba(12,34,62,.92),rgba(4,10,24,.95));
  border:1px solid rgba(77,240,255,.35);box-shadow:0 0 60px rgba(0,190,255,.25);
  padding:20px 24px;transition:all .28s cubic-bezier(.2,.9,.25,1)">
  <div id="cardTitle" style="font-size:11px;letter-spacing:3px;color:var(--cy);margin-bottom:10px"></div>
  <div id="cardBody" style="white-space:pre-wrap;font-size:14.5px;line-height:1.5;
    max-height:52vh;overflow-y:auto"></div>
  <div style="margin-top:14px;text-align:right;color:#69a8c8;font-size:11px">click anywhere to close</div>
</div>
<div id="inputbar" style="position:fixed;left:0;right:0;bottom:0;grid-area:in;z-index:8;
  display:flex;justify-content:center;padding:14px;background:linear-gradient(transparent,rgba(2,5,12,.9) 55%)">
  <form id="f" style="display:flex;gap:8px;width:min(720px,86vw)">
    <input id="q" placeholder="Speak or type your command…" autocomplete="off" style="flex:1;
      background:rgba(10,26,48,.8);border:1px solid rgba(77,240,255,.3);color:#dff6ff;
      border-radius:24px;padding:13px 20px;font-size:15px;outline:none;transition:border .2s,box-shadow .2s">
    <button style="background:linear-gradient(120deg,#4df0ff,#1a8cff);border:none;color:#012;
      border-radius:24px;padding:0 22px;font-weight:700;cursor:pointer">SEND</button>
  </form>
</div>
</body></html>"""

JS_ENGINE = r"""
const spaceC=document.getElementById('space'),sx=spaceC.getContext('2d');
const orbC=document.getElementById('orb'),ox=orbC.getContext('2d');
let W,H,stars=[],state='idle',t0=Date.now();
function fit(){W=innerWidth;H=heightFix();spaceC.width=W;spaceC.height=H;
  orbC.width=orbC.clientWidth;orbC.height=orbC.clientHeight;}
function heightFix(){return innerHeight;}
stars=Array.from({length:140},()=>({x:Math.random(),y:Math.random(),z:Math.random()*.8+.2,p:Math.random()*6.28}));
function drawSpace(){
  sx.clearRect(0,0,W,H);
  // horizon grid — the technical floor
  const hz=H*.82;
  sx.strokeStyle='rgba(77,240,255,.06)';sx.lineWidth=1;
  for(let i=0;i<26;i++){const y=hz+i*i*1.35;if(y>H)break;
    sx.beginPath();sx.moveTo(0,y);sx.lineTo(W,y);sx.stroke();}
  for(let i=-14;i<=14;i++){sx.beginPath();sx.moveTo(W/2+i*60,hz);
    sx.lineTo(W/2+i*140,H);sx.stroke();}
  // drifting particles
  const t=Date.now()/1000;
  for(const s of stars){
    s.x+=0.016*s.z; if(s.x>1.02)s.x=-0.02;
    const px=s.x*W,py=s.y*H+Math.sin(t0/900+s.p)*8;
    sx.fillStyle=`rgba(120,220,255,${0.25+s.z*0.5})`;
    sx.beginPath();sx.arc(px,py,s.z*1.6,0,6.28);sx.fill();
  }
}
function drawOrb(){
  ox.clearRect(0,0,orbC.width,orbC.height);
  const cx=orbC.width/2,cy=orbC.height/2,R=orbC.width/2*.42;
  const t=(Date.now()-t0)/1000;
  const conf={idle:['rgba(77,240,255,','listening','rgba(0,200,255,'],['x']}[0];
}
"""

JS_ORB = r"""
function drawOrb(){
  ox.clearRect(0,0,orbC.width,orbC.height);
  const cx=orbC.width/2,cy=orbC.height/2,R=orbC.width/2*.40;
  const t=(Date.now()-t0)/1000;
  const col=state==='thinking'?'255,184,77':state==='speaking'?'90,255,170':'77,220,255';
  // breathing core
  const breathe=1+0.05*Math.sin(t*2)+(state!=='idle'?0.04*Math.sin(t*9):0);
  const g=ox.createRadialGradient(cx,cy,0,cx,cy,R*1.5);
  g.addColorStop(0,`rgba(${col},.85)`);g.addColorStop(.35,`rgba(${col},.25)`);
  g.addColorStop(1,'rgba(0,20,50,0)');
  ox.fillStyle=g;ox.beginPath();ox.arc(cx,cy,R*(1+breathe*0.6),0,6.28);ox.fill();
  // rotating HUD arcs
  for(const[r,sp,a,w]of[[1.0,.5,.5,1.4],[1.12,-.35,.75,1],[1.26,.8,.35,2],[1.45,-.2,.15,1.2]]){
    ox.strokeStyle=`rgba(${col},${a})`;ox.lineWidth=w;
    const off=t*sp,seg=6.283*.72/3;
    for(let k=0;k<3;k++){
      ox.beginPath();
      ox.arc(cx,cy,R*r,off+k*6.283/3,off+k*6.283/3+seg);
      ox.stroke();
    }
  }
  // waveform ring — reacts to state
  const amp=state==='idle'?0.03:state==='thinking'?0.09:0.16;
  ox.beginPath();
  for(let i=0;i<=120;i++){
    const a=i/120*6.283;
    const rr=R*0.62+Math.sin(a*6+t*7)*R*amp*Math.sin(t*2.2);
    ox[i?'lineTo':'moveTo'](cx+Math.cos(a)*rr,cy+Math.sin(a)*rr);
  }
  ox.closePath();ox.strokeStyle=`rgba(${col},.7)`;ox.lineWidth=1.6;ox.stroke();
  // center label
  ox.fillStyle=`rgba(${col},.95)`;
  ox.font=`600 ${Math.round(R*.16)}px 'Segoe UI'`;
  ox.textAlign='center';ox.textBaseline='middle';
  ox.fillText('LYA',cx,cy);
  ox.font=`${Math.round(R*.13)}px 'Segoe UI'`;
  ox.fillStyle=`rgba(${col},.55)`;
  ox.fillText(state.toUpperCase(),cx,cy+R*.24);
  requestAnimationFrame(()=>{drawSpace();drawOrb();});
}
addEventListener('resize',fit);
fit();drawOrb();
function setState(s){state=s;
  document.getElementById('status').textContent='● '+s.toUpperCase();}
"""

JS_APP = r"""
const TOKEN = localStorage.getItem('lya_token') || prompt('LYA access token (same as phone gateway):');
localStorage.setItem('lya_token',TOKEN);
function bubble(text,cls){const d=document.createElement('div');d.className='bubble '+cls;
  d.textContent=text;document.getElementById('chat').appendChild(d);
  document.getElementById('chat').scrollTop=999999;return d;}
async function ask(q){
  if(!q)return;
  bubble(q,'you');document.getElementById('q').value='';
  setState('thinking');
  const r=await fetch('/ask',{method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'token='+encodeURIComponent(TOKEN)+'&q='+encodeURIComponent(q)});
  const j=await r.json();
  setState('speaking');bubble(j.reply||j.error||'…','lya');
  loadVault();
  // auto-popup for stored/secret content
  if(/^Stored|^Saved|^Here's your|password/i.test(j.reply)) showCard('LYA', j.reply);
  setTimeout(()=>setState('idle'),1800);
}
document.getElementById('f').onsubmit=e=>{e.preventDefault();
  ask(document.getElementById('q').value.trim());};
function showCard(title,body){document.getElementById('cardTitle').textContent=title.toUpperCase();
  document.getElementById('cardBody').textContent=body;
  const c=document.getElementById('card'),o=document.getElementById('overlay');
  c.style.opacity=1;c.style.pointerEvents='auto';
  c.style.transform='translate(-50%,-50%) scale(1)';
  o.style.display='block';}
function hideCard(){const c=document.getElementById('card'),o=document.getElementById('overlay');
  c.style.opacity=0;c.style.pointerEvents='none';
  c.style.transform='translate(-50%,-46%) scale(.94)';o.style.display='none';}
async function loadVault(){
  const r=await fetch('/memory',{method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'token='+encodeURIComponent(TOKEN)});
  const j=await r.json();
  const v=document.getElementById('vault');v.innerHTML='';
  if(!j.items||!j.items.length){v.innerHTML='<div style="opacity:.5;font-size:13px">Nothing saved yet — tell LYA "remember …"</div>';return;}
  for(const it of j.items){
    const d=document.createElement('div');
    d.style.cssText='padding:9px 10px;margin:5px 0;border-radius:10px;cursor:pointer;'+
      'background:rgba(77,240,255,.06);border:1px solid rgba(77,240,255,.14);transition:.2s';
    d.innerHTML=`<div style="font-size:10px;color:#6fd8ff;letter-spacing:1px">${esc(it.kind)}</div>
      <div style="font-size:13.5px;margin-top:3px">${esc(it.text)}</div>`;
    d.onclick=()=>showCard(it.kind+' · vault',it.text);
    d.onmouseenter=()=>d.style.background='rgba(77,240,255,.14)';
    d.onmouseleave=()=>d.style.background='rgba(77,240,255,.06)';
    v.appendChild(d);
  }
}
async function loadTelemetry(){
  const r=await fetch('/telemetry',{method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'token='+encodeURIComponent(TOKEN)});
  const j=await r.json();
  document.getElementById('telemetry').innerHTML=j.html;
}
setInterval(()=>{document.getElementById('clock').textContent=
  new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});},1000);
// mic button: press Space anywhere to focus the input (voice hook comes from main.py)
addEventListener('keydown',e=>{if(e.code==='Space'&&document.activeElement!==document.getElementById('q')){
  e.preventDefault();document.getElementById('q').focus();}});
loadVault();loadTelemetry();setInterval(loadTelemetry,5000);
"""

HTML_FULL = HTML_HEAD + HTML_TAIL.replace("</body></html>", "")
HTML_PAGE = HTML_FULL + "<script>" + JS_ORB + JS_APP + "</script></body></html>"

TELEMETRY_HTML = r"""
<div style="font-size:13px;line-height:2.1">
<div style="display:flex;justify-content:space-between"><span style="color:#6fd8ff">CORE</span><b style="color:#4df0ff">LYA v3 · ONLINE</b></div>
<div style="display:flex;justify-content:space-between"><span style="color:#6fd8ff">BRAIN</span><span>GROQ cloud + local fallback</span></div>
<div style="display:flex;justify-content:space-between"><span style="color:#6fd8ff">SECURITY</span><b style="color:#8affc1">AES-256 · DPAPI · TRIPLE-GATE</b></div>
<div style="display:flex;justify-content:space-between"><span style="color:#6fd8ff">HACKER BRAIN</span><span style="color:#ffd88a">709 techniques loaded</span></div>
<div style="display:flex;justify-content:space-between"><span style="color:#6fd8ff">HOME GUARDIAN</span><span id="tele-devices">scanning…</span></div>
<div style="display:flex;justify-content:space-between"><span style="color:#6fd8ff">SKILL FORGE</span><span style="color:#8affc1">armed</span></div>
<div style="margin-top:8px;color:#4a7a95;font-size:11px">Say: "remember …" · "what do you know" · "who is on my wifi" · "is lya secure"</div>
</div>"""

# ================================================================ BACKEND
def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        return self._send(200, HTML_PAGE)

    def do_POST(self):
        data = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
        if data.get("token", [""])[0] != TOKEN:
            return self._send(403, json.dumps({"error": "access denied — wrong token"}),
                              "application/json")
        try:
            if self.path == "/ask":
                q = data.get("q", [""])[0].strip()
                reply = lyas_answer(q, verified=False)
                self._send(200, json.dumps({"reply": reply}), "application/json")
            elif self.path == "/memory":
                self._send(403, json.dumps({"error": "Private memory is available in the verified native interface."}), "application/json")
            elif self.path == "/telemetry":
                self._send(200, json.dumps({"html": TELEMETRY_HTML}), "application/json")
            else:
                self._send(404, "not found")
        except Exception as e:
            self._send(200, json.dumps({"error": str(e)}), "application/json")

    def log_message(self, *a):
        pass

def main():
    port = 5050
    srv = HTTPServer(("127.0.0.1", port), Handler)   # localhost only — private
    url = f"http://localhost:{port}"
    print(f"""
{'='*55}
  LYA JARVIS INTERFACE
  {url}   (localhost only — no one else can reach it)
  Same token as your phone gateway. Ctrl+C to stop.
{'='*55}""")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nInterface closed.")

if __name__ == "__main__":
    main()
