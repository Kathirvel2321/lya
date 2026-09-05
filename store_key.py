"""Store the Groq API key DPAPI-encrypted instead of in a plaintext env var.
Run once:  python store_key.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from security import vault

key = input("Paste your Groq API key: ").strip()
if not key:
    print("No key given."); sys.exit(1)
enc = os.path.join(os.path.dirname(__file__), "security", "groq_key.lya")
with open(enc, "wb") as f:
    f.write(vault.encrypt(key.encode()))
print("Key encrypted and locked to your Windows account at:", enc)

# make mind.py auto-load it
mind = os.path.join(os.path.dirname(__file__), "brain", "mind.py")
src = open(mind, encoding="utf-8").read()
loader = '''GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
# Auto-load the DPAPI-encrypted key if present (safer than env vars)
if not GROQ_KEY:
    _k = os.path.join(os.path.dirname(__file__), "..", "security", "groq_key.lya")
    if os.path.exists(_k):
        try:
            GROQ_KEY = vault.decrypt_file(_k).decode()
        except Exception:
            pass
'''
if "groq_key.lya" not in src:
    src = src.replace('GROQ_KEY = os.environ.get("GROQ_API_KEY", "")', loader)
    # add vault import
    src = src.replace("from brain import memory", "from brain import memory\nfrom security import vault")
    open(mind, "w", encoding="utf-8").write(src)
    print("mind.py now auto-loads the encrypted key.")
