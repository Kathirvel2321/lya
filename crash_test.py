"""Isolate which native library crashes when combined."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
step = sys.argv[1]

if step == "1":
    print("1: insightface alone")
    from security.auth_wall import face_embedding
    import numpy as np, cv2
    img = np.full((240, 240, 3), 120, np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    try:
        face_embedding(buf.tobytes())
    except ValueError as e:
        print("   insightface OK (no face found, as expected):", e)
elif step == "2":
    print("2: torch/Silent-Face alone")
    from security import liveness
    import numpy as np, cv2
    img = np.full((240, 240, 3), 120, np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    print("   result:", liveness.face_liveness(buf.tobytes()))
elif step == "3":
    print("3: insightface FIRST, then torch")
    from security.auth_wall import face_embedding
    import numpy as np, cv2
    img = np.full((240, 240, 3), 120, np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    try: face_embedding(buf.tobytes())
    except ValueError: pass
    from security import liveness
    print("   result:", liveness.face_liveness(buf.tobytes()))
print(f"STEP {step} COMPLETED WITHOUT CRASH")
