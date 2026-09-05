"""skills/reminder.py — LYA never lets you forget.
Stores encrypted reminders in SQLite, parses natural language times,
and a watcher thread fires each one at the exact moment — surviving restarts.

Usage from LYA's brain:
    reminder.add("remind me to go to the mall tomorrow at 5pm")
    reminder.due_now()              # called every 30s by watcher thread
    reminder.list_all()
    reminder.clear_done()
"""
import os, re, sqlite3, datetime, threading, json

from security import vault

# Cloud mirror (optional): when Supabase is configured, every reminder is ALSO
# stored encrypted in the cloud, so the cloud edition can fire it even if this
# laptop is off. See brain/sync.py.
try:
    from brain import sync
except Exception:
    sync = None

DB = os.path.join(os.path.dirname(__file__), "..", "data", "reminders.db")

WORDS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


# ---------------------------------------------------------- storage
def _conn():
    os.makedirs(os.path.dirname(os.path.abspath(DB)), exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS reminders(
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 what TEXT, when_iso TEXT, done INTEGER DEFAULT 0,
                 fired INTEGER DEFAULT 0, created TEXT)""")
    return c


def _close(c):
    c.commit(); c.close()


# ---------------------------------------------------------- time parsing
def _time_hint(text):
    """Return (datetime|None, remaining_text). Understands:
       in 2 hours / in 30 minutes | tomorrow at 5pm | next monday 9am
       on june 5 at 6pm | december 10 | today 8:30pm | at 7pm"""
    now = datetime.datetime.now()
    t, words = now, text

    def grab(pat, caster, n=1):
        nonlocal t, words
        m = re.search(pat, words, re.I)
        if m:
            try:
                t = caster(t, m)
            except Exception:
                return None
            words = (words[:m.start()] + " " + words[m.end():]).strip(" ,")
            return m
        return None

    # --- relative: in N minutes/hours/days/weeks
    def rel(base, m):
        n, unit = int(m.group(1)), m.group(2).lower()
        if unit.startswith("min"):  return base + datetime.timedelta(minutes=n)
        if unit.startswith("hour"): return base + datetime.timedelta(hours=n)
        if unit.startswith("day"):  return base + datetime.timedelta(days=n)
        if unit.startswith("week"): return base + datetime.timedelta(weeks=n)
        return base
    grab(r"\bin (\d+) (minutes?|mins?|hours?|hrs?|days?|weeks?)\b", rel)

    # --- tomorrow / day after tomorrow / next weekday
    def tom(base, m):
        base = base + datetime.timedelta(days=1)
        if "day after" in m.group(0):
            base += datetime.timedelta(days=1)
        return base
    grab(r"\b(day after )?tomorrow\b", tom)
    grab(r"\bnext (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
         lambda b, m: b + datetime.timedelta(days=(7 - b.weekday() +
              WORDS[m.group(1).lower()] + 1) % 7 or 7))
    grab(r"\b(on |this )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
         lambda b, m: b + datetime.timedelta(days=(WORDS[m.group(2).lower()] -
              b.weekday()) % 7 or 7))

    # --- explicit date: on june 5 / december 10 2026 / 5 june
    def month_day(base, m):
        y = int(m.group(2)) if m.group(2) else base.year
        d = datetime.datetime(y, MONTHS[m.group(1).lower()], int(m.group(3)))
        if d < base.replace(hour=0, minute=0, second=0, microsecond=0):
            d = d.replace(year=y + 1)
        return d
    grab(r"\b(january|february|march|april|may|june|july|august|september|"
         r"october|november|december) (\d{4})?[ ,]*(\d{1,2})\b", month_day)
    grab(r"\b(\d{1,2}) (january|february|march|april|may|june|july|august|"
         r"september|october|november|december)\b",
         lambda b, m: month_day(b, re.match(r"(\w+) (\d+)", f"{m.group(2)} {m.group(1)}")))

    # --- clock time: 5pm / 5:30 pm / 17:00 / at 9 am
    def clock(base, m):
        hh, mm = int(m.group(1)), int(m.group(2) or 0)
        ap = (m.group(3) or "").lower()
        if ap == "pm" and hh != 12: hh += 12
        if ap == "am" and hh == 12: hh = 0
        cand = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if cand <= base and not re.search(r"\bat\b", m.group(0)):
            cand += datetime.timedelta(days=1)   # '5pm' already passed → tomorrow
        return cand
    grab(r"\b(?:at )?(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?\b", clock)

    # drop filler words
    words = re.sub(r"\b(remind me|reminder|to|me|on|at|about|that|please)\b",
                   " ", words, flags=re.I)
    words = re.sub(r"\s+", " ", words).strip(" ,")
    return (t if t != now else None, words or text)


# ---------------------------------------------------------- api
def add(text):
    """'remind me to visit grandma on june 5 at 6pm' -> saved + human reply."""
    when, what = _time_hint(text)
    if when is None:
        return None   # no time found — let other skills try
    c = _conn()
    c.execute("INSERT INTO reminders(what,when_iso,created) VALUES(?,?,?)",
              (vault.encrypt_text(what or "reminder"), vault.encrypt_text(when.isoformat()),
               datetime.datetime.now().isoformat()))
    _close(c)
    # mirror to cloud so she can fire it even with the laptop off
    try:
        if sync:
            sync.push_reminder(what or "reminder", when)
    except Exception:
        pass
    return (f"Got it. I'll remind you '{what}' on "
            f"{when:%A, %d %B at %I:%M %p}. I won't forget.")


def due_now():
    """Return list of (id, what) whose time has come. Marks them fired."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    c = _conn()
    out = []
    for rid, w_enc, t_enc in c.execute(
            "SELECT id, what, when_iso FROM reminders WHERE fired=0 AND done=0"):
        t = vault.decrypt_text(t_enc)
        if t <= now:
            out.append((rid, vault.decrypt_text(w_enc)))
            c.execute("UPDATE reminders SET fired=1 WHERE id=?", (rid,))
    _close(c)
    return out


def list_all():
    c = _conn()
    rows = [(rid, vault.decrypt_text(w), vault.decrypt_text(t))
            for rid, w, t in c.execute(
                "SELECT id, what, when_iso FROM reminders WHERE done=0 "
                "ORDER BY when_iso")]
    _close(c)
    return rows


def cancel(what_hint):
    c = _conn()
    n = 0
    for rid, w_enc in c.execute("SELECT id, what FROM reminders WHERE done=0"):
        if what_hint.lower() in vault.decrypt_text(w_enc).lower():
            c.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,)); n += 1
    _close(c)
    return f"Cancelled {n} reminder(s)." if n else "No matching reminder found."


# ---------------------------------------------------------- watcher thread
def push_notification(text):
    """Send a real push notification to the admin's phone via ntfy.sh (free).
    Set NTFY_TOPIC env var to your private topic name."""
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        return
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}", data=text.encode(),
            headers={"Title": "LYA reminder", "Priority": "high",
                     "Tags": "bell"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def _watch(say_fn, every=30):
    while True:
        try:
            # Pull reminders created from the phone/cloud down to the laptop brain.
            try:
                from brain.sync import pull_future_cloud
                pull_future_cloud()
            except Exception:
                pass
            for rid, what in due_now():
                msg = (f"Reminder: {what}. That's happening now — "
                       f"you asked me not to let you forget.")
                say_fn(msg)
                push_notification(msg)   # reach you even if laptop speakers are off
        except Exception:
            pass
        threading.Event().wait(every)


def start_watcher(say_fn):
    threading.Thread(target=_watch, args=(say_fn,), daemon=True).start()
