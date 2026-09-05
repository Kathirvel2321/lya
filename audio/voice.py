"""LYA's voice — listens for the wake word, answers casual questions from
anyone, but private/secure actions require identity verification first.
Microphone capture uses sounddevice (prebuilt wheels, no PyAudio needed)."""
import io, wave
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import pyttsx3

WAKE_WORDS = ("lya", "leya", "liya")

# --- Conversation mode: after she answers, keep listening this long for a
# follow-up WITHOUT the wake word — like a real phone call, not one-shot Siri.
CONVERSATION_SECONDS = 25

# --- Privacy: which output names count as earphones/headphones ---
_EAR_HINTS = ("headphone", "headset", "earphone", "bluetooth", "airpod",
              "buds", "galaxy b", "wireless stereo", "hands-free", "jbl",
              "boat", "boult", "oneplus", "sony", "jabra", " beats")

# Pick the most sensitive input device at import time.
# Laptop mic arrays expose many endpoints — some are near-silent.
def _best_input():
    """Prefer the Sound Mapper (device 0) — it routes to the real Windows mic.
    Raw WDM-KS endpoints (device 21 etc.) show big peaks but are loopback/PC-speaker
    channels that contain no speech. Mapper is the safe universal choice."""
    for d in sd.query_devices():
        if d["max_input_channels"] >= 1 and "sound mapper" in d["name"].lower():
            return d["index"]
    # fallback: first plain MME input
    for d in sd.query_devices():
        if d["max_input_channels"] >= 1 and d["hostapi"] == 0:
            return d["index"]
    return None

engine = pyttsx3.init()
engine.setProperty("rate", 175)

def speak(text):
    # Windows consoles choke on fancy Unicode — clean it before speaking
    text = text.encode("ascii", "ignore").decode().replace("  ", " ")
    print(f"LYA >> {text}")
    engine.say(text)
    engine.runAndWait()

def _record(seconds):
    """Record from the best mic as 16-bit mono WAV bytes."""
    rate, ch = 16000, 1
    dev = getattr(_record, "device", None)
    if dev is None:
        _record.device = dev = _best_input()
        if dev is not None:
            print(f"[LYA] using mic device {dev}")
    sd.default.device = (dev, None) if dev is not None else sd.default.device
    audio = sd.rec(int(seconds * rate), samplerate=rate, channels=ch, dtype="int16")
    sd.wait()
    sd.default.device = None
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(audio.tobytes())
    buf.seek(0)
    return buf

def listen(timeout=6):
    """One listening pass. Returns lowercase text or None."""
    r = sr.Recognizer()
    try:
        wav = _record(max(2, timeout))
        audio = sr.AudioData(wav.read(), 16000, 2)
        text = r.recognize_google(audio).lower()
        print(f"YOU >> {text}")
        return text
    except (sr.UnknownValueError, sr.WaitTimeoutError, sr.RequestError, Exception):
        return None

def _double_clap(audio_bytes):
    """Detect TWO sharp hand-claps in recorded WAV bytes (transient spikes
    0.08-1.5s apart, each far louder than the background). Returns True/False."""
    try:
        buf = io.BytesIO(audio_bytes)
        with wave.open(buf, "rb") as w:
            rate = w.getframerate()
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
        # envelope in 10 ms hops
        hop = rate // 100
        env = np.array([np.abs(data[i:i+hop]).max() for i in range(0, len(data) - hop, hop)])
        if len(env) == 0:
            return False
        floor = np.percentile(env, 30) + 1e-6      # background level
        thr = max(floor * 6, 6000)                 # a clap is LOUD + sudden
        hits = env > thr
        # collapse consecutive hot hops into clap events
        events, prev = [], -10
        for i, h in enumerate(hits):
            if h and i - prev > 8:                 # 80ms refractory = new clap
                events.append(i); prev = i
        # keep only sharp attacks (claps rise in one hop, speech doesn't)
        sharp = [i for i in events if i > 0 and env[i] > env[max(0, i-2)] * 2]
        for a in range(len(sharp) - 1):
            gap = (sharp[a+1] - sharp[a]) / 100.0  # seconds between claps
            if 0.08 <= gap <= 1.5:
                return True
        return False
    except Exception:
        return False

