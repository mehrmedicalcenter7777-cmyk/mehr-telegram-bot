from mehrbot.pipeline import pick_doctor

DOCTORS = [
    {"name": "A", "specialty": "LOR"},
    {"name": "B", "specialty": "LOR"},
    {"name": "C", "specialty": "Kardiolog"},
    {"name": "D", "specialty": "Xirurg"},
]


def test_never_featured_doctor_goes_first():
    posts = [{"doctor": "A"}, {"doctor": "C"}]
    assert pick_doctor(DOCTORS, posts)["name"] == "D"


def test_rotates_through_everyone():
    posts, seen = [], []
    for _ in range(4):
        d = pick_doctor(DOCTORS, posts)["name"]
        seen.append(d)
        posts.append({"doctor": d})
    assert sorted(seen) == ["A", "B", "C", "D"]
    assert seen[0] in "AB" and seen[1] not in "AB" or seen[0] not in "AB"


def test_exclude_skips_doctor_tried_in_this_run():
    assert pick_doctor(DOCTORS, [], exclude=["A"])["name"] != "A"
