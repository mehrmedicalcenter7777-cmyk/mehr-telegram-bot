"""Runs agents 1-5 and returns a post that passed quality control."""

from dataclasses import dataclass, field

from . import history
from .agents import illustrator, narrator, researcher, reviewer, video_writer, writer

MAX_REWRITES = 3


@dataclass
class Post:
    topic: dict
    title: str
    html: str
    audio_script: str
    doctor: str
    sources: list
    image: bytes | None
    audio: bytes | None
    warning: str = ""
    kind: str = "photo"
    video_file_id: str = ""


@dataclass
class TopicQueue:
    """Candidate topics; asks the researcher for more when they run out."""
    llm: object
    cfg: object
    today: str
    used: list = field(default_factory=list)
    queue: list = field(default_factory=list)
    fixed: str = ""  # admin-chosen topic: every variant is about it
    doctors_tried: list = field(default_factory=list)

    def next(self) -> dict:
        if self.fixed:
            angle = "boshqa jihatdan, oldingi variantdan farqli" if self.used else ""
            self.used.append(self.fixed)
            return {"topic": self.fixed, "angle": angle}
        if not self.queue:
            posts = history.load()
            past = [p.get("title", "") for p in posts] + [p.get("topic", "") for p in posts] + self.used
            doctor = pick_doctor(self.cfg.doctors, posts, self.doctors_tried)
            if doctor:
                self.doctors_tried.append(doctor["name"])
            self.queue = researcher.find_topics(
                self.llm, self.cfg.settings, self.cfg.doctors, past, self.today, count=3, doctor=doctor)
            if doctor:
                for t in self.queue:
                    t["doctor"] = doctor["name"]
                    t["specialty"] = doctor.get("specialty", "")
            if not self.queue:
                raise RuntimeError("Mavzu topilmadi")
        topic = self.queue.pop(0)
        self.used.append(topic["topic"])
        # A rewrite of a failed topic goes to a different doctor next time.
        self.queue = []
        return topic


def pick_doctor(doctors: list, posts: list, exclude: list = ()) -> dict | None:
    """The doctor whose last post is oldest (never featured comes first), so every doctor
    gets a turn instead of the same two again and again."""
    candidates = [d for d in doctors if d.get("name") and d["name"] not in exclude] or \
        [d for d in doctors if d.get("name")]
    if not candidates:
        return None
    last = {}
    for i, p in enumerate(posts):
        if p.get("doctor"):
            last[p["doctor"]] = i
    # Two doctors of the same specialty share a turn, so the specialty rotates too.
    spec_last = {}
    for d in doctors:
        if d.get("name") in last:
            spec_last[d.get("specialty")] = max(spec_last.get(d.get("specialty"), -1), last[d["name"]])
    return min(candidates, key=lambda d: (spec_last.get(d.get("specialty"), -1), last.get(d["name"], -1)))


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

        image = illustrator.make_image(llm, draft, cfg.settings, cfg.doctors, log)
        log(f"[3] Rasm tayyor ({len(image) // 1024} KB)")
        el = cfg.settings["elevenlabs"]
        audio, warning = None, ""
        try:
            audio = narrator.make_audio(
                cfg.secrets.elevenlabs_api_key, el.get("voice_id") or cfg.secrets.elevenlabs_voice_id,
                draft["audio_script"], el["model_id"], el["output_format"],
            )
            log(f"[4] Audio tayyor ({len(audio) // 1024} KB)")
        except Exception as error:
            # A missing voice-over shouldn't stop the post; the admin is told why.
            warning = f"Audio tayyorlanmadi: {str(error)[:300]}"
            log(f"[4] {warning}")
        return Post(
            topic=topic, title=draft.get("title", ""), html=draft["post_html"],
            audio_script=draft["audio_script"], doctor=draft.get("doctor", ""),
            sources=draft.get("sources") or [], image=image, audio=audio, warning=warning,
        )
    raise RuntimeError("3 ta mavzu bo'yicha ham sifat nazoratidan o'tgan post tayyorlanmadi")


def build_video(llm, cfg, tg, item: dict, log=print) -> Post:
    """Post for a video the admin sent: the video itself plus a caption written from it."""
    data = tg.download(item["file_id"])
    log(f"[V] Video yuklab olindi ({len(data) // 1024} KB)")
    feedback = ""
    for attempt in range(1, MAX_REWRITES + 1):
        draft = video_writer.write_caption(llm, cfg.settings, cfg.style, cfg.doctors, data,
                                           item.get("mime_type", "video/mp4"), item.get("hint", ""), feedback)
        log(f"[2] Video uchun post yozildi ({attempt}-urinish): {draft.get('title')}")
        problems = reviewer.review(llm, cfg.settings, cfg.style, cfg.doctors, draft)
        if not problems:
            log("[5] Matn sifat nazoratidan o'tdi")
            break
        feedback = "\n".join(f"- {p}" for p in problems)
        log(f"[5] Muammolar:\n{feedback}")
    else:
        raise RuntimeError("Video uchun sifatli post yozilmadi:\n" + feedback)
    return Post(
        topic={"topic": "video: " + draft.get("video_summary", "")[:80]}, title=draft.get("title", ""),
        html=draft["post_html"], audio_script="", doctor=draft.get("doctor", ""), sources=[],
        image=None, audio=None, kind="video", video_file_id=item["file_id"],
    )