# ---- QUIET MODE -------------------------------------------------------
# 'wake up lya quietly/bluetooth/private' -> she checks for a bluetooth
# earphone. Found -> talk through it. Not found -> she can still HEAR you
# but will NOT speak out loud (text only) until you say 'speak normal'.
QUIET = {"on": False}

def set_quiet(on):
    QUIET["on"] = bool(on)
    print(f"[LYA] quiet mode {'ON (listen only)' if on else 'OFF'}")

def _has_speech(pcm, thresh=900):
    """Cheap energy check on 200ms of raw int16 audio — no STT, ~0 CPU."""
    try:
        return bool(pcm) and np.abs(np.frombuffer(pcm, dtype=np.int16)).max() > thresh
    except Exception:
        return False

def _record_stream(max_seconds=25, silence=1.0, thresh=900):
    """BATTERY-FRIENDLY listener. Instead of blindly recording 6s and paying
    for cloud STT every cycle, she streams 200ms chunks and only buffers when
    energy says someone is actually talking. STT (the expensive part) runs
    ONCE per phrase, and full silence costs almost nothing. Returns WAV bytes
    or None if nobody spoke."""
    import time as _t
    rate, ch = 16000, 1
    dev = getattr(_record, "device", None)
    if dev is None:
        _record.device = dev = _best_input()
        if dev is not None:
            print(f"[LYA] using mic device {dev}")
    sd.default.device = (dev, None) if dev is not None else sd.default.device
    pieces, spoken, quiet_chunks, start = [], False, 0, _t.time()
    try:
        stream = sd.InputStream(samplerate=rate, channels=ch, dtype="int16")
        stream.start()
        try:
            while _t.time() - start < max_seconds:
                data, _ = stream.read(rate // 5)          # 200 ms chunk
                pcm = data.tobytes()
                loud = _has_speech(pcm, thresh)
                if loud:
                    spoken, quiet_chunks = True, 0
                elif spoken:
                    quiet_chunks += 1
                    if quiet_chunks >= silence / 0.2:      # phrase finished
                        break
                if loud or spoken:
                    pieces.append(pcm)
        finally:
            stream.stop(); stream.close()
    except Exception:
        return None
    finally:
        sd.default.device = None
    if not spoken:
        return None
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(pieces))
    buf.seek(0)
    return buf

_QUIET_HINTS = ("quiet", "bluetooth", "whisper", "private", "earphone")
_LOUD_HINTS = ("speak normal", "normal mode", "speak up", "loud mode",
               "no bluetooth", "out loud")

