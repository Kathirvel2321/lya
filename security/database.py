"""Small encrypted SQLite stores: in-memory work and atomic disk commits."""
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from security import vault

_thread_lock = threading.RLock()


@contextmanager
def connection(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock, open(str(path) + ".lock", "a+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.seek(0, 2)
            if lock.tell() == 0:
                lock.write(b"0"); lock.flush()
            deadline = time.monotonic() + 10
            while True:
                try:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Memory is busy; retry shortly.")
                    time.sleep(0.05)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        db = sqlite3.connect(":memory:")
        try:
            if path.exists():
                db.deserialize(vault.decrypt(path.read_bytes()))
            yield db
            db.commit()
            encrypted = vault.encrypt(db.serialize())
            tmp = path.with_name(path.name + ".tmp")
            with open(tmp, "wb") as output:
                output.write(encrypted); output.flush(); os.fsync(output.fileno())
            os.replace(tmp, path)
        finally:
            db.close()
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)
