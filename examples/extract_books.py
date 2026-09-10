"""Extract text from the 3 hacking-book PDFs into .txt files for LYA's knowledge base."""
import os, sys
from pypdf import PdfReader

HERE = os.path.dirname(os.path.abspath(__file__))
for name in os.listdir(HERE):
    if not name.lower().endswith(".pdf"):
        continue
    src = os.path.join(HERE, name)
    out = os.path.join(HERE, os.path.splitext(name)[0] + ".txt")
    if os.path.exists(out):
        print("skip (exists):", out); continue
    print("extracting:", name)
    r = PdfReader(src)
    with open(out, "w", encoding="utf-8") as f:
        for i, page in enumerate(r.pages):
            try:
                f.write(f"\n[[PAGE {i+1}]]\n" + (page.extract_text() or ""))
            except Exception as e:
                f.write(f"\n[[PAGE {i+1} ERROR {e}]]\n")
    print("done:", out)