def wake_loop(on_wake, clap_enabled=True):
    """Main loop — PRO VERSION.
    - Wakes on 'LYA' / 'wake up lya' OR a double clap.
    - 'wake up lya quietly/bluetooth/private' -> checks for a bluetooth
      earphone: found = speak through it, not found = listen-only quiet mode.
    - Every wake runs in a BACKGROUND THREAD, so a long task (>25s) never
      blocks her: she keeps hearing you while she works.
    - Energy-gated listening = near-idle CPU between phrases (battery safe).
    - Conversation mode: follow-ups need no wake word; say 'stop/sleep/bye'."""
    import time, threading
    speak("LYA online. Say my name or clap twice when you need me.")
    last_talk = 0.0
    while True:
        wav = _record_stream(max_seconds=25)
        if wav is None:
            continue                       # pure silence — loop cost ~0
        if clap_enabled and _double_clap(wav.getvalue()):
            print("[LYA] double clap detected")
            last_talk = time.time()
            threading.Thread(target=on_wake, args=(False,), daemon=True).start()
            continue
        try:
            audio = sr.AudioData(wav.getvalue(), 16000, 2)
            text = sr.Recognizer().recognize_google(audio).lower()
        except Exception:
            continue
        if not text:
            continue
        in_conversation = (time.time() - last_talk) < CONVERSATION_SECONDS
        if in_conversation and any(k in text for k in ("stop", "sleep", "bye")):
            last_talk = 0.0                 # end the conversation window
            set_quiet(False)
            speak("Okay, going quiet. Say my name when you need me.")
        elif any(w in text for w in WAKE_WORDS):
            want_quiet = any(h in text for h in _QUIET_HINTS)
            if want_quiet:
                if _earphone_connected():
                    set_quiet(False)
                    speak("Bluetooth audio found — I'll talk through it.")
                else:
                    set_quiet(True)         # she can hear, but won't talk aloud
                    # 'ask in device': tell you on SCREEN, not out loud
                    _notify("LYA — Quiet Mode",
                            "No Bluetooth earphone found.\n"
                            "I can HEAR you, but I will NOT speak out loud.\n"
                            "My replies will show as text in the console.\n\n"
                            "Say 'speak normal' to talk out loud again.")
            if any(h in text for h in _LOUD_HINTS):
                set_quiet(False)
            last_talk = time.time()
            # background thread: she stays available even mid-long-task
            threading.Thread(target=on_wake, args=(want_quiet,), daemon=True).start()
        elif in_conversation:
            last_talk = time.time()         # follow-up, no wake word needed
            threading.Thread(target=on_wake, args=(False,), daemon=True).start()

# ======================================================================
#  CLOUD VOICE — neural "girlfriend on the phone" voice for LYA.
#  Uses Microsoft Edge TTS (free, no API key): natural neural voices
#  in 12 languages, auto-detected from what you type/say. The audio
#  is post-processed with ffmpeg into a warm late-night phone-call
#  tone: soft low-pass, gentle presence boost, slight speed-down.
#  Falls back silently to pyttsx3 if offline/ffmpeg missing.
# ======================================================================
import os, json, asyncio, subprocess, tempfile, shutil, re

import edge_tts

# PowerShell can't auto-execute .py/.ps1... ffmpeg lives in ~/.codegpt/ffmpeg
_FFMPEG_DIR = os.path.join(os.path.expanduser("~"), ".codegpt", "ffmpeg")
if os.path.isdir(_FFMPEG_DIR):
    os.environ["PATH"] = _FFMPEG_DIR + os.pathsep + os.environ["PATH"]

# LYA's per-language voices: warm, young, female, soft-spoken.
# Each is chosen to sound like someone you like calling you late at night.
_VOICE = {
    "en-IN": "en-IN-NeerjaNeural",      # India — sweet, soft Indian English
    "en-US": "en-US-AriaNeural",        # US English
    "en-GB": "en-GB-SoniaNeural",       # UK English
    "hi-IN": "hi-IN-SwaraNeural",       # Hindi
    "bn-IN": "bn-IN-TanishkaNeural",    # Bengali
    "ta-IN": "ta-IN-PallaviNeural",     # Tamil
    "te-IN": "te-IN-ShrutiNeural",      # Telugu
    "mr-IN": "mr-IN-AarohiNeural",      # Marathi
    "gu-IN": "gu-IN-DhwaniNeural",      # Gujarati
    "kn-IN": "kn-IN-SapnaNeural",       # Kannada
    "ml-IN": "ml-IN-SobhanaNeural",     # Malayalam
    "ur-PK": "ur-PK-UzmaNeural",        # Urdu
}
_VOICE_DEFAULT = "en-IN-NeerjaNeural"   # LYA's home voice

