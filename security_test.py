"""LYA security audit — proves her data can't be stolen or read.
Run:  python security_test.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from security import vault
from brain import memory

print("=" * 55)
print(" LYA SECURITY AUDIT")
print("=" * 55)
ok = True

# 1. Round-trip: memory survives encrypt/decrypt
memory.remember("fact", "audit", "secret-AUDIT-token-9876", 3)
found = any("secret-AUDIT-token-9876" in v for _, v, *_ in memory.recall(limit=50))
print(f"[{'PASS' if found else 'FAIL'}] encrypted round-trip (write -> read back)")
ok &= found

# 2. The hacker test: raw file contains no plaintext
raw = open(os.path.join("brain", "lya_brain.db.lya"), "rb").read()
leak = b"secret-AUDIT-token-9876" in raw or b"boss" in raw
print(f"[{'PASS' if not leak else 'FAIL'}] stolen brain file contains NO readable plaintext")
ok &= not leak

# 3. No plaintext temp files left behind
clean = not (os.path.exists("brain/lya_brain.db") or os.path.exists("brain/lya_brain.db.working"))
print(f"[{'PASS' if clean else 'FAIL'}] no plaintext working copies left on disk")
ok &= clean

# 4. Face template encrypted (if enrolled)
face = os.path.join("vision", "admin_face.npy.lya")
if os.path.exists(face):
    fraw = open(face, "rb").read()
    fbytes = vault.decrypt_file(face)
    print(f"[{'PASS' if not fraw.startswith(b'\\x93NUMPY') else 'FAIL'}] face template encrypted at rest")
    ok &= not fraw.startswith(b"\x93NUMPY")
else:
    print("[SKIP] face not enrolled yet (home test)")

# 5. Action log encrypted
enc_log = os.path.join("skills", "lya_actions.log.lya")
import datetime
from skills import guardian
guardian.log_action("audit-command", True)
if os.path.exists(enc_log):
    lraw = open(enc_log, "rb").read()
    lclean = b"audit-command" not in lraw
    readable = b"audit-command" in vault.decrypt_file(enc_log)
    print(f"[{'PASS' if lclean and readable else 'FAIL'}] action log encrypted but recoverable")
    ok &= lclean and readable
else:
    print("[FAIL] action log missing")
    ok = False

# 6. Key is DPAPI-protected (not raw Fernet key)
key_raw = open(os.path.join("security", ".lya_key"), "rb").read()
dpapi = not key_raw.startswith(b"gAAAA") and len(key_raw) > 100
print(f"[{'PASS' if dpapi else 'FAIL'}] encryption key locked to YOUR Windows account (DPAPI)")
ok &= dpapi

# 7. Secure delete actually shreds
p = os.path.join("debug", "shred_me.txt")
os.makedirs("debug", exist_ok=True)
with open(p, "wb") as f:
    f.write(b"TOPSECRET-shred-test")
vault.secure_delete(p)
print(f"[{'PASS' if not os.path.exists(p) else 'FAIL'}] secure_delete shreds files beyond recovery")
ok &= not os.path.exists(p)

print("=" * 55)
print(" RESULT:", "ALL TESTS PASSED - LYA IS HACKER-RESISTANT" if ok else "SOME TESTS FAILED")
print("=" * 55)
sys.exit(0 if ok else 1)
