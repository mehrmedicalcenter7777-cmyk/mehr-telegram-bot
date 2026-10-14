"""End-to-end run with fake Gemini, ElevenLabs and Telegram."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from mehrbot import config, history, main, schedule
from mehrbot.agents import narrator

POST = ("🫀 <b>QON BOSIMI</b>\n\nFakt.\n\n🔹 <b>Maslahat:</b> tuzni kamaytiring\n\n"
        "❗ Ma'lumot tanishish uchun.\n\n<b>MEHR MEDICAL</b> ❤️")


class FakeLLM:
    command = {"action": "unknown"}
    def media_json(self, prompt, data, mime, system=""):
        return {"title": "Video", "post_html": POST, "doctor": "", "video_summary": "Shifokor maslahati"}

    def __init__(self):
        self.topics = 0

    def json(self, prompt, system="", search=False, temperature=0.7):
        if "Buyruqni" in prompt:
            return self.command
        if "JSON massiv" in prompt:
            self.topics += 1
            return [{"topic": f"Mavzu {self.topics}-{i}"} for i in range(3)]
        if "approved" in prompt:
            return {"approved": True, "issues": []}
        return {"title": "Qon bosimi", "post_html": POST, "audio_script": "Salom",
                "image_prompt": "heart", "doctor": "", "sources": ["WHO"]}

    def image(self, prompt):
        return b"png"


class FakeTelegram:
    def __init__(self, presses):
        self.sent = []
        self.presses = presses
        self.next_id = 0
        self.last_buttons = None
        self.inbox = []

    def call(self, method, data=None, files=None, timeout=60):
        return True

    def _msg(self, kind, chat, payload):
        self.next_id += 1
        self.sent.append((kind, str(chat), payload))
        return {"message_id": self.next_id}

    def send_photo(self, chat, photo, caption):
        return self._msg("photo", chat, caption)

    def send_audio(self, chat, audio, title, performer, caption=""):
        return self._msg("audio", chat, title)

    def send_message(self, chat, text, buttons=None):
        self.last_buttons = buttons
        return self._msg("message", chat, text)

    def edit_text(self, chat, message_id, text):
        self.sent.append(("edit", str(chat), text))

    def answer_callback(self, callback_id, text=""):
        pass

    def send_video(self, chat, file_id, caption, buttons=None):
        return self._msg("video", chat, file_id)

    def download(self, file_id):
        return b"mp4"

    def get_updates(self, offset, timeout=25):
        offset = offset or 1
        if self.inbox:
            update = {"update_id": offset, "message": self.inbox.pop(0)}
            return [update]
        if self.presses and self.last_buttons:
            self.presses -= 1
            data = self.last_buttons[0][1]
            return [{"update_id": offset, "callback_query": {"id": "q", "data": data, "from": {"id": 42}}}]
        return []


def isolate(monkeypatch, tmp_path):
    from mehrbot import inbox, videos
    monkeypatch.setattr(history, "PATH", tmp_path / "history.json")
    monkeypatch.setattr(videos, "PATH", tmp_path / "videos.json")
    monkeypatch.setattr(inbox, "STATE", tmp_path / "state.json")
    for name, value in [("TELEGRAM_BOT_TOKEN", "t"), ("ADMIN_CHAT_ID", "42"), ("GEMINI_API_KEY", "g"),
                        ("ELEVENLABS_API_KEY", "e"), ("ELEVENLABS_VOICE_ID", "v")]:
        monkeypatch.setenv(name, value)


def run(monkeypatch, tmp_path, presses):
    isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(narrator, "make_audio", lambda *a, **k: b"mp3")
    monkeypatch.setattr(main, "sleep_until", lambda moment: None)
    # Publish window already over after one poll: plan() returns a time in the past.
    monkeypatch.setattr(schedule, "plan", lambda now, slot, m: (now, now + timedelta(seconds=1)))
    for name, value in [("TELEGRAM_BOT_TOKEN", "t"), ("ADMIN_CHAT_ID", "42"), ("GEMINI_API_KEY", "g"),
                        ("ELEVENLABS_API_KEY", "e"), ("ELEVENLABS_VOICE_ID", "v")]:
        monkeypatch.setenv(name, value)
    cfg = config.load()
    tg = FakeTelegram(presses)
    now = datetime.now(ZoneInfo(cfg.settings["timezone"]))
    assert main.run_scheduled(cfg, FakeLLM(), tg, f"{now:%H:%M}") == 0
    return tg


def test_publishes_without_press(monkeypatch, tmp_path):
    tg = run(monkeypatch, tmp_path, presses=0)
    channel = [s for s in tg.sent if s[1] == "@mehr_medical7"]
    assert [s[0] for s in channel] == ["photo", "audio"]
    assert history.load()[0]["topic"] == "Mavzu 1-0"


def test_regenerate_uses_new_topic(monkeypatch, tmp_path):
    tg = run(monkeypatch, tmp_path, presses=1)
    previews = [s for s in tg.sent if s[1] == "42" and s[0] == "photo"]
    assert len(previews) == 2
    assert history.load()[0]["topic"] == "Mavzu 1-1"


def test_video_from_admin_is_posted(monkeypatch, tmp_path):
    from mehrbot import videos
    isolate(monkeypatch, tmp_path)
    cfg = config.load()
    cfg.settings["preview_minutes_before"] = 0
    tg = FakeTelegram(presses=0)
    tg.inbox.append({"message_id": 5, "from": {"id": 42}, "video": {"file_id": "VID", "file_size": 1000}})
    assert main.run_inbox(cfg, FakeLLM(), tg) == 0
    assert ("video", "@mehr_medical7", "VID") in tg.sent
    assert videos.load() == []


def test_oversized_video_is_rejected(monkeypatch, tmp_path):
    from mehrbot import videos
    monkeypatch.setattr(videos, "PATH", tmp_path / "videos.json")
    tg = FakeTelegram(presses=0)
    videos.accept(tg, "42", {"file_id": "BIG", "file_size": 50 * 1024 * 1024, "hint": ""})
    assert videos.load() == [] and "20 MB" in tg.sent[0][2]


def test_post_now_command_publishes_on_requested_topic(monkeypatch, tmp_path):
    isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(narrator, "make_audio", lambda *a, **k: b"mp3")
    cfg = config.load()
    cfg.settings["preview_minutes_before"] = 0
    llm = FakeLLM()
    llm.command = {"action": "post_now", "topic": "Diabet"}
    tg = FakeTelegram(presses=0)
    tg.inbox.append({"message_id": 7, "from": {"id": 42}, "text": "Hozir diabet haqida post chiqar"})
    assert main.run_inbox(cfg, llm, tg) == 0
    assert [s[0] for s in tg.sent if s[1] == "@mehr_medical7"] == ["photo", "audio"]
    assert history.load()[0]["topic"] == "Diabet"


def test_skip_command_stops_scheduled_post(monkeypatch, tmp_path):
    from mehrbot import inbox
    isolate(monkeypatch, tmp_path)
    cfg = config.load()
    now = datetime.now(ZoneInfo(cfg.settings["timezone"]))
    slot = (now + timedelta(minutes=30)).replace(second=0, microsecond=0)
    inbox.save_state({"requests": [], "topic": None, "skip": [f"{slot:%Y-%m-%d %H:%M}"]})
    tg = FakeTelegram(presses=0)
    assert main.run_scheduled(cfg, FakeLLM(), tg, f"{slot:%H:%M}") == 0
    assert not [s for s in tg.sent if s[1] == "@mehr_medical7"]
    assert inbox.load_state()["skip"] == []


def test_unknown_message_gets_help(monkeypatch, tmp_path):
    from mehrbot import inbox
    isolate(monkeypatch, tmp_path)
    cfg = config.load()
    tg = FakeTelegram(presses=0)
    tg.inbox.append({"message_id": 8, "from": {"id": 42}, "text": "salom"})
    inbox.collect(tg, FakeLLM(), cfg)
    assert "tushunaman" in tg.sent[-1][2]
