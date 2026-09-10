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
import os, sys, time, hashlib, hmac, json, secrets

# Legacy salt: a hardcoded constant, identical on every LYA install. Kept ONLY
# so security words set before the per-install salt existed still verify.
# New words get a random 16-byte salt stored beside the hash (see set_security_word).
_LEGACY_SALT = "lya-escalation-v1"


def _normalize(text):
    """Lowercase; letters and spaces only; whitespace collapsed.

    BOTH set_security_word and check_security_word run through this, so the
    phrase that was stored is exactly the phrase that can match. (They used to
    normalize differently — set hashed the whole string, check hashed single
    tokens — which meant any multi-word phrase could never be matched.)"""
    cleaned = "".join(c if (c.isalpha() or c.isspace()) else " " for c in text.lower())
    return " ".join(cleaned.split())


def _hash_word(phrase, salt=_LEGACY_SALT):
    """Salted, iterated hash (PBKDF2) so rainbow tables & fast GPU brute force
    are useless even if the file leaks. `phrase` must already be normalized."""
    return hashlib.pbkdf2_hmac("sha256", phrase.encode(),
                               salt.encode(), 200_000).hex()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security import vault

_DIR = os.path.dirname(os.path.abspath(__file__))
WORD_FILE = os.path.join(_DIR, "security_word.lya")     # encrypted sha256 of the word
GRANT_FILE = os.path.join(_DIR, "escalation_grant.lya") # one-time phone approval
GRANT_TTL = 120          # a phone approval is valid for 2 minutes
POLL_SECONDS = 45        # how long she waits for the phone
_NONCE = None            # binds a phone grant to THIS escalation request


CHALLENGE_FILE = os.path.join(_DIR, "escalation_challenge.lya")


def _write_challenge(nonce, task="Protected action"):
    with open(CHALLENGE_FILE, "wb") as f:
        f.write(vault.encrypt(json.dumps({"nonce": nonce, "t": time.time(), "task": task}).encode()))


def _clear_challenge():
    if os.path.exists(CHALLENGE_FILE):
        os.remove(CHALLENGE_FILE)


def current_nonce():
    """The nonce the phone page must echo back for its grant to count.

    Read by web_server.py, which runs in a DIFFERENT PROCESS - so this has to
    come off disk, not from the in-memory global. It used to return `_NONCE`,
    which on the server side was always None; the grant was then written with
    nonce=None and the laptop's check `g["nonce"] != _NONCE` rejected it every
    single time. Phone approval could never succeed."""
    try:
        with open(CHALLENGE_FILE, "rb") as f:
            c = json.loads(vault.decrypt(f.read()))
    except Exception:
        return None
    # A challenge outlives its escalate() call by at most one grant window.
    if time.time() - c.get("t", 0) > POLL_SECONDS + GRANT_TTL:
        return None
    return c.get("nonce")


# ---------------- SECURITY WORD (fallback) ----------------
def set_security_word(word, duress=None):
    """ADMIN sets the spoken fallback word OR PHRASE. Stored only as a salted,
    iterated hash, under a salt unique to this install. Optionally a DURESS
    phrase: saying it under threat grants access but raises a silent duress
    flag the guardian skill can act on (lockdown, silent alert, etc.).

    Multi-word phrases work: the word count is stored so check_security_word
    knows how wide a window to slide over the transcript."""
    phrase = _normalize(word)
    if not phrase:
        raise ValueError("security word must contain at least one letter")
    salt = secrets.token_hex(16)          # unique per install, not a constant
    data = {"salt": salt,
            "sha256": _hash_word(phrase, salt),
            "words": len(phrase.split()),
            "t": time.time()}
    if duress:
        d_phrase = _normalize(duress)
        if d_phrase == phrase:
            raise ValueError("duress phrase must differ from the security phrase")
        if d_phrase:
            data["duress"] = _hash_word(d_phrase, salt)
            data["duress_words"] = len(d_phrase.split())
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
    except Exception as e:
        # Fail-closed (an empty dict makes every check return False), but say so.
        # Silence here looked identical to "no security word set", which is how
        # a corrupted or wrong-Windows-user vault went unnoticed.
        print(f"[LYA][SECURITY] security word file unreadable ({e}) - the spoken "
              f"fallback is DISABLED until you re-set it.")
        return {}


# Transcripts are searched with a sliding window, and every window costs one
# 200k-iteration PBKDF2 (~50-100ms). Cap the scan so a rambling transcript
# can't stall the voice loop for seconds. A security phrase is never buried
# 12 words into a sentence in practice.
MAX_SCAN_TOKENS = 12


