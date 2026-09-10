"""Native orb with one Tk event loop; workers communicate through a queue.
Hallmark component: desktop assistant; existing Segoe UI, restrained reactor palette.
Pre-emit critique: philosophy 4, hierarchy 4, execution 3, specificity 4, restraint 4, variety 3.
"""
import math
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from ui.themes import THEMES, TOKENS, load


class LyasFace:
    def __init__(self):
        self.root = None
        self.canvas = None
        self.card = None
        self.state = "idle"
        self.zoomed = False
        self._awake = False
        self._last_reply = ""
        self._messages = queue.Queue()
        self._main_thread = None
        self._anim_job = None
        self.theme = load()["theme"]
        self.motion = load().get("motion", True)
        self.on_command = lambda text: None
        self._panel_data = None
        self._started = time.monotonic()

    def _post(self, fn, *args):
        if threading.get_ident() == self._main_thread:
            fn(*args)
        else:
            self._messages.put((fn, args))

    def run(self, on_command, preview=False, seconds=None):
        self._main_thread = threading.get_ident()
        self.on_command = on_command
        self.root = tk.Tk()
        self.root.title("LYA")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TOKENS["transparent"])
        try:
            self.root.attributes("-transparentcolor", TOKENS["transparent"])
        except tk.TclError:
            self.root.configure(bg=TOKENS["background"])
        self.canvas = tk.Canvas(self.root, width=240, height=260,
                                bg=TOKENS["transparent"], highlightthickness=0)
        self.canvas.pack()
        self.entry = tk.Entry(self.root, bg=TOKENS["panel"], fg=TOKENS["text"],
                              insertbackground=TOKENS["text"], relief="flat",
                              font=(TOKENS["font"], 11), justify="center")
        self.entry.place(x=15, y=229, width=210, height=28)
        self.entry.bind("<Return>", self._submit)
        self.root.bind("<Escape>", lambda e: self.on_command("stop"))
        self.root.bind("<Control-q>", lambda e: self.shutdown())
        self._position()
        self._draw()
        self.root.withdraw()
        self._drain()
        if preview:
            self.wake()
            self.show_reply("Preview · no microphone, model calls or device actions.\nType help, show styles, or show folders.")
        if seconds:
            self.root.after(int(seconds * 1000), self.shutdown)
        self.root.mainloop()

    def _position(self):
        w, h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"240x260+{max(0,w//2-120)}+{max(0,h-320)}")

    def _drain(self):
        for _ in range(30):
            try:
                fn, args = self._messages.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args)
            except tk.TclError:
                pass
        if self.root:
            self.root.after(40, self._drain)

    def _submit(self, event=None):
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        if text:
            self.on_command(text)

    def wake(self, on_command=None):
        self._post(self._wake)

    def _wake(self):
        if not self.root:
            return
        self._awake = True
        self.root.deiconify()
        if self._anim_job is None:
            self._animate()

    def sleep(self):
        self._post(self._sleep)

    def _sleep(self):
        self._awake = False
        self._close_card()
        self._last_reply = ""
        self._panel_data = None
        self.zoomed = False
        if self._anim_job:
            self.root.after_cancel(self._anim_job)
            self._anim_job = None
        self.root.withdraw()

    def shutdown(self):
        if self.root:
            self.root.destroy()
            self.root = None

    def is_awake(self):
        return self._awake

    def set_state(self, state):
        self._post(self._set_state, state)

    def _set_state(self, state):
        self.state = state
        if self.canvas:
            self.canvas.itemconfigure("status", text=state.upper())

    def _draw(self):
        c = self.canvas
        c.delete("all")
        theme = THEMES[self.theme]
        self._arcs = []
        for i, radius in enumerate((88, 76, 62)):
            if theme["style"] == "rings":
                item = c.create_oval(120-radius, 110-radius, 120+radius, 110+radius,
                                     outline=theme["accent"], width=1)
            else:
                item = c.create_arc(120-radius, 110-radius, 120+radius, 110+radius,
                                    start=i*110, extent=245 if theme["style"] == "arcs" else 100,
                                    style="arc", outline=theme["accent"], width=2)
                self._arcs.append((item, (-1 if i%2 else 1)*(12+i*5)))
        c.create_oval(77,67,163,153,fill=theme["core"],outline=theme["accent"],width=1)
        c.create_text(120,105,text="LYA",fill=TOKENS["text"],font=(TOKENS["font"],19,"bold"))
        c.create_text(120,132,text=self.state.upper(),tags="status",fill=theme["accent"],font=(TOKENS["font"],8))
        c.create_text(120,211,text="SPEAK  /  TYPE",fill=TOKENS["muted"],font=(TOKENS["font"],8))
        c.tag_bind("all", "<Double-Button-1>", lambda e: self.expand())

    def _animate(self):
        self._anim_job = None
        if not self._awake or not self.root:
            return
        if self.motion:
            t = time.monotonic() - self._started
            for item, speed in self._arcs:
                self.canvas.itemconfigure(item,start=(t*speed)%360)
        self._anim_job = self.root.after(33 if self.motion else 300,self._animate)

    def _close_card(self):
        if self.card:
            self.card.destroy()
        self.card = None

    def _panel(self, title):
        self._wake()
        self._close_card()
        self.card = tk.Toplevel(self.root)
        self.card.title("LYA · " + title)
        self.card.attributes("-topmost",True)
        self.card.configure(bg=TOKENS["background"])
        sw,sh = self.root.winfo_screenwidth(),self.root.winfo_screenheight()
        w,h = (min(960,sw-48),min(680,sh-90)) if self.zoomed else (min(560,sw-40),min(440,sh-90))
        self.card.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2-60)}")
        self.card.minsize(min(w,320),min(h,240))
        self.card.protocol("WM_DELETE_WINDOW",lambda:self.on_command("close panel"))
        self.card.bind("<Escape>",lambda e:self.on_command("stop"))
        head=tk.Frame(self.card,bg=TOKENS["background"])
        head.pack(fill="x",padx=20,pady=(16,10))
        tk.Label(head,text=title,fg=TOKENS["text"],bg=TOKENS["background"],
                 font=(TOKENS["font"],14,"bold")).pack(side="left")
        self._button(head,"Shrink" if self.zoomed else "Expand",self.shrink if self.zoomed else self.expand).pack(side="right")
        return self.card

    def _button(self,parent,text,command):
        return tk.Button(parent,text=text,command=command,bg=TOKENS["panel"],fg=TOKENS["text"],
                         activebackground=TOKENS["border"],activeforeground=TOKENS["text"],
                         relief="flat",padx=12,pady=8,font=(TOKENS["font"],10),takefocus=True)

    def show_reply(self,text,timeout=None):
        self._post(self._show_reply,str(text))

    def _show_reply(self,text):
        self._last_reply=text
        self._panel_data=("reply",text)
        panel=self._panel("LYA")
        body=tk.Text(panel,bg=TOKENS["background"],fg=TOKENS["text"],relief="flat",wrap="word",
                     padx=20,pady=10,font=(TOKENS["font"],12),spacing3=8)
        bar=tk.Scrollbar(panel,command=body.yview)
        body.configure(yscrollcommand=bar.set)
        bar.pack(side="right",fill="y")
        body.pack(fill="both",expand=True)
        body.insert("1.0",text);body.configure(state="disabled")
        self._text_body=body

    def show_folders(self,data):
        self._post(self._show_folders,data)

    def _show_folders(self,data):
        self._panel_data=("folders",data)
        panel=self._panel("Folders")
        tk.Label(panel,text=data["path"],bg=TOKENS["background"],fg=TOKENS["muted"],
                 font=(TOKENS["font"],10),anchor="w",wraplength=480).pack(fill="x",padx=20)
        style=ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("LYA.Treeview",background=TOKENS["background"],fieldbackground=TOKENS["background"],
                        foreground=TOKENS["text"],rowheight=34,font=(TOKENS["font"],11),borderwidth=0)
        style.map("LYA.Treeview",background=[("selected",TOKENS["border"])])
        frame=tk.Frame(panel,bg=TOKENS["background"]);frame.pack(fill="both",expand=True,padx=20,pady=12)
        tree=ttk.Treeview(frame,columns=("name","kind"),show="headings",style="LYA.Treeview",selectmode="browse")
        tree.heading("name",text="Name · say open folder 1");tree.heading("kind",text="Type")
        tree.column("name",width=340,minwidth=150);tree.column("kind",width=80,minwidth=65,stretch=False)
        bar=ttk.Scrollbar(frame,command=tree.yview);tree.configure(yscrollcommand=bar.set)
        bar.pack(side="right",fill="y");tree.pack(fill="both",expand=True)
        for i,e in enumerate(data["entries"],1):
            tree.insert("","end",iid=str(i),values=(f"{i:02}  {e['name']}","Folder" if e["folder"] else "File"))
        def select(event=None):
            selection=tree.selection()
            if selection:self.on_command("open folder "+selection[0])
        tree.bind("<Double-Button-1>",select);tree.bind("<Return>",select)
        foot=tk.Frame(panel,bg=TOKENS["background"]);foot.pack(fill="x",padx=20,pady=(0,12))
        for label,cmd in (("Back","go back"),("Previous","scroll up"),("Next","scroll down")):
            self._button(foot,label,lambda v=cmd:self.on_command(v)).pack(side="left",padx=(0,6))
        tk.Label(foot,text=f"Page {data['page']} · read only",fg=TOKENS["muted"],bg=TOKENS["background"]).pack(side="right")
        self._folder_tree=tree

    def show_styles(self):
        self._post(self._show_styles)

    def _show_styles(self):
        self._panel_data=("styles",None)
        panel=self._panel("Choose an orb")
        for name,theme in THEMES.items():
            row=tk.Frame(panel,bg=TOKENS["background"]);row.pack(fill="x",padx=20,pady=8)
            c=tk.Canvas(row,width=72,height=72,bg=TOKENS["background"],highlightthickness=0);c.pack(side="left")
            if theme["style"]=="rings":
                for r in (29,23,17):c.create_oval(36-r,36-r,36+r,36+r,outline=theme["accent"])
            else:
                for i,r in enumerate((29,23,17)):c.create_arc(36-r,36-r,36+r,36+r,start=i*100,extent=240 if theme["style"]=="arcs" else 100,style="arc",outline=theme["accent"],width=2)
            tk.Label(row,text=name.title()+"  ·  "+theme["style"],fg=TOKENS["text"],bg=TOKENS["background"],font=(TOKENS["font"],12)).pack(side="left",padx=12)
            self._button(row,"Apply",lambda n=name:self.on_command("use theme "+n)).pack(side="right")
        tk.Label(panel,text="Say use theme halo · undo theme restores the previous choice",fg=TOKENS["muted"],bg=TOKENS["background"],wraplength=480).pack(padx=20,pady=8)

    def apply_theme(self,name):
        self._post(self._apply_theme,name)

    def _apply_theme(self,name):
        if name not in THEMES:raise ValueError("Unknown theme")
        self.theme=name
        if self.canvas:self._draw()

    def close_panel(self):
        self._post(self._clear_panel)

    def _clear_panel(self):
        self._close_card();self._panel_data=None;self._last_reply=""

    def expand(self):
        self._post(self._zoom,True)

    def shrink(self):
        self._post(self._zoom,False)

    def _zoom(self,big):
        self.zoomed=big
        if self._panel_data:
            kind,data=self._panel_data
            if kind=="reply":self._show_reply(data)
            elif kind=="folders":self._show_folders(data)
            else:self._show_styles()

    def pump(self,ms=20):
        pass  # compatibility: run() owns the sole Tk event loop
