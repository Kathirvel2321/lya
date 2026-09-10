"""LYA LLM COUNCIL — three AI minds debate before she answers big questions.
========================================================================
Inspired by deer-flow / minimind multi-agent research patterns:
  - 3 advisor models answer independently (different Groq models, free tier)
  - a chairman model reads all three and synthesizes ONE decision

Say:  "council: should I ..."   or  "gather the council, ..."
Falls back to her normal single brain if only one model is reachable.
"""
import os, sys, json, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from brain import mind

HEADERS = mind.HEADERS
GROQ_KEY = mind.GROQ_KEY

# Free-tier council seats (all on Groq's free plan — different model families
# so they genuinely disagree, like minimind vs deer-flow reviewer agents).
COUNCIL = [
    ("openai/gpt-oss-20b",    "THE LOGICIAN — cold facts, risks, numbers"),
    ("openai/gpt-oss-120b",   "THE STRATEGIST — long game, second-order effects"),
    ("qwen/qwen3.8-27b",     "THE GUARDIAN — ethics, safety, what could go wrong"),
]
CHAIRMAN = "openai/gpt-oss-120b"


def _ask(model, system, user, tokens=400):
    if not GROQ_KEY:
        return None
    # gpt-oss-20b is a reasoning model: without these params it spends the
    # whole token budget on hidden reasoning and returns empty content.
    body = json.dumps({"model": model, "max_tokens": tokens,
                       "reasoning_effort": "low", "reasoning_format": "hidden",
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]}).encode()  # noqa
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=body,
        headers={**HEADERS, "Authorization": f"Bearer {GROQ_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def decide(question, on_progress=None):
    """Run the council. on_progress(seat_name) fires as each seat speaks."""
    if not GROQ_KEY:
        return None
    from concurrent.futures import ThreadPoolExecutor
    def consult(seat):
        model, role = seat
        answer = _ask(model,
            "You are %s. Give evidence, assumptions, an alternative and the biggest risk. "
            "Do not claim to have researched sources you were not given. "
            "Agreement is not proof. Four sentences maximum." % role, question)
        return role.split(" —")[0], answer
    if on_progress:
        on_progress("Reviewing alternatives")
    with ThreadPoolExecutor(max_workers=3) as pool:
        votes = [(role, answer) for role, answer in pool.map(consult, COUNCIL) if answer]
    if not votes:
        return None
    if on_progress:
        try: on_progress("CHAIRMAN")
        except Exception: pass
    transcript = "\n\n".join("## %s\n%s" % (n, v) for n, v in votes)
    verdict = _ask(CHAIRMAN,
                   "You are CHAIRMAN of the council. Three advisors answered. "
                   "Synthesize: where they agree (not proof), where they split "
                   "(say it honestly), and ONE clear recommendation. Max 8 sentences, "
                   "spoken like a friend, not a report. Do not use markdown headers.",
                   "QUESTION: %s\n\nCOUNCIL TRANSCRIPT:\n%s" % (question, transcript),
                   tokens=450)
    if not verdict:
        # chairman failed — stitch manually
        verdict = "The council spoke:\n\n" + transcript
    return verdict, votes


def match(text):
    t = (text or "").lower()
    return ("council" in t
            or t.startswith("gather ")
            or ("should i " in t and any(w in t for w in
                ("important", "big", "decision", "invest", "quit", "buy", "career",
                 "move", "risk", "trust", "sign", "money")))
            or "second opinion" in t)


def reply(text, say, ask):
    q = text.split(":", 1)[-1].strip() or text
    if say:
        say("Gathering the council — three minds, one verdict.")
    result = decide(q, on_progress=say if say else None)
    if not result:
        return "My council needs the Groq key to seat all three minds — set GROQ_API_KEY and try again."
    verdict, votes = result
    lines = ["🎩 COUNCIL VERDICT", "", verdict, ""]
    lines.append("— %d seats voted · advisory only; no action executed" % len(votes))
    return "\n".join(lines)
