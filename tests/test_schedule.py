from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from mehrbot.schedule import pick_slot, plan

TZ = ZoneInfo("Asia/Tashkent")
TIMES = ["08:00", "12:00"]


def at(h, m, day=14):
    return datetime(2026, 10, day, h, m, tzinfo=TZ)


def test_early_run_picks_next_slot():
    assert pick_slot(at(7, 35), TIMES) == at(8, 0)
    assert pick_slot(at(11, 35), TIMES) == at(12, 0)


def test_delayed_run_still_picks_missed_slot():
    assert pick_slot(at(8, 20), TIMES) == at(8, 0)


def test_no_slot_far_away():
    assert pick_slot(at(16, 0), TIMES) is None


def test_after_midnight_wraps_to_next_day():
    assert pick_slot(datetime(2026, 10, 14, 23, 0, tzinfo=TZ), ["00:30"]) == at(0, 30, day=15)


def test_plan_on_time():
    preview, publish = plan(at(7, 40), at(8, 0), 10)
    assert preview == at(7, 50) and publish == at(8, 0)


def test_plan_late_run_keeps_review_window():
    preview, publish = plan(at(7, 58), at(8, 0), 10)
    assert preview == at(7, 58) and publish == at(8, 3)
    preview, publish = plan(at(8, 20), at(8, 0), 10)
    assert publish - preview == timedelta(minutes=5)
