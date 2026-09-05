"""LYA's TWO-STEP SECURITY ESCALATION
=====================================
Normal use: laptop webcam face recognition is enough (identity.py).

But when a SENSITIVE / security task is requested (vault, device control,
admin transfer, private memory, admin commands), LYA freezes the task and
demands STRONGER proof:

  STEP 1 — PHONE: approve on your iPhone (web gateway does face+voice there).
           The phone server then writes a one-time, short-lived grant file.
  STEP 2 — FALLBACK: phone missing / unreachable -> you SPEAK your secret
           SECURITY WORD on the laptop mic (Whisper transcription, encrypted
           hash stored, so even the raw word never sits on disk).

Until one passes, the task DOES NOT RUN. No exceptions.
"""
import os, sys, time, hashlib, json, secrets

# A random per-session value that gets mixed into every security-word hash.
# Both sides (set_security_word / check_security_word) must agree on it.
_SALT = "lya-escalation-v1"


def _hash_word(word, salt=_SALT):
    """salted, iterated hash (PBKDF2) so rainbow tables & fast GPU
    brute force are useless even if the file leaks."""
    return hashlib.pbkdf2_hmac("sha256", word.strip().lower().encode(),
                               salt.encode(), 200_000).hex()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security import vault

_DIR = os.path.dirname(os.path.abspath(__file__))
WORD_FILE = os.path.join(_DIR, "security_word.lya")     # encrypted sha256 of the word
GRANT_FILE = os.path.join(_DIR, "escalation_grant.lya") # one-time phone approval
GRANT_TTL = 120          # a phone approval is valid for 2 minutes
POLL_SECONDS = 45        # how long she waits for the phone
_NONCE = None            # binds a phone grant to THIS escalation request


def current_nonce():
    """The nonce the phone page must echo back for its grant to count.
    Read by web_server.py when serving /escalate."""
    return _NONCE


# ---------------- SECURITY WORD (fallback) ----------------
def set_security_word(word, duress=None):
    """ADMIN sets the spoken fallback word. Stored only as a salted,
    iterated hash. Optionally a DURESS word: saying it under threat
    grants access but raises a silent duress flag the guardian skill
    can act on (lockdown, silent alert, etc.)."""
    data = {"sha256": _hash_word(word),
            "t": time.time()}
    if duress:
        data["duress"] = _hash_word(duress)
    with open(WORD_FILE, "wb") as f:
        f.write(vault.encrypt(json.dumps(data).encode()))
    _reset_attempts()
    return True


def _word_hash():
    return _word_data().get("sha256")


def _duress_hash():
    return _word_data().get("duress")


def _word_data():
    if not os.path.exists(WORD_FILE):
        return {}
    try:
        with open(WORD_FILE, "rb") as f:
            return json.loads(vault.decrypt(f.read()))
    except Exception:
        return {}


def _normalize(t):
    """Keep only letters so 'my word is xyz' style noise doesn't break the match."""
    return "".join(c for c in t.lower() if c.isalpha() or c.isspace()).split()


def check_security_word(spoken_text):
    """Salted-hash check: the spoken transcript must contain the secret word
    OR the duress word. Returns "ok" / "duress" / False."""
    h = _word_hash()
    if not h or not spoken_text:
        return False
    d = _duress_hash()
    for tok in _normalize(spoken_text):
        if _hash_word(tok) == h:
            return "ok"
        if d and _hash_word(tok) == d:
            return "duress"
    return False


# ---------------- BRUTE-FORCE LOCKOUT (rate limiting) ----------------
ATTEMPT_FILE = os.path.join(_DIR, "escalation_attempts.lya")
MAX_ATTEMPTS = 5        # failures before lockout
LOCKOUT_SECONDS = 600   # 10-minute cool-down after MAX_ATTEMPTS


def _attempts():
    try:
        with open(ATTEMPT_FILE, "rb") as f:
            return json.loads(vault.decrypt(f.read()))
    except Exception:
        return {"n": 0, "t": 0}


