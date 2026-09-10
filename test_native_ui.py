"""Native widget/worker smoke test; no sensors, network or private data."""
import threading
import time
from ui.orb import LyasFace


def main():
    face=LyasFace()
    errors=[]
    ticks=[]
    start=time.monotonic()
    cpu=time.process_time()

    def tick():
        ticks.append(time.monotonic())
        if face.root:face.root.after(20,tick)

    def exercise():
        try:
            face._show_folders({"path":"Synthetic preview", "entries":[
                {"name":"Projects","folder":True}, {"name":"Notes.txt","folder":False}],
                "page":1,"more":False})
            face.root.update_idletasks()
            assert len(face._folder_tree.get_children())==2
            face._zoom(True);assert face.zoomed
            face._zoom(False);assert not face.zoomed
            face._show_styles()
            for theme in ("reactor","halo","pulse"):face._apply_theme(theme)
            face._sleep();assert face._anim_job is None and face.card is None
            face._wake();assert face._anim_job is not None
            def worker():
                time.sleep(0.3)
                face.show_reply("Worker completed without blocking the UI thread.")
            threading.Thread(target=worker,daemon=True).start()
        except Exception as e:errors.append(repr(e))

    def finish():
        try:
            assert face._last_reply.startswith("Worker completed")
            assert len(ticks)>=15, "UI event loop did not remain responsive"
            face._sleep();assert face._anim_job is None
        except Exception as e:errors.append(repr(e))
        face.shutdown()

    face._messages.put((lambda: (tick(),face.root.after(100,exercise),face.root.after(1100,finish)),()))
    face.run(lambda _:None,preview=True,seconds=5)
    if errors:raise AssertionError("; ".join(errors))
    print(f"PASS: native widgets, theme previews, scoped folder rows, worker delivery, hidden animation stopped; {len(ticks)} event-loop ticks")
    print(f"Smoke measurement only: wall={time.monotonic()-start:.3f}s CPU={time.process_time()-cpu:.3f}s")


if __name__=="__main__":main()
