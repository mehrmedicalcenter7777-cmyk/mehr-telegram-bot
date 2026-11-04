"""Turns a post's image and voice-over into a short vertical video with the title on screen."""

import io
import json
import subprocess
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw

from .card import CARD_MARK, _font

WIDTH, HEIGHT, FPS = 1080, 1350, 25
TEAL = (10, 122, 128)


def _overlay(title: str, doctor: str, specialty: str, clinic: str, phone: str, badge: bool = True) -> bytes:
    """Transparent layer: clinic badge on top, dark band with the title and doctor at the bottom."""
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if not badge:
        return _png(layer)

    badge_font = _font(34, bold=True)
    left, top, right, bottom = draw.textbbox((0, 0), clinic.upper(), font=badge_font)
    draw.rounded_rectangle((48, 48, 48 + right - left + 56, 48 + bottom - top + 36), radius=30, fill=TEAL + (235,))
    draw.text((76, 62), clinic.upper(), font=badge_font, fill=(255, 255, 255))

    band = 560
    for i in range(band):
        alpha = int(225 * min(1, i / (band * 0.55)))
        draw.line([(0, HEIGHT - band + i), (WIDTH, HEIGHT - band + i)], fill=(5, 30, 40, alpha))

    title_font = _font(62, bold=True)
    lines = textwrap.wrap(title.upper(), width=20)[:4]
    small = _font(36)
    tail = [specialty + ": " + doctor if doctor else "", "Yozilish: " + phone if phone else ""]
    tail = [t for t in tail if t]
    y = HEIGHT - 70 - len(tail) * 52 - len(lines) * 78
    for line in lines:
        draw.text((60, y), line, font=title_font, fill=(255, 255, 255))
        y += 78
    draw.line([(60, y + 6), (180, y + 6)], fill=(255, 196, 120), width=6)
    y += 30
    for text in tail:
        draw.text((60, y), text, font=small, fill=(225, 240, 240))
        y += 52

    return _png(layer)


def _png(layer) -> bytes:
    out = io.BytesIO()
    layer.save(out, "PNG")
    return out.getvalue()


def _duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def make_clip(image: bytes, audio: bytes, title: str, doctor: str, specialty: str,
              clinic: str, phone: str) -> bytes:
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        img = Image.open(io.BytesIO(image))
        is_card = CARD_MARK in img.info
        img = img.convert("RGB")
        # fill 1080x1350 exactly, cropping whatever sticks out
        scale = max(WIDTH / img.width, HEIGHT / img.height)
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
        left, top = (img.width - WIDTH) // 2, (img.height - HEIGHT) // 2
        img.crop((left, top, left + WIDTH, top + HEIGHT)).save(work / "bg.png")
        # A clinic card already carries the title and doctor; only an AI picture needs the overlay.
        (work / "top.png").write_bytes(
            _overlay("", "", "", "", "", badge=False) if is_card else _overlay(title, doctor, specialty, clinic, phone))
        (work / "voice.mp3").write_bytes(audio)

        seconds = _duration(work / "voice.mp3") + 0.8
        frames = int(seconds * FPS)
        zoom = f"min(1+0.12*on/{frames},1.12)"  # slow push-in over the whole clip
        graph = (
            f"[0:v]scale={WIDTH * 2}:{HEIGHT * 2},"
            f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}[bg];"
            f"[bg][1:v]overlay=0:0,fade=t=in:st=0:d=0.4,fade=t=out:st={seconds - 0.5:.2f}:d=0.5,format=yuv420p[v]"
        )
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-i", str(work / "bg.png"), "-loop", "1", "-i", str(work / "top.png"), "-i", str(work / "voice.mp3"),
             "-filter_complex", graph, "-map", "[v]", "-map", "2:a",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k",
             "-t", f"{seconds:.2f}", "-movflags", "+faststart", str(work / "post.mp4")],
            check=True, capture_output=True, timeout=600,
        )
        return (work / "post.mp4").read_bytes()
