# LYA — a personal voice assistant with real identity gating

Windows-only (the encryption is bound to your Windows account via DPAPI).

## Security — what is actually true

Encrypted with AES-256 (Fernet) before touching the disk:
- Memory DB (`brain/lya_brain.db.lya`) — facts, conversations, admin identity
- Face templates (`vision/known_faces.lya`) — ArcFace embeddings
- Password vault (`security/passwords.lya`)
- Security-word hash, phone token, escalation grants (`security/*.lya`)

The AES key itself is wrapped by **Windows DPAPI**, bound to YOUR Windows user
account. Copying these files to another PC or user account yields nothing.

**Limits, stated honestly:**
- `secure_delete()` overwrites a file in place before unlinking. On an SSD or
  any copy-on-write/journaling filesystem this does **not** guarantee the
  original blocks are gone. Treat it as tidying, not forensic erasure.
- The DPAPI entropy constant lives in `security/vault.py`, i.e. in this repo.
  DPAPI still stops other Windows accounts on the machine — but do not model
  it as a secret.
- Anything under `debug/`, `shots/`, or `examples/` is **not** encrypted.
  `.gitignore` keeps them out of git; don't commit them.

Verify: `python security_test.py` and `python test_security_fixes.py`

## Install

Python 3.11 or 3.12 (the face/voice stacks need it).

```
cd lya
pip install SpeechRecognition pyttsx3 pyautogui opencv-python numpy
pip install cryptography pywin32          # vault + DPAPI  (required)
pip install insightface onnxruntime       # ArcFace face ID (required)
pip install resemblyzer                   # voiceprint      (optional)
```

`ffmpeg` must be on PATH for the voiceprint path to work.

## Her brain — GROQ (free, no GPU)

1. Free account at https://console.groq.com (no credit card)
2. Copy your API key
3. `setx GROQ_API_KEY "your_key_here"` then restart the terminal

Optional offline fallback: `ollama pull qwen2.5:0.5b`

## First boot

```
python main.py                    # enrolls your face, then comes alive
python main.py setsecurityword "open sesame"   # spoken fallback (phrases OK)
python main.py enrollvoice        # optional: voiceprint fallback
```

Face enrollment retries 3 times and then **aborts** — it will not boot into a
half-enrolled state where the face database is empty and every check silently
falls through to the spoken fallback.

## Modes

```
python main.py          # voice — wake with "LYA", sleep with "go to sleep"
python main.py text     # silent text mode, same brain and same gates
python main.py build    # DEV ONLY — no face ID, no gates, everyone a guest
```

`build` mode disables every identity check. Don't run it on real data.

## Access levels

| Role | How they're known | What they get |
|---|---|---|
| admin | face match (or security word / voiceprint if the camera can't see) | everything, sensitive actions still escalate |
| secondary | face match + their own password | read-only vault and reminders |
| friend | face match | casual chat only |
| stranger | unrecognised | casual chat only |

Sensitive requests (vault, device control, admin transfer, private memory)
freeze and demand a second factor: phone approval, or the spoken security
word/phrase. Five failures locks the spoken fallback for 10 minutes; a corrupt
attempt counter locks it too, rather than opening it.

## Phone gateway

`python web_server.py`, then on the same WiFi open `http://<pc-ip>:5000`.

- `/enroll` — capture face + voice from the phone's better sensors
- `/verify` — face (+voice) check; mints a session valid for 10 minutes
- `/escalate` — approve a protected task waiting on the laptop

The access token proves *this is the paired phone*. It does **not** prove
*you* are holding it — private memory needs the face check. Traffic is plain
HTTP on your LAN; treat the token as LAN-only.

## Talk to her

- "remember I love biryani" → stored, encrypted
- "what do you know" → private recall, face-verified
- "open chrome" / "volume up" / "screenshot" → device control
- "remind me to call mom tomorrow at 5pm"
- "change primary admin" → face-verified admin transfer

## Roadmap

1. ✅ Wake word + voice loop
2. ✅ Face verification (ArcFace / insightface)
3. ✅ Memory brain (SQLite, encrypted) — next: vector search for recall
4. ✅ Voiceprint fallback (Resemblyzer)
5. ⬜ Offline Whisper speech recognition
6. ⬜ Learning loop: summarize each day and store what she learned
7. ⬜ GUI avatar face

## Known gaps

- Skill dispatch is substring matching, so "tell me about **open** source"
  can trip the `"open "` sensitive-action gate.
- `list_all()` on the password vault returns live secrets and `main.py` speaks
  them through TTS. Fine alone in a room; nowhere else.
- Reminder watcher runs on a thread that shares `say()` with the main loop.
