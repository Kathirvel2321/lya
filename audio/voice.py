"""One microphone reader, command forwarding, optional local transcription.
Set LYA_VOSK_MODEL to an existing Vosk model directory for offline voice.
Otherwise voice mode uses Google speech recognition; text/build stay offline.
"""
import io
import os
import re
import threading
import time
import wave

WAKE_WORDS=("lya","leya","liya")
CONVERSATION_SECONDS=45
QUIET={"on":False}
LAST_WAV={"wav":None}
_SPEAKING=threading.Event()
_engine=None
_mic_lock=threading.Lock()
_local=None


def set_quiet(on):QUIET["on"]=bool(on)
def get_last_wav():return LAST_WAV["wav"]


def speak(text,*args,**kwargs):
    """Local speech, no network dependency; private results must not call this."""
    global _engine
    if QUIET["on"]:return
    _SPEAKING.set()
    try:
        if _engine is None:
            import pyttsx3
            _engine=pyttsx3.init();_engine.setProperty("rate",175)
        _engine.say(str(text));_engine.runAndWait()
    finally:
        _SPEAKING.clear()


def _record(seconds):
    import sounddevice as sd
    with _mic_lock:
        audio=sd.rec(int(seconds*16000),samplerate=16000,channels=1,dtype="int16")
        sd.wait()
    return _wav(audio.tobytes())


def _wav(pcm):
    buf=io.BytesIO()
    with wave.open(buf,"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm)
    buf.seek(0)
    return buf


def _record_stream(max_seconds=25,silence=0.8,thresh=700):
    import numpy as np
    import sounddevice as sd
    from collections import deque
    parts=[];pre=deque(maxlen=2);quiet=0;started=False
    with _mic_lock, sd.RawInputStream(samplerate=16000,channels=1,dtype="int16") as stream:
        deadline=time.monotonic()+max_seconds
        while time.monotonic()<deadline:
            data,_=stream.read(3200);pcm=bytes(data)
            loud=float(np.abs(np.frombuffer(pcm,np.int16).astype(np.int32)).max())>thresh
            if loud and not started:
                parts.extend(pre);started=True
            if started:
                parts.append(pcm);quiet=0 if loud else quiet+1
                if quiet>=silence/0.2:break
            else:pre.append(pcm)
    return _wav(b"".join(parts)) if parts else None


def transcribe(wav_bytes):
    global _local
    with wave.open(io.BytesIO(wav_bytes),"rb") as wav:
        pcm=wav.readframes(wav.getnframes())
    path=os.environ.get("LYA_VOSK_MODEL","")
    if path:
        import json
        import vosk
        if not os.path.isdir(path):raise RuntimeError("LYA_VOSK_MODEL must name an existing model directory.")
        if _local is None:_local=vosk.Model(path)
        recognizer=vosk.KaldiRecognizer(_local,16000)
        recognizer.AcceptWaveform(pcm)
        return json.loads(recognizer.FinalResult()).get("text","").strip()
    import speech_recognition as sr
    recognizer=sr.Recognizer();recognizer.operation_timeout=8
    return recognizer.recognize_google(sr.AudioData(pcm,16000,2),language="en-IN").strip()


def listen(timeout=6,lang=None):
    wav=_record(timeout).getvalue();LAST_WAV["wav"]=wav
    try:return transcribe(wav)
    except Exception:return None


def wake_loop(on_wake,clap_enabled=False):
    """Forward the recognized utterance exactly once; never start wake threads."""
    # Dependency/configuration failures reach the native fallback instead of
    # being retried forever inside the microphone loop.
    import sounddevice
    import numpy
    if os.environ.get("LYA_VOSK_MODEL"):
        import vosk
        if not os.path.isdir(os.environ["LYA_VOSK_MODEL"]):
            raise RuntimeError("LYA_VOSK_MODEL must name an existing model directory.")
    else:
        import speech_recognition
    last=0
    while True:
        try:
            wav=_record_stream()
            if wav is None:continue
            LAST_WAV["wav"]=wav.getvalue()
            text=transcribe(wav.getvalue())
        except Exception:
            time.sleep(0.5);continue
        low=text.casefold()
        if not low:continue
        if _SPEAKING.is_set() and low not in {"stop","cancel"}:continue
        match=re.search(r"\b(?:hey\s+|wake up\s+)?(?:lya|leya|liya)\b",low)
        active=time.monotonic()-last<CONVERSATION_SECONDS
        if low in {"stop","cancel","go to sleep","sleep"} and active:
            on_wake(low,False);last=0;continue
        if match:
            text=text[match.end():].strip(" ,.!?")
            last=time.monotonic()
            on_wake(text or "help",QUIET["on"])
        elif active:
            last=time.monotonic();on_wake(text,QUIET["on"])
