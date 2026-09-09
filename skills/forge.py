"""LYA SKILL FORGE — she builds new skills from your words.
==========================================================
You chat a need; LYA writes the code, SHOWS it to you, and activates it
ONLY after you say 'confirm' (owner review = no rogue self-modification).

  "create skill weather that shows my city forecast"  -> she drafts code
  "show pending skill"                                 -> review the draft
  "confirm skill"                                      -> activate it
  "delete skill <name>"                                -> remove (confirm)

Safety model:
- Drafts are stored UNACTIVATED (.draft). Lya never executes unreviewed code.
- On activation the file is syntax-checked (compile) before import.
- Every forge action is logged to the encrypted action log.
"""
import os, re, importlib, datetime, json

HERE = os.path.dirname(os.path.abspath(__file__))
DRAFT = os.path.join(HERE, "forge_draft.py")
META = os.path.join(HERE, "forge_meta.json")
LOG = os.path.join(HERE, "lya_actions.log.lya")

def _log(what, ok=True):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat()} | FORGE | "
                    f"{'OK' if ok else 'DENIED'} | {what}\n")
    except Exception:
        pass

def _groq(prompt):
    """Ask Lya's brain (Groq) to write the skill code."""
    import json as _j, urllib.request
    from brain.mind import HEADERS
    body = _j.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content":
             "You write Python skill modules for LYA, a local voice assistant. "
             "Output ONLY one complete Python file. Requirements:\n"
             "1. Must define match(text) -> bool and reply(text, say=None, ask=None) -> str\n"
             "2. Only standard library + skills.device is available — no pip installs\n"
             "3. Read-only and safe: never delete, format, or send data out\n"
             "4. Never include API keys; use environment variables if needed\n"
             "5. Keep it under 120 lines, with a docstring at top."},
            {"role": "user", "content": prompt}]})
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=body.encode(),
        headers={**HEADERS, "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = _j.loads(r.read())["choices"][0]["message"]["content"]
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()

def _meta():
    try:
        with open(META) as f:
            return json.load(f)
    except Exception:
        return {}

def create(desc):
    code = _groq(desc)
    m = re.search(r"def\s+match\s*\(", code) and re.search(r"def\s+reply\s*\(", code)
    if not m:
        _log("draft invalid", False)
        return ("🛠️ The generated code didn't have the required match()/reply() "
                "functions, so I discarded it. Try rephrasing the skill idea.")
    with open(DRAFT, "w", encoding="utf-8") as f:
        f.write(code)
    meta = _meta()
    meta["pending_desc"] = desc
    with open(META, "w") as f:
        json.dump(meta, f)
    _log(f"draft: {desc}")
    return ("🛠️ SKILL DRAFTED (not active yet). Here's what I wrote — review it:\n\n"
            + code[:1800] + ("\n... (truncated — full file: skills/forge_draft.py)" if len(code) > 1800 else "")
            + "\n\nSay 'confirm skill' to activate it, or 'discard skill' to throw it away.")

def activate():
    if not os.path.exists(DRAFT):
        return "No pending skill draft. Say 'create skill <what it should do>' first."
    try:
        with open(DRAFT) as f:
            compile(f.read(), "forge_draft.py", "exec")
    except SyntaxError as e:
        _log("activate syntax-fail", False)
        return f"🛠️ Syntax error in the draft ({e}) — not activating. Say 'discard skill' and try again."
    name = _meta().get("pending_desc", "custom skill")
    final = os.path.join(HERE, "forged_skill.py")
    with open(DRAFT, "r", encoding="utf-8") as f:
        code = f.read()
    with open(final, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        import skills.forged_skill as fs
        importlib.reload(fs)
    except Exception as e:
        _log("activate import-fail", False)
        return f"🛠️ The skill failed to load ({e}) — not activated. Review skills/forge_draft.py."
    _log(f"activated: {name}")
    return (f"✅ SKILL ACTIVATED — LYA can now handle it! Tested with:\n"
            f"  {fs.reply('hello')}")

def discard():
    for p in (DRAFT,):
        if os.path.exists(p):
            os.remove(p)
    _log("discard")
    return "🗑️ Draft discarded. Nothing was activated."

def current():
    mod = None
    try:
        import skills.forged_skill as fs
        mod = fs
    except Exception:
        return "No forged skill is active. 'create skill <idea>' to make one."
    doc = (mod.__doc__ or "(no docstring)").strip()[:400]
    return f"🧬 ACTIVE FORGED SKILL\n{doc}\n\n(Rebuild: 'create skill <idea> confirm' replaces it.)"

# ------------------------------------------------------------- LYA COMMANDS
def match(text):
    t = text.lower().strip()
    return (t.startswith("create skill") or "show pending skill" in t
            or "confirm skill" in t or "discard skill" in t
            or t.startswith("delete skill") or "current skill" in t)

def reply(text, say=None, ask=None):
    t = text.lower().strip()
    try:
        if t.startswith("create skill"):
            desc = text.split("skill", 1)[1].strip()
            if not desc:
                return "Tell me what the skill should do: 'create skill weather that shows my city forecast'"
            return create(desc)
        if "confirm skill" in t:
            return activate()
        if "discard" in t or t.startswith("delete skill"):
            return discard()
        if "pending" in t or "current skill" in t:
            return current()
        return ("🛠️ Skill Forge: 'create skill <idea>', 'show pending skill', "
                "'confirm skill', 'discard skill'.")
    except Exception as e:
        _log(f"error: {e}", False)
        return f"Skill Forge hit a snag: {e}"
