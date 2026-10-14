"""Runs agents 1-5 and returns a post that passed quality control."""

from dataclasses import dataclass, field

from . import history
from .agents import illustrator, narrator, researcher, reviewer, writer

MAX_REWRITES = 3


@dataclass
class Post:
    topic: dict
    title: str
    html: str
    audio_script: str
    doctor: str
    sources: list
    image: bytes
    audio: bytes


@dataclass
class TopicQueue:
    """Candidate topics; asks the researcher for more when they run out."""
    llm: object
    cfg: object
    today: str
    used: list = field(default_factory=list)
    queue: list = field(default_factory=list)

    def next(self) -> dict:
        if not self.queue:
            past = [p.get("title", "") for p in history.load()] + self.used
            self.queue = researcher.find_topics(self.llm, self.cfg.settings, self.cfg.doctors, past, self.today)
            if not self.queue:
                raise RuntimeError("Mavzu topilmadi")
        topic = self.queue.pop(0)
        self.used.append(topic["topic"])
        return topic


def build(llm, cfg, topics: TopicQueue, log=print) -> Post:
    for _ in range(3):  # up to three topics
        topic = topics.next()
        log(f"[1] Mavzu: {topic['topic']}")
        feedback = ""
        for attempt in range(1, MAX_REWRITES + 1):
            draft = writer.write_post(llm, cfg.settings, cfg.style, cfg.doctors, topic, feedback)
            log(f"[2] Post yozildi ({attempt}-urinish): {draft.get('title')}")
            problems = reviewer.review(llm, cfg.settings, cfg.style, cfg.doctors, draft)
            if not problems:
                log("[5] Matn sifat nazoratidan o'tdi")
                break
            feedback = "\n".join(f"- {p}" for p in problems)
            log(f"[5] Muammolar:\n{feedback}")
        else:
            log("[5] Bu mavzu bo'yicha sifatli post chiqmadi, keyingi mavzu olinadi")
            continue

        image = illustrator.make_image(llm, draft)
        log(f"[3] Rasm tayyor ({len(image) // 1024} KB)")
        el = cfg.settings["elevenlabs"]
        audio = narrator.make_audio(
            cfg.secrets.elevenlabs_api_key, cfg.secrets.elevenlabs_voice_id,
            draft["audio_script"], el["model_id"], el["output_format"],
        )
        log(f"[4] Audio tayyor ({len(audio) // 1024} KB)")
        return Post(
            topic=topic, title=draft.get("title", ""), html=draft["post_html"],
            audio_script=draft["audio_script"], doctor=draft.get("doctor", ""),
            sources=draft.get("sources") or [], image=image, audio=audio,
        )
    raise RuntimeError("3 ta mavzu bo'yicha ham sifat nazoratidan o'tgan post tayyorlanmadi")