def check_security_word(spoken_text):
    """Salted-hash check: the transcript must CONTAIN the secret phrase (or the
    duress phrase) as a run of consecutive words. Returns "ok"/"duress"/False.

    Slides a window as wide as the stored phrase, so "my word is open sesame"
    still matches a stored phrase of "open sesame". Single words are just the
    width-1 case, so short secrets behave exactly as before."""
    data = _word_data()
    h = data.get("sha256")
    if not h or not spoken_text:
        return False
    salt = data.get("salt", _LEGACY_SALT)   # legacy files have no stored salt
    toks = _normalize(spoken_text).split()[:MAX_SCAN_TOKENS]
    if not toks:
        return False

    def _contains(target_hash, width):
        if not target_hash or not (0 < width <= len(toks)):
            return False
        for i in range(len(toks) - width + 1):
            if hmac.compare_digest(_hash_word(" ".join(toks[i:i + width]), salt),
                                   target_hash):
                return True
        return False

    # Duress is checked FIRST: if a transcript could be read either way, the
    # safe interpretation is "he is being coerced", not "all clear".
    if _contains(data.get("duress"), data.get("duress_words", 1)):
        return "duress"
    if _contains(h, data.get("words", 1)):
        return "ok"
    return False


# ---------------- BRUTE-FORCE LOCKOUT (rate limiting) ----------------
ATTEMPT_FILE = os.path.join(_DIR, "escalation_attempts.lya")
MAX_ATTEMPTS = 5        # failures before lockout
LOCKOUT_SECONDS = 600   # 10-minute cool-down after MAX_ATTEMPTS


_TAMPERED = {"n": MAX_ATTEMPTS, "t": 0, "tampered": True}


def _attempts():
    """Read the failure counter.

    Fails CLOSED. This used to `return {"n": 0}` on ANY exception, so deleting
    or corrupting escalation_attempts.lya silently switched the brute-force
    lockout off entirely - the one file an attacker would most want to break.
    A missing file is a genuine zero; an unreadable one is treated as locked.
    Recover with:  python main.py setsecurityword <word>   (resets the counter)"""
    if not os.path.exists(ATTEMPT_FILE):
        return {"n": 0, "t": 0}
    try:
        with open(ATTEMPT_FILE, "rb") as f:
            return json.loads(vault.decrypt(f.read()))
    except Exception as e:
        print(f"[LYA][SECURITY] attempt counter unreadable ({e}) - "
              f"assuming LOCKED OUT. Re-set your security word to reset it.")
        return dict(_TAMPERED)


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
    if a.get("tampered"):
        return True          # unreadable counter -> locked, no timer to wait out
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
        if g.get("used") or not 0 <= time.time() - g.get("t", 0) <= GRANT_TTL:
            return False
        # Fail CLOSED: was `if _NONCE and ...`, which accepted any grant
        # whenever no challenge was active. A grant must always name the
        # challenge it answers.
        if not _NONCE or g.get("nonce") != _NONCE:
            return False   # no active challenge, or grant for a different one
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
    # escalation can never satisfy this one. Published to disk so the phone
    # gateway (separate process) can echo it back.
    global _NONCE
    _NONCE = secrets.token_hex(16)
    _write_challenge(_NONCE)
    try:
        return _escalate_inner(say, ask, task_hint)
    finally:
        _NONCE = None
        _clear_challenge()   # challenge dies with the request, win or lose


def _escalate_inner(say, ask, task_hint):
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
                    # ..\..\ escaped the project entirely - the flag landed
                    # outside the repo where nothing would ever read it.
                    with open(os.path.join(_DIR, "duress_flag.lya"), "wb") as f:
                        f.write(vault.encrypt(json.dumps({"t": time.time()}).encode()))
            except Exception as e:
                # A duress alarm that fails silently is worse than none - the
                # user believes an alert went out. Say it, without tipping off
                # whoever is standing over them (stderr, not the voice channel).
                print(f"[LYA][SECURITY] DURESS FLAG FAILED TO WRITE: {e}",
                      file=sys.stderr)
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