# Recognizer: understand 12 languages too (Google STT is multilingual).
_LANG_RE = {
    "hi": "hi-IN", "bn": "bn-IN", "ta": "ta-IN", "te": "te-IN",
    "mr": "mr-IN", "gu": "gu-IN", "kn": "kn-IN", "ml": "ml-IN", "ur": "ur-PK",
}

def _detect_lang(text):
    """Pick the right voice/script by looking at the Unicode blocks used."""
    for ch in text:
        o = ord(ch)
        if 0x0900 <= o <= 0x097F: return "hi-IN"    # Devanagari (hi/mr)
        if 0x0980 <= o <= 0x09FF: return "bn-IN"    # Bengali
        if 0x0B80 <= o <= 0x0BFF: return "ta-IN"    # Tamil
        if 0x0C00 <= o <= 0x0C7F: return "te-IN"    # Telugu
        if 0x0A80 <= o <= 0x0AFF: return "gu-IN"    # Gujarati
        if 0x0C80 <= o <= 0x0CFF: return "kn-IN"    # Kannada
        if 0x0D00 <= o <= 0x0D7F: return "ml-IN"    # Malayalam
        if 0x0600 <= o <= 0x06FF: return "ur-PK"    # Arabic script (Urdu)
    return "en-IN"

def _smooth_wav(src, dst):
    """ffmpeg 'crush on the phone at midnight' filter chain:
    lowpass 4.2kHz (telephone warmth), presence shelf for clarity,
    tiny tremolo breath, slow down 2% for that unhurried tone,
    soft-compress and normalize so every sentence is intimate."""
    try:
        subprocess.run([
            shutil.which("ffmpeg") or "ffmpeg", "-y", "-loglevel", "error",
            "-i", src, "-af",
            "lowpass=f=4200,highpass=f=120,treble=g=2:f=3000,"
            "acompressor=threshold=0.15:ratio=3:attack=15:release=200,"
            "atempo=0.98,volume=1.6,dynaudnorm",
            "-ar", "24000", "-ac", "1", dst,
        ], check=True, capture_output=True)
        return os.path.exists(dst)
    except Exception:
        return False

async def _tts_to_file(text, path, lang):
    vc = edge_tts.Communicate(text, _VOICE.get(lang, _VOICE_DEFAULT), rate="-8%", pitch="-2Hz")
    await vc.save(path)

# ---- Privacy: earphone routing + public-place guard -----------------
# CONVERSATION_SECONDS: after any interaction LYA stays "open" for this
# long — follow-ups need no wake word (fixes the Siri one-shot problem).
CONVERSATION_SECONDS = 45
_EARPHONE_WORDS = ("earphone", "earphones", "headphone", "headphones",
                   "bluetooth", "headset", "buds", "airpods")

def _list_audio_devices():
    """(name, com_port) for every active audio endpoint, via PowerShell."""
    try:
        ps = ("Get-CimInstance Win32_SoundDevice | "
              "Select-Object Name,Status | ConvertTo-Json")
        r = subprocess.run(["powershell", "-NoProfile", "-c", ps],
                           capture_output=True, text=True, timeout=15)
        data = json.loads(r.stdout or "[]")
        if isinstance(data, dict):
            data = [data]
        return [(d.get("Name", ""), d.get("Status", "")) for d in data]
    except Exception:
        return []

def _earphone_connected():
    """True if any earphone/bluetooth audio device is present & OK."""
    for name, status in _list_audio_devices():
        if status != "OK":
            continue
        low = name.lower()
        if any(w in low for w in _EARPHONE_WORDS):
            return True
    return False

def _notify(title, msg):
    """Show a message on SCREEN (non-blocking) — used in quiet mode so she
    can 'ask in device' without speaking aloud in a public/quiet place."""
    import threading as _th
    def _box():
        try:
            import ctypes
            # MB_TOPMOST | MB_SETFOREGROUND | MB_OK — but non-blocking via thread
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0x40000 | 0x10000 | 0x0)
        except Exception:
            pass
    _th.Thread(target=_box, daemon=True).start()

