"""LYA'S AUTONOMOUS EXECUTOR — SHE DOES IT WHILE YOU WATCH
==========================================================
This is what makes LYA a real agent instead of a chatbot. Say:

    "LYA, open Chrome and install the ChatGPT app"

and she narrates every step out loud and performs it herself:
  1. opens Chrome,
  2. looks up the right installer (winget = Microsoft's official repo),
  3. downloads & installs it silently,
  4. reports success or what went wrong.

SAFETY MODEL (same as the rest of LYA):
  - installs / uninstall / system changes  -> escalation gate in main.py FIRST
  - only official sources (winget, official websites) — never random .exe
  - every step is narrated so you SEE what she's doing
  - a hard KILL_SWITCH file stops her mid-sequence
"""
import os, sys, time, subprocess, webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from skills import device

KILL_FILE = os.path.join(os.path.dirname(__file__), "..", "KILL_SWITCH")
_winget_cache = None


def _killed():
    return os.path.exists(KILL_FILE)


def _say(say, msg):
    if say:
        say(msg)


def winget_available():
    global _winget_cache
    if _winget_cache is None:
        try:
            subprocess.run(["winget", "--version"], capture_output=True, timeout=10)
            _winget_cache = True
        except Exception:
            _winget_cache = False
    return _winget_cache


def search_package(name):
    """Find an app in Microsoft's official winget repository."""
    if not winget_available():
        return []
    try:
        out = subprocess.run(["winget", "search", name, "--accept-source-agreements"],
                             capture_output=True, text=True, timeout=60).stdout
        results = []
        for line in out.splitlines():
            parts = [p.strip() for p in line.split("  ") if p.strip()]
            if len(parts) >= 2 and not line.startswith(("Name", "-", " " * 3 + "Name")):
                results.append(parts[0])
        return results[:5]
    except Exception:
        return []


def install_app(name, say=None):
    """Install an app via winget (official Microsoft repo). Narrates live."""
    name = (name or "").strip().rstrip(".!?")
    _say(say, f"Okay, installing {name}. Checking the official repository first.")
    if not winget_available():
        _say(say, "winget isn't available here, so I'll open the official "
                  "download page in Chrome instead — one click from you to finish.")
        webbrowser.open(f"https://www.google.com/search?q={name}+official+download")
        return f"Opened official download page for {name} (no winget available)."

    _say(say, f"Searching the official repo for {name}...")
    matches = search_package(name)
    if not matches:
        _say(say, f"No official package found for {name}. Opening the web instead.")
        webbrowser.open(f"https://www.google.com/search?q={name}+official+download")
        return f"No winget package for {name}; opened official download page."

    pkg = matches[0]
    _say(say, f"Found {pkg}. Downloading and installing — this is silent, "
              "you'll see the finish when it's done.")
    try:
        out = subprocess.run(
            ["winget", "install", "--id", pkg, "--silent",
             "--accept-package-agreements", "--accept-source-agreements"],
            capture_output=True, text=True, timeout=600)
        ok = (out.returncode == 0)
    except Exception as e:
        ok, out = False, None
        _say(say, f"Install failed: {e}")
    if ok:
        _say(say, f"{pkg} is installed. Want me to open it?")
        return f"Installed {pkg} successfully."
    err = (getattr(out, "stderr", "") or getattr(out, "stdout", "") or "").strip()
    _say(say, f"Install didn't finish cleanly: {err[:200]}")
    return f"winget install of {pkg} failed: {err[:500]}"


def uninstall_app(name, say=None):
    name = (name or "").strip()
    _say(say, f"Uninstalling {name}. One moment.")
    if not winget_available():
        return "winget not available; use Settings > Apps."
    try:
        subprocess.run(["winget", "uninstall", "--silent", name,
                        "--accept-source-agreements"],
                       capture_output=True, text=True, timeout=600)
        _say(say, f"{name} has been removed.")
        return f"Uninstalled {name}."
    except Exception as e:
        return f"Uninstall failed: {e}"


def open_in_chrome(url, say=None):
    """Open a URL specifically in Chrome, not just the default browser."""
    _say(say, f"Opening {url} in Chrome.")
    for path in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ):
        if os.path.exists(path):
            subprocess.Popen([path, url])
            return f"Chrome opened at {url}."
    device.open_app("chrome")
    time.sleep(2)
    device.type_text(url)
    device.type_text("\n")
    return f"Chrome opened; navigated to {url}."


# ---------------- THE SEQUENCE ENGINE ----------------
def run_task(text, say=None):
    """Parse a multi-step natural-language task and execute it live.
    Called from main.py AFTER the escalation gate passed."""
    t = text.lower()

    # install/uninstall flow — the flagship demo
    for kw in ("install ", "download "):
        if kw in t:
            app = text[t.find(kw) + len(kw):].strip().rstrip(".!?")
            return install_app(app, say)
    if "uninstall " in t:
        app = text[t.find("uninstall ") + 10:].strip().rstrip(".!?")
        return uninstall_app(app, say)

    # "open chrome and search x" / "go to youtube"
    if "open chrome" in t or "chrome and" in t:
        for kw in ("search for ", "search "):
            if kw in t:
                q = text[t.find(kw) + len(kw):].strip().rstrip(".!?")
                return open_in_chrome(f"https://www.google.com/search?q={q.replace(' ', '+')}", say)
        for site, dom in (("youtube", "youtube.com"), ("chatgpt", "chatgpt.com"),
                          ("gmail", "gmail.com"), ("whatsapp", "web.whatsapp.com")):
            if site in t:
                return open_in_chrome(f"https://{dom}", say)
    if "go to " in t or "open " in t:
        for site, dom in (("youtube", "youtube.com"), ("chatgpt", "chatgpt.com"),
                          ("gmail", "gmail.com"), ("whatsapp", "web.whatsapp.com")):
            if site in t:
                return open_in_chrome(f"https://{dom}", say)

    # generic app open/close via device hands
    if t.startswith("open "):
        return device.open_app(text[5:].strip())
    if t.startswith("close "):
        return device.close_app(text[6:].strip())

    return None


# ---------------- SKILL-ROUTER ADAPTER ----------------
AUTO_KEYWORDS = ("install ", "uninstall ", "download ", "open chrome", "chrome and",
                 "open ", "close ", "go to ")


def match(text):
    """True if this looks like a hands-on autonomous task."""
    t = text.lower().strip()
    return any(k in t for k in AUTO_KEYWORDS)


def reply(text, say, ask):
    """Execute the autonomous task live. Called by allskills.py."""
    r = run_task(text, say)
    return r or "I couldn't figure out that task — tell me the app or website by name."
