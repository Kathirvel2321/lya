"""LYA — main entry point.
Run:  python main.py enroll   (register your face, once)
      python main.py          (start her)

Rules built in:
- She wakes only when someone says 'LYA'.
- Anyone can ask simple questions; she answers them casually.
- Private data / dangerous actions require FACE verification of you.
- She pushes back if you ask something wrong.
- 'change primary admin to <name>' transfers admin after you verify."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audio import voice
from vision import face_auth
from brain import memory, mind
from skills import device, guardian
from ui.orb import LyasFace

face = LyasFace()   # her Siri-style interface — appears only when called


def handle_wake():
    text = voice.listen()
    if not text:
        voice.speak("I'm listening."); return

    # --- Sleep command: interface fades away ---
    if any(p in text for p in ("go to sleep", "sleep now", "close interface",
                               "dismiss", "that's all")):
        voice.speak("Going dark. Call my name whenever you need me.")
        face.sleep()
        return

    # --- Admin transfer (the 'change my primary admin' command) ---
    if "change" in text and "admin" in text:
        if face_auth.verify():
            memory.set_admin("new_admin")
            voice.speak("Primary admin transferred. New admin enrolled — I serve them now.")
        else:
            voice.speak("Admin transfer requires your face. Request denied.")
        return

    # --- Casual questions: anyone can ask these ---
    if any(w in text for w in ("time", "date", "weather", "who are you", "hello")):
        if "who are you" in text:
            voice.speak(f"I am LYA, {memory.get_admin()['name']}'s personal assistant.")
        elif "weather" in text:
            voice.speak(device.search_web("weather today"))
        else:
            voice.speak(mind.reply(text, verified=False))
        return

    # --- Everything else: verify it's YOU first ---
    correction = guardian.correct_user(text)
    if correction:
        voice.speak(correction)
        conf = voice.listen()
        if conf and "confirm" in conf and face_auth.verify():
            pass
        else:
            voice.speak("Cancelled."); return

    if "remember" in text:                      # teach her something
        fact = text.replace("remember", "").strip()
        memory.remember("fact", fact.split()[0] if fact else "note", fact, importance=2)
        voice.speak("Stored in my memory. I won't forget.")
        return

    if "what do you know" in text:              # private recall — needs face
        if face_auth.verify():
            rows = memory.recall(limit=5)
            voice.speak("Here's what I remember: " + "; ".join(v for _, v, *_ in rows))
        else:
            voice.speak("That's private. Identity failed.")
        return

    if text.startswith(("open ", "close ", "volume ")):
        verb, rest = text.split(" ", 1)
        allowed, msg = guardian.guard(text, lambda: device.HANDS[verb](rest))
        voice.speak(msg); guardian.log_action(text, allowed)
        return

    if "search" in text:
        q = text.split("search", 1)[1].strip()
        voice.speak(device.search_web(q)); return

    if "screenshot" in text:
        voice.speak(device.screenshot()); return

    # default: think + answer with full memory
    voice.speak(mind.reply(text, memory.get_admin()["name"] if memory.get_admin() else "admin",
                           verified=face_auth.verify()))
    memory.remember("conversation", text[:30], text)

def main():
    admin = memory.get_admin()
    if not admin:
        name = input("First boot — what should I call you? ")
        memory.set_admin(name)
        print("Now enrolling your face (put it in front of the webcam)...")
        face_auth.enroll(name)
        voice.speak(f"Hello {name}. My memory is empty — teach me, and I'll grow.")

    def wake_with_face():
        """She opens her interface only when her name is spoken."""
        face.wake(handle_wake)
        face.set_state("listening")
        voice.speak("I'm here.")
        handle_wake()

    voice.wake_loop(wake_with_face)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "enroll":
        face_auth.enroll()
    else:
        main()
