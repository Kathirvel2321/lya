n """LYA TRAP DETECTION — she checks the ground BEFORE stepping on it.
====================================================================
Before any network action (scan, block, connect), she looks for the
classic waiting-traps an attacker sets on a network:

  1. ARP SPOOFING / MITM  — two IPs share one MAC, or the gateway MAC
     suddenly changed (attacker positioning himself between you & router)
  2. ROGUE DNS            — DNS server is not your router/trusted one
     (attacker redirecting your traffic)
  3. UNTRUSTED NETWORK    — you're not on your own home subnet anymore
  4. GATEWAY LOOKALIKE    — an IP answering as gateway that isn't yours

Every check is read-only observation of your own connection. If anything
smells wrong, LYA REFUSES risky actions and warns you in plain words.
"""
import os, json, subprocess, socket, time

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, ".home_baseline.json")

def _arp_table():
    out = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                         timeout=10).stdout
    table = {}
    for line in out.splitlines():
        m = None
        import re
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+((?:[0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2})", line)
        if m and not m.group(1).startswith(("224.", "239.", "233.")):
            table[m.group(1)] = m.group(2).replace("-", ":").lower()
    return table

def _dns_servers():
    out = subprocess.run(["powershell", "-c",
        "(Get-DnsClientServerAddress -AddressFamily IPv4 | "
        "Where-Object {$_.ServerAddresses}).ServerAddresses"],
        capture_output=True, text=True, timeout=15).stdout
    return [l.strip() for l in out.splitlines() if l.strip().count(".") == 3]

def check(trusted_subnet=None, trusted_dns=None):
    """Returns (safe: bool, warnings: list[str])."""
    warnings = []
    from skills.home import gateway_ip, subnet_of, local_ip
    gw = gateway_ip()
    me = local_ip()
    if trusted_subnet and subnet_of(me) != trusted_subnet:
        warnings.append(f"🌐 You are NOT on your trusted network "
                        f"(you're on {subnet_of(me)}x, home is {trusted_subnet}x). "
                        "Anyone could be watching this network. Don't access private things here.")
    table = _arp_table()
    macs = {}
    for ip, mac in table.items():
        macs.setdefault(mac, []).append(ip)
    for mac, ips in macs.items():
        if len(ips) > 2 and gw in ips:
            warnings.append(
                f"⚠️ ARP SPOOFING SIGNATURE: gateway MAC {mac} is claimed by {len(ips)} IPs "
                f"({', '.join(ips[:4])}). Someone may be positioning a man-in-the-middle. "
                "Do NOT send passwords anywhere until this is resolved.")
            break
    if gw in table:
        cur = table[gw]
        base = _load_baseline()
        known = base.get("gateway_mac")
        if known and known != cur:
            warnings.append(
                f"🚨 GATEWAY LOOKALIKE: your gateway MAC changed from {known} to {cur}! "
                "This is the classic evil-twin trap — a fake router pretending to be yours. "
                "Lya will not run network actions on this connection.")
        elif known is None:
            base["gateway_mac"] = cur
            _save_baseline(base)
    dns = _dns_servers()
    if trusted_dns:
        if dns and not any(d in trusted_dns for d in dns):
            warnings.append(f"🚨 ROGUE DNS: your DNS is {dns}, but your trusted DNS is {trusted_dns}. "
                            "Traffic may be redirected. Avoid logins until fixed.")
    elif dns and gw not in dns:
        warnings.append(f"ℹ️ Note: DNS ({dns[0]}) is not your router ({gw}). "
                        "If you didn't set that yourself, check your adapter settings.")
    return (len(warnings) == 0, warnings)

def _load_baseline():
    try:
        with open(BASELINE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_baseline(d):
    with open(BASELINE, "w") as f:
        json.dump(d, f, indent=1)
