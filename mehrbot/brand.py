"""Mehr Medical Center branding on every post: logo, gold/brown colours, the doctor's photo."""

import io
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw

from .agents.card import _font

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "assets" / "logo.png"
WIDTH, HEIGHT = 1080, 1350

GOLD = (190, 155, 95)
GOLD_LIGHT = (236, 214, 160)
BROWN = (122, 92, 66)
DARK = (40, 28, 20)
CREAM = (245, 236, 220)


def fit(image: bytes) -> Image.Image:
    """The picture filling 1080x1350 exactly, cropped in the middle."""
    img = Image.open(io.BytesIO(image)).convert("RGB")
    scale = max(WIDTH / img.width, HEIGHT / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - WIDTH) // 2, (img.height - HEIGHT) // 2
    return img.crop((left, top, left + WIDTH, top + HEIGHT))


def _circle(photo: Path, size: int, ring: int) -> Image.Image:
    face = Image.open(photo).convert("RGB").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size + 2 * ring, size + 2 * ring), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, out.width - 1, out.height - 1), fill=GOLD + (255,))
    out.paste(face, (ring, ring), mask)
    return out


def overlay(title: str, doctor: dict | None, phone: str, show_title: bool = True) -> Image.Image:
    """Transparent 1080x1350 layer: logo top-left; at the bottom a dark band with the title,
    and the doctor's round photo, specialty and name, and the phone number."""
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA").resize((170, 170), Image.LANCZOS)
        layer.alpha_composite(logo, (40, 40))

    doctor = doctor or {}
    photo = ROOT / doctor["photo"] if doctor.get("photo") else None
    has_photo = bool(photo and photo.exists())
    lines = textwrap.wrap(title.upper(), width=20)[:4] if show_title else []

    panel = 250  # doctor row height
    band = panel + 40 + len(lines) * 78 + (40 if lines else 0) + 110
    for i in range(band):
        alpha = int(235 * min(1, i / 110))
        draw.line([(0, HEIGHT - band + i), (WIDTH, HEIGHT - band + i)], fill=DARK + (alpha,))

    y = HEIGHT - panel - 40 - len(lines) * 78 - (40 if lines else 0)
    title_font = _font(62, bold=True)
    for line in lines:
        draw.text((60, y), line, font=title_font, fill=(255, 255, 255))
        y += 78
    if lines:
        draw.line([(60, y + 8), (200, y + 8)], fill=GOLD_LIGHT, width=6)
        y += 40

    x = 60
    if has_photo:
        face = _circle(photo, 190, 7)
        layer.alpha_composite(face, (x, y + 10))
        x += face.width + 36
    text_y = y + 40
    if doctor.get("name"):
        draw.text((x, text_y), doctor.get("specialty", ""), font=_font(36), fill=GOLD_LIGHT)
        draw.text((x, text_y + 50), doctor["name"], font=_font(46, bold=True), fill=(255, 255, 255))
        text_y += 115
    if phone:
        draw.text((x, text_y), "Yozilish: " + phone, font=_font(36, bold=True), fill=CREAM)
    return layer


def still(image: bytes, title: str, doctor: dict | None, phone: str, show_title: bool = True) -> bytes:
    """The post picture with the branding drawn on it."""
    base = fit(image).convert("RGBA")
    base.alpha_composite(overlay(title, doctor, phone, show_title))
    out = io.BytesIO()
    base.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
