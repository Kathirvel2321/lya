"""LYA HOME GUARDIAN — universal WiFi guardian (works with ANY router).
=======================================================================
LEGAL LINE: your own network only. Scanning is passive observation of
YOUR LAN (like any router admin app). Blocking goes through YOUR router's
official admin interface — never attack tools (no deauth, ever).

Commands (allskills routes here):
  "who is on my wifi" / "scan my wifi"     -> full device inventory
  "how many devices on my wifi"            -> exact count
  "is dad's phone connected"               -> presence check (registry)
  "register dad's phone aa:bb:cc:..."      -> label a MAC as family
  "block <name|mac>"                       -> needs 'confirm' + owner auth
  "unblock <name|mac>"                     -> same gate
  "unknown devices"                        -> devices NOT in registry
Router creds are stored DPAPI-encrypted in security/vault.py.
"""
import os, re, json, subprocess, socket, struct, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REG_FILE = os.path.join(HERE, "home_devices.json")
ACTION_LOG = os.path.join(HERE, "lya_actions.log.lya")

# ------------------------------------------------------------- helpers
def gateway_ip():
    """Default gateway — works on any Windows box."""
    out = subprocess.run(["route", "print", "0.0.0.0"], capture_output=True,
                         text=True, timeout=10).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "0.0.0.0":
            return parts[2]
    return "192.168.1.1"

def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

def subnet_of(ip):
    return ".".join(ip.split(".")[:3]) + "."

# Small offline OUI table: first 3 MAC bytes -> maker (top home devices)
OUI = {
    "Samsung": ["00:16:32","8C:77:12","AC:5F:3E","40:0E:85","A0:07:98","34:23:BA","D0:22:BE","F8:E9:4E"],
    "Apple":   ["F0:18:98","AC:BC:32","A4:D1:8C","D0:03:4B","F8:FF:C2","7C:6D:62","DC:2B:61"],
    "Xiaomi":  ["64:09:80","78:02:F8","F8:59:71","C8:58:C0","64:CC:2E","AC:C1:5E"],
    "TP-Link": ["50:C7:BF","A4:2B:B0","F4:EC:38","14:CC:20","C0:25:E9"],
    "Huawei":  ["00:46:4B","18:C5:8A","28:6E:D4","F4:63:1F","C8:0C:C8"],
    "Intel":   ["00:1B:21","3C:97:0E","84:7B:57","A0:A8:CD"],
    "Realtek": ["00:E0:4C","52:54:00"],
    "OnePlus": ["64:A2:F9","F4:95:4B","C0:EE:FB"],
    "Vivo":    ["38:A4:ED","48:9E:11","9C:2A:70"],
    "Oppo":    ["48:43:2C","78:02:F8","9C:6B:00"],
    "Google":  ["F4:F5:D8","30:D9:D9","DC:A6:97"],
    "RaspberryPi": ["B8:27:EB","DC:A6:32","E4:5F:01"],
}

def mac_vendor(mac):
    if not mac:
        return "unknown"
    mac = mac.upper().replace("-", ":")
    prefix = mac[:8]
    for maker, prefixes in OUI.items():
        if prefix in prefixes or any(mac.startswith(p) for p in prefixes):
            return maker
    if mac.startswith("01:00:5E") or mac.startswith("33:33"):
        return "multicast (not a device)"
    if int(mac[1:2], 16) & 2 and not int(mac[0:2], 16) & 1:
        return "randomized MAC (phone privacy mode)"
    # online OUI lookup (MacVendors free API), cached forever
    vendor = _oui_online(mac)
    return vendor or "unlisted maker"

_OUI_CACHE = {}
def _oui_online(mac):
    if mac in _OUI_CACHE:
        return _OUI_CACHE[mac]
    cache = os.path.join(HERE, ".oui_cache.json")
    try:
        import json as _j
        with open(cache) as f:
            _OUI_CACHE.update(_j.load(f))
    except Exception:
        pass
    if mac in _OUI_CACHE:
        return _OUI_CACHE[mac]
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.macvendors.com/{mac}",
            headers={"User-Agent": "LYA-guardian/1.0"})
        with urllib.request.urlopen(req, timeout=3) as r:
            vendor = r.read().decode("utf-8", "ignore").strip()[:40]
        _OUI_CACHE[mac] = vendor if vendor and "not found" not in vendor.lower() else ""
        with open(cache, "w") as f:
            import json as _j2
            _j2.dump(_OUI_CACHE, f)
        return _OUI_CACHE[mac] or None
    except Exception:
        return None

