"""Pinpoint the crash inside the Silent-Face path."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
step = sys.argv[1]

if step == "a":
    print("a: import torch")
    import torch
    print("   torch", torch.__version__, "ok")
elif step == "b":
    print("b: torch + load MiniFASNet weights")
    import os
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "security", "Silent-Face-Anti-Spoofing"))
    sys.path.insert(0, os.getcwd())
    import torch
    from src.anti_spoof_predict import AntiSpoofPredict
    print("   AntiSpoofPredict imported")
    checker = AntiSpoofPredict(0)
    model_path = os.path.join("resources", "anti_spoof_models", "2.7_80x80_MiniFASNetV2.pth")
    state = torch.load(model_path, map_location=torch.device("cpu"))
    print("   weights loaded:", type(state))
elif step == "c":
    print("c: full liveness face check")
    from security import liveness
    import numpy as np, cv2
    img = np.full((240, 240, 3), 120, np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    print("   result:", liveness.face_liveness(buf.tobytes()))
print(f"STEP {step} COMPLETED")
