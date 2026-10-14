"""Thin wrapper around the Gemini API (text, web-grounded text, JSON, images).

Falls back gracefully when the API key's quota doesn't cover a feature:
web search is dropped, and the next text model in the list is tried.
"""

import time

from google import genai
from google.genai import errors, types

from .textutil import extract_json

TRANSIENT = {500, 502, 503, 504}
UNUSABLE = {404, 429}  # model closed for this key, or no quota on this tier


class Gemini:
    def __init__(self, api_key: str, text_models, image_model: str, aspect_ratio: str = "1:1",
                 web_search: bool = True, log=print):
        self.client = genai.Client(api_key=api_key)
        self.text_models = [text_models] if isinstance(text_models, str) else list(text_models)
        self.image_model = image_model
        self.aspect_ratio = aspect_ratio
        self.web_search = web_search
        self.log = log

    def _call(self, model: str, contents, config):
        last_error = None
        for attempt in range(3):
            try:
                return self.client.models.generate_content(model=model, contents=contents, config=config)
            except errors.APIError as error:
                if error.code not in TRANSIENT:
                    raise
                last_error = error
            except Exception as error:  # network errors
                last_error = error
            time.sleep(5 * 2 ** attempt)
        raise last_error

    def _text_once(self, model: str, prompt: str, system: str, search: bool, temperature: float) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
            tools=[types.Tool(google_search=types.GoogleSearch())] if search else None,
        )
        return self._call(model, prompt, config).text or ""

    def text(self, prompt: str, system: str = "", search: bool = False, temperature: float = 0.7) -> str:
        last_error = None
        for model in list(self.text_models):
            if search and self.web_search:
                try:
                    return self._text_once(model, prompt, system, True, temperature)
                except errors.APIError as error:
                    if error.code != 429:
                        last_error = error
                        continue
                    self.web_search = False
                    self.log("Internetdan qidirish limitga tushdi, qidiruvsiz davom etiladi")
            try:
                return self._text_once(model, prompt, system, False, temperature)
            except errors.APIError as error:
                last_error = error
                if error.code in UNUSABLE or error.code in TRANSIENT:
                    self.log(f"{model} ishlamadi ({error.code}), keyingi model sinab ko'riladi")
                    self.text_models.remove(model)
                    continue
                raise
        raise last_error or RuntimeError("Matn modeli yo'q")

    def json(self, prompt: str, system: str = "", search: bool = False, temperature: float = 0.7):
        """JSON from the model. Grounded search can't be combined with a response
        schema, so the prompt asks for JSON and we parse it out of the text."""
        last_error = None
        for _ in range(3):
            raw = self.text(prompt, system=system, search=search, temperature=temperature)
            try:
                return extract_json(raw)
            except ValueError as error:
                last_error = error
        raise last_error

    def image(self, prompt: str) -> bytes:
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=self.aspect_ratio),
        )
        for _ in range(3):
            response = self._call(self.image_model, prompt, config)
            for candidate in response.candidates or []:
                for part in (candidate.content.parts if candidate.content else []) or []:
                    if part.inline_data and part.inline_data.data:
                        return part.inline_data.data
        raise RuntimeError("Gemini rasm qaytarmadi")
