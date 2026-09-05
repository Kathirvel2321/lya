"""
One-time enrollment for Lya's top-level authentication wall.
Run from a TRUSTED session (this is the only window where biometrics can be written):

    python security/enroll.py enroll selfie.jpg voice.wav "open sesame"

  - selfie.jpg : a clear photo of YOUR face (webcam capture or phone photo)
  - voice.wav  : 3-6 seconds of you speaking calmly (any wav/mp3/webm)
  - keyword    : the secret phrase you'll speak to unlock the vault

Everything is stored ENCRYPTED (Fernet, same key as the rest of Lya's memories)
in Supabase under kinds: biometric_face / biometric_voice / biometric_phrase.
"""
import base64
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.auth_wall import face_embedding, voice_embedding      # noqa: E402
from cloud.lya_cloud import sb_request, enc                          # noqa: E402


def enroll(selfie_path: str, voice_path: str, phrase: str):
    with open(selfie_path, "rb") as f:
        selfie = f.read()
    with open(voice_path, "rb") as f:
        voice = f.read()

    print("[1/4] Extracting ArcFace face embedding ...")
    fe = face_embedding(selfie)
    print(f"      -> 512-d embedding OK")

    print("[2/4] Extracting Resemblyzer voiceprint ...")
    ve = voice_embedding(voice)
    print(f"      -> 256-d embedding OK")

    print("[3/4] Encrypting templates ...")
    for kind, payload in (("biometric_face", base64.b64encode(selfie).decode()),
                          ("biometric_voice", base64.b64encode(voice).decode()),
                          ("biometric_phrase", phrase)):
        # replace any previous enrollment
        sb_request("DELETE", "memories", query=f"?kind=eq.{kind}")
        sb_request("POST", "memories", body={"kind": kind, "evalue": enc(payload)})

    print("[4/4] Stored encrypted in Supabase. Enrollment complete.")
    print("      The vault now unlocks ONLY with: your face + your voice + the keyword.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    enroll(sys.argv[1], sys.argv[2], sys.argv[3])