# ------------------------------------------------------------- SCAN (universal)
def scan_devices():
    """Ping-sweep the subnet then read the ARP table. Universal: works with
    every router/OS because it only observes, never logs into anything."""
    gw = gateway_ip()
    base = subnet_of(gw)
    me = local_ip()
    # parallel ping sweep — one PowerShell job, ~5s total
    try:
        subprocess.run(
            ["powershell", "-c",
             "1..254 | ForEach-Object -ThrottleLimit 40 -Parallel { "
             "ping -n 1 -w 60 192.168.1.$_ >$null 0>$null }"],
            capture_output=True, timeout=25)
    except Exception:
        pass
    out = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                         timeout=10).stdout
    devices = {}
    for line in out.splitlines():
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+((?:[0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2})", line)
        if not m:
            continue
        ip, mac = m.group(1), m.group(2).replace("-", ":").lower()
        if mac == "ff:ff:ff:ff:ff:ff" or ip.endswith(".255") or ip.startswith(("224.", "239.", "233.", "235.", "232.", "234.", "236.", "237.", "238.", "231.")):
            continue
        # hostname reverse-lookup (best effort)
        host = ""
        try:
            host = socket.gethostbyaddr(ip)[0]
        except Exception:
            pass
        devices[ip] = {"mac": mac, "vendor": mac_vendor(mac),
                       "host": host, "gateway": (ip == gw), "me": (ip == me)}
    return devices

def _load_registry():
    try:
        with open(REG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_registry(reg):
    with open(REG_FILE, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1)

def register(mac, name):
    reg = _load_registry()
    reg[mac.lower()] = name
    _save_registry(reg)
    return f"📝 Registered {mac} as '{name}'."

def inventory():
    devs = scan_devices()
    reg = _load_registry()
    lines = [f"🏠 WIFI INVENTORY — {len(devs)} device(s) on {subnet_of(gateway_ip())}x", ""]
    for ip, d in sorted(devs.items(), key=lambda kv: tuple(int(x) for x in kv[0].split("."))):
        who = reg.get(d["mac"], "")
        tag = who or "❓ UNKNOWN"
        marks = ["🔒 gateway" if d["gateway"] else "", "💻 this PC" if d["me"] else ""]
        lines.append(f"  {ip:<16} {d['mac']}  {d['vendor']}"
                     + (f"  ({d['host']})" if d["host"] else "")
                     + f"  [{tag}] {' '.join(m for m in marks if m)}")
    unknown = sum(1 for d in devs.values() if d["mac"] not in reg
                  and not d["gateway"] and not d["me"])
    lines.append("")
    if unknown:
        lines.append(f"🚨 {unknown} UNKNOWN device(s) — say 'unknown devices' to review, 'block <name or mac> confirm' to kick.")
    else:
        lines.append("✅ Every device is registered family. Network looks clean.")
    return "\n".join(lines)

# ------------------------------------------------------------- ROUTER CONTROL
# Universal workflow: detect brand -> try its native admin API -> else guide.
ROUTER_HINTS = {
    "tplink":  ("TP-Link", "http://tplinkwifi.net", "Admin page > 'Attached Devices' > block, or 'Access Control'."),
    "dlink":   ("D-Link",  "http://dlinkrouter.local", "Admin > 'Wireless' > 'MAC Filter' > deny list."),
    "netgear": ("Netgear", "http://routerlogin.net", "Admin > 'Attached Devices' > 'Block' or 'Access Control'."),
    "asus":    ("Asus",    "http://router.asus.com", "Admin > 'Network Map' > clients > block, or 'Wireless MAC Filter'."),
    "jio":     ("JioFiber", "http://jiorouter.local or 192.168.1.1", "Admin > 'Network' > connected devices > block; or WiFi password change."),
    "airtel":  ("Airtel",  "http://192.168.1.1", "Admin > 'Device Management' > block; or WiFi password change."),
    "openwrt": ("OpenWrt", "http://192.168.1.1", "LuCI > Network > Wireless > associated clients."),
}

def detect_router():
    gw = gateway_ip()
    try:
        import urllib.request
        html = urllib.request.urlopen(f"http://{gw}/", timeout=5).read(8000).decode("utf-8", "ignore")
        low = html.lower()
    except Exception:
        return ("Unknown router", f"http://{gw}", None)
    for key, (brand, url, how) in ROUTER_HINTS.items():
        if key in low:
            return (brand, url, how)
    return ("Unknown router", f"http://{gw}", None)

def _log(action, mac, allowed):
    try:
        with open(ACTION_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat()} | HOME | "
                    f"{'ALLOWED' if allowed else 'DENIED'} | {action} {mac}\n")
    except Exception:
        pass

def block(name_or_mac, confirmed=False, owner_ok=False):
    """Kick a device through the router's own admin interface.
    NO deauth attacks. Needs owner auth + 'confirm' (guardian rules)."""
    reg = _load_registry()
    mac, label = None, name_or_mac
    devs = scan_devices()
    for ip, d in devs.items():
        who = reg.get(d["mac"], "")
        if d["mac"] == name_or_mac.lower() or who.lower() == name_or_mac.lower():
            mac, label = d["mac"], who or d["vendor"]
    if not confirmed:
        _log("BLOCK?", mac or name_or_mac, False)
        return (f"⚠️ You want to BLOCK '{label}' from the WiFi. "
                "This kicks them off the network. Say 'block ... confirm' to proceed.")
    if not owner_ok:
        _log("BLOCK", mac or name_or_mac, False)
        return ("🚫 Blocking needs OWNER verification (face + voice + secret phrase) "
                "from the web UI first. Lya will not cut anyone's connection unverified.")
    _log("BLOCK", mac or name_or_mac, True)
    brand, url, how = detect_router()
    if how:
        return (f"✂️ Router detected: {brand}.\n"
                f"1. Open {url} (admin login is on the router sticker)\n"
                f"2. {how}\n3. Block MAC: {mac} ({label})\n"
                f"I've logged this action. Want me to also change the WiFi password "
                f"instead — that instantly removes every unknown device?")
    return (f"✂️ Open your router admin at {url} (login on the router sticker), "
            f"find connected devices or MAC filter, and block: {mac} ({label}).\n"
            "Or say 'change wifi password guidance' — one password change kicks every unknown out.")

# ------------------------------------------------------------- LYA COMMANDS
PRESENCE = ("is dad", "is my dad", "dad's phone", "is mom", "is my mom",
            "is home", "connected right now")

def match(text):
    t = text.lower().strip()
    return any(k in t for k in (
        "who is on my wifi", "scan my wifi", "how many devices",
        "devices on my wifi", "unknown devices", "register ",
        "block ", "wifi block",
        "unblock", "change wifi password")) or (
        any(k in t for k in PRESENCE) and ("wifi" in t or "connected" in t))

def reply(text, say=None, ask=None):
    t = text.lower().strip()
    try:
        # TRAP CHECK before any network action — she refuses unsafe ground
        if any(k in t for k in ("block", "unblock", "scan", "who is on", "unknown")):
            from skills import trap
            safe, warns = trap.check()
            if not safe:
                return ("🚨 HOLD ON — I detected a trap on this network:\n\n"
                        + "\n".join("  " + w for w in warns)
                        + "\n\nI will not run network actions here. "
                          "Reconnect to your trusted WiFi first.")
        if "register" in t:
            m = re.search(r"register\s+(.+?)\s+((?:[0-9a-f]{2}[-:]){5}[0-9a-f]{2})", t)
            if m:
                return register(m.group(2), m.group(1).title())
            return "Tell me like: 'register dad's phone aa:bb:cc:dd:ee:ff'"
        if "how many" in t:
            n = len(scan_devices())
            return f"📶 Right now I see {n} device(s) connected to your WiFi. Say 'who is on my wifi' for the full list."
        if "unknown" in t:
            devs = scan_devices()
            reg = _load_registry()
            unk = [(ip, d) for ip, d in devs.items()
                   if d["mac"] not in reg and not d["gateway"] and not d["me"]]
            if not unk:
                return "✅ No unknown devices — everything on the network is registered family."
            lines = [f"🚨 {len(unk)} UNKNOWN device(s):"]
            for ip, d in unk:
                lines.append(f"  {ip:<16} {d['mac']}  {d['vendor']}")
            lines.append("\nBlock one: 'block <mac> confirm' (owner verification required).")
            return "\n".join(lines)
        if "block" in t or "unblock" in t:
            target = re.sub(r".*?(?:un)?block\s*", "", text, flags=re.I).replace("confirm", "").strip()
            return block(target, confirmed="confirm" in t, owner_ok=False)
        if "unblock" in t:
            return "To unblock: open the router admin page and remove the device from the block list. I'll guide you step by step if you say which router you have."
        if any(k in t for k in PRESENCE):
            name = "dad's phone" if "dad" in t else text.strip("? ")
            devs = scan_devices()
            reg = _load_registry()
            hits = [(ip, d) for ip, d in devs.items() if reg.get(d["mac"], "").lower() in t]
            if hits:
                ips = ", ".join(ip for ip, _ in hits)
                return f"✅ Yes — {name} is connected (IP {ips})."
            return f"❌ {name.title()} is not on the WiFi right now. Say 'who is on my wifi' to see who is."
        return inventory()
    except Exception as e:
        return f"Home guardian hit a snag: {e}"
