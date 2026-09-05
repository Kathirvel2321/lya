"""LYA — main entry point.
Run:  python main.py enroll   (register your face, once)
      python main.py          (voice mode — wake with 'LYA', sleep with 'go to sleep')
      python main.py text     (SILENT TEXT MODE — for office/workplaces, no mic needed)

Rules built in:
- Voice mode: she wakes only when someone says 'LYA'.
- Text mode: type directly, everything else identical.
- Anyone can ask simple questions; she answers them casually.
- Private data / dangerous actions require FACE verification of you.
- She pushes back if you ask something wrong.
- 'change primary admin to <name>' transfers admin after you verify."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audio import voice
from vision import face_auth, identity
from brain import memory, mind, knowledge
from skills import device, guardian, reminder, passwords
from skills import allskills
from security import escalation
from ui.orb import LyasFace

face = LyasFace()   # her Siri-style interface — appears only when called
TEXT_MODE = False   # set by command-line arg — silences voice in/out
SESSION = {"role": None, "who": None}   # role: admin / secondary / friend / stranger


def identify_visitor():
    """The Face ID moment: grab a frame, match it against everyone she knows.
    Unknown faces are AUTO-STORED so the admin can name them later."""
    try:
        res = identity.identify(identity.snapshot_jpg())
    except Exception as e:
        res = {"role": "stranger", "who": None}
        print(f"[LYA] camera/identity unavailable: {e}")
    SESSION["role"], SESSION["who"] = res["role"], res["who"]
    return res


def name_unknowns():
    """Admin is back — ask who the un-named new faces were, store the names."""
    for face_id in list(identity.name_pending):
        say("Someone new talked to me while you were away. What's their name?")
        nm = ask()
        if nm:
            identity.name_person(face_id, nm.strip().title())
            say(f"Noted — next time {nm.strip().title()} shows up, I'll greet them by name.")
    identity.name_pending.clear()


def admit():
    """Gate-keeper: identify the face, greet each role the right way.
    Returns True only if the session may continue."""
    res = identify_visitor()
    role, who = res["role"], res["who"]
    if role == "admin":
        face.wake(handle_wake); face.set_state("listening")
        if identity.name_pending:
            name_unknowns()
        say("Hey boss. Good to see you.")
        return True
    if role == "secondary":
        face.wake(handle_wake); face.set_state("listening")
        say(f"Welcome back, {who}. Say your password.")
        pw = ask() or ""
        if not identity.check_secondary_password(who, pw):
            say("Wrong password. Private mode stays locked.")
            face.sleep(); return False
        say("Access granted — read-only mode.")
        return True
    if role == "friend":
        face.wake(handle_wake); face.set_state("listening")
        say(f"Hey {who}! Good to see you again.")
        return True
    face.wake(handle_wake); face.set_state("listening")
    say("Hi! I don't think we've met. How can I help you?")
    return True


def say(text):
    """Speak or print depending on mode."""
    if TEXT_MODE:
        print(f"LYA >> {text}")
    else:
        voice.speak(text)


def ask(prompt=""):
    """Listen or read depending on mode."""
    if TEXT_MODE:
        return input(f"YOU >> {prompt}").lower().strip()
    return voice.listen()


def handle_wake():
    text = ask()
    if not text:
        say("I'm listening."); return

    # --- Sleep command: interface fades away ---
    if any(p in text for p in ("go to sleep", "sleep now", "close interface",
                               "dismiss", "that's all")):
        say("Going dark. Call my name whenever you need me.")
        face.sleep()
        return

    # --- SENSITIVE-TASK GATE: phone approval OR spoken security word, or nothing runs ---
    SENSITIVE = ("password", "change", "admin", "open ", "close ", "volume ",
                 "screenshot", "remember", "what do you know", "shutdown", "delete",
                 "hack", "scan", "exploit", "payload", "install", "nmap")
    if SESSION["role"] == "admin" and any(s in text for s in SENSITIVE):
        if not escalation.escalate(say, ask, task_hint=text):
            face.sleep()
            return   # task frozen — no work until identity is proven

    # --- NON-ADMIN SESSIONS: READ-ONLY. No device control, no memory writes, no admin. ---
    if SESSION["role"] in ("friend", "stranger"):
        say(mind.reply(text, verified=False)); return
    if SESSION["role"] == "secondary":
        if "password" in text:                              # read-only vault access
            rows = passwords.list_all()
            say("Read-only vault — " + ("; ".join(f"{s}: {p}" for s, p in rows)
                                        if rows else "it's empty."))
        elif "remind" in text and any(w in text for w in ("list", "what are", "do i have", "show")):
            rows = reminder.list_all()
            say("You have " + ("; ".join(f"{w} on {t}" for _, w, t in rows)
                               if rows else "no reminders.") + ".")
        else:
            say(mind.reply(text, verified=False))
        return
    # --- ADMIN-ONLY: password vault (write) ---
    if "password" in text:
        if any(w in text for w in ("save", "store", "add")):
            say("Which site or app?"); site = ask()
            say("Say the password."); pw = ask()
            if site and pw:
                say(passwords.save(site, pw))
        else:
            rows = passwords.list_all()
            say("; ".join(f"{s}: {p}" for s, p in rows) if rows else "Your vault is empty.")
        return
    # --- Admin transfer (the 'change my primary admin' command) ---
    if "change" in text and "admin" in text:
        if face_auth.verify() and SESSION["role"] == "admin":
            memory.set_admin("new_admin")
            say("Primary admin transferred. New admin enrolled — I serve them now.")
        else:
            say("Admin transfer requires your face. Request denied.")
        return

    # --- Casual questions: anyone can ask these ---
    if any(w in text for w in ("time", "date", "weather", "who are you", "hello")):
        if "who are you" in text:
            say(f"I am LYA, {memory.get_admin()['name']}'s personal assistant.")
        elif "weather" in text:
            say(device.search_web("weather today"))
        else:
            say(mind.reply(text, verified=False))
        return

    # --- Everything else: verify it's YOU first ---
    correction = guardian.correct_user(text)
    if correction:
        say(correction)
        conf = ask()
        if conf and "confirm" in conf and face_auth.verify():
            pass
        else:
            say("Cancelled."); return

    # --- Reminders: 'remind me to X tomorrow at 5pm' (exact-moment alarms) ---
    if "remind" in text or "reminder" in text:
        if "cancel" in text or "delete" in text:
            say(reminder.cancel(text.split("cancel")[-1].split("delete")[-1].strip(" the my ")))
        elif any(w in text for w in ("list", "what are", "do i have", "show")):
            rows = reminder.list_all()
            say("You have " + ("; ".join(f"{w} on {t}" for _, w, t in rows)
                               if rows else "no reminders set. All clear.") + ".")
        else:
            reply = reminder.add(text)
            say(reply or "When should I remind you? Say a time like 'tomorrow at 5pm'.")
        return

    if "remember" in text:                      # teach her something
        fact = text.replace("remember", "").strip()
        memory.remember("fact", fact.split()[0] if fact else "note", fact, importance=2)
        knowledge.ingest("remember forever " + fact)   # hub classifies + graphs it
        say("Stored in my memory. I won't forget.")
        return

    if "what do you know" in text:              # private recall — needs face
        if face_auth.verify():
            rows = memory.recall(limit=5)
            say("Here's what I remember: " + "; ".join(v for _, v, *_ in rows))
        else:
            say("That's private. Identity failed.")
        return

    if text.startswith(("open ", "close ", "volume ")):
        verb, rest = text.split(" ", 1)
        allowed, msg = guardian.guard(text, lambda: device.HANDS[verb](rest))
        say(msg); guardian.log_action(text, allowed)
        return

    # --- ALL-ROUNDER SKILLS: cooking / guiding / teaching / techno / hacker ---
    skill_reply = allskills.reply(text, say, ask)
    if skill_reply is not None:
        say(skill_reply)
        return

    if "search" in text:
        q = text.split("search", 1)[1].strip()
        say(device.search_web(q)); return

    if "screenshot" in text:
        say(device.screenshot()); return

    # --- knowledge status: what's in the hub, what's protected ---
    if "knowledge status" in text or "memory status" in text:
        s = knowledge.stats()
        say(f"Hub: {s.get('session', 0)} session, {s.get('knowledge', 0)} knowledge, "
            f"{s.get('topic', 0)} topics, {knowledge.protect_count()} protected. "
            "Protected items can never be auto-deleted.")
        return

    # --- cleanup: the safe sweep — removes only expired ephemera, never protected ---
    if "cleanup" in text and ("memory" in text or "brain" in text):
        if face_auth.verify():
            say(knowledge.maintenance())
        else:
            say("Cleanup needs your face verified — it touches memory.")
        return

    # default: think + answer with full memory
    say(mind.reply(text, memory.get_admin()["name"] if memory.get_admin() else "admin",
                   verified=face_auth.verify()))
    knowledge.ingest(text)   # classify + route: ephemeral chats never touch disk

def text_mode():
    """SILENT MODE — for office/workplaces. Chat by typing, no mic needed.
    Same brain, same memory, same guardian — just no voice in or out."""
    admin = memory.get_admin()
    name = admin["name"] if admin else "you"
    print("=" * 55)
    print(f"  LYA TEXT MODE — silent office chat with {name}")
    print("  Type 'exit' to leave | 'go to sleep' closes her orb")
    print("=" * 55)
    reminder.start_watcher(say)
    while True:
        text = input("YOU >> ").lower().strip()
        if not text:
            continue
        if text in ("exit", "quit", "bye"):
            print("LYA >> See you later. I'll remember everything.")
            break
        face.wake(handle_wake)      # orb appears while working
        face.set_state("thinking")
        handle_wake_input(text)
        face.sleep()                # orb hides again after each answer

def handle_wake_input(text):
    """Run the same logic as voice mode but with a pre-set text."""
    original_ask = globals()["ask"]
    globals()["_pending"] = text
    def fake_ask(prompt=""):
        t = globals().get("_pending")
        globals()["_pending"] = None
        return t if t else None
    globals()["ask"] = fake_ask
    try:
        handle_wake()
    finally:
        globals()["ask"] = original_ask

def main():
    admin = memory.get_admin()
    if not admin:
        name = input("First boot — what should I call you? ")
        memory.set_admin(name)
        print("Now enrolling your face (put it in front of the webcam)...")
        face_auth.enroll(name)
        try:
            identity.enroll_admin(identity.snapshot_jpg())
            print("Face ID database ready — you are the one and only admin.")
        except Exception as e:
            print(f"Face ID enrollment skipped: {e}")
        voice.speak(f"Hello {name}. My memory is empty — teach me, and I'll grow.")

    def wake_with_face():
        """She opens her interface for whoever summoned her — Face ID first,
        then the greeting that matches who it is."""
        if not admit():
            return
        handle_wake()

    reminder.start_watcher(say)   # she never sleeps on a reminder
    voice.wake_loop(wake_with_face)

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "enroll":
        face_auth.enroll()
    elif arg == "text":
        TEXT_MODE = True
        text_mode()
    elif arg == "setsecurityword":
        # python main.py setsecurityword <word>  — the spoken fallback phrase
        if len(sys.argv) >= 3:
            escalation.set_security_word(sys.argv[2])
            print("Security word set (stored only as an encrypted hash).")
        else:
            print("Usage: python main.py setsecurityword <word>")
    elif arg == "secondary":
        # python main.py secondary <name> <password>  — register a trusted read-only user
        if len(sys.argv) >= 4:
            identity.set_secondary_password(sys.argv[2], sys.argv[3])
            print(f"Secondary user '{sys.argv[2]}' registered (read-only access).")
        else:
            print("Usage: python main.py secondary <name> <password>")
    else:
        main()
