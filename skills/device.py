"""LYA's hands — full device control. Windows-focused.
She acts ONLY on your explicit command, and dangerous commands are
double-checked by guardian.py first."""
import os, subprocess, webbrowser, pyautogui, datetime

pyautogui.FAILSAFE = True

APP_MAP = {
    "notepad": "notepad", "calculator": "calc", "chrome": "chrome",
    "file explorer": "explorer", "cmd": "cmd", "terminal": "wt",
    "settings": "start ms-settings:", "task manager": "taskmgr",
    "vs code": "code", "spotify": "spotify",
}

def open_app(name):
    exe = APP_MAP.get(name.lower(), name)
    try:
        os.system(f"start {exe}")
        return f"Opening {name}."
    except Exception as e:
        return f"Couldn't open {name}: {e}"

def close_app(name):
    os.system(f"taskkill /f /im {name}.exe >nul 2>&1")
    return f"Closed {name}."

def search_web(query):
    webbrowser.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
    return f"Searching the web for {query}."

def type_text(text):
    pyautogui.typewrite(text, interval=0.02)
    return "Typed."

def screenshot():
    folder = os.path.join(os.path.dirname(__file__), "..", "shots")
    os.makedirs(folder, exist_ok=True)
    path = os.path.abspath(os.path.join(folder, f"lya_shot_{datetime.datetime.now():%Y%m%d_%H%M%S}.png"))
    pyautogui.screenshot(path)
    return f"Screenshot saved to {path}."

def run_command(cmd):
    """Direct shell command — guardian must approve first."""
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return (out.stdout or out.stderr or "Done.").strip()[:1500]

def volume(action):
    key = {"up": "volumeup", "down": "volumedown", "mute": "volumemute"}.get(action)
    pyautogui.press(key)
    return f"Volume {action}."

HANDS = {
    "open": open_app, "close": close_app, "search": search_web,
    "type": type_text, "screenshot": screenshot, "volume": volume,
}
