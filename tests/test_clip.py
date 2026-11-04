import io
import shutil
import subprocess

import pytest
from PIL import Image

from mehrbot.agents.clip import make_clip

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg yo'q")


def test_clip_is_vertical_video_with_voice(tmp_path):
    audio = tmp_path / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=2", str(audio)], check=True)
    picture = io.BytesIO()
    Image.new("RGB", (1024, 1280), (180, 200, 210)).save(picture, "PNG")
    video = make_clip(picture.getvalue(), audio.read_bytes(), "Sarlavha", "Shifokor", "Kardiolog", "Mehr", "+998")
    out = tmp_path / "v.mp4"
    out.write_bytes(video)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
                            "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout
    assert "video,1080,1350" in probe and "audio" in probe
