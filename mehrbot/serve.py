"""Always-on mode for a server: answers the admin within seconds and publishes at the post times.

Replaces the GitHub Actions schedules (every 5 minutes for the inbox, twice a day for posts)."""

import html
import json
import os
import subprocess
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import inbox, schedule, videos
from .config import DATA_DIR

SERVED = DATA_DIR / "served_slots.json"
# Building a post (search, writing, review, image, voice, video) takes a few minutes,
# so work on a slot starts this long before it; the preview still goes out 10 minutes before.
LEAD = timedelta(minutes=25)


def _served() -> list[str]:
    return json.loads(SERVED.read_text(encoding="utf-8")) if SERVED.exists() else []


def _mark_served(key: str) -> None:
    SERVED.write_text(json.dumps((_served() + [key])[-20:]) + "\n", encoding="utf-8")


def due_slot(now: datetime, post_times: list[str], served: list[str]) -> datetime | None:
    """The post time whose work should start now and hasn't been done yet."""
    for day in (now.date() - timedelta(days=1), now.date()):
        for value in post_times:
            slot = datetime.combine(day, schedule.parse_time(value), tzinfo=now.tzinfo)
            if slot - LEAD <= now <= slot + schedule.MAX_LATE and f"{slot:%Y-%m-%d %H:%M}" not in served:
                return slot
    return None


def _save(log) -> None:
    """On GitHub Actions the data folder is committed back after every change (MEHR_SAVE_CMD)."""
    command = os.environ.get("MEHR_SAVE_CMD")
    if command:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode:
            log(f"Ma'lumot saqlanmadi: {result.stderr[-300:]}")


def serve(cfg, llm, tg, log, max_minutes: int | None = None) -> int:
    """max_minutes: stop when idle after this long (GitHub Actions jobs end after 6 hours;
    the next queued run takes over)."""
    from . import main  # the run_* steps live there

    tz = ZoneInfo(cfg.settings["timezone"])
    admin = cfg.secrets.admin_chat_id
    started = time.monotonic()
    log("Bot ishga tushdi, xabarlarni kutyapti.")
    offset = inbox.collect(tg, llm, cfg)
    while True:
        try:
            slot = due_slot(datetime.now(tz), cfg.settings["post_times"], _served())
            if slot:
                _mark_served(f"{slot:%Y-%m-%d %H:%M}")  # first, so a crash can't post twice
                _save(log)
                main.run_scheduled(cfg, llm, tg, f"{slot:%H:%M}", slot_date=slot.date())
                _save(log)
                offset = inbox.collect(tg, llm, cfg)
                continue
            if videos.load() or inbox.load_state()["requests"]:
                main.run_inbox(cfg, llm, tg)
                _save(log)
                offset = inbox.collect(tg, llm, cfg)
                continue
            if max_minutes and time.monotonic() - started > max_minutes * 60:
                inbox.collect(tg, llm, cfg, offset)  # confirm what was handled
                _save(log)
                log("Vaqt tugadi, navbatdagi ishga topshirildi.")
                return 0
            # Wait for the admin; long polling returns the moment something arrives.
            for update in tg.get_updates(offset, timeout=25):
                offset = update["update_id"] + 1
                if not inbox.handle(update, tg, llm, cfg) and update.get("callback_query"):
                    tg.answer_callback(update["callback_query"]["id"], "Bu tugma eskirgan")
            offset = inbox.collect(tg, llm, cfg, offset)
            _save(log)
        except KeyboardInterrupt:
            return 0
        except Exception as error:
            log(f"XATO: {error!r}")
            try:
                tg.send_message(admin, f"⚠️ Botda xato yuz berdi:\n<code>{html.escape(str(error))[:800]}</code>")
            except Exception:
                pass
            time.sleep(30)
