"""Messages the admin sends to the bot: videos and plain-language commands.

Commands are understood by Gemini and turned into one of a few actions, which are
stored in data/state.json and carried out by the next run.
"""

import html
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import videos
from .config import DATA_DIR

STATE = DATA_DIR / "state.json"

HELP = (
    "Men quyidagilarni tushunaman:\n"
    "• <i>Hozir diabet haqida post chiqar</i>\n"
    "• <i>Ertangi postlar gripp haqida bo'lsin</i>\n"
    "• <i>Bugun 12:00 da post chiqarma</i>\n"
    "• <i>Yurak haqida rasm chiz</i>\n"
    "• <i>Holat</i>\n"
    "Yoki video yuboring, uning tagiga post yozib chiqaraman."
)


def load_state() -> dict:
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    state.setdefault("requests", [])   # [{"kind": "post"|"image", "text": ...}]
    state.setdefault("topic", None)    # {"text": ..., "remaining": n}
    state.setdefault("skip", [])       # ["2026-10-15 08:00", ...]
    return state


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def interpret(llm, text: str, now: datetime, post_times: list[str]) -> dict:
    prompt = f"""Siz Mehr Medical Center Telegram kanali botisiz. Admin sizga yozdi:
"{text}"

Hozir: {now:%Y-%m-%d %H:%M} (Toshkent). Kunlik post vaqtlari: {', '.join(post_times)}.

Buyruqni quyidagi amallardan biriga aylantiring va faqat JSON qaytaring:
- "post_now": hozir post chiqarish. "topic" = mavzu (aytilmagan bo'lsa bo'sh).
- "set_topic": keyingi kunlik postlar mavzusini belgilash. "topic" = mavzu,
  "count" = nechta kunlik post shu mavzuda bo'lsin (masalan "ertangi postlar" = {len(post_times)}, aytilmasa 1).
- "skip": kunlik postni o'tkazib yuborish. "slots" = ["YYYY-MM-DD HH:MM", ...] ro'yxati
  (faqat {', '.join(post_times)} vaqtlaridan; "bugun" desa bugungi hali o'tmagan vaqtlar).
- "unskip": o'tkazib yuborishni bekor qilish. "slots" yuqoridagidek.
- "image": rasm chizish. "topic" = rasm nimani tasvirlashi (ingliz tilida batafsil).
- "status": holat so'ralmoqda.
- "cancel_topic": belgilangan mavzuni bekor qilish.
- "unknown": tushunarsiz yoki salomlashish.

{{"action": "...", "topic": "", "count": 1, "slots": []}}"""
    return llm.json(prompt, temperature=0.1)


def status_text(state: dict, now: datetime, post_times: list[str]) -> str:
    lines = ["📋 <b>Holat</b>"]
    upcoming = []
    for day in (now.date(), now.date() + timedelta(days=1)):
        for t in post_times:
            slot = f"{day} {t}"
            if slot > f"{now:%Y-%m-%d %H:%M}":
                upcoming.append(slot + (" (o'tkaziladi)" if slot in state["skip"] else ""))
    lines.append("Keyingi kunlik postlar: " + ", ".join(upcoming[:3]))
    if state["topic"]:
        lines.append(f"Belgilangan mavzu: {html.escape(state['topic']['text'])} "
                     f"({state['topic']['remaining']} ta post)")
    queue = videos.load()
    if queue:
        lines.append(f"Navbatdagi videolar: {len(queue)} ta")
    if state["requests"]:
        lines.append(f"Bajarilishi kutilayotgan buyruqlar: {len(state['requests'])} ta")
    return "\n".join(lines)


def handle_command(tg, llm, cfg, text: str) -> None:
    admin = cfg.secrets.admin_chat_id
    settings = cfg.settings
    now = datetime.now(ZoneInfo(settings["timezone"]))
    try:
        command = interpret(llm, text, now, settings["post_times"])
    except Exception as error:
        tg.send_message(admin, f"⚠️ Buyruqni tushunolmadim: {html.escape(str(error))[:200]}")
        return
    action = command.get("action")
    topic = str(command.get("topic") or "").strip()
    state = load_state()

    if action == "post_now":
        state["requests"].append({"kind": "post", "text": topic})
        reply = "✅ Post tayyorlanmoqda" + (f": <b>{html.escape(topic)}</b>" if topic else "") + \
                ". Bir necha daqiqada sizga ko'rsataman, 10 daqiqadan keyin kanalga chiqadi."
    elif action == "set_topic" and topic:
        count = max(1, min(int(command.get("count") or 1), 14))
        state["topic"] = {"text": topic, "remaining": count}
        reply = f"✅ Keyingi {count} ta kunlik post <b>{html.escape(topic)}</b> haqida bo'ladi."
    elif action in ("skip", "unskip"):
        valid = {f"{d} {t}" for d in (now.date(), now.date() + timedelta(days=1), now.date() + timedelta(days=2))
                 for t in settings["post_times"]}
        slots = [s for s in command.get("slots") or [] if s in valid and s > f"{now:%Y-%m-%d %H:%M}"]
        if not slots:
            reply = "Qaysi post vaqtini nazarda tutganingizni tushunmadim. Masalan: <i>Bugun 12:00 da post chiqarma</i>"
        elif action == "skip":
            state["skip"] = sorted(set(state["skip"]) | set(slots))
            reply = "⏭ Bu postlar chiqmaydi: " + ", ".join(slots)
        else:
            state["skip"] = [s for s in state["skip"] if s not in slots]
            reply = "✅ Bu postlar yana chiqadi: " + ", ".join(slots)
    elif action == "image" and topic:
        state["requests"].append({"kind": "image", "text": topic})
        reply = "🎨 Rasm tayyorlanmoqda, bir necha daqiqada yuboraman."
    elif action == "cancel_topic":
        state["topic"] = None
        reply = "✅ Belgilangan mavzu bekor qilindi, mavzular yana avtomatik tanlanadi."
    elif action == "status":
        reply = status_text(state, now, settings["post_times"])
    else:
        reply = HELP
    save_state(state)
    tg.send_message(admin, reply)


def handle(update: dict, tg, llm, cfg) -> bool:
    """Handles a video or a text command from the admin. True if the update was one."""
    admin = cfg.secrets.admin_chat_id
    item = videos.extract(update, admin)
    if item:
        videos.accept(tg, admin, item)
        return True
    message = update.get("message") or {}
    if str((message.get("from") or {}).get("id", "")) != str(admin):
        return False
    text = (message.get("text") or "").strip()
    if not text or text == "/start":
        if text == "/start":
            tg.send_message(admin, HELP)
        return bool(text)
    handle_command(tg, llm, cfg, text)
    return True


def collect(tg, llm, cfg, offset: int | None = None) -> int:
    """Reads every pending update, handling admin videos and commands and expiring
    old buttons. Returns the offset after the last update."""
    tg.call("deleteWebhook", {"drop_pending_updates": "false"})
    while True:
        updates = tg.get_updates(offset, timeout=0)
        if not updates:
            return offset or 0
        for update in updates:
            offset = update["update_id"] + 1
            if not handle(update, tg, llm, cfg) and update.get("callback_query"):
                tg.answer_callback(update["callback_query"]["id"], "Bu tugma eskirgan")
