"""Regression tests for the six security fixes.

Each test names the bug it guards. Run:  python test_security_fixes.py

These are the checks that would have caught the original defects:
  1. secrets tracked in git            -> test_no_secrets_tracked
  2. main.py <-> identity.py mismatch  -> test_identity_api_matches_call_sites
  3. plaintext password vault          -> skills/passwords.py self-check
  4. security-word hash mismatch       -> security/escalation.py self-check
  5. global web session                -> test_sessions_are_per_client / _expire
  6. swallowed auth exceptions         -> test_lockout_fails_closed
"""
import ast, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def test_no_secrets_tracked():
    """BUG: .lya key material, voice recordings and MACs were committed to a
    PUBLIC GitHub repo because .gitignore only covered __pycache__."""
    out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    bad = [f for f in out.splitlines()
           if re.search(r"\.lya$|\.lya_key$|\.wav$|\.npy$|oui_cache|home_baseline", f)]
    assert not bad, f"secrets/biometrics still tracked by git: {bad}"


def test_identity_api_matches_call_sites():
    """BUG: main.py called enroll_admin/name_person/name_pending and read
    res['who'] - none of which identity.py provided. Face ID never enrolled."""
    src = open(os.path.join(ROOT, "vision", "identity.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    defined = {f.name: len(f.args.args)
               for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)}
    main_src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()

    for name in sorted(set(re.findall(r"identity\.(\w+)", main_src))):
        assert name in defined, f"main.py calls identity.{name}() which does not exist"

    for name, argc in [("check_secondary_password", 2), ("set_secondary_password", 2),
                       ("name_person", 2), ("enroll_admin", 2)]:
        assert defined.get(name, -1) >= argc, \
            f"identity.{name} takes {defined.get(name)} args, called with {argc}"

    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name == "identify":
            for node in ast.walk(fn):
                if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                    keys = {k.value for k in node.value.keys}
                    assert {"role", "who"} <= keys, \
                        f"identify() returns {keys}, main.py reads res['role'] and res['who']"


def test_sessions_are_per_client():
    """BUG: _session was one module-global dict. One client's face check marked
    the WHOLE SERVER verified, for everyone, forever."""
    import web_server as ws
    alice = ws._new_session()
    assert ws._session_valid(alice) is True, "issued session should be valid"
    # Bob never verified. He must not inherit Alice's state.
    assert ws._session_valid("") is False, "empty sid must not be verified"
    assert ws._session_valid(None) is False, "missing sid must not be verified"
    assert ws._session_valid("guessed-sid") is False, "unknown sid must not be verified"
    bob = ws._new_session()
    assert bob != alice, "sessions must be distinct"


def test_sessions_expire():
    """BUG: nothing ever reset the verified flag - it survived until restart."""
    import web_server as ws
    sid = ws._new_session()
    ws._sessions[sid] = time.time() - 1          # force expiry
    assert ws._session_valid(sid) is False, "expired session still accepted"
    assert sid not in ws._sessions, "expired session was not reaped"


def test_private_memory_needs_face_not_just_token():
    """BUG: the access token alone unlocked private memory reads AND writes.
    The token proves 'paired phone', not 'owner holding it'."""
    import web_server as ws
    for q in ("remember my pin is 1234", "what do you know about me",
              "when is my birthday"):
        reply = ws.lyas_answer(q, verified=False)
        assert reply == ws._NEEDS_FACE, \
            f"unverified {q!r} was answered instead of gated: {reply[:60]!r}"


def test_lockout_fails_closed():
    """BUG: _attempts() returned {'n': 0} on ANY exception, so corrupting
    escalation_attempts.lya silently disabled the brute-force lockout."""
    import shutil, tempfile
    from security import escalation as esc
    backup = None
    if os.path.exists(esc.ATTEMPT_FILE):
        backup = tempfile.mktemp(suffix=".lya")
        shutil.copy2(esc.ATTEMPT_FILE, backup)
    try:
        with open(esc.ATTEMPT_FILE, "wb") as f:
            f.write(b"corrupted")
        assert esc._locked_out() is True, "corrupt attempt counter must LOCK, not open"
        os.remove(esc.ATTEMPT_FILE)
        assert esc._locked_out() is False, "a missing counter is a genuine zero"
    finally:
        os.path.exists(esc.ATTEMPT_FILE) and os.remove(esc.ATTEMPT_FILE)
        if backup:
            shutil.copy2(backup, esc.ATTEMPT_FILE)
            os.remove(backup)


def test_phone_nonce_crosses_processes():
    """BUG: current_nonce() returned an in-memory global that was always None
    in the web-server process, so every phone approval was rejected."""
    from security import escalation as esc
    esc._clear_challenge()
    try:
        esc._NONCE = "laptop-challenge"
        esc._write_challenge(esc._NONCE)
        assert esc.current_nonce() == "laptop-challenge", "nonce did not reach disk"
        esc.phone_approve(nonce=esc.current_nonce())
        assert esc._consume_phone_grant() is True, "valid phone grant rejected"
        assert esc._consume_phone_grant() is False, "grant was replayable"
    finally:
        esc._NONCE = None
        esc._clear_challenge()
        os.path.exists(esc.GRANT_FILE) and os.remove(esc.GRANT_FILE)


def _run_module_selfcheck(rel):
    r = subprocess.run([sys.executable, os.path.join(ROOT, rel)],
                       capture_output=True, text=True, cwd=ROOT)
    assert "PASSED" in r.stdout, f"{rel} self-check failed:\n{r.stdout}\n{r.stderr}"


def test_password_vault_encrypted():
    _run_module_selfcheck(os.path.join("skills", "passwords.py"))


def test_security_word_hashing():
    _run_module_selfcheck(os.path.join("security", "escalation.py"))


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            print(f"  FAIL  {name}\n          {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {name}\n          {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
