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

def wake_loop(on_wake):
    """Main loop: sleeps until 'LYA' is spoken, then hands control to on_wake."""
    speak("LYA online. Say my name when you need me.")
    while True:
        text = listen(timeout=8)
        if text and any(w in text for w in WAKE_WORDS):
            on_wake()
