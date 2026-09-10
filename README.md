# LYA — native personal assistant, under development

LYA now starts as a native floating desktop orb. The browser gateway is only a
phone-approval surface. This is an early implementation, not a certified secure
assistant or a general-purpose autonomous device operator.

## Try the interface without enrollment

```powershell
python main.py build
```

Type `show folders` for a clearly labelled synthetic folder preview, `show styles`
for three orb patterns, `use theme halo` to preview a change, `zoom`, `shrink`,
`close panel`, or `sleep`. Build mode has no microphone, model, private memory or
real device access. Preview theme changes are not saved. Ctrl+Q on the orb exits.

```powershell
python main.py text     # native typed interface, actual actions remain gated
python main.py          # voice mode, wake with hey LYA
python -B test_foundations.py
```

Admin enrollment remains deferred. Startup never asks to enroll a face or voice.
Without a registered identity, LYA stays a guest. Sensitive features below cannot
be used end-to-end until enrollment and the trusted phone connection are configured.

## Implemented paths

- One Tk event loop; a background worker processes one command at a time.
- Native answer panels, read-only paged folder browsing, expand/shrink and theme previews.
- Real folder browsing requires admin + phone approval, is scoped to the Windows
  user directory and lasts five minutes. It never executes a selected file.
- Exact app names: calculator, notepad, file explorer, chrome. These and volume
  are available to recognized trusted roles; other app names are not shell commands.
- Private memory reads/writes, lessons, reminders, screenshots and persistent
  theme changes require phone approval. Password disclosure is disabled.
- `stop` cancels an approval wait, drops queued commands and closes private panels.
  It cannot undo an operation already committed or interrupt every OS/network call.
- Guest model prompts contain no saved private facts or another session's history.
- Memory SQLite operations happen in RAM. Disk writes are encrypted, atomic and
  serialized across processes. Existing encrypted memory schema is retained.
- Code-generation produces drafts only. Activation is disabled until isolated
  execution checks and rollback are implemented.

## Learning and retention

- Ordinary chat history is bounded and held in RAM; it is not automatically saved.
- `remember <fact>` saves an explicit fact; `remember forever <fact>` labels it protected.
- `show memories` lists saved keys and categories.
- `learn <topic>` generates an unverified lesson draft. It does not browse the web,
  train a model or install an executable feature.
- `save lesson <title>` saves the current draft, which otherwise expires after ten minutes.
- `forget memory <exact key>` explicitly removes matching entries, including
  protected entries if the owner authorizes it. There is no automatic deletion of explicit memories.
- `using my memory <question>` requests a phone-approved answer using saved facts;
  those facts are sent to the configured model provider for that request.
- `create skill <description>` drafts code without executing it.
- `council: <question>` gets bounded advisory model opinions. The council does not
  gather sources automatically, and model agreement is not proof.

## Voice and dependencies

Python 3.11/3.12 with Tk and SQLite serialize/deserialize support is expected.
The UI preview uses the standard library. Normal chat/storage needs
`cryptography` and Windows `pywin32`. Voice mode additionally needs `sounddevice`,
`numpy`, `SpeechRecognition`, and `pyttsx3`. Device actions use `pyautogui`.
Biometric checks need `opencv-python`, `insightface`, `onnxruntime`, and the
anti-spoofing stack and models. No dependencies were installed by this change.

Voice capture has one reader and forwards the recognized utterance, so commands
are not re-recorded by a second competing microphone loop. Output uses local TTS.
Default transcription uses Google and sends recorded phrases to that service.
For offline transcription, install Vosk separately and set `LYA_VOSK_MODEL` to an
already downloaded model directory. That path is implemented but not validated
with your microphone or a downloaded model. Offline chat still requires a locally
running, configured model. Native folders, themes and text UI do not require an LLM.

## iPhone approval — integration pending

`python web_server.py` now requires a certificate/key pair in `LYA_TLS_CERT` and
`LYA_TLS_KEY`. It binds to loopback by default; an explicitly configured
`LYA_PHONE_HOST` selects the private-network interface. `LYA_PHONE_PORT` defaults
to 5000. The iPhone must trust the HTTPS certificate. Do not expose this development
server directly to the public internet.

The `/escalate` page displays the exact pending task. Approval requires the paired
token, the current challenge nonce, the owner phrase and an owner face/liveness
check. The grant expires and is consumed once. A token alone cannot enroll or
replace the owner. Missing liveness support denies verification. These biometric
thresholds are experimental and have not been calibrated against real attacks.
This is not iPhone Face ID/passkey authentication.

No certificate, phone pairing, enrollment, Oracle deployment or external account
configuration was performed. iOS does not grant an ordinary app unrestricted
control over other apps. A hands-free phone approval path still needs device testing.

Legacy browser HUD skill execution and token-only memory access have been removed.
The separate legacy cloud server's POST actions are disabled pending shared auth
integration; it is not the new production backend.

## Verification and remaining work

`test_foundations.py` uses fake secrets and temporary stores, with no camera,
network calls or real credentials. The older `security_test.py` and
`test_security_fixes.py` exercise legacy behavior and may modify real stores;
use the isolated foundation suite for this milestone.

Still pending: live microphone/phone testing, visual review on the actual screen,
fully hands-free iPhone approval, calibrated enrollment, per-person durable memory,
visitor naming, web research and reference-to-theme extraction, isolated skill
execution with rollback, broader application workflows, safe cloud integration,
and hardware-specific performance budgets. The reminder watcher starts when reminders are first used in each run and shows
a generic due notice without disclosing contents. It runs only while LYA is running;
automatic startup and off-device delivery remain pending.

See [LYA_VISION.md](LYA_VISION.md) for requirements and [BUILD_PROGRESS.md](BUILD_PROGRESS.md)
for this milestone's evidence and limits. No claim of being unhackable is made.
