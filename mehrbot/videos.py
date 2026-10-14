"""Videos the admin sends to the bot: queued until the next posting slot."""

import json

from .config import DATA_DIR

PATH = DATA_DIR / "video_queue.json"
MAX_BYTES = 20 * 1024 * 1024  # Bot API download limit


def load() -> list[dict]:
    if not PATH.exists():
        return []
    return json.loads(PATH.read_text(encoding="utf-8")).get("videos", [])


def save(items: list[dict]) -> None:
    PATH.write_text(json.dumps({"videos": items}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def remove(file_id: str) -> None:
    save([v for v in load() if v["file_id"] != file_id])


def extract(update: dict, admin) -> dict | None:
    """The video in an admin's message, if there is one."""
    message = update.get("message") or {}
    if str((message.get("from") or {}).get("id", "")) != str(admin):
        return None
    video = message.get("video")
    document = message.get("document") or {}
    if not video and str(document.get("mime_type", "")).startswith("video/"):
        video = document
    if not video:
        return None
    return {
        "file_id": video["file_id"],
        "file_size": video.get("file_size", 0),
        "mime_type": video.get("mime_type", "video/mp4"),
        "hint": message.get("caption", ""),
        "message_id": message.get("message_id"),
    }


def accept(tg, admin, item: dict) -> None:
    """Queues a video and tells the admin what will happen to it."""
    if item["file_size"] and item["file_size"] > MAX_BYTES:
        tg.send_message(admin, f"❌ Video juda katta ({item['file_size'] // (1024 * 1024)} MB). "
                               "Telegram botlar faqat 20 MB gacha videoni yuklab oladi. "
                               "Videoni siqib (kichikroq sifatda) qayta yuboring.")
        return
    queue = load()
    if any(v["file_id"] == item["file_id"] for v in queue):
        return
    save(queue + [item])
    tg.send_message(admin, "✅ Video qabul qilindi. Unga post yozilib, eng yaqin post vaqtida "
                           "(8:00 yoki 12:00) kanalga chiqadi. 10 daqiqa oldin sizga ko'rsatiladi.")
