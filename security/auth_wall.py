"""LYA's TOP-LEVEL AUTHENTICATION WALL
=====================================
Face:  InsightFace ArcFace (buffalo_l) — 99.4%+ accuracy embeddings, the
       industry-standard open-source model used in production systems.
Voice: Resemblyzer speaker encoder — real voicePRINT matching (is it YOUR
       voice, not just the right words). Research shows reliable auth with
       clips as short as ~2.6 seconds.
Keyword: Whisper transcription — you must SPEAK the secret phrase.

All three must pass for vault access. Templates stored encrypted (vault.py).
"""
import os, sys, io, base64
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security import vault

_face_app = None
_voice_encoder = None

def _face():
    """Lazy-load InsightFace buffalo_l (downloads models on first use)."""
    global _face_app
    if _face_app is None:
        from insightface.app import FaceAnalysis
        _face_app = FaceAnalysis(name="buffalo_l")
        _face_app.prepare(ctx_id=-1, det_size=(640, 640))   # CPU
    return _face_app

def _voice():
    global _voice_encoder
    if _voice_encoder is None:
        from resemblyzer import VoiceEncoder
        _voice_encoder = VoiceEncoder()
    return _voice_encoder

# ---------------- FACE: ArcFace embedding matching ----------------
def detect_face_bbox(img):
    """Largest face bbox (x1,y1,x2,y2) or None — shared with liveness module."""
    faces = _face().get(img[:, :, ::-1])
    if not faces:
        return None
    best = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
    x1, y1, x2, y2 = [int(v) for v in best.bbox]
    return x1, y1, x2, y2

def face_embedding(image_bytes) -> np.ndarray:
    """512-d ArcFace embedding of the largest face in the image."""
    cv2 = __import__("cv2")
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode the image.")
    faces = _face().get(img[:, :, ::-1])   # BGR->RGB
    if not faces:
        raise ValueError("No face detected in the image.")
    best = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
    return best.normed_embedding

def face_match(embedding_a, embedding_b, threshold=0.45):
    """Cosine similarity — ArcFace typical: same person 0.6-0.8, different <0.3."""
    sim = float(np.dot(embedding_a, embedding_b))
    return sim >= threshold, sim

# ---------------- VOICE: Resemblyzer voiceprint matching ----------------
def voice_embedding(audio_bytes, source_format="webm") -> np.ndarray:
    """256-d speaker embedding from raw audio bytes (any format ffmpeg reads)."""
    from resemblyzer import preprocess_wav
    import tempfile, subprocess
    with tempfile.NamedTemporaryFile(suffix=f".{source_format}", delete=False) as f:
        f.write(audio_bytes); tmp = f.name
    try:
        wav_path = tmp + ".wav"
        subprocess.run(["ffmpeg", "-y", "-i", tmp, "-ar", "16000", "-ac", "1", wav_path],
                       capture_output=True, timeout=30)
        wav = preprocess_wav(wav_path)
        return _voice().embed_utterance(wav)
    finally:
        os.remove(tmp)
        if os.path.exists(tmp + ".wav"): os.remove(tmp + ".wav")

def voice_match(emb_a, emb_b, threshold=0.75):
    """Cosine similarity — same speaker typically 0.80-0.95, different <0.65."""
    sim = float(np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b)))
    return sim >= threshold, sim

# ---------------- KEYWORD: Whisper transcription ----------------
def keyword_match(audio_bytes, stored_phrase, source_format="webm"):
    """The spoken audio must contain the secret phrase (content check)."""
    import json, urllib.request
    from brain.mind import HEADERS
    boundary = "----lyaboundary"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name='file'; "
            f"filename='audio.{source_format}'\r\nContent-Type: application/octet-stream\r\n\r\n").encode() \
           + audio_bytes + \
           f"\r\n--{boundary}\r\nContent-Disposition: form-data; name='model'\r\n\r\nwhisper-large-v3\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request("https://api.groq.com/openai/v1/audio/transcriptions", data=body,
        headers={**HEADERS, "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        spoken = json.loads(r.read()).get("text", "").strip().lower()
    return stored_phrase.lower() in spoken, spoken

# ---------------- THE WALL: all three gates ----------------
class AuthWall:
    """Enroll once; every vault request must pass face + voiceprint + keyword."""

    def __init__(self, store_face_bytes, store_voice_bytes):
        self.store_face = face_embedding(store_face_bytes)
        self.store_voice = voice_embedding(store_voice_bytes)
        self.store_face = vault.encrypt(self.store_face.tobytes())
        self.store_voice = vault.encrypt(self.store_voice.tobytes())

    def verify(self, selfie_bytes, voice_bytes, phrase, voice_fmt="webm"):
        """Returns (ok, report). ALL THREE gates must pass."""
        report = []
        try:
            emb = face_embedding(selfie_bytes)
            ok_f, sim = face_match(np.frombuffer(vault.decrypt(self.store_face)), emb)
            report.append(f"face {'PASS' if ok_f else 'FAIL'} (similarity {sim:.2f})")
        except Exception as e:
            return False, f"face FAIL ({e})"
        try:
            emb = voice_embedding(voice_bytes, voice_fmt)
            ok_v, sim = voice_match(np.frombuffer(vault.decrypt(self.store_voice)), emb)
            report.append(f"voiceprint {'PASS' if ok_v else 'FAIL'} (similarity {sim:.2f})")
        except Exception as e:
            return False, f"voiceprint FAIL ({e})"
        try:
            ok_k, spoken = keyword_match(voice_bytes, phrase, voice_fmt)
            report.append(f"keyword {'PASS' if ok_k else 'FAIL'} (heard: '{spoken}')")
        except Exception as e:
            return False, f"keyword FAIL ({e})"
        ok = ok_f and ok_v and ok_k
        return ok, " | ".join(report)
