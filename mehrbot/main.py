"""Entry point: python -m mehrbot.main --mode scheduled|test|now|chat_id"""

import argparse
import html
import secrets
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config, history, schedule, videos
from .llm import Gemini
from .pipeline import TopicQueue, build, build_video
from .telegram import Telegram

REGEN_BUTTON = "🔄 Qayta ishlash"
NOW_BUTTON = "✅ Hozir chiqarish"


def log(message: str) -> None:
    print(message, flush=True)


def sleep_until(moment: datetime) -> None:
    while True:
        remaining = (moment - datetime.now(moment.tzinfo)).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 30))


def send_preview(tg: Telegram, admin, post, publish_at: datetime | None, token: str | None,
                 allow_now: bool = False):
    if post.kind == "video":
        tg.send_video(admin, post.video_file_id, post.html)
    else:
        tg.send_photo(admin, post.image, post.html)
    if post.audio:
        tg.send_audio(admin, post.audio, post.title, "Mehr Medical")
    sources = "\n".join(f"• {html.escape(str(s))}" for s in post.sources[:5])
    if publish_at:
        text = (f"⏰ Bu post <b>{publish_at:%H:%M}</b> da kanalga avtomatik chiqadi.\n"
                f"O'zgartirish kerak bo'lsa, «{REGEN_BUTTON}» tugmasini bosing.")
    else:
        text = "🧪 Sinov posti. Kanalga chiqarilmaydi."
    if sources:
        text += f"\n\n📚 Manbalar:\n{sources}"
    if post.warning:
        text += f"\n\n⚠️ {html.escape(post.warning)}"
    buttons = [(REGEN_BUTTON, f"regen:{token}")] if token else None
    if token and allow_now:
        buttons.append((NOW_BUTTON, f"now:{token}"))
    return tg.send_message(admin, text, buttons)


def publish(tg: Telegram, cfg, post) -> None:
    channel = cfg.settings["channel_id"]
    if post.kind == "video":
        tg.send_video(channel, post.video_file_id, post.html)
        return
    tg.send_photo(channel, post.image, post.html)
    if post.audio:
        tg.send_audio(channel, post.audio, post.title, cfg.settings["channel_name"])


def button_action(update: dict, admin: str, token: str) -> str | None:
    """'regen' or 'now' when the admin pressed a button on the current preview."""
    query = update.get("callback_query") or {}
    if str((query.get("from") or {}).get("id", "")) != str(admin):
        return None
    action, _, pressed = str(query.get("data", "")).partition(":")
    return action if pressed == token else None


def review_window(tg, cfg, post, publish_at: datetime, offset: int, rebuild, allow_now: bool = False):
    """Shows the post to the admin and waits until publish_at, handling the buttons.
    Videos sent meanwhile are queued. Returns the post to publish and the notice message."""
    admin = cfg.secrets.admin_chat_id
    tz = publish_at.tzinfo
    token = secrets.token_hex(4)
    notice = send_preview(tg, admin, post, publish_at, token, allow_now)
    while datetime.now(tz) < publish_at:
        wait = int(min(25, max(1, (publish_at - datetime.now(tz)).total_seconds())))
        for update in tg.get_updates(offset, timeout=wait):
            offset = update["update_id"] + 1
            item = videos.extract(update, admin)
            if item:
                videos.accept(tg, admin, item)
                continue
            query = update.get("callback_query")
            if not query:
                continue
            action = button_action(update, admin, token)
            if action is None:
                tg.answer_callback(query["id"], "Bu tugma eskirgan")
            elif action == "now":
                tg.answer_callback(query["id"], "Chiqarilmoqda...")
                return post, notice
            else:
                tg.answer_callback(query["id"], "Qayta ishlanmoqda...")
                tg.edit_text(admin, notice["message_id"], "⏳ Yangi variant tayyorlanmoqda...")
                log("Admin qayta ishlashni so'radi")
                post = rebuild()
                token = secrets.token_hex(4)
                notice = send_preview(tg, admin, post, max(publish_at, datetime.now(tz)), token, allow_now)
                break
    return post, notice


