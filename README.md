# LYA — your personal ULTRON-level assistant

## Security — her brain is fully encrypted
Everything LYA knows is encrypted with AES-256 before touching the disk:
- Memory DB (`lya_brain.db.lya`) — facts, conversations, admin identity
- Face template (`admin_face.npy.lya`) — your biometric data
- Action logs (`lya_actions.log.lya`) — command history
- The AES key itself is protected by **Windows DPAPI**, bound to YOUR Windows user account.
  Copying the files to another PC or user account = useless garbage.
- Working copies are **secure-deleted** (overwritten with random bytes) after every use.

Verify yourself: `python security_test.py`

## Her brain on a simple laptop — GROQ (free, no GPU needed)
LYA's thinking happens in the cloud so your laptop does nothing heavy.
1. Free account at https://console.groq.com (no credit card)
2. Copy your API key
3. In PowerShell:
```
setx GROQ_API_KEY "your_key_here"
```
4. Restart the terminal, run `python main.py` — she's now a genius.

Optional offline fallback (works without GPU, uses RAM):
```
ollama pull qwen2.5:0.5b
```

## What she can do right now
- Wake up only when someone says **"LYA"** (Siri-style)
- Answer simple questions from **anyone** (time, weather, "who are you")
- **Face-verify you** before touching private data or dangerous commands
- Remember everything you teach her (`remember <fact>`) — her brain grows daily
- Full device control: open/close apps, search web, type, screenshots, volume
- Push back and warn you if you ask for something destructive
- Transfer admin: `change primary admin` (only after your face verifies)

## Install (Python 3.11 or 3.12 recommended — face tools need it)
```
cd lya
pip install SpeechRecognition pyttsx3 pyautogui opencv-python numpy openai-whisper
```
Optional (smarter brain): install [Ollama](https://ollama.com) then `ollama pull llama3`

## First boot
```
python main.py enroll     # register your face ONCE
python main.py            # she comes alive
```

## Talk to her
- "LYA" → she wakes
- "remember I love biryani" → stored forever
- "what do you know" → face-verified private recall
- "open chrome" / "volume up" / "screenshot" → device control
- "change primary admin" → face-verified admin transfer

## Roadmap to full ULTRON
1. ✅ Wake word + voice loop
2. ✅ Face verification (basic — upgrade to insightface for better accuracy)
3. ✅ Memory brain (SQLite) — next: add vector search for smarter recall
4. ⬜ Voiceprint (verify your voice, not just face)
5. ⬜ Offline whisper speech recognition
6. ⬜ Learning loop: she summarizes each day and stores what she learned
7. ⬜ GUI avatar face (like Ultron's red eyes)
