"""Validated visual settings; applying a theme never executes generated code."""
import json
import os
from pathlib import Path

THEMES = {
    "reactor": {"accent": "#70D6E5", "core": "#123640", "style": "arcs"},
    "halo": {"accent": "#D8C9A5", "core": "#353126", "style": "rings"},
    "pulse": {"accent": "#A6B9E9", "core": "#202C48", "style": "wave"},
}
TOKENS = {"background": "#10151C", "panel": "#171E27", "text": "#E6EDF5",
          "muted": "#A6B3C3", "border": "#344252", "transparent": "#010102",
          "font": "Segoe UI"}
PATH = Path(__file__).resolve().parent.parent / "data" / "appearance.json"


def load(path=PATH):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("theme") in THEMES:
            return data
    except (OSError, ValueError, AttributeError):
        pass
    return {"theme": "reactor", "previous": "reactor", "motion": True}


def save(name, path=PATH):
    if name not in THEMES:
        raise ValueError("Choose reactor, halo, or pulse.")
    old = load(path)
    data = {"theme": name, "previous": old["theme"], "motion": old.get("motion", True)}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)
    return data


def undo(path=PATH):
    return save(load(path).get("previous", "reactor"), path)
