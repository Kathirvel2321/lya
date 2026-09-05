"""LYA's voice — listens for the wake word, answers casual questions from
anyone, but private/secure actions require identity verification first.
Microphone capture uses sounddevice (prebuilt wheels, no PyAudio needed)."""
import io, wave
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import pyttsx3

WAKE_WORDS = ("lya", "leya", "liya")

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

def wake_loop(on_wake, clap_enabled=True):
    """Main loop: wakes on 'LYA' (voice) OR a double clap, then hands control
    to on_wake — like Face ID, the interface only appears when summoned."""
    speak("LYA online. Say my name or clap twice when you need me.")
    while True:
        wav = _record(6)
        if clap_enabled and _double_clap(wav.getvalue()):
            print("[LYA] double clap detected")
            on_wake()
            continue
        try:
            audio = sr.AudioData(wav.getvalue(), 16000, 2)
            text = sr.Recognizer().recognize_google(audio).lower()
            if text and any(w in text for w in WAKE_WORDS):
                on_wake()
        except Exception:
            pass
