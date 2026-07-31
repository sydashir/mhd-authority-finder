"""Cron schedule parsing: days, time, timezone.

The scheduler moved from "every N hours" to named days (default Mon+Wed at 03:00). The
timezone is deliberate, not incidental — see parse_schedule's docstring.
"""

import pytest

from authority_finder.scheduler.schedule import ScheduleSpec, parse_schedule


class TestDays:
    def test_the_default_is_monday_and_wednesday(self) -> None:
        assert parse_schedule("mon,wed", "03:00").day_of_week == "mon,wed"

    def test_whitespace_and_case_are_tolerated(self) -> None:
        assert parse_schedule(" MON , Wed ", "03:00").day_of_week == "mon,wed"

    def test_a_single_day_works(self) -> None:
        assert parse_schedule("fri", "03:00").day_of_week == "fri"

    def test_all_seven_days(self) -> None:
        spec = parse_schedule("mon,tue,wed,thu,fri,sat,sun", "03:00")
        assert spec.day_of_week.count(",") == 6

    def test_duplicates_collapse_but_order_is_kept(self) -> None:
        assert parse_schedule("wed,mon,wed", "03:00").day_of_week == "wed,mon"

    def test_an_unknown_day_is_rejected_loudly(self) -> None:
        """A typo must not silently produce a scheduler that never fires."""
        with pytest.raises(ValueError, match="monday"):
            parse_schedule("monday,wed", "03:00")

    def test_empty_days_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            parse_schedule("", "03:00")


class TestTime:
    def test_hour_and_minute_are_split(self) -> None:
        spec = parse_schedule("mon", "03:30")
        assert (spec.hour, spec.minute) == (3, 30)

    def test_midnight(self) -> None:
        assert (parse_schedule("mon", "00:00").hour, parse_schedule("mon", "00:00").minute) == (
            0,
            0,
        )

    def test_late_hour(self) -> None:
        assert parse_schedule("mon", "23:59").hour == 23

    @pytest.mark.parametrize("bad", ["3pm", "24:00", "03:60", "0300", "", "03:00:00"])
    def test_malformed_time_is_rejected(self, bad: str) -> None:
        with pytest.raises(ValueError):
            parse_schedule("mon", bad)


class TestTimezone:
    def test_defaults_to_us_eastern_not_utc(self) -> None:
        """The client is US-based; a 03:00 run must land before THEIR business day."""
        assert parse_schedule("mon", "03:00").timezone == "America/New_York"

    def test_an_explicit_timezone_is_honoured(self) -> None:
        assert parse_schedule("mon", "03:00", "America/Chicago").timezone == "America/Chicago"

    def test_an_unknown_timezone_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone"):
            parse_schedule("mon", "03:00", "Mars/Olympus_Mons")

    def test_the_spec_is_usable_as_cron_kwargs(self) -> None:
        spec = parse_schedule("mon,wed", "03:00")
        assert isinstance(spec, ScheduleSpec)
        assert spec.as_cron_kwargs() == {
            "day_of_week": "mon,wed",
            "hour": 3,
            "minute": 0,
            "timezone": "America/New_York",
        }
