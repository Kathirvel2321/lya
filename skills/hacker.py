"""LYA'S HACKER SUITE — JARVIS MODE
===================================
Real security tooling she can run on command — with ONE unbreakable rule:

    SHE ONLY TESTS WHAT THE ADMIN OWNS OR HAS WRITTEN PERMISSION TO TEST.

Anything aimed at a stranger's machine, a website she doesn't own, or a
network that isn't hers → she refuses and explains why. This is what makes
her a REAL hacker instead of a dangerous one.

Capabilities:
  recon / netscan / wifi / portscan / hash / password / ciphers / guardian
"""
import os, socket, hashlib, base64, random, string, subprocess, platform

def _refuse(target):
    return (f"NO. '{target}' is not a machine on YOUR private network. "
            "I only test machines you own or have written permission to test — "
            "that's the line between a hacker and a criminal.")

def _is_local_target(target):
    t = (target or "").strip().lower()
    if t in ("localhost", "127.0.0.1", "self", "my pc", "my computer", "this pc", ""):
        return True
    if t.endswith(".local"):
        return True
    try:
        ip = socket.gethostbyname(t)
    except Exception:
        return False  # can't resolve = don't touch it
    if ip.startswith(("127.", "10.", "192.168.", "169.254.")):
        return True
    parts = ip.split(".")
    return parts[0] == "172" and 16 <= int(parts[1]) <= 31

def _resolve(target):
    t = (target or "").strip().lower()
    if t in ("", "localhost", "127.0.0.1", "self", "my pc", "my computer", "this pc"):
        return "127.0.0.1"
    return socket.gethostbyname(t)

# ---------------- RECON ----------------
def recon():
    info = [f"Host: {platform.node()}  ({platform.system()} {platform.release()})"]
    try:
        hostname = socket.gethostname()
        info.append(f"Local IPs: {', '.join(socket.gethostbyname_ex(hostname)[2])}")
    except Exception:
        pass
    try:
        s = socket.create_connection(("1.1.1.1", 80), timeout=3)
        info.append(f"LAN-facing IP: {s.getsockname()[0]}")
        s.close()
    except Exception:
        pass
    return "\n".join(info)

def netscan():
    try:
        out = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10).stdout
        return "Devices on your network (ARP):\n" + out.strip()
    except Exception as e:
        return f"ARP scan failed: {e}"

def wifi_info():
    try:
        out = subprocess.run(["netsh", "wlan", "show", "profiles"],
                             capture_output=True, text=True, timeout=10).stdout
        return "Saved WiFi profiles:\n" + out.strip()
    except Exception as e:
        return f"WiFi query failed: {e}"

# ---------------- PORT SCANNER (pure python, no nmap needed) ----------------
KNOWN = {21: "ftp", 22: "ssh", 23: "telnet (danger!)", 25: "smtp", 53: "dns",
         80: "http", 110: "pop3", 135: "rpc", 139: "netbios (danger!)",
         443: "https", 445: "smb (danger!)", 3389: "rdp", 8080: "http-alt"}

def portscan(target="127.0.0.1", ports=range(1, 1025), timeout=0.3):
    if not _is_local_target(target):
        return _refuse(target)
    ip = _resolve(target)
    open_ports = []
    for p in ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            if s.connect_ex((ip, p)) == 0:
                open_ports.append(p)
        except Exception:
            pass
        finally:
            s.close()
    if not open_ports:
        return f"Scan of {ip}: no open ports in range."
    lines = [f"Scan of {ip} — {len(open_ports)} open port(s):"]
    risky = []
    for p in open_ports:
        svc = KNOWN.get(p, "unknown service")
        lines.append(f"  {p}/tcp  {svc}")
        if "danger" in svc:
            risky.append(p)
    if risky:
        lines.append(f"⚠ Risky services exposed: {risky} — I recommend closing them.")
    return "\n".join(lines)

# ---------------- CRYPTO UTILITIES ----------------
def hash_text(text, algo="sha256"):
    h = hashlib.new(algo); h.update(text.encode())
    return f"{algo}: {h.hexdigest()}"

def hash_file(path, algo="sha256"):
    if not os.path.exists(path):
        return f"File not found: {path}"
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"{algo} of {os.path.basename(path)}: {h.hexdigest()}"

def gen_password(length=16, symbols=True):
    pool = string.ascii_letters + string.digits + (string.punctuation if symbols else "")
    return "".join(random.SystemRandom().choice(pool) for _ in range(length))

