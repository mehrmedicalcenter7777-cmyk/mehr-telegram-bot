"""Text helpers: JSON extraction, Telegram HTML checks."""

import html
import json
import re

CAPTION_LIMIT = 1024
ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
                "a", "code", "pre", "blockquote", "tg-spoiler", "span"}
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
TRIPLED = re.compile(r"\w*([a-zA-Z])\1\1\w*", re.IGNORECASE)
TAG = re.compile(r"<\s*(/?)\s*([a-zA-Z0-9-]+)[^>]*>")


def extract_json(text: str):
    """Returns the first JSON object or array found in a model response."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    pairs = sorted((("{", "}"), ("[", "]")), key=lambda p: (text.find(p[0]) == -1, text.find(p[0])))
    for opener, closer in pairs:
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Javobda JSON topilmadi: {text[:200]!r}")


def visible_text(post_html: str) -> str:
    """Text as Telegram counts it: tags removed, entities decoded."""
    return html.unescape(TAG.sub("", post_html))


def html_problems(post_html: str) -> list[str]:
    """Unsupported or unbalanced tags that would make Telegram reject the message."""
    problems = []
    stack = []
    for closing, name in TAG.findall(post_html):
        name = name.lower()
        if name not in ALLOWED_TAGS:
            problems.append(f"Telegram qo'llamaydigan teg: <{name}>")
            continue
        if not closing:
            stack.append(name)
        elif stack and stack[-1] == name:
            stack.pop()
        else:
            problems.append(f"Yopilmagan yoki noto'g'ri yopilgan teg: </{name}>")
    problems += [f"Yopilmagan teg: <{name}>" for name in stack]
    stray = re.sub(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);", "", TAG.sub("", post_html))
    if "<" in stray or ">" in stray:
        problems.append("Matnda escape qilinmagan < yoki > belgisi bor")
    return problems


def mechanical_problems(post_html: str, limit: int = CAPTION_LIMIT) -> list[str]:
    """Checks that don't need a model: length, script, markup."""
    problems = html_problems(post_html)
    length = len(visible_text(post_html))
    if length > limit:
        problems.append(f"Post juda uzun: {length} belgi (chegara {limit})")
    if CYRILLIC.search(visible_text(post_html)):
        problems.append("Postda kirill harflari bor, faqat lotin yozuvi bo'lishi kerak")
    tripled = [m.group(0) for m in TRIPLED.finditer(visible_text(post_html))]
    if tripled:
        problems.append(f"Bir harf ketma-ket 3 marta yozilgan (imlo xatosi): {', '.join(tripled)}")
    if "#" in visible_text(post_html):
        problems.append("Xeshteg ishlatilmasligi kerak")
    return problems
