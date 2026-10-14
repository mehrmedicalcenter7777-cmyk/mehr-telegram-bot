"""End-to-end run with fake Gemini, ElevenLabs and Telegram."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from mehrbot import config, history, main, schedule
from mehrbot.agents import narrator

POST = ("🫀 <b>QON BOSIMI</b>\n\nFakt.\n\n🔹 <b>Maslahat:</b> tuzni kamaytiring\n\n"
        "❗ Ma'lumot tanishish uchun.\n\n<b>MEHR MEDICAL</b> ❤️")


class FakeLLM:
    def __init__(self):
        self.topics = 0

    def json(self, prompt, system="", search=False, temperature=0.7):
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

    def skip_pending_updates(self):
        return 1

    def get_updates(self, offset, timeout=25):
        if self.presses:
            self.presses -= 1
            data = self.last_buttons[0][1]
            return [{"update_id": offset, "callback_query": {"id": "q", "data": data, "from": {"id": 42}}}]
        return []


def run(monkeypatch, tmp_path, presses):
    monkeypatch.setattr(history, "PATH", tmp_path / "history.json")
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