def audit_password(pw):
    score, tips = 0, []
    if len(pw) >= 12: score += 2
    elif len(pw) >= 8: score += 1
    else: tips.append("too short (use 12+)")
    if any(c.isupper() for c in pw): score += 1
    else: tips.append("add uppercase")
    if any(c.isdigit() for c in pw): score += 1
    else: tips.append("add digits")
    if any(c in string.punctuation for c in pw): score += 1
    else: tips.append("add symbols")
    verdict = ["terrible", "weak", "okay", "good", "strong"][min(score, 4)]
    out = f"Strength: {verdict} ({score}/5)."
    return out + (" Fix: " + "; ".join(tips) + "." if tips else "")

def caesar(text, shift=13, decode=False):
    if decode: shift = -shift
    out = []
    for c in text:
        if c.isalpha():
            base = ord('A') if c.isupper() else ord('a')
            out.append(chr((ord(c) - base + shift) % 26 + base))
        else:
            out.append(c)
    return "".join(out)

def b64(text, decode=False):
    if decode:
        return base64.b64decode(text + "=" * (-len(text) % 4)).decode(errors="replace")
    return base64.b64encode(text.encode()).decode()

# ---------------- HARDENING CHECK ----------------
def guardian_check():
    lines = ["Security posture check:"]
    try:
        fw = subprocess.run(["netsh", "advfirewall", "show", "allprofiles", "state"],
                            capture_output=True, text=True, timeout=10).stdout
        lines.append("Firewall: " + ("ON ✓" if "ON" in fw else "OFF ✗ — turn it on!"))
    except Exception:
        lines.append("Firewall: couldn't check")
    try:
        av = subprocess.run(["powershell", "-Command",
                             "(Get-MpComputerStatus).RealTimeProtectionEnabled"],
                            capture_output=True, text=True, timeout=15).stdout.strip()
        lines.append(f"Defender real-time: {'ON ✓' if 'True' in av else 'OFF ✗'}")
    except Exception:
        lines.append("Defender: couldn't check")
    return "\n".join(lines)

# ---------------- COMMAND ROUTER ----------------
def handle(text):
    """Parse a hacker-flavored command. Returns reply string or None."""
    t = text.lower()

    def _arg(*afts):
        for a in afts:
            idx = t.find(a)
            if idx != -1:
                rest = text[idx + len(a):].strip()
                if rest:
                    return rest
        return ""

    # teaching questions go to the LLM (handled by skillbook/mind)
    if any(k in t for k in ("what is", "how does", "teach me", "explain", "learn")):
        return None

    # any aggressive phrasing gets the ownership gate FIRST
    if any(k in t for k in ("hack ", "hack", "attack ", "exploit ", "ddos", "brute force", "crack ")):
        target = _arg("hack ", "attack ", "exploit ", "ddos ", "crack ") or "my pc"
        if not _is_local_target(target):
            return _refuse(target)
        return ("Target verified as YOUR machine. Running full local audit...\n"
                + recon() + "\n\n" + portscan(target))
    if "port scan" in t or "portscan" in t or ("scan" in t and "port" in t):
        return portscan(_arg("scan ", "of ") or "127.0.0.1")
    if "who is on my network" in t or "network scan" in t or "devices on my" in t or "arp" in t:
        return netscan()
    if "recon" in t or "fingerprint" in t or ("system" in t and "info" in t):
        return recon()
    if "wifi" in t and any(k in t for k in ("profile", "info", "show", "list")):
        return wifi_info()
    if "hash file" in t or "checksum" in t:
        return hash_file(_arg("file "), "md5" if "md5" in t else "sha256")
    if ("hash" in t and ("md5" in t or "sha" in t)) or t.startswith("hash "):
        return hash_text(_arg("hash ") or text, "md5" if "md5" in t else "sha256")
    if "generate password" in t or "strong password" in t or "password for me" in t:
        return (f"Here's a strong one: `{gen_password()}` — "
                "store it in your vault, never in plain text.")
    if "how strong is" in t or "password strength" in t or "audit password" in t:
        pw = _arg("is ", "password ")
        return audit_password(pw) if pw else "Tell me the password and I'll audit it."
    if "caesar" in t or "rot13" in t:
        return f"Result: {caesar(_arg('decode ', 'encode ', 'caesar ') or text, decode='decode' in t)}"
    if "base64" in t:
        return f"Result: {b64(_arg('decode ', 'encode ', 'base64 ') or text, decode='decode' in t)}"
    if "am i secure" in t or "security check" in t or "am i safe" in t or "hardening" in t:
        return guardian_check()
    return None


# ---------------- SKILL-ROUTER ADAPTER ----------------
def match(text):
    """True if this looks like a hacker-suite command (allskills.py calls this)."""
    return handle(text) is not None


def reply(text, say, ask):
    """Execute the hacker command. Falls back to a menu if nothing matched."""
    r = handle(text)
    if r:
        return r
    return ("Hacker suite ready. Try: 'scan my ports', 'who is on my network', "
            "'recon', 'am I secure', 'hash this text', 'generate a password', "
            "'how strong is my password', 'base64 encode hello'.")
