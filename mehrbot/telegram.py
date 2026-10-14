"""Minimal Telegram Bot API client."""

import json
import time

import requests


class TelegramError(RuntimeError):
    pass


class Telegram:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}/"

    def call(self, method: str, data: dict | None = None, files: dict | None = None, timeout: int = 60):
        last_error = None
        for attempt in range(4):
            try:
                response = requests.post(self.base + method, data=data, files=files, timeout=timeout)
                body = response.json()
            except (requests.RequestException, ValueError) as error:
                last_error = error
                time.sleep(3 * 2 ** attempt)
                continue
            if body.get("ok"):
                return body["result"]
            retry_after = (body.get("parameters") or {}).get("retry_after")
            if response.status_code == 429 and retry_after:
                time.sleep(int(retry_after) + 1)
                continue
            # Don't leak the token: the URL is never included in the message.
            raise TelegramError(f"{method}: {body.get('description')}")
        raise TelegramError(f"{method}: {last_error}")

    @staticmethod
    def _markup(buttons):
        if not buttons:
            return None
        return json.dumps({"inline_keyboard": [[{"text": text, "callback_data": data}] for text, data in buttons]})

    def send_message(self, chat_id, text: str, buttons=None):
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        if buttons:
            data["reply_markup"] = self._markup(buttons)
        return self.call("sendMessage", data)

    def send_photo(self, chat_id, photo: bytes, caption: str):
        return self.call(
            "sendPhoto",
            {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"photo": ("post.png", photo, "image/png")},
            timeout=120,
        )

    def send_video(self, chat_id, file_id: str, caption: str, buttons=None):
        data = {"chat_id": chat_id, "video": file_id, "caption": caption, "parse_mode": "HTML"}
        if buttons:
            data["reply_markup"] = self._markup(buttons)
        return self.call("sendVideo", data)

    def download(self, file_id: str) -> bytes:
        path = self.call("getFile", {"file_id": file_id})["file_path"]
        url = self.base.replace("/bot", "/file/bot", 1) + path
        response = requests.get(url, timeout=300)
        if not response.ok:
            raise TelegramError(f"getFile: fayl yuklab olinmadi ({response.status_code})")
        return response.content

    def send_audio(self, chat_id, audio: bytes, title: str, performer: str, caption: str = ""):
        return self.call(
            "sendAudio",
            {"chat_id": chat_id, "title": title, "performer": performer, "caption": caption, "parse_mode": "HTML"},
            files={"audio": ("maslahat.mp3", audio, "audio/mpeg")},
            timeout=120,
        )

    def edit_text(self, chat_id, message_id: int, text: str):
        return self.call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML",
            "reply_markup": json.dumps({"inline_keyboard": []}),
        })

    def answer_callback(self, callback_id: str, text: str = ""):
        return self.call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

    def get_updates(self, offset: int | None, timeout: int = 25):
        data = {"timeout": timeout, "allowed_updates": json.dumps(["callback_query", "message"])}
        if offset is not None:
            data["offset"] = offset
        return self.call("getUpdates", data, timeout=timeout + 15)
