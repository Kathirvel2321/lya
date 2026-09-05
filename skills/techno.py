"""TECHNO SKILL — LYA as the smart technical person: fix, install, explain, code.
All operations go through the SAFE executor (skills/autonomous.py) so anything
dangerous is guarded."""
import os, json, datetime

import skills.autonomous as autonomous

_DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(_DIR, "techno_log.lya")

_QUE = ("fix", "error", "not working", "crash", "install", "uninstall", "update",
        "driver", "wifi", "bluetooth", "slow", "storage", "battery", "code",
        "debug", "python", "cmd", "terminal", "powershell", "run ", "script",
        "explain code", "why is my", "technical")

_FIXED = {
    "wifi": "Network reset: run 'netsh winsock reset' then 'netsh int ip reset', "
            "then restart. I can run both for you — just say 'fix my wifi' again "
            "and approve.",
    "bluetooth": "Toggle airplane mode twice, or run 'net stop bthserv && net "
                 "start bthserv' to restart the Bluetooth service.",
    "slow": "Top causes: too many startup apps, full disk, or overheating. Say "
            "'clean my pc' and I'll free space safely.",
    "storage": "Run Disk Cleanup or let me — I'll clear temp files safely.",
    "battery": "Run 'powercfg /batteryreport' — I can open the report for you.",
    "driver": "Device Manager → find the yellow-triangle device → Update driver. "
              "Or tell me the device and I'll open the right panel.",
}


def match(text):
    return any(q in text for q in _QUE)


def _web_summary(query):
    """One-line summary from DuckDuckGo Instant Answer API (no key, safe)."""
    try:
        import urllib.request, urllib.parse
        url = ("https://api.duckduckgo.com/?q=" + urllib.parse.quote(query)
               + "&format=json&no_html=1&skip_disambig=1")
        req = urllib.request.Request(url, headers={"User-Agent": "LYA/1.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        for k in ("AbstractText", "Answer", "Definition"):
            v = (data.get(k) or "").strip()
            if v:
                return f"Quick answer: {v[:300]}"
        for t in data.get("RelatedTopics", []):
            if isinstance(t, dict) and t.get("Text"):
                return f"Quick answer: {t['Text'][:300]}"
    except Exception:
        pass
    return ""


def reply(text, say, ask):
    low = text.lower()

    # --- known fixes ---
    for key, fix in _FIXED.items():
        if key in low and any(w in low for w in ("fix", "not working", "problem", "error")):
            say(fix)
            if "wifi" in low:
                return _fix_wifi(say, ask)
            return fix

    # --- install requests ---
    if "install" in low:
        app = (low.split("install", 1)[-1].strip(" ?.")
               or ask("What should I install?").lower().strip())
        return autonomous.handle(text, say, ask)

    # --- clean pc ---
    if any(w in low for w in ("clean my pc", "clean pc", "free up space", "temp files")):
        return autonomous.handle(text, say, ask)

    # --- technical questions / errors ---
    web = _web_summary(text)
    if web:
        return f"{web} Want me to try the fix myself? Say 'you do it'."

    return ("Describe the problem and I'll diagnose it. You can also say "
            "'run a command' and I'll execute it under safety rules.")
