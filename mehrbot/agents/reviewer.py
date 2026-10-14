"""5-agent: quality control before anything reaches the channel."""

import json

from ..textutil import mechanical_problems

SYSTEM = (
    "Siz klinikaning tibbiy sifat nazoratchisisiz. Postni bemor xavfsizligi, tibbiy "
    "aniqlik, uslub va til nuqtai nazaridan qat'iy tekshirasiz."
)


def review(llm, settings: dict, style: str, doctors: list, post: dict) -> list[str]:
    """Returns a list of problems; an empty list means the post is approved."""
    problems = mechanical_problems(post.get("post_html", ""))
    if not post.get("audio_script"):
        problems.append("Audio matni yo'q")

    names = {d.get("name") for d in doctors}
    if post.get("doctor") and post["doctor"] not in names:
        problems.append(f"Shifokor '{post['doctor']}' klinika ro'yxatida yo'q")

    prompt = f"""Uslub qo'llanmasi:
{style}

Klinika shifokorlari: {json.dumps(doctors, ensure_ascii=False)}

Post (Telegram HTML):
{post.get('post_html')}

Audio matni:
{post.get('audio_script')}

Tekshiring:
1. Tibbiy faktlar to'g'rimi, xavfli yoki noto'g'ri maslahat yo'qmi (dori dozasi, o'z-o'zini davolash)?
2. O'zbek tili grammatikasi va imlosi to'g'rimi, faqat lotin yozuvimi?
3. Uslub qo'llanmasidagi tuzilishga mosmi (sarlavha, 🔹 qatorlar, shifokor, ogohlantirish, imzo)?
4. Tavsiya qilingan mutaxassis mavzuga mosmi?
5. Audio matni postga mos va ovozda o'qishga qulaymi?

Faqat JSON qaytaring: {{"approved": true/false, "issues": ["har bir muammo aniq va qisqa"]}}
Kichik did masalalari uchun rad etmang; faqat haqiqiy xato bo'lsa approved=false."""
    verdict = llm.json(prompt, system=SYSTEM, temperature=0.1)
    if not verdict.get("approved", False):
        problems += [str(i) for i in verdict.get("issues") or ["Sifat nazoratidan o'tmadi"]]
    return problems
