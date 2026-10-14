"""Branded title card used when AI image generation isn't available."""

import io
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1350
TOP, BOTTOM = (10, 122, 128), (6, 66, 92)
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


def make_card(title: str, specialty: str, doctor: str, clinic: str, phone: str) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        t = y / HEIGHT
        draw.line([(0, y), (WIDTH, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)))

    # soft decorative circles
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-260, -260, 420, 420), fill=(255, 255, 255, 22))
    od.ellipse((700, 980, 1400, 1680), fill=(255, 255, 255, 18))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)

    y = _centered(draw, 110, clinic.upper(), _font(40, bold=True), (255, 255, 255)) + 20
    draw.line([(WIDTH / 2 - 60, y + 10), (WIDTH / 2 + 60, y + 10)], fill=(255, 196, 120), width=5)

    title_font = _font(78, bold=True)
    lines = textwrap.wrap(title.upper(), width=16)[:5]
    y = 520 - len(lines) * 50
    for line in lines:
        y = _centered(draw, y, line, title_font, (255, 255, 255)) + 24

    panel_top = 1010
    draw.rounded_rectangle((90, panel_top, WIDTH - 90, panel_top + 220), radius=36, fill=(255, 255, 255))
    y = panel_top + 34
    if doctor:
        y = _centered(draw, y, specialty, _font(36), (10, 122, 128)) + 18
        y = _centered(draw, y, doctor, _font(46, bold=True), (20, 40, 50)) + 22
    else:
        y = _centered(draw, y + 30, "Mutaxassislarimiz yordam beradi", _font(40, bold=True), (20, 40, 50)) + 40
    if phone:
        _centered(draw, y, phone, _font(38, bold=True), (6, 66, 92))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
