"""LYA's face — a Siri-style floating orb, NOT a fullscreen app.
It only appears when you call her name, glows while she listens/thinks/speaks,
and fades away when you say 'go to sleep'. Built with tkinter (built into Python)."""
import tkinter as tk

class LyasFace:
    """Round glowing orb on a click-through-ish always-on-top borderless window."""

    def __init__(self):
        self.root = None
        self.canvas = None
        self.orb_ids = []
        self.state = "idle"          # idle | listening | thinking | speaking
        self._anim_job = None

    # ---------- lifecycle ----------
    def wake(self, on_command):
        """Show the orb; call on_command(text_getter) — LYA logic hooks in here."""
        if self.root:               # already awake
            return
        self.root = tk.Tk()
        self.root.overrideredirect(True)             # no title bar / no frame
        self.root.attributes("-topmost", True)       # always on top, like Siri
        self.root.attributes("-alpha", 0.95)
        size = 220
        w = self.root.winfo_screenwidth()
        h = self.root.winfo_screenheight()
        self.root.geometry(f"{size}x{size}+{w//2-size//2}+{h-size-180}")  # lower center
        self.root.configure(bg="black")
        try:
            self.root.attributes("-transparentcolor", "black")  # rounded look
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self.root, width=size, height=size, bg="black",
                                highlightthickness=0)
        self.canvas.pack()
        self.state = "listening"
        self._draw()
        self._animate()
        # place a slim command box under the orb
        self.entry = tk.Entry(self.root, bg="#101018", fg="#66e0ff", insertbackground="#66e0ff",
                              relief="flat", font=("Segoe UI", 11), width=22, justify="center")
        self.entry.place(x=0, y=size-34, width=size, height=30)
        self.entry.bind("<Return>", self._submit)
        self.entry.focus_set()
        self.on_command = on_command
        self.root.protocol("WM_DELETE_WINDOW", self.sleep)

    def _submit(self, event=None):
        text = self.entry.get().strip()
        self.entry.delete(0, tk.END)
        if text:
            self.on_command(text)

    def sleep(self):
        """Fade out and destroy — 'go to sleep' calls this."""
        if self.root:
            try:
                self.root.attributes("-alpha", 0.0)
                self.root.update()
            except tk.TclError:
                pass
            self._destroy()

    def _destroy(self):
        if self._anim_job:
            try: self.root.after_cancel(self._anim_job)
            except tk.TclError: pass
        self._anim_job = None
        if self.root:
            try: self.root.destroy()
            except tk.TclError: pass
        self.root = None; self.canvas = None; self.orb_ids = []

    def is_awake(self):
        return self.root is not None

    # ---------- visuals ----------
    def _draw(self):
        c, size = self.canvas, 220
        cx = cy = size // 2
        for item in self.orb_ids:
            try: c.delete(item)
            except tk.TclError: pass
        self.orb_ids = []
        colors = {"idle":       ("#1a2a4a", "#0a1230"),
                  "listening":  ("#00d0ff", "#0a3a66"),
                  "thinking":   ("#ffaa00", "#7a3a00"),
                  "speaking":   ("#00ff88", "#0a5a30")}
        outer, inner = colors.get(self.state, colors["idle"])
        for r, col in ((98, inner), (80, outer), (60, inner), (40, outer)):
            self.orb_ids.append(c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=col, width=3))
        self.orb_ids.append(c.create_text(cx, cy, text="LYA", fill="#66e0ff",
                                          font=("Segoe UI", 16, "bold")))

    def set_state(self, state):
        """Change glow: 'idle', 'listening', 'thinking', 'speaking'."""
        if state != self.state:
            self.state = state
            if self.canvas: self._draw()

    def _animate(self):
        """Gentle pulsing so she feels alive."""
        if not self.root: return
        import random
        c = self.canvas
        for item in self.orb_ids[:4]:
            r = c.itemcget(item, "width")
            new_w = max(2.0, float(r) + random.uniform(-0.8, 0.8))
            c.itemconfigure(item, width=new_w)
        self._anim_job = self.root.after(120, self._animate)

    def pump(self, ms=20):
        """Keep her face responsive while the voice loop runs elsewhere."""
        if self.root:
            try: self.root.update()
            except tk.TclError: pass