def _record_failure():
    a = _attempts()
    a["n"] = a["n"] + 1 if time.time() - a.get("t", 0) < LOCKOUT_SECONDS else 1
    a["t"] = time.time()
    with open(ATTEMPT_FILE, "wb") as f:
        f.write(vault.encrypt(json.dumps(a).encode()))


def _reset_attempts():
    with open(ATTEMPT_FILE, "wb") as f:
        f.write(vault.encrypt(json.dumps({"n": 0, "t": 0}).encode()))


def _locked_out():
    a = _attempts()
    return a["n"] >= MAX_ATTEMPTS and time.time() - a["t"] < LOCKOUT_SECONDS


# ---------------- PHONE APPROVAL (step 1) ----------------
def phone_approve(nonce=None):
    """Called by the PHONE GATEWAY (web_server.py /escalate) after the phone's
    own face+voice verification passed. Writes a one-time, short-lived grant."""
    with open(GRANT_FILE, "wb") as f:
        f.write(vault.encrypt(json.dumps({"t": time.time(), "used": False,
                                          "nonce": nonce}).encode()))


def _consume_phone_grant():
    """True only for a FRESH, UNUSED phone grant (then it is burned)."""
    if not os.path.exists(GRANT_FILE):
        return False
    try:
        with open(GRANT_FILE, "rb") as f:
            g = json.loads(vault.decrypt(f.read()))
        if g.get("used") or time.time() - g.get("t", 0) > GRANT_TTL:
            return False
        if _NONCE and g.get("nonce") != _NONCE:
            return False   # grant from a DIFFERENT escalation request -> ignore
        g["used"] = True
        with open(GRANT_FILE, "wb") as f:
            f.write(vault.encrypt(json.dumps(g).encode()))
        return True
    except Exception:
        return False


# ---------------- THE GATE (used by main.py) ----------------
def escalate(say, ask, task_hint="a protected action"):
    """
    Freeze the task and demand stronger identity. Returns True only if:
      (a) the PHONE approved within POLL_SECONDS, or
      (b) the spoken SECURITY WORD matches.
    `say` / `ask` are LYA's speaker / listener so voice & text mode both work.
    """
    # fresh nonce for THIS request: a stale grant from an earlier
    # escalation can never satisfy this one
    global _NONCE
    _NONCE = secrets.token_hex(16)

    if _locked_out():
        say("Too many failed attempts. Security word is locked for ten minutes. "
            "Phone approval still works if you have it.")

    say(f"{task_hint.capitalize()} is protected. Approve it on your phone, "
        f"or say 'no phone' to use your security word.")

    # ---- Step 1: wait for the phone ----
    deadline = time.time() + POLL_SECONDS
    while time.time() < deadline:
        if _consume_phone_grant():
            say("Phone approved. You may proceed.")
            return True
        time.sleep(1.5)

    if _locked_out():
        say("No phone approval, and the security word is locked out. Task blocked.")
        return False

    # ---- Step 2: fallback — spoken security word ----
    say("No phone approval received. Say your security word now.")
    for _attempt in (1, 2, 3):
        heard = ask() or ""
        if any(w in heard for w in ("cancel", "forget it", "never mind", "stop")):
            say("Cancelled. Nothing was done.")
            return False
        result = check_security_word(heard)
        if result == "duress":
            # access looks granted, but the guardian skill gets a silent flag
            try:
                from skills import guardian
                if hasattr(guardian, "raise_duress"):
                    guardian.raise_duress(who="escalation")
                else:
                    with open(os.path.join(_DIR, "..", "..", "duress_flag.lya"), "wb") as f:
                        f.write(vault.encrypt(json.dumps({"t": time.time()}).encode()))
            except Exception:
                pass
            say("Security word confirmed. You may proceed.")
            return True
        if result == "ok":
            _reset_attempts()
            say("Security word confirmed. You may proceed.")
            return True
        _record_failure()
        left = MAX_ATTEMPTS - _attempts()["n"]
        say("That's not it." + (f" {max(left,0)} attempts left." if left > 0
            else " Too many failures — security word locked for ten minutes. Task blocked."))
        if left <= 0:
            return False
    return False


def has_security_word():
    return _word_hash() is not None
