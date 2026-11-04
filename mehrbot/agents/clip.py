"""Turns a post's image and voice-over into a short vertical video with the branding on top."""

import io
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from .. import brand

FPS = 25


def _duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def make_clip(image: bytes, audio: bytes, layer: Image.Image) -> bytes:
    """image slowly zooms in under the fixed branding layer while the voice-over plays."""
    width, height = brand.WIDTH, brand.HEIGHT
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        brand.fit(image).save(work / "bg.png")
        layer.save(work / "top.png")
        (work / "voice.mp3").write_bytes(audio)

        seconds = _duration(work / "voice.mp3") + 0.8
        frames = int(seconds * FPS)
        zoom = f"min(1+0.12*on/{frames},1.12)"
        graph = (
            f"[0:v]scale={width * 2}:{height * 2},"
            f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={FPS}[bg];"
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
