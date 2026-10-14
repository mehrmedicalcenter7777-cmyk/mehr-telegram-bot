"""Remembers published topics so they aren't repeated."""

import json

from .config import DATA_DIR

PATH = DATA_DIR / "history.json"


def load() -> list[dict]:
    if not PATH.exists():
        return []
    return json.loads(PATH.read_text(encoding="utf-8")).get("posts", [])


def add(entry: dict, keep: int) -> None:
    posts = (load() + [entry])[-keep:]
    PATH.write_text(json.dumps({"posts": posts}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
