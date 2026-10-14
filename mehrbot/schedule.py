"""Works out which posting slot a run belongs to."""

from datetime import datetime, timedelta, time as dtime

# A run may start this long before its slot (GitHub schedules start early-ish)...
MAX_EARLY = timedelta(hours=2)
# ...or this long after it (GitHub schedules are sometimes delayed).
MAX_LATE = timedelta(hours=1)


def parse_time(value: str) -> dtime:
    hours, minutes = value.split(":")
    return dtime(int(hours), int(minutes))


def pick_slot(now: datetime, post_times: list[str]) -> datetime | None:
    """The slot this run should publish for, or None if no slot is near."""
    candidates = []
    for day in (now.date() - timedelta(days=1), now.date(), now.date() + timedelta(days=1)):
        for value in post_times:
            slot = datetime.combine(day, parse_time(value), tzinfo=now.tzinfo)
            if -MAX_LATE <= slot - now <= MAX_EARLY:
                candidates.append(slot)
    upcoming = [s for s in candidates if s >= now]
    if upcoming:
        return min(upcoming)
    return max(candidates) if candidates else None


def plan(now: datetime, slot: datetime, preview_minutes: int, min_review_minutes: int = 5):
    """Returns (preview_at, publish_at). A late run still gives the admin a short window."""
    preview_at = max(now, slot - timedelta(minutes=preview_minutes))
    publish_at = max(slot, preview_at + timedelta(minutes=min_review_minutes))
    return preview_at, publish_at