def _ask_can_i_speak():
    """No earphones + possibly public: ask the human once (y/n) whether
    the speakers are okay. Returns True to talk, False to text-only."""
    try:
        ans = input("[LYA] No earphones connected. May I speak out loud? (y/n): ")
    except EOFError:
        return True
    return ans.strip().lower().startswith("y")

def _maybe_earphones():
    """Earphones connected -> return 'EARPHONES'. Else ask permission;
    if refused return 'TEXT_ONLY', else 'SPEAKER'."""
    if _earphone_connected():
        return "EARPHONES"
    return "SPEAKER" if _ask_can_i_speak() else "TEXT_ONLY"

def _play_on(path, target):
    """Play a wav through a specific output device via a tiny embedded
    powershell player (SoundPlayer cannot pick a device, so we use the
    default endpoint of the chosen render device). Returns True on success."""
    try:
        ps = (f"Add-Type -AssemblyName presentationCore;"
              f"$p = New-Object System.Windows.Media.MediaPlayer;"
              f"$p.Open('{path}');"
              f"$p.Play(); Start-Sleep -Seconds 1;"
              f"while(-not $p.Position.HasEnded -and $p.NaturalDuration.HasTimeSpan){{"
              f" Start-Sleep -Milliseconds 200; if($p.Position -ge $p.NaturalDuration.TimeSpan){{break}}}}")
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                        "-c", ps], capture_output=True, timeout=120)
        return True
    except Exception:
        return False

def speak(text, *args, **kwargs):
    """Speak with the smooth neural voice when possible, else the robot.
    QUIET MODE: she can always HEAR you, but stays silent out loud unless a
    bluetooth earphone is connected (then she talks only through it)."""
    try:
        print(f"LYA >> {text}")
    except UnicodeEncodeError:
        print(f"LYA >> {text.encode('ascii', 'replace').decode()}")
    global engine
    out = _maybe_earphones()
    if QUIET["on"] and out != "EARPHONES":
        print("[LYA] (quiet mode — listening only, not speaking aloud)")
        return
    lang = _detect_lang(text)
    tmpdir = tempfile.mkdtemp(prefix="lya_voice_")
    raw = os.path.join(tmpdir, "raw.mp3")
    smooth = os.path.join(tmpdir, "smooth.wav")
    try:
        asyncio.run(_tts_to_file(text, raw, lang))
        ok = _smooth_wav(raw, smooth)
        src = smooth if ok else raw
        if out is not None:
            # route the private voice straight to the earphone device
            if _play_on(src, out):
                return
        # Play via Windows-native, no console window flash
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-c",
             f"(New-Object Media.SoundPlayer '{src}').PlaySync();"],
            capture_output=True, timeout=120)
    except Exception as e:
        print(f"[LYA] neural voice unavailable ({e.__class__.__name__}), using local voice")
        try:
            engine.say(text); engine.runAndWait()
        except Exception:
            pass
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

# Raw audio of the LAST thing heard — lets voice_auth verify WHO spoke
# without recording twice (the phrase audio IS the voiceprint sample).
LAST_WAV = {"wav": None}

def get_last_wav():
    """WAV bytes of the most recent listen() — for speaker verification."""
    return LAST_WAV["wav"]

def listen(timeout=6, lang=None):
    """One listening pass, multilingual. lang = 'hi','bn','ta','te','mr',
    'gu','kn','ml','ur' forces a language; None = auto (English default)."""
    r = sr.Recognizer()
    try:
        wav = _record(max(2, timeout))
        LAST_WAV["wav"] = wav.getvalue()
        audio = sr.AudioData(wav.read(), 16000, 2)
        code = "en-IN" if lang is None else _LANG_RE.get(lang, "en-IN")
        text = r.recognize_google(audio, language=code).lower()
        print(f"YOU >> {text}")
        return text
    except Exception:
        return None
