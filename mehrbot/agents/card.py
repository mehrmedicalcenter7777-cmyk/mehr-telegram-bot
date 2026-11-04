"""Branded title card used when AI image generation isn't available."""

import io
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

WIDTH, HEIGHT = 1080, 1350
CARD_MARK = "mehr-card"
TOP, BOTTOM = (122, 92, 66), (40, 28, 20)  # Mehr brown
FONT_DIRS = [Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/dejavu")]


def _font(size: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for folder in FONT_DIRS:
        if (folder / name).exists():
            return ImageFont.truetype(str(folder / name), size)
    return ImageFont.load_default(size=size)


def _centered(draw, y: int, text: str, font, fill) -> int:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(((WIDTH - (right - left)) / 2, y), text, font=font, fill=fill)
    return y + (bottom - top)


def make_card(title: str, specialty: str = "", doctor: str = "", clinic: str = "", phone: str = "") -> bytes:
    """Brown-gold background with the title in the middle; the logo and the doctor are added
    on top by the branding layer, like on every other post picture."""
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        t = y / HEIGHT
        draw.line([(0, y), (WIDTH, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)))

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((560, -300, 1400, 540), outline=(236, 214, 160, 70), width=6)
    od.ellipse((-300, 640, 420, 1360), outline=(236, 214, 160, 45), width=6)
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)

    title_font = _font(80, bold=True)
    lines = textwrap.wrap(title.upper(), width=16)[:5]
    y = 480 - len(lines) * 50
    for line in lines:
        y = _centered(draw, y, line, title_font, (255, 255, 255)) + 24
    draw.line([(WIDTH / 2 - 70, y + 16), (WIDTH / 2 + 70, y + 16)], fill=(236, 214, 160), width=6)

    buffer = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add_text(CARD_MARK, "1")  # the title is already drawn, the branding layer skips it
    image.save(buffer, format="PNG", optimize=True, pnginfo=info)
    return buffer.getvalue()
