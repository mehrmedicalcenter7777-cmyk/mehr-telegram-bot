"""2-agent: researches the advice and writes the post in the clinic's style."""

import json

SYSTEM = (
    "Siz Mehr Medical Center Telegram kanalining tajribali tibbiy kopirayterisiz. "
    "Faktlarni ishonchli manbalardan (JSST, CDC, NHS, Mayo Clinic, O'zbekiston SSV) "
    "tekshirib, sodda o'zbek tilida (faqat lotin yozuvi) yozasiz."
)


def _doctor_block(settings: dict, doctors: list) -> str:
    if not doctors:
        phone = settings.get("clinic_phone") or "[klinika telefoni]"
        return (f"Klinika shifokorlari ro'yxati hali berilmagan. Shifokor qatori o'rniga: "
                f"\"🏥 {settings['clinic_name']} mutaxassislari sizga yordam beradi\" va "
                f"\"📞 Yozilish: {phone}\" yozing.")
    return ("Klinika shifokorlari (mavzuga eng mosini tanlang, ro'yxatda yo'q shifokorni "
            "o'ylab topmang):\n" + json.dumps(doctors, ensure_ascii=False, indent=1))


def write_post(llm, settings: dict, style: str, doctors: list, topic: dict, feedback: str = "") -> dict:
    fix = f"\n\nOldingi variant sifat nazoratidan o'tmadi. Tuzating:\n{feedback}" if feedback else ""
    prompt = f"""Mavzu: {json.dumps(topic, ensure_ascii=False)}

Uslub qo'llanmasi:
{style}

{_doctor_block(settings, doctors)}
Klinika telefoni: {settings.get('clinic_phone') or '(berilmagan)'}
Kanal imzosi: {settings['channel_name']}

Avval internetdan mavzu bo'yicha aniq faktlar va amaliy maslahatni toping, keyin postni yozing.{fix}

Faqat JSON obyekt qaytaring:
{{"title": "sarlavha (oddiy matn)",
  "post_html": "Telegram HTML formatidagi to'liq post (faqat <b>, <i>, <u>, <a> teglari; yangi qator uchun \\n)",
  "audio_script": "post mazmunini ovozda aytish uchun 60-90 so'zli matn: emoji, teg, qavs va qisqartmalarsiz, raqamlar so'z bilan, oxirida klinikaga taklif",
  "image_prompt": "rasm uchun ingliz tilidagi batafsil tavsif (mavzu, sahna, kayfiyat)",
  "doctor": "tanlangan shifokor ismi yoki bo'sh",
  "sources": ["foydalanilgan manbalar"]}}"""
    post = llm.json(prompt, system=SYSTEM, search=True, temperature=0.7)
    post["post_html"] = post.get("post_html", "").replace("\\n", "\n").strip()
    return post
