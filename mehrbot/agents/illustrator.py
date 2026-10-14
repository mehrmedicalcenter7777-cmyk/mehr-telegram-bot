"""3-agent: generates the post image with Gemini "Nano Banana".

If the API key has no image quota, a branded title card is drawn instead.
"""

from . import card

STYLE = (
    "Clean, modern, friendly medical illustration for a clinic's social media post. "
    "Soft natural light, calm palette with white, teal and warm accents, high detail, "
    "realistic but approachable. Absolutely no text, letters, numbers, logos or watermarks "
    "in the image. No gore, no needles close-up, nothing frightening."
)


def make_image(llm, post: dict, settings: dict, doctors: list, log=print) -> bytes:
    if settings.get("image_mode", "ai") == "ai":
        try:
            return llm.image(f"{post.get('image_prompt') or post.get('title')}\n\nStyle: {STYLE}")
        except Exception as error:
            log(f"AI rasm chizilmadi ({str(error)[:80]}), klinika kartasi ishlatiladi")
    doctor = next((d for d in doctors if d.get("name") == post.get("doctor")), {})
    return card.make_card(
        title=post.get("title", ""), specialty=doctor.get("specialty", ""),
        doctor=doctor.get("name", ""), clinic=settings["clinic_name"],
        phone=settings.get("clinic_phone", ""),
    )
