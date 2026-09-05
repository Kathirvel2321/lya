"""Test the liveness layer: synthetic image (no face) must FAIL."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, cv2
from security import liveness

# 1. synthetic flat image — no face -> must fail
img = np.full((240, 240, 3), 120, np.uint8)
ok, buf = cv2.imencode(".jpg", img)
r = liveness.face_liveness(buf.tobytes())
print("TEST1 synthetic no-face:", r)
assert r[0] is False, "synthetic image should not pass liveness"

# 2. tiny image -> must fail fast
r = liveness.face_liveness(buf.tobytes()) if False else None
tiny = cv2.resize(img, (40, 40))
ok, buf2 = cv2.imencode(".jpg", tiny)
r = liveness.face_liveness(buf2.tobytes())
print("TEST2 tiny image:", r)
assert r[0] is False

# 3. voice liveness — too-short WAV must fail
import io, wave
buf3 = io.BytesIO()
with wave.open(buf3, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b"\x00\x10" * 3200)   # 0.1s of quiet
r = liveness.voice_liveness(buf3.getvalue())
print("TEST3 short voice:", r)
assert r[0] is False

# 4. adequate-length but FLAT audio (replay artifact) must fail
import math
frames = bytearray()
for i in range(16000 * 2):   # 2 seconds of constant tone
    frames += int(3000 * math.sin(2 * math.pi * 440 * i / 16000)).to_bytes(2, "little", signed=True)
buf4 = io.BytesIO()
with wave.open(buf4, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(bytes(frames))
r = liveness.voice_liveness(buf4.getvalue())
print("TEST4 flat replay tone:", r)
assert r[0] is False, "constant tone should be flagged as replay"

print("ALL LIVENESS TESTS PASS")
