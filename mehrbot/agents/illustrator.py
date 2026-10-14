"""3-agent: generates the post image with Gemini "Nano Banana"."""

STYLE = (
    "Clean, modern, friendly medical illustration for a clinic's social media post. "
    "Soft natural light, calm palette with white, teal and warm accents, high detail, "
    "realistic but approachable. Absolutely no text, letters, numbers, logos or watermarks "
    "in the image. No gore, no needles close-up, nothing frightening."
)


def make_image(llm, post: dict) -> bytes:
    prompt = f"{post.get('image_prompt') or post.get('title')}\n\nStyle: {STYLE}"
    return llm.image(prompt)
