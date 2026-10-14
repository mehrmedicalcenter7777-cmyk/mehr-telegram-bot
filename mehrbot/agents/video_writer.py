"""Watches a video the clinic sent and writes the post that goes under it."""

import json

from .writer import SYSTEM, _doctor_block


def write_caption(llm, settings: dict, style: str, doctors: list, video: bytes, mime: str,
                  hint: str = "", feedback: str = "") -> dict:
    fix = f"\n\nOldingi variant sifat nazoratidan o'tmadi. Tuzating:\n{feedback}" if feedback else ""
    note = f"\nAdmin videoga izoh yozgan: {hint}" if hint else ""
    prompt = f"""Bu video Mehr Medical Center Telegram kanaliga joylanadi. Videoni diqqat bilan
ko'ring va eshiting: unda kim (shifokor, bemor), nima haqida gapirilmoqda, qanday
muolaja yoki maslahat ko'rsatilmoqda.{note}

Shu video tagiga qo'yiladigan postni yozing. Post video mazmunini to'g'ri aks ettirsin,
videoda yo'q narsani o'ylab topmang. Uslub qo'llanmasi:
{style}

{_doctor_block(settings, doctors)}
Klinika telefoni: {settings.get('clinic_phone') or '(berilmagan)'}
Kanal imzosi: {settings['channel_name']}{fix}

Faqat JSON obyekt qaytaring:
{{"title": "sarlavha (oddiy matn)",
  "post_html": "Telegram HTML formatidagi to'liq post (faqat <b>, <i>, <u>, <a> teglari; yangi qator uchun \\n)",
  "doctor": "videodagi yoki mavzuga mos shifokor ismi (ro'yxatdan) yoki bo'sh",
  "video_summary": "videoda nima borligi, 1-2 gap"}}"""
    post = llm.media_json(prompt, video, mime, system=SYSTEM)
    post["post_html"] = post.get("post_html", "").replace("\\n", "\n").strip()
    post["kind"] = "video"
    return post
