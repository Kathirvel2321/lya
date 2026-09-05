"""LYA's eyes — face authentication using OpenCV.
The admin face template is stored ENCRYPTED (AES-256 via security/vault.py) —
biometric data never touches the disk in plaintext."""
import os
import cv2
import numpy as np

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security import vault

STORE = os.path.join(os.path.dirname(__file__), "admin_face.npy.lya")

# Jarvis-style hook: LYA's orb sets this so the scan shows up ONLY in her own
# interface — never as a separate camera window. ui/orb.py installs it.
_status_callback = None          # fn(state:str, detail:str) -> None

def set_status_callback(fn):
    ""Register a callback so LYA's interface shows 'scanning' states.
    States: 'scanning' | 'scanned_ok' | 'scanned_fail'.""
    global _status_callback
    _status_callback = fn

def _emit(state, detail=""):
    if _status_callback:
        try:
            _status_callback(state, detail)
        except Exception:
            pass

def enroll(name="admin"):
    """Run once to register your face. Look at the webcam when prompted."""
    cam = cv2.VideoCapture(0)
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    frames = []
    msg = f"{name}, look at the camera — enrolling your face (10 samples)..."
    print(f"[LYA] {msg}")
    _emit("scanning", msg)
    while len(frames) < 10:
        ok, frame = cam.read()
        if not ok: continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            face = cv2.resize(gray[y:y+h, x:x+w], (128, 128))
            frames.append(face.astype(np.float32) / 255.0)
        _emit("scanning", f"capturing {len(frames)}/10")
    cam.release()
    if frames:
        mean_face = np.mean(frames, axis=0)
        with open(STORE, "wb") as f:
            f.write(vault.encrypt(mean_face.tobytes()))
        _emit("scanned_ok", "Face enrolled and encrypted")
        print("[LYA] Face enrolled and ENCRYPTED. I will recognize you now.")
        return True
    _emit("scanned_fail", "No face seen")
    print("[LYA] Could not see your face. Try better lighting.")
    return False

def _face_vector_from_jpg(jpg_bytes):
    """Decode a JPEG (e.g. from the iPhone camera) -> 128x128 gray face vector.
    Returns None if no face is found."""
    arr = cv2.imdecode(np.frombuffer(jpg_bytes, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return None
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = detector.detectMultiScale(gray, 1.3, 5)
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])   # biggest face
    face = cv2.resize(gray[y:y+h, x:x+w], (128, 128))
    return face.astype(np.float32) / 255.0

def enroll_from_jpg(jpg_bytes_list, name="admin"):
    """Enroll from iPhone-captured JPEGs (web gateway sends several frames)."""
    vecs = [v for v in (_face_vector_from_jpg(b) for b in jpg_bytes_list) if v is not None]
    if not vecs:
        return False
    mean_face = np.mean(vecs, axis=0)
    with open(STORE, "wb") as f:
        f.write(vault.encrypt(mean_face.tobytes()))
    print(f"[LYA] {name}'s face (from iPhone) enrolled and ENCRYPTED.")
    return True

def verify_from_jpg(jpg_bytes, threshold=0.12):
    """One-shot check of an iPhone photo against the stored admin face."""
    if not os.path.exists(STORE):
        return False, 1.0
    stored = np.frombuffer(vault.decrypt_file(STORE)).reshape(128, 128)
    vec = _face_vector_from_jpg(jpg_bytes)
    if vec is None:
        return False, 1.0
    diff = float(np.mean(np.abs(vec - stored)))
    return diff < threshold, diff

def verify(threshold=0.12, tries=15):
    """Live face check. Returns True if it's the admin."""
    if not os.path.exists(STORE):
        print("[LYA] No face enrolled yet — run enroll() first.")
        return False
    stored = np.frombuffer(vault.decrypt_file(STORE)).reshape(128, 128)
    cam = cv2.VideoCapture(0)
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    confirmed = 0
    print("[LYA] Verifying your face... (invisible scan — no camera window)")
    _emit("scanning", "Identity scan")
    while confirmed < 5 and tries > 0:
        tries -= 1
        ok, frame = cam.read()
        if not ok: continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            face = cv2.resize(gray[y:y+h, x:x+w], (128, 128)).astype(np.float32) / 255.0
            diff = np.mean(np.abs(face - stored))
            if diff < threshold: confirmed += 1
        _emit("scanning", f"match {confirmed}/5")
    cam.release()
    ok = confirmed >= 5
    if ok:
        _emit("scanned_ok", "Welcome back")
        print("[LYA] Identity CONFIRMED — welcome back.")
    else:
        _emit("scanned_fail", "Identity rejected")
        print("[LYA] Identity REJECTED. Private data stays locked.")
    return ok
