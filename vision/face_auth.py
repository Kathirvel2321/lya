"""LYA's eyes — face authentication using OpenCV.
First run: enroll() captures your face. Later: verify() compares live webcam
frames against the stored face. Only YOU get access to private data."""
import os, json
import cv2
import numpy as np

STORE = os.path.join(os.path.dirname(__file__), "admin_face.npy")

def enroll(name="admin"):
    """Run once to register your face. Look at the webcam when prompted."""
    cam = cv2.VideoCapture(0)
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    frames = []
    print(f"[LYA] {name}, look at the camera — enrolling your face (10 samples)...")
    while len(frames) < 10:
        ok, frame = cam.read()
        if not ok: continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            face = cv2.resize(gray[y:y+h, x:x+w], (128, 128))
            frames.append(face.astype(np.float32) / 255.0)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.imshow("LYA face enrollment", frame)
        if cv2.waitKey(1) & 0xFF == 27: break
    cam.release(); cv2.destroyAllWindows()
    if frames:
        np.save(STORE, np.mean(frames, axis=0))
        print("[LYA] Face enrolled. I will recognize you now.")
        return True
    print("[LYA] Could not see your face. Try better lighting.")
    return False

def verify(threshold=0.12, tries=15):
    """Live face check. Returns True if it's the admin."""
    if not os.path.exists(STORE):
        print("[LYA] No face enrolled yet — run enroll() first.")
        return False
    stored = np.load(STORE)
    cam = cv2.VideoCapture(0)
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    confirmed = 0
    print("[LYA] Verifying your face...")
    while confirmed < 5 and tries > 0:
        tries -= 1
        ok, frame = cam.read()
        if not ok: continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            face = cv2.resize(gray[y:y+h, x:x+w], (128, 128)).astype(np.float32) / 255.0
            diff = np.mean(np.abs(face - stored))
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0) if diff < threshold else (0, 0, 255), 2)
            if diff < threshold: confirmed += 1
        cv2.putText(frame, f"match {confirmed}/5", (10, 30), 0, 0.8, (255, 255, 255), 2)
        cv2.imshow("LYA verifying", frame)
        if cv2.waitKey(1) & 0xFF == 27: break
    cam.release(); cv2.destroyAllWindows()
    ok = confirmed >= 5
    print("[LYA] Identity", "CONFIRMED — welcome back." if ok else "REJECTED. Private data stays locked.")
    return ok
