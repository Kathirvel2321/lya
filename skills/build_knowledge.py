"""Build LYA's security KNOWLEDGE BASE from her example PDFs.
==============================================================
Reads every .pdf in lya/examples/ (your 3 ethical-hacking books),
extracts the text with pypdf and stores it in ONE compressed
knowledge file that the trainer loads at startup.

Run manually:   python lya/skills/build_knowledge.py
It also auto-runs the first time learnhack starts (takes ~30s once).
"""
import os, gzip, re, logging

# pypdf spams thousands of font warnings to stderr (looks like a crash)
logging.getLogger("pypdf").setLevel(logging.ERROR)

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.normpath(os.path.join(HERE, "..", "examples"))
OUT = os.path.join(HERE, "book_knowledge.txt.gz")

def build():
    try:
        from pypdf import PdfReader
    except ImportError:
        return "pypdf missing — run: pip install pypdf"
    chunks = []
    names = sorted(f for f in os.listdir(EXAMPLES) if f.lower().endswith(".pdf"))
    if not names:
        return f"No PDFs found in {EXAMPLES}"
    for name in names:
        path = os.path.join(EXAMPLES, name)
        try:
            reader = PdfReader(path)
        except Exception as e:
            chunks.append(f"\n\n=== {name}: unreadable ({e}) ===\n")
            continue
        buf = [f"\n\n===== BOOK: {name} ({len(reader.pages)} pages) =====\n"]
        for i, page in enumerate(reader.pages):
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            txt = re.sub(r"[ \t]+", " ", txt)
            txt = re.sub(r"\n{3,}", "\n\n", txt)
            if txt.strip():
                buf.append(f"\n[p{i+1}]\n{txt.strip()}\n")
        chunks.append("".join(buf))
        print(f"  + {name}: {len(reader.pages)} pages ingested")
    text = "".join(chunks)
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        f.write(text)
    return (f"Knowledge base built: {len(names)} book(s), "
            f"{len(text):,} characters -> {os.path.basename(OUT)}")

if __name__ == "__main__":
    print(build())