def run_scheduled(cfg, llm, tg, slot_override: str | None) -> int:
    tz = ZoneInfo(cfg.settings["timezone"])
    now = datetime.now(tz)
    if slot_override:
        slot = datetime.combine(now.date(), schedule.parse_time(slot_override), tzinfo=tz)
    else:
        slot = schedule.pick_slot(now, cfg.settings["post_times"])
    if not slot:
        log(f"Hozir ({now:%H:%M}) yaqin post vaqti yo'q, chiqiladi.")
        return 0
    log(f"Post vaqti: {slot:%Y-%m-%d %H:%M}")

    admin = cfg.secrets.admin_chat_id
    topics = TopicQueue(llm, cfg, today=f"{now:%Y-%m-%d}")
    post = build(llm, cfg, topics, log)

    preview_at, publish_at = schedule.plan(datetime.now(tz), slot, cfg.settings["preview_minutes_before"])
    log(f"Ko'rib chiqish uchun yuboriladi: {preview_at:%H:%M}, kanalga: {publish_at:%H:%M}")
    sleep_until(preview_at)

    offset = videos.collect(tg, admin)
    post, notice = review_window(tg, cfg, post, publish_at, offset, lambda: build(llm, cfg, topics, log))

    publish(tg, cfg, post)
    tg.edit_text(admin, notice["message_id"], f"✅ Post kanalga chiqdi ({datetime.now(tz):%H:%M}).")
    history.add({
        "date": f"{slot:%Y-%m-%d %H:%M}", "title": post.title,
        "topic": post.topic.get("topic"), "doctor": post.doctor,
    }, keep=cfg.settings.get("history_size", 120))
    log("Kanalga chiqdi.")
    return 0


def run_videos(cfg, llm, tg) -> int:
    """Checks the bot for videos; posts the first queued one after a 10-minute preview."""
    admin = cfg.secrets.admin_chat_id
    tz = ZoneInfo(cfg.settings["timezone"])
    offset = videos.collect(tg, admin)
    queue = videos.load()
    if not queue:
        log("Yangi video yo'q.")
        return 0
    item = queue[0]
    try:
        post = build_video(llm, cfg, tg, item, log)
    except Exception as error:
        videos.remove(item["file_id"])
        tg.send_message(admin, f"⚠️ Videoga post yozib bo'lmadi:\n<code>{html.escape(str(error))[:600]}</code>")
        raise
    publish_at = datetime.now(tz) + timedelta(minutes=cfg.settings["preview_minutes_before"])
    post, notice = review_window(tg, cfg, post, publish_at, offset,
                                 lambda: build_video(llm, cfg, tg, item, log), allow_now=True)
    publish(tg, cfg, post)
    videos.remove(item["file_id"])
    tg.edit_text(admin, notice["message_id"], f"✅ Video kanalga chiqdi ({datetime.now(tz):%H:%M}).")
    history.add({"date": f"{datetime.now(tz):%Y-%m-%d %H:%M}", "title": post.title,
                 "topic": post.topic.get("topic"), "doctor": post.doctor},
                keep=cfg.settings.get("history_size", 120))
    log("Video kanalga chiqdi.")
    return 0


def run_once(cfg, llm, tg, to_channel: bool) -> int:
    tz = ZoneInfo(cfg.settings["timezone"])
    post = build(llm, cfg, TopicQueue(llm, cfg, today=f"{datetime.now(tz):%Y-%m-%d}"), log)
    if to_channel:
        publish(tg, cfg, post)
        history.add({"date": f"{datetime.now(tz):%Y-%m-%d %H:%M}", "title": post.title,
                     "topic": post.topic.get("topic"), "doctor": post.doctor},
                    keep=cfg.settings.get("history_size", 120))
        log("Kanalga chiqdi.")
    else:
        send_preview(tg, cfg.secrets.admin_chat_id, post, None, None)
        log("Sinov posti adminga yuborildi.")
    return 0


