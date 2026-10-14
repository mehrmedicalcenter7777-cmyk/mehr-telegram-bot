"""Thin wrapper around the Gemini API (text, web-grounded text, JSON, images)."""

import time

from google import genai
from google.genai import types

from .textutil import extract_json


class Gemini:
    def __init__(self, api_key: str, text_model: str, image_model: str, aspect_ratio: str = "1:1"):
        self.client = genai.Client(api_key=api_key)
        self.text_model = text_model
        self.image_model = image_model
        self.aspect_ratio = aspect_ratio

    def _call(self, **kwargs):
        last_error = None
        for attempt in range(4):
            try:
                return self.client.models.generate_content(**kwargs)
            except Exception as error:  # network errors, 429, 5xx
                last_error = error
                time.sleep(5 * 2 ** attempt)
        raise last_error

    def text(self, prompt: str, system: str = "", search: bool = False, temperature: float = 0.7) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
            tools=[types.Tool(google_search=types.GoogleSearch())] if search else None,
        )
        response = self._call(model=self.text_model, contents=prompt, config=config)
        return response.text or ""

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
            response = self._call(model=self.image_model, contents=prompt, config=config)
            for candidate in response.candidates or []:
                for part in (candidate.content.parts if candidate.content else []) or []:
                    if part.inline_data and part.inline_data.data:
                        return part.inline_data.data
        raise RuntimeError("Gemini rasm qaytarmadi")
