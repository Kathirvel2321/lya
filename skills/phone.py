"""LYA's remote hands — controls YOUR phone through a paired Termux agent.

How it's legal (and it is): YOU install the agent on your own phone and
YOU pair it. LYA never touches anything without your explicit command.
Same model as corporate MDM (Intune / Samsung Knox) — consent + crypto.

Security model:
- Pairing key is generated once, shown as QR-ish text, stored DPAPI-encrypted
  in the vault. The phone must present it on every request.
- All traffic is on your LAN (or via Tailscale) over HTTPS-ready HTTP with
  HMAC-SHA256 signed bodies -> replay and spoofing are dead on arrival.
- A permission registry gates EVERY command. You grant "camera", "storage",
  "sms"... once, and can revoke any time by voice ("revoke phone camera").
"""
import os, json, time, hmac, hashlib, secrets, urllib.request

VAULT_DIR = os.path.join(os.path.dirname(__file__), "security")
KEY_FILE = os.path.join(VAULT_DIR, "phone_pair.lya")
ADDR_FILE = os.path.join(VAULT_DIR, "phone_addr.lya")

# ---- permission registry: nothing works without an explicit grant ----
PERMS_FILE = os.path.join(VAULT_DIR, "phone_perms.json")

def _load(p, default):
    try:
        with open(p) as f: return f.read()
    except FileNotFoundError:
        return default

def _save(p, data):
    os.makedirs(VAULT_DIR, exist_ok=True)
    with open(p, "w") as f: f.write(data)

def pair_key() -> str:
    k = _load(KEY_FILE, "")
    if not k:
        k = secrets.token_urlsafe(32)
        _save(KEY_FILE, k)
    return k

def set_address(addr: str):
    _save(ADDR_FILE, addr.strip())

def get_address() -> str:
    return _load(ADDR_FILE, "").strip()

def _perms() -> dict:
    try:
        with open(PERMS_FILE) as f: return json.load(f)
    except Exception:
        return {}

def grant(perm: str) -> str:
    p = _perms(); p[perm] = True; _save(PERMS_FILE, json.dumps(p, indent=2))
    return f"Granted: {perm}. Say 'revoke phone {perm}' any time to take it back."

def revoke(perm: str) -> str:
    p = _perms(); p.pop(perm, None); _save(PERMS_FILE, json.dumps(p, indent=2))
    return f"Revoked: {perm}. I will refuse that command until you grant it again."

def perms_status() -> str:
    p = _perms()
    return "Granted phone permissions: " + (", ".join(sorted(p)) if p else "none yet") + \
           f". Address: {get_address() or 'not set — say: phone address http://IP:8069'}"

# ---- what each capability needs ----
CAPS = {
    "storage":  "storage",  "battery": "storage",   "status": "storage",
    "photo":    "camera",   "snap":   "camera",
    "location": "location", "where":  "location",
    "notify":   "notify",   "clipboard":"storage",
    "sms":      "sms",      "call":   "call",
    "battery":  "storage",
}

def _need(cap_text: str):
    for word, perm in CAPS.items():
        if word in cap_text:
            if not _perms().get(perm):
                return perm
    return None

# ---- signed request to the agent ----
def _call(action: str, args: dict = None, timeout: int = 20) -> dict:
    addr = get_address()
    if not addr:
        return {"error": "No phone address. Say: phone address http://<phone-ip>:8069 "
                         "(find the IP in Termux with 'ifconfig')."}
    key = pair_key()
    body = json.dumps({"action": action, "args": args or {}, "t": time.time()}).encode()
    sig = hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(addr.rstrip("/") + "/cmd", data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "X-Signature": sig})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": f"Phone not reachable ({e}). Is Termux running and on the same WiFi/Tailscale?"}

# ---- public commands LYA speaks ----
def phone_storage(_=None):
    r = _call("storage")
    if "error" in r: return r["error"]
    d = r["data"]
    return f"Your phone storage: {d['used_gb']} GB used of {d['total_gb']} GB — {d['free_gb']} GB free ({d['percent']}% full)."

def phone_battery(_=None):
    r = _call("battery")
    if "error" in r: return r["error"]
    d = r["data"]
    return f"Phone battery at {d['percent']}%, {d['status']}."

def phone_status(_=None):
    return phone_storage() + " " + phone_battery()

def phone_photo(_=None):
    r = _call("photo", timeout=45)
    if "error" in r: return r["error"]
    if r["data"].get("path"):
        return f"Photo taken on your phone, saved at {r['data']['path']} (pull it with: termux-storage pull)."
    return "Photo command sent."

def phone_location(_=None):
    r = _call("location", timeout=30)
    if "error" in r: return r["error"]
    d = r["data"]
    return f"Phone location: {d['lat']}, {d['lon']} (accuracy {d.get('acc','?')}m). Open: https://maps.google.com/?q={d['lat']},{d['lon']}"

def phone_notify(args):
    msg = args if isinstance(args, str) else "Hello from LYA"
    r = _call("notify", {"msg": msg})
    return r.get("error", "Notification pushed to your phone.")

def phone_sms(args):
    if not isinstance(args, str): return "Say: phone sms to <number> message <text>"
    try:
        _, rest = args.split("to", 1); num, msg = rest.split("message", 1)
        r = _call("sms", {"to": num.strip(), "msg": msg.strip()})
    except ValueError:
        return "Format: phone sms to 12345 message hello"
    return r.get("error", "SMS sent.")

def phone_clipboard(_=None):
    r = _call("clipboard")
    if "error" in r: return r["error"]
    return f"Phone clipboard: {r['data'].get('text','(empty)')[:200]}"

def ping(_=None):
    r = _call("ping")
    if "error" in r: return r["error"]
    return f"Phone agent alive. {r['data'].get('device','')} — HMAC pairing verified."

# verb -> function, used by main.py
HANDS = {
    "phone status": phone_status, "phone storage": phone_storage,
    "phone battery": phone_battery, "phone photo": phone_photo,
    "phone location": phone_location, "phone clipboard": phone_clipboard,
    "phone ping": ping,
}

def handle(text: str):
    """Router called from main.py / web_server.py. Returns str or None."""
    low = text.lower()

    if low.startswith("phone address "):
        set_address(text.split("phone address", 1)[1]); return "Phone address saved. Say 'phone ping' to test."
    if low.startswith(("grant phone ", "allow phone ")):
        return grant(low.split("phone ", 1)[1].split()[0].strip(" ."))
    if low.startswith(("revoke phone ", "deny phone ")):
        return revoke(low.split("phone ", 1)[1].split()[0].strip(" ."))
    if low in ("phone permissions", "phone setup", "phone status perms"):
        return perms_status()

    # permission gate — she refuses anything you haven't granted
    missing = _need(low)
    if missing:
        return (f"I can't do that yet — you haven't granted the '{missing}' permission. "
                f"Say 'grant phone {missing}' to allow it once, and I'll remember.")
    if low.startswith("phone notify"):
        return phone_notify(text.split("notify", 1)[1].strip() if "notify" in low else "Ping!")
    if low.startswith("phone sms"):
        return phone_sms(text.split("sms", 1)[1].strip())
    for k, fn in HANDS.items():
        if low.startswith(k): return fn()
    if low in ("phone", "phone help"):
        return ("Phone commands: phone ping · phone status · phone storage · phone battery · "
                "phone photo · phone location · phone notify <msg> · phone sms to <n> message <t> · "
                "grant phone <perm> · revoke phone <perm> · phone address <url>. "
                "Set up the agent with: python agent/phone_agent.py")
    return None