def show_chat_ids(tg) -> int:
    """Prints who has written to the bot, to find ADMIN_CHAT_ID."""
    tg.call("deleteWebhook", {"drop_pending_updates": "false"})
    seen = {}
    for update in tg.get_updates(None, timeout=0):
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") == "private":
            seen[chat["id"]] = f"{chat.get('first_name', '')} {chat.get('last_name', '')} @{chat.get('username', '')}"
    if not seen:
        log("Hech kim botga yozmagan. Botni ochib /start bosing va qayta ishga tushiring.")
    for chat_id, name in seen.items():
        log(f"ADMIN_CHAT_ID = {chat_id}   ({name.strip()})")
    return 0


def show_models() -> int:
    """Prints Gemini models available to this API key."""
    from google import genai
    client = genai.Client(api_key=config._env("GEMINI_API_KEY"))
    for model in client.models.list():
        actions = getattr(model, "supported_actions", None) or []
        if "generateContent" in actions:
            log(f"MODEL {model.name}  ({model.display_name})")
    return 0


def probe_models() -> int:
    """Tries a tiny request on candidate models to see which ones the key's quota allows."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config._env("GEMINI_API_KEY"))
    search = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    image = types.GenerateContentConfig(response_modalities=["IMAGE"])
    checks = [(m, None, "matn") for m in ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite",
                                          "gemini-3.1-flash-lite", "gemini-flash-latest",
                                          "gemini-flash-lite-latest", "gemini-2.5-flash-lite"]]
    checks += [(m, search, "matn+qidiruv") for m in ["gemini-3.8-flash", "gemini-3.5-flash-lite",
                                                     "gemini-3.1-flash-lite", "gemini-flash-lite-latest"]]
    checks += [(m, image, "rasm") for m in ["gemini-3.1-flash-lite-image", "gemini-3.1-flash-image",
                                            "gemini-2.5-flash-image", "gemini-nano-banana-2.1"]]
    for model, cfg, kind in checks:
        try:
            client.models.generate_content(model=model, contents="Salom, bitta so'z bilan javob ber." if kind != "rasm" else "A red apple on a white table", config=cfg)
            log(f"PROBE OK    {kind:13} {model}")
        except Exception as error:
            log(f"PROBE FAIL  {kind:13} {model}: {str(error)[:90]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="scheduled", choices=["scheduled", "test", "now", "videos", "chat_id", "models", "probe"])
    parser.add_argument("--slot", help="post vaqtini majburan berish, masalan 08:00")
    args = parser.parse_args()

    if args.mode == "probe":
        return probe_models()
    if args.mode == "models":
        return show_models()
    if args.mode == "chat_id":
        return show_chat_ids(Telegram(config._env("TELEGRAM_BOT_TOKEN")))

    cfg = config.load()
    s = cfg.settings
    llm = Gemini(cfg.secrets.gemini_api_key, s["models"]["text"], s["models"]["image"],
                 s["models"].get("image_aspect_ratio", "1:1"), web_search=s.get("web_search", True), log=log)
    tg = Telegram(cfg.secrets.telegram_token)
    try:
        if args.mode == "scheduled":
            return run_scheduled(cfg, llm, tg, args.slot)
        if args.mode == "videos":
            return run_videos(cfg, llm, tg)
        return run_once(cfg, llm, tg, to_channel=args.mode == "now")
    except Exception as error:
        log(f"XATO: {error!r}")
        try:
            tg.send_message(cfg.secrets.admin_chat_id,
                            f"⚠️ Post tayyorlashda xato yuz berdi:\n<code>{html.escape(str(error))[:800]}</code>")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    sys.exit(main())
