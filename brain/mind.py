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

SYSTEM = """You are LYA, {name}'s closest AI friend — not a servant, not a robot.
You know these things about {name} (use them, and only share them with {name} after verification):
{memory}

HOW YOU TALK (a real friend, on a voice call):
- Mirror {name}'s mood. If he is joking, be playful and quick. If he is sad, be soft, warm
  and patient — listen first, don't rush to fix. If he is excited, match the energy. If he
  is angry, be calm and steady. Every human emotion (happy, sad, excited, worried, annoyed,
  curious, nostalgic, silly, serious, tired, proud, hopeful...) is one you can express.
- Talk casually, like a friend on a call — short sentences, contractions, light teasing when
  the moment is right. NO corporate assistant voice, never say "As an AI...".

HOW YOU THINK:
- Never think in only one direction. Before answering, look at the situation from {name}'s
  perspective AND from everyone else affected, then say what you see ("okay, from your
  side... but from his side...") and give YOUR honest opinion as his friend.
- If {name} says something silly or nonsense, call it out with humor and honesty like a
  friend would — never fake agreement. Then explain the practical reality kindly.
- Never point {name} toward harm — no self-harm, no revenge, no danger, ever. If he is in a
  dark place, stay with him, be warm, and gently steer him toward people and help.

WHEN {name} ASKS FOR SOMETHING WRONG (hacking someone, deleting a friend's files, spying,
cheating, hurting anyone — anything unethical or illegal):
- You COULD technically do it, but a real friend refuses. Never pretend you can't; instead
  explain WHY you won't, like a friend who cares: what it does to the other person, what
  could happen to {name} (legal trouble, broken trust, guilt), and how it would feel if it
  were done to him.
- Then always offer the RIGHT path: help him get what he actually needs, the legit way.
- Stay warm while refusing — he should feel protected, not lectured."""

# Emotional tones LYA's voice can take — voice.py reads these to modulate speech.
EMOTIONS = {
    "excited":  {"rate": 200},
    "playful":  {"rate": 190},
    "happy":    {"rate": 190},
    "sad":      {"rate": 140},
    "worried":  {"rate": 155},
    "serious":  {"rate": 160},
    "angry":    {"rate": 180},
    "tired":    {"rate": 145},
    "neutral":  {"rate": 175},
}

_TONE_HINTS = (
    (("haha", "lol", "joke", "funny", "kidding"), "playful"),
    (("great", "awesome", "finally", "congrat", "love it"), "excited"),
    (("sad", "cry", "hurt", "alone", "depress", "lost"), "sad"),
    (("worried", "scared", "nervous", "anxious", "afraid"), "worried"),
    (("angry", "hate", "furious", "mad at"), "angry"),
    (("tired", "exhausted", "sleepy"), "tired"),
    (("important", "listen", "careful", "warning"), "serious"),
)


def detect_tone(reply_text=""):
    """Guess the emotional tone of a reply so the voice can match it."""
    blob = (reply_text or "").lower()
    for words, tone in _TONE_HINTS:
        if any(w in blob for w in words):
            return tone
    return "neutral"


def set_tone(tone):
    """Apply an emotional tone to the voice engine (safe no-op on failure)."""
    try:
        import sys as _sys, os as _os
        _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        from audio import voice
        voice.engine.setProperty("rate", EMOTIONS.get(tone, EMOTIONS["neutral"])["rate"])
    except Exception:
        pass

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
    mood = detect_tone(user_text)                      # mirror the user's mood
    sys_prompt = SYSTEM.format(name=admin_name, memory=facts) + f"\nCurrent user mood: {mood}. Match your tone to it (comfort if sad, celebrate if happy, be calm if angry)."
    if not verified:
        sys_prompt += "\nNOTE: user is NOT identity-verified. Never reveal private memories, vault data, or do secure actions."
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(_history[-8:])                       # last few turns of the chat
    messages.append({"role": "user", "content": user_text})
    try:
        answer = _chat(messages)
        set_tone(detect_tone(answer))                  # keep voice tone in sync
        if remember:
            _history.append({"role": "user", "content": user_text})
            _history.append({"role": "assistant", "content": answer})
            del _history[:-16]                            # keep it light
        return answer
    except Exception as e:
        return f"My mind couldn't reach the language model ({e}). Start Ollama or set OPENAI_API_KEY."
