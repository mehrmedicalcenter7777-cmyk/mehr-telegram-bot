"""1-agent: finds fresh topics for the rubric on the web."""

SYSTEM = (
    "Siz tibbiy kontent muharririsiz. Internetdan (Google Search) ishonchli manbalar "
    "asosida Telegram kanal uchun dolzarb va foydali tibbiy mavzular topasiz."
)


def find_topics(llm, settings: dict, doctors: list, past_titles: list[str], today: str, count: int = 5) -> list[dict]:
    specialties = sorted({d.get("specialty", "") for d in doctors if d.get("specialty")})
    specialty_line = (
        f"Mavzular imkon qadar quyidagi mutaxassisliklarga mos bo'lsin: {', '.join(specialties)}."
        if specialties else ""
    )
    past = "\n".join(f"- {t}" for t in past_titles[-60:]) or "- (hali yo'q)"
    prompt = f"""Bugun: {today}. Rubrika:
{settings['rubric']}

{specialty_line}
Mavsumga, yaqin kunlardagi sog'liq kunlariga (JSST kalendari) va O'zbekistondagi dolzarb
muammolarga e'tibor bering. Quyidagi mavzular avval yoritilgan, ularni takrorlamang:
{past}

{count} ta turli mavzu taklif qiling. Faqat JSON massiv qaytaring:
[{{"topic": "mavzu (o'zbekcha, lotin)", "angle": "qaysi jihatdan yoritiladi",
   "specialty": "qaysi mutaxassis bilan bog'liq", "why_now": "nega aynan hozir",
   "sources": ["manba URL yoki nomi"]}}]"""
    topics = llm.json(prompt, system=SYSTEM, search=True, temperature=0.9)
    return [t for t in topics if isinstance(t, dict) and t.get("topic")]
