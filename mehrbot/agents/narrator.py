"""4-agent: reads the advice aloud with ElevenLabs."""

import time

import requests

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def make_audio(api_key: str, voice_id: str, text: str, model_id: str, output_format: str) -> bytes:
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(
                API.format(voice_id=voice_id),
                params={"output_format": output_format},
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json={"text": text, "model_id": model_id, "language_code": "uz"},
                timeout=180,
            )
            if response.status_code == 400 and "language" in response.text.lower():
                # Some models reject language_code; retry without it.
                response = requests.post(
                    API.format(voice_id=voice_id),
                    params={"output_format": output_format},
                    headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                    json={"text": text, "model_id": model_id},
                    timeout=180,
                )
            if response.ok:
                return response.content
            last_error = RuntimeError(f"ElevenLabs xatosi {response.status_code}: {response.text[:300]}")
            if response.status_code < 500 and response.status_code != 429:
                break
        except requests.RequestException as error:
            last_error = error
        time.sleep(5 * 2 ** attempt)
    raise last_error
