"""Voice authentication for LYA — voiceprint stored ENCRYPTED (security/vault.py).
The iPhone's mic (via the web gateway) is far better than the laptop mic for
CAPTURING the samples; this module does the actual recognition on the laptop.

How it works: converts audio into an averaged log-spectrum "voiceprint"
(captures your vocal-tract shape), then compares with cosine similarity.
"""
import io, wave, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security import vault

STORE = os.path.join(os.path.dirname(__file__), "admin_voice.lya")
RATE = 16000

def _wav_bytes_to_float(wav_bytes):
    """Any WAV byte payload -> mono float array at 16 kHz."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as w:
        ch, sw, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(w.getnframes())
    if sw == 2:
        audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    else:  # 32-bit float (browser MediaRecorder path)
        audio = np.frombuffer(raw, np.float32).copy()
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    # naive resample to RATE if needed (good enough for a voiceprint)
    if rate != RATE:
        n = int(len(audio) * RATE / rate)
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio)
    return audio.astype(np.float32)

def _voiceprint(audio):
    """Averaged log-spectrum over voiced frames = the speaker's fingerprint."""
    frame, hop = 400, 160                      # 25 ms / 10 ms
    n = (len(audio) - frame) // hop
    if n < 20:
        return None                            # too short to be reliable
    win = np.hanning(frame).astype(np.float32)
    specs, energies = [], []
    for i in range(n):
        seg = audio[i*hop : i*hop+frame] * win
        spec = np.abs(np.fft.rfft(seg)[:128])  # keep 0-4 kHz
        specs.append(spec)
        energies.append(np.sqrt(np.mean(seg**2)))
    specs = np.array(specs)
    energies = np.array(energies)
    voiced = specs[energies > max(0.005, np.median(energies) * 0.5)]
    if len(voiced) < 10:
        return None
    mean_spec = voiced.mean(axis=0) + 1e-8
    fp = np.log(mean_spec)
    return fp / np.linalg.norm(fp)             # normalized

def enroll_from_wav(wav_bytes_list):
    """Store the admin voiceprint from several samples (better accuracy).
    The iPhone page records 3 samples of ~4 s each."""
    prints = []
    for b in wav_bytes_list:
        fp = _voiceprint(_wav_bytes_to_float(b))
        if fp is not None:
            prints.append(fp)
    if not prints:
        return False
    combined = np.mean(prints, axis=0)
    combined /= np.linalg.norm(combined)
    with open(STORE, "wb") as f:
        f.write(vault.encrypt(combined.astype(np.float32).tobytes()))
    print("[LYA] Voice enrolled and ENCRYPTED. I know your voice now.")
    return True

def verify_from_wav(wav_bytes, threshold=0.82):
    """Live check: True if the speaker is the admin."""
    if not os.path.exists(STORE):
        return False
    stored = np.frombuffer(vault.decrypt_file(STORE), dtype=np.float32)
    fp = _voiceprint(_wav_bytes_to_float(wav_bytes))
    if fp is None:
        return False
    sim = float(np.dot(stored, fp))
    print(f"[LYA] voice match: {sim:.3f} (need {threshold})")
    return sim >= threshold

def enrolled():
    return os.path.exists(STORE)
