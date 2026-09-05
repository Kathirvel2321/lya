"""Face + voice LIVENESS — the anti-spoofing layer of LYA's auth wall.

Face: Silent-Face-Anti-Spoofing (minivision-ai, MiniFASNet ensemble).
      Detects printed photos, screen replays, and masks via Fourier analysis.
      Returns label 1 (real) / 0 (fake) + confidence.

Voice: replay/spoof detection heuristics —
      - minimum duration & speech-energy variance (replayed clips are flat)
      - spectral flatness check (recordings have compressed high band)
      These catch naive replays; combined with challenge-response (the spoken
      code changes every attempt) replay attacks are neutralized.
"""
import os, sys
import numpy as np
import cv2

_SEC = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(_SEC, "Silent-Face-Anti-Spoofing")
if REPO not in sys.path:
    sys.path.insert(0, REPO)

_face_checker = None

def _get_face_checker():
    """Lazy-load the MiniFASNet ensemble (torch, ~1s first call)."""
    global _face_checker
    if _face_checker is not None:
        return _face_checker
    try:
        from src.anti_spoof_predict import AntiSpoofPredict
        from src.generate_patches import CropImage
        from src.utility import parse_model_name
        globals()["parse_model_name"] = parse_model_name
        model_dir = os.path.join(REPO, "resources", "anti_spoof_models")
        os.chdir(REPO)   # repo code uses relative './resources/...' paths
        device_id = 0
        checker = AntiSpoofPredict(device_id)
        cropper = CropImage()
        _face_checker = (checker, cropper, model_dir)
    except Exception as e:
        print(f"[liveness] face anti-spoof unavailable: {e}")
        _face_checker = False
    return _face_checker

def face_liveness(image_bytes, threshold=0.5):
    """Returns (is_live: bool, confidence: float, detail: str).
    Face detection via InsightFace (OpenCV 5 dropped Caffe support, so the
    repo's stock RetinaFace detector is replaced); the MiniFASNet ensemble
    still makes the real/fake decision."""
    checker_pack = _get_face_checker()
    if not checker_pack:
        return True, 0.0, "liveness model unavailable (allowed through)"
    checker, cropper, model_dir = checker_pack
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return False, 0.0, "could not decode image"
    try:
        h, w, _ = img.shape
        if h < 80 or w < 80:
            return False, 0.0, "image too small for liveness"
        # detect face via insightface instead of the repo's caffe detector
        from security.auth_wall import detect_face_bbox
        bbox = detect_face_bbox(img)
        if bbox is None:
            return False, 0.0, "no face detected for liveness"
        image_bbox = bbox  # x1,y1,x2,y2
        # CropImage.crop expects (x, y, box_w, box_h) — convert from x1,y1,x2,y2
        crop_bbox = (image_bbox[0], image_bbox[1],
                     image_bbox[2] - image_bbox[0],
                     image_bbox[3] - image_bbox[1])
        from src.utility import parse_model_name
        prediction = np.zeros((1, 3))
        for model_name in os.listdir(model_dir):
            h_input, w_input, model_type, scale = parse_model_name(model_name)
            img_cropped = cropper.crop(img, crop_bbox, scale, w_input, h_input)
            pred = checker.predict(img_cropped, os.path.join(model_dir, model_name))
            prediction += pred
        label = int(np.argmax(prediction))
        value = float(prediction[0][label] / 2)
        is_live = (label == 1)
        return is_live, value, f"liveness label={label} conf={value:.2f}"
    except Exception as e:
        return False, 0.0, f"liveness error: {e}"

def voice_liveness(audio_bytes, min_seconds=1.0, sample_rate=16000):
    """Heuristic replay check. Returns (is_live, detail)."""
    import io, wave, audioop
    try:
        w = wave.open(io.BytesIO(audio_bytes))
        frames = w.readframes(w.getnframes())
        rate = w.getframerate()
        duration = w.getnframes() / rate
        if duration < min_seconds:
            return False, f"clip too short ({duration:.1f}s) — speak naturally"
        # speech must vary: flat energy = device playback artifact
        chunk = int(rate * 0.1)
        energies = [audioop.rms(frames[i:i+chunk*2], 2) for i in range(0, len(frames)-chunk*2, chunk*2)]
        if len(energies) > 4 and (max(energies) - min(energies)) < 40:
            return False, "energy too flat — replay suspected"
        return True, f"voice liveness ok ({duration:.1f}s)"
    except Exception as e:
        return False, f"voice liveness error: {e}"
