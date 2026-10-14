from mehrbot.textutil import extract_json, html_problems, mechanical_problems, visible_text

GOOD = ("🫀 <b>QON BOSIMINGIZNI BILASIZMI?</b>\n\nHar 3 kattadan 1 nafarida qon bosimi yuqori.\n\n"
        "🔹 <b>Maslahat:</b> tuzni kamaytiring\n\n<b>MEHR MEDICAL</b> ❤️")


def test_extract_json_from_fenced_block():
    assert extract_json('Mana:\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('[{"topic": "x"}] tamom') == [{"topic": "x"}]


def test_good_post_passes():
    assert mechanical_problems(GOOD) == []


def test_visible_text_strips_tags_and_entities():
    assert visible_text("<b>A</b> &amp; B") == "A & B"


def test_detects_bad_markup():
    assert html_problems("<b>ochiq") != []
    assert html_problems("<h1>x</h1>") != []
    assert html_problems("bosim < 140") != []


def test_detects_cyrillic_length_and_hashtags():
    assert any("kirill" in p for p in mechanical_problems("Привет"))
    assert any("uzun" in p for p in mechanical_problems("a" * 1100))
    assert any("Xeshteg" in p for p in mechanical_problems("#salomatlik"))


def test_detects_tripled_letters():
    problems = mechanical_problems("<b>TOMOQ OG'RIG'I ODDDIY SHAMOLLASHMI?</b>")
    assert any("ODDDIY" in p for p in problems)
    assert mechanical_problems("Ishtaha va uyqu") == []
