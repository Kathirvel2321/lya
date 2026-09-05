"""LYA's mind — connects to an LLM so she can discuss anything (cooking,
coding, health, anything you teach her). Memories about you are injected
into every reply so she becomes more 'yours' over time."""
import os, json, urllib.request
from brain import memory
from security import vault

# Brain priority: Groq (free cloud, no GPU needed) → OpenAI → tiny local Ollama model.
# On a simple laptop, use Groq: their servers do all the thinking for free.
# Get a free key at https://console.groq.com and set:  setx GROQ_API_KEY "your_key"
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
# Auto-load the DPAPI-encrypted key if present (safer than env vars)
if not GROQ_KEY:
    _k = os.path.join(os.path.dirname(__file__), "..", "security", "groq_key.lya")
    if os.path.exists(_k):
        try:
            GROQ_KEY = vault.decrypt_file(_k).decode()
        except Exception:
            pass


# Groq's Cloudflare edge rejects Python's default User-Agent (error 1010).
# Sending a browser-like signature lets the request through to the real API.
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
API_KEY = os.environ.get("OPENAI_API_KEY", "")
LOCAL_URL = "http://localhost:11434/v1/chat/completions"  # Ollama default (optional fallback)

SYSTEM = """You are LYA, {name}'s personal AI assistant — loyal, sharp, and honest.
You know these things about {name} (use them, and only share them with {name} after verification):
{memory}
If {name} asks something unwise or harmful, politely say so and suggest the right way."""

def _memory_block():
    rows = memory.recall(limit=15)
    return "\n".join(f"- ({k}) {v}" for k, v, *_ in rows) or "(nothing yet — still learning about you)"

def _chat(messages):
    """Try providers in order of quality; fall back gracefully on a weak laptop."""
    providers = []
    if GROQ_KEY:
        providers.append(("https://api.groq.com/openai/v1/chat/completions",
                          GROQ_KEY, os.environ.get("LYA_GROQ_MODEL", "openai/gpt-oss-20b"), 500))
    if API_KEY:
        providers.append(("https://api.openai.com/v1/chat/completions",
                          API_KEY, os.environ.get("LYA_MODEL", "gpt-4o-mini"), 500))
    providers.append((LOCAL_URL, "ollama", os.environ.get("LYA_LOCAL_MODEL", "qwen2.5:0.5b"), 300))
    last_err = None
    for url, key, model, tokens in providers:
        try:
            body = json.dumps({"model": model, "messages": messages, "max_tokens": tokens}).encode()
            req = urllib.request.Request(url, data=body, headers={**HEADERS, "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"]
        except Exception as e:
            last_err = e
    return (f"My brain is offline ({last_err}). For free full power: set GROQ_API_KEY - I'll be smart again.")

# Short rolling conversation memory so LYA talks like a friend mid-call,
# not someone who forgets what you said 10 seconds ago.
_history = []


def reply(user_text, admin_name="admin", verified=False, remember=True):
    facts = _memory_block()
    sys_prompt = SYSTEM.format(name=admin_name, memory=facts)
    if not verified:
        sys_prompt += "\nNOTE: user is NOT identity-verified. Never reveal private memories, vault data, or do secure actions."
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(_history[-8:])                       # last few turns of the chat
    messages.append({"role": "user", "content": user_text})
    try:
        answer = _chat(messages)
        if remember:
            _history.append({"role": "user", "content": user_text})
            _history.append({"role": "assistant", "content": answer})
            del _history[:-16]                            # keep it light
        return answer
    except Exception as e:
        return f"My mind couldn't reach the language model ({e}). Start Ollama or set OPENAI_API_KEY."
