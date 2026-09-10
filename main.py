"""LYA native desktop runtime. No automatic enrollment and no browser UI.
python main.py            # voice + native orb
python main.py text       # native orb with typed commands
python main.py build      # safe UI preview, synthetic folder data, no sensors
"""
import datetime
import os
import queue
import re
import secrets
import sys
import threading
import time
from security.policy import Session, allowed
from ui.orb import LyasFace
from ui import themes

HELP = """LYA · available commands
Show folders · open folder 1 · go back · scroll down · close panel
Show styles · use theme reactor/halo/pulse · undo theme
Zoom · shrink · stop · sleep
What time is it · open calculator · volume up
Remember <fact> · remember forever <fact> · show memories
Learn <topic> · save lesson <title> · forget memory <exact key>
Create skill <description> (draft only)
Council: <important question>
Private actions need your enrolled identity and fresh phone approval.
Build mode previews synthetic folders and styles; it cannot operate your device.
"""


class Assistant:
    def __init__(self, face, build=False, voice_enabled=False):
        self.face, self.build, self.voice_enabled = face, build, voice_enabled
        self.commands = queue.Queue(maxsize=8)
        self.cancelled = threading.Event()
        self.busy = threading.Event()
        self.session = Session(id=secrets.token_urlsafe(16))
        self.browser = None
        self.browse_until = 0
        self.pending_lesson = None
        self._reminder_started = False
        self.generation = 0
        threading.Thread(target=self._worker, daemon=True).start()

    def submit(self, text):
        text = text.strip()
        if not text:return
        if text.casefold() in {"stop","cancel","sleep","go to sleep","close panel"}:
            self.cancelled.set()
            self.generation += 1
            self.browser=None;self.browse_until=0;self.pending_lesson=None
            while True:
                try:self.commands.get_nowait()
                except queue.Empty:break
            if "sleep" in text.casefold():self.face.sleep()
            else:self.face.close_panel();self.face.set_state("cancelled")
            return
        if self.busy.is_set():
            self.face.show_reply("A task is running. Say stop to cancel it before starting another.")
            return
        try:self.commands.put_nowait((self.generation,text))
        except queue.Full:self.face.show_reply("Command queue is full. Say stop and try again.")

    def _worker(self):
        while True:
            generation,text=self.commands.get()
            if generation != self.generation:continue
            self.cancelled.clear();self.busy.set();self.face.wake();self.face.set_state("thinking")
            try:
                reply=self.handle(text)
                if reply and not self.cancelled.is_set():
                    self.face.show_reply(reply)
                    # No secret output enters speech; the UI is the default output.
                    if self.voice_enabled and not getattr(self,"private_output",False):
                        from audio import voice
                        voice.speak(reply)
            except Exception as e:
                if not self.cancelled.is_set():
                    self.face.show_reply(f"Task stopped: {type(e).__name__}: {e}")
            finally:
                self.busy.clear();self.face.set_state("idle")

    def identify(self):
        if self.build:return
        from vision import identity
        # No template means guest mode; do not start enrollment or a camera loop.
        if not os.path.exists(identity.STORE):
            self.session=Session(id=self.session.id)
            return
        result=identity.identify(identity.snapshot_jpg())
        role=result.get("role") or "stranger"
        who=result.get("who") or "guest"
        if (role,who)!=(self.session.role,self.session.person):
            from brain import mind
            mind.clear_history(self.session.id)
            self.session=Session(role,who,secrets.token_urlsafe(16))
            self.browser=None;self.browse_until=0;self.pending_lesson=None

    def permit(self, action, task):
        if self.build:return False
        if allowed(self.session,action):return True
        if self.session.role!="admin":return False
        from security import escalation
        self.face.set_state("approval")
        self.face.show_reply("Approve on your paired iPhone:\n\n"+task+"\n\nOpen its HTTPS approval page. Say stop to cancel. This request expires in two minutes.")
        ok=escalation.request_phone(task,self.cancelled)
        self.face.set_state("thinking")
        return allowed(self.session,action,phone_approved=ok) and not self.cancelled.is_set()

    def handle(self,text):
        self.private_output=False
        low=text.casefold().strip()
        if low in {"help","what can you do"}:return HELP
        if low in {"zoom","lya zoom","open full screen","full screen"}:self.face.expand();return
        if low in {"shrink","lya shrink","minimize"}:self.face.shrink();return
        if low in {"show styles","show themes","orb styles"}:self.face.show_styles();return
        if low in {"what time is it","time","date","what day is it"}:
            return datetime.datetime.now().strftime("%I:%M %p · %A, %d %B %Y")
        if self.build:
            if low=="show folders":
                self.face.show_folders({"path":"Preview · synthetic folders, no disk access","entries":[{"name":n,"folder":True} for n in ("Projects","Documents","Learning")],"page":1,"more":False});return
            if low.startswith("use theme "):
                self.face.apply_theme(low.removeprefix("use theme ").strip());return "Preview applied for this run only."
            return "Build preview has no device access. Try show folders, show styles, zoom, shrink, or help."
        self.identify()
        denied="This requires the primary admin and phone approval. Enrollment remains deferred; no action was taken."
        if low.startswith("use theme ") or low=="undo theme":
            name=low.removeprefix("use theme ").strip()
            if low!="undo theme" and name not in themes.THEMES:return "Choose reactor, halo, or pulse."
            if not self.permit("theme_apply",text):return denied
            data=themes.undo() if low=="undo theme" else themes.save(name)
            self.face.apply_theme(data["theme"]);return "Theme changed. Say undo theme to restore the previous choice."
        if low in {"show folders","show my folders","show all folders","go back","scroll down","scroll up"} or low.startswith("open folder "):
            self.private_output=True
            if self.session.role!="admin":return denied
            if not self.browser or time.monotonic()>=self.browse_until:
                if not self.permit("files","Browse my user folder, read-only, for five minutes. No file execution, deletion or system folders."):return denied
                from skills.files import FolderBrowser
                self.browser=FolderBrowser();self.browse_until=time.monotonic()+300
            if self.cancelled.is_set():return
            if low=="go back":data=self.browser.back()
            elif low.startswith("scroll "):data=self.browser.scroll(1 if low.endswith("down") else -1)
            elif low.startswith("open folder "):data=self.browser.open(text[len("open folder "):].strip())
            else:data=self.browser.listing()
            if "entries" in data:self.face.show_folders(data);return
            return f"{data['file']} · {data['bytes']:,} bytes\n{data['message']}"
        if low.startswith("open ") or low.startswith("volume "):
            action="volume" if low.startswith("volume ") else "open_app"
            if not self.permit(action,text):return denied
            from skills import device
            return device.volume(low[7:]) if action=="volume" else device.open_app(low[5:])
        if low.startswith("remind me to ") or low in {"show reminders", "list reminders"}:
            self.private_output=True
            if not self.permit("reminders",text):return denied
            from skills import reminder
            if not self._reminder_started:
                # Existing schedules authorize reminders, but public notifications
                # must not disclose their private contents.
                def notify_due():
                    while True:
                        try:
                            if reminder.due_now():
                                self.face.show_reply("A saved reminder is due. Ask to show reminders to view it privately.")
                        except Exception:
                            self.face.set_state("reminder error")
                        threading.Event().wait(30)
                threading.Thread(target=notify_due,daemon=True).start()
                self._reminder_started=True
            if low.startswith("remind me to "):
                return reminder.add(text) or "Include a time, such as tomorrow at 5pm."
            return "\n".join(f"{what} · {when}" for _,what,when in reminder.list_all()) or "No reminders."
        if low in {"screenshot", "take a screenshot"}:
            self.private_output=True
            if not self.permit("screenshot",text):return denied
            from skills import device
            return device.screenshot()
        if low.startswith("using my memory "):
            self.private_output=True
            if not self.permit("memory_read","Use saved facts to answer this request via the configured language model: "+text[16:]):return denied
            from brain import mind
            return mind.reply(text[16:],admin_name=self.session.person,verified=True,remember=False)
        if low in {"show memories","what do you know","what do you remember"}:
            self.private_output=True
            if not self.permit("memory_read",text):return denied
            from brain import memory
            rows=memory.recall(limit=30)
            return "\n\n".join(f"{k} [{kind}]\n{v}" for k,v,kind,_ in rows) or "No saved memories."
        if low.startswith("remember "):
            if not self.permit("memory_write",text):return denied
            from brain import memory
            protected=low.startswith("remember forever ")
            content=text[len("remember forever ") if protected else len("remember "):].strip()
            if not content:return "Tell me what to remember."
            key=" ".join(content.split()[:6])
            memory.remember("protected" if protected else "fact",key,content,3 if protected else 2)
            return f"Saved under {key}. Explicit memories do not expire automatically."
        if low.startswith("learn "):
            if not self.permit("learn",text):return denied
            from brain import mind
            topic=text[6:].strip()
            if not topic:return "Name a topic to learn."
            answer=mind.reply("Explain this topic and distinguish established facts from uncertainty. Do not claim to have searched the web. Topic: "+topic,remember=False)
            if self.cancelled.is_set():return
            self.pending_lesson=(answer,time.monotonic()+600,self.session.id)
            return answer+"\n\nThis is a draft lesson, not verified web research or an installed capability. Say save lesson <title> within ten minutes to retain it."
        if low.startswith("save lesson "):
            if not self.pending_lesson or self.pending_lesson[1]<time.monotonic() or self.pending_lesson[2]!=self.session.id:return "No current lesson draft. Say learn <topic> first."
            if not self.permit("memory_write",text):return denied
            from brain import memory
            memory.remember("lesson",text[12:].strip(),self.pending_lesson[0],2)
            self.pending_lesson=None
            return "Lesson saved, labelled as model-generated and requiring verification."
        if low.startswith("forget memory "):
            self.private_output=True
            if not self.permit("memory_forget",text):return denied
            from brain import memory
            n=memory.forget_exact(text[14:].strip())
            return f"Removed {n} exact matching memory entries."
        if low.startswith("create skill "):
            if not self.permit("skill_draft",text):return denied
            from skills import forge
            return forge.create(text[13:].strip())
        if low in {"confirm skill","activate skill"}:
            return "Automatic code activation is disabled. Drafts need isolated execution tests and a rollback review before becoming capabilities."
        if low.startswith("council:"):
            if not self.permit("council",text):return denied
            from brain import council
            result=council.decide(text.split(":",1)[1].strip())
            return result[0] if result else "The council is unavailable. No decision was executed."
        if "password" in low or "vault" in low:
            return "Password operations remain disabled in this development stage. No secrets were read or spoken."
        from brain import mind
        return mind.reply(text,admin_name=self.session.person,verified=False,
                          session_id=self.session.id if self.session.role in {"admin","friend","secondary"} else None)


def main():
    try:sys.stdout.reconfigure(encoding="utf-8",errors="replace")
    except AttributeError:pass
    mode=sys.argv[1] if len(sys.argv)>1 else "voice"
    if mode not in {"voice","text","build"}:
        raise SystemExit("Use python main.py [voice|text|build]. Enrollment is deferred.")
    face=LyasFace()
    assistant=Assistant(face,build=mode=="build",voice_enabled=mode=="voice")
    if mode=="voice":
        def listen():
            try:
                from audio import voice
                voice.wake_loop(lambda text,quiet=False:assistant.submit(text))
            except Exception as e:
                face.show_reply(f"Voice unavailable ({e}). Type commands in the orb.")
        threading.Thread(target=listen,daemon=True).start()
    face.run(assistant.submit,preview=mode!="voice")


if __name__=="__main__":main()
