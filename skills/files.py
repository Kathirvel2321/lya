"""Read-only, paged folder navigation. No file execution or recursive scans."""
import os
from pathlib import Path


class FolderBrowser:
    def __init__(self, root=None, page_size=50):
        self.root = Path(root or Path.home()).resolve()
        self.current = self.root
        self.page_size = page_size
        self.page = 0
        self.entries = []
        self.has_more = False

    def _inside(self, path):
        resolved = Path(path).resolve()
        if not resolved.is_relative_to(self.root):
            raise PermissionError("That location is outside this approved folder session.")
        return resolved

    def listing(self):
        # One directory at a time; cap result storage even in huge directories.
        self.current = self._inside(self.current)
        start = self.page * self.page_size
        rows = []
        with os.scandir(self.current) as scan:
            for i, entry in enumerate(scan):
                if i < start:
                    continue
                if len(rows) > self.page_size:
                    break
                rows.append({"name": entry.name,
                             "folder": entry.is_dir(follow_symlinks=False),
                             "link": entry.is_symlink()})
        self.has_more = len(rows) > self.page_size
        self.entries = rows[:self.page_size]
        return {"path": str(self.current), "entries": self.entries,
                "page": self.page + 1, "more": self.has_more}

    def open(self, selection):
        if str(selection).isdigit():
            index = int(selection) - 1
            if not 0 <= index < len(self.entries):
                raise ValueError("Choose a number from the current page.")
            name = self.entries[index]["name"]
        else:
            matches = [e["name"] for e in self.entries if e["name"].casefold() == str(selection).casefold()]
            if not matches:
                raise ValueError("Choose a folder shown on the current page.")
            name = matches[0]
        path = self._inside(self.current / name)
        if not path.is_dir():
            return {"file": path.name, "bytes": path.stat().st_size,
                    "message": "File details only; executable files are not launched."}
        self.current, self.page = path, 0
        return self.listing()

    def back(self):
        self.current = self.root if self.current == self.root else self._inside(self.current.parent)
        self.page = 0
        return self.listing()

    def scroll(self, direction):
        if direction > 0 and self.has_more:
            self.page += 1
        elif direction < 0:
            self.page = max(0, self.page - 1)
        return self.listing()
