"""Parse the scheduler's day/time/timezone configuration into cron fields.

The scheduler used to fire every N hours, which drifts: a 24h interval started at 14:00 keeps
running at 14:00, and a restart moves it permanently. Named days at a fixed local time are
what an operator actually means by "Mondays and Wednesdays at 3am".

**Timezone is a deliberate choice, not a default we inherited.** The schedule is interpreted
in the CLIENT's timezone (US Eastern), not the server's UTC. The run exists to have fresh
prospects waiting at the start of their business day; under UTC a 03:00 job would land at
22:00 or 23:00 the previous evening depending on the season, and would shift twice a year as
US daylight saving changes while UTC does not. Pinning to an IANA zone makes 03:00 mean 03:00
to the people using the output, in summer and winter alike.

Parsing is separated from APScheduler so the rules are testable without a scheduler running.
"""

from typing import Any, NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VALID_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DEFAULT_TIMEZONE = "America/New_York"
_MAX_HOUR = 23
_MAX_MINUTE = 59


class ScheduleSpec(NamedTuple):
    day_of_week: str
    hour: int
    minute: int
    timezone: str

    def as_cron_kwargs(self) -> dict[str, Any]:
        """Keyword arguments for APScheduler's ``CronTrigger``."""
        return {
            "day_of_week": self.day_of_week,
            "hour": self.hour,
            "minute": self.minute,
            "timezone": self.timezone,
        }

    def describe(self) -> str:
        return f"{self.day_of_week} at {self.hour:02d}:{self.minute:02d} {self.timezone}"


def _parse_days(raw: str) -> str:
    days = [d.strip().lower() for d in raw.split(",") if d.strip()]
    if not days:
        raise ValueError("RUN_DAYS is empty — the scheduler would never fire")
    for day in days:
        if day not in VALID_DAYS:
            # Loud, because a typo would otherwise produce a scheduler that silently never runs.
            raise ValueError(f"RUN_DAYS has an unknown day {day!r}; use one of {VALID_DAYS}")
    return ",".join(dict.fromkeys(days))


def _parse_time(raw: str) -> tuple[int, int]:
    parts = raw.strip().split(":")
    expected = 2
    if len(parts) != expected or not all(p.isdigit() for p in parts):
        raise ValueError(f"RUN_TIME must be HH:MM 24-hour, got {raw!r}")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= _MAX_HOUR and 0 <= minute <= _MAX_MINUTE):
        raise ValueError(f"RUN_TIME out of range: {raw!r}")
    return hour, minute


def parse_schedule(days: str, time_of_day: str, timezone: str = DEFAULT_TIMEZONE) -> ScheduleSpec:
    """Validate and normalise the schedule. Raises ``ValueError`` on anything unusable."""
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"RUN_TIMEZONE is not a known IANA timezone: {timezone!r}") from exc
    hour, minute = _parse_time(time_of_day)
    return ScheduleSpec(day_of_week=_parse_days(days), hour=hour, minute=minute, timezone=timezone)
