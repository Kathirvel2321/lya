"""LYA's multi-user FACE IDENTITY ENGINE (iPhone-FaceID-style flow)
====================================================================
One ADMIN (full power), optional SECONDARY user (password, READ-ONLY),
and KNOWN FRIENDS (greeted by name). Unknown faces are stored as
'pending' — the next time the ADMIN wakes LYA, she asks who they were,
and once named they're recognized forever.

Uses ArcFace 512-d embeddings (via security/auth_wall.py) — same model
family as production face-recognition. All data encrypted (vault.py).
"""
import os, sys, json, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security import vault
from security import auth_wall

STORE = os.path.join(os.path.dirname(__file__), "known_faces.lya")

ADMIN, SECONDARY, FRIEND, UNKNOWN = "admin", "secondary", "friend", "unknown"


def _load():
    if not os.path.exists(STORE):
        return {"people": [], "pending": []}
    with open(STORE, "rb") as f:
        return json.loads(vault.decrypt(f.read()))


def _save(db):
    with open(STORE, "wb") as f:
        f.write(vault.encrypt(json.dumps(db).encode()))


def _cos(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


# ---------------- ENROLLMENT ----------------
def enroll_person(name, role, image_bytes_list):
    """Enroll a person from one or more JPEG snapshots (multi-sample = robust)."""
    embs = []
    for b in image_bytes_list:
        try:
            embs.append(auth_wall.face_embedding(b).tolist())
        except Exception:
            pass
    if not embs:
        return False
    db = _load()
    db["people"] = [p for p in db["people"] if p["name"].lower() != name.lower()]
    db["people"].append({"name": name, "role": role, "embeddings": embs})
    _save(db)
    print(f"[LYA] {name} enrolled as {role} ({len(embs)} face samples).")
    return True


def set_secondary_password(password):
    """ADMIN sets the secondary user's password (stored hashed+encrypted)."""
    import hashlib
    db = _load()
    db["secondary_password"] = hashlib.sha256(password.encode()).hexdigest()
    _save(db)
    return True


def check_secondary_password(password):
    import hashlib
    db = _load()
    return db.get("secondary_password") == hashlib.sha256(password.encode()).hexdigest()


# ---------------- RECOGNITION ----------------
def identify(image_bytes, admin_threshold=0.45, friend_threshold=0.50):
    """Match a webcam snapshot against every known person + pending faces.
    Returns dict: {status, name, role, similarity}
      status: 'admin' | 'secondary' | 'friend' | 'unknown' | 'no_face'"""
    try:
        emb = auth_wall.face_embedding(image_bytes)
    except Exception as e:
        return {"status": "no_face", "name": None, "role": None, "similarity": 0.0, "error": str(e)}

    db = _load()
    best_p, best_s = None, -1.0
    for p in db["people"]:
        s = max(_cos(emb, e) for e in p["embeddings"])
        if s > best_s:
            best_p, best_s = p, s
    thr = admin_threshold if (best_p and best_p["role"] == ADMIN) else friend_threshold
    if best_p and best_s >= thr:
        return {"status": best_p["role"], "name": best_p["name"],
                "role": best_p["role"], "similarity": round(best_s, 3)}

    # Unknown face — keep it in the background so the admin can name it later.
    if not any(_cos(emb, p_e) > 0.75 for p in db["pending"] for p_e in p["embeddings"]):
        db["pending"].append({"embeddings": [emb.tolist()], "first_seen": time.time()})
        db["pending"] = db["pending"][-10:]      # keep only the 10 newest strangers
        _save(db)
    return {"status": UNKNOWN, "name": None, "role": None, "similarity": round(best_s, 3)}


def list_pending():
    return [{"index": i, "seen": p["first_seen"]}
            for i, p in enumerate(_load()["pending"])]


def name_pending(index, name):
    """ADMIN names a stored stranger -> they become a known friend."""
    db = _load()
    if not (0 <= index < len(db["pending"])):
        return False
    p = db["pending"].pop(index)
    db["people"].append({"name": name, "role": FRIEND, "embeddings": p["embeddings"]})
    _save(db)
    print(f"[LYA] Stranger #{index} is now known as {name}.")
    return True


def forget(name):
    db = _load()
    db["people"] = [p for p in db["people"] if p["name"].lower() != name.lower()]
    _save(db)
    return True


# ---------------- WEBCAM SNAPSHOT ----------------
def snapshot_jpg(camera=0, warmup=6):
    """Grab one good webcam frame as JPEG bytes (lets auto-exposure settle)."""
    import cv2
    cam = cv2.VideoCapture(camera)
    frame = None
    for _ in range(warmup):
        ok, frame = cam.read()
    cam.release()
    if frame is None:
        return None
    ok, buf = cv2.imencode(".jpg", frame)
    return buf.tobytes() if ok else None