if __name__ == "__main__":
    # Self-check for the set/check hashing contract. Backs up and restores the
    # real security word — running this must never lock the owner out.
    import shutil, tempfile
    _backups = {}
    for _p in (WORD_FILE, ATTEMPT_FILE, GRANT_FILE, CHALLENGE_FILE):
        if os.path.exists(_p):
            _b = tempfile.mktemp(suffix=".lya")
            shutil.copy2(_p, _b)
            _backups[_p] = _b
    try:
        # --- the bug this fixes: a multi-word phrase could never match ---
        set_security_word("open sesame")
        assert check_security_word("open sesame") == "ok", "exact phrase failed"
        assert check_security_word("my word is open sesame") == "ok", "embedded phrase failed"
        assert check_security_word("Open, Sesame!") == "ok", "punctuation/case failed"
        assert check_security_word("open") is False, "partial phrase must NOT pass"
        assert check_security_word("sesame open") is False, "word order must matter"
        assert check_security_word("") is False, "empty must not pass"

        # --- single word still behaves as before ---
        set_security_word("thunderbolt")
        assert check_security_word("thunderbolt") == "ok", "single word failed"
        assert check_security_word("uh my word is thunderbolt i think") == "ok", "noise failed"
        assert check_security_word("thunder") is False, "prefix must not pass"

        # --- duress wins over the normal phrase, and is length-independent ---
        set_security_word("blue horizon", duress="red winter sky")
        assert check_security_word("blue horizon") == "ok", "phrase failed w/ duress set"
        assert check_security_word("red winter sky") == "duress", "duress failed"
        assert check_security_word("say red winter sky now") == "duress", "embedded duress failed"

        # --- salt really is per-install, not the old shared constant ---
        set_security_word("same phrase")
        h1 = _word_data()
        set_security_word("same phrase")
        h2 = _word_data()
        assert h1["salt"] != h2["salt"], "salt is not random per set"
        assert h1["sha256"] != h2["sha256"], "same phrase produced same hash"

        try:
            set_security_word("!!!")
            raise AssertionError("empty-after-normalize should have raised")
        except ValueError:
            pass
        try:
            set_security_word("alpha", duress="alpha")
            raise AssertionError("identical duress should have raised")
        except ValueError:
            pass

        # --- cross-process nonce: the phone gateway reads it off DISK ---
        _clear_challenge()
        assert current_nonce() is None, "no challenge should mean no nonce"

        _NONCE = "challenge-abc123"
        _write_challenge(_NONCE)
        # what the SERVER process sees (it has no _NONCE of its own):
        assert current_nonce() == "challenge-abc123", "nonce did not cross to disk"

        # a grant echoing the right nonce is consumed exactly once
        phone_approve(nonce=current_nonce())
        assert _consume_phone_grant() is True, "valid phone grant rejected"
        assert _consume_phone_grant() is False, "grant was reusable - not one-time"

        # a grant for a DIFFERENT challenge is refused
        phone_approve(nonce="some-other-challenge")
        assert _consume_phone_grant() is False, "grant from another request accepted"

        # the old bug: server wrote nonce=None, laptop must refuse it
        phone_approve(nonce=None)
        assert _consume_phone_grant() is False, "nonce-less grant accepted"

        # fail CLOSED when no challenge is active
        _NONCE = None
        phone_approve(nonce="challenge-abc123")
        assert _consume_phone_grant() is False, "grant accepted with no active challenge"
        _clear_challenge()

        # --- lockout must fail CLOSED on a corrupt counter ---
        _reset_attempts()
        assert _locked_out() is False, "fresh counter should not be locked"
        with open(ATTEMPT_FILE, "wb") as _f:
            _f.write(b"not valid ciphertext")      # simulate tamper/corruption
        assert _locked_out() is True, "corrupt counter must lock out, not open up"
        os.remove(ATTEMPT_FILE)
        assert _locked_out() is False, "a MISSING counter is a genuine zero"

        # counting still works
        _reset_attempts()
        for _ in range(MAX_ATTEMPTS):
            _record_failure()
        assert _locked_out() is True, "should lock after MAX_ATTEMPTS"
        _reset_attempts()
        assert _locked_out() is False, "reset should clear the lockout"

        print("escalation.py self-check PASSED - phrases, duress, salting, "
              "rejects, cross-process nonce, fail-closed lockout")
    finally:
        for _p in (WORD_FILE, ATTEMPT_FILE):
            os.path.exists(_p) and os.remove(_p)
        for _p, _b in _backups.items():
            shutil.copy2(_b, _p)
            os.remove(_b)
        print("(original security word restored)")


# Desktop runtime uses phone-only approval; spoken fallback is legacy only.
import threading
_request_lock = threading.Lock()

def current_challenge():
    try:
        with open(CHALLENGE_FILE, "rb") as f:
            data = json.loads(vault.decrypt(f.read()))
        if 0 <= time.time() - data["t"] <= POLL_SECONDS + GRANT_TTL:
            return data
    except (OSError, ValueError, KeyError):
        pass
    return None

def request_phone(task, cancelled=None, seconds=120):
    global _NONCE
    if not _request_lock.acquire(blocking=False):
        return False
    try:
        _NONCE = secrets.token_hex(16)
        _write_challenge(_NONCE, task)
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if cancelled and cancelled.is_set():
                return False
            if _consume_phone_grant():
                return True
            time.sleep(0.2)
        return False
    finally:
        _NONCE = None
        _clear_challenge()
        _request_lock.release()
