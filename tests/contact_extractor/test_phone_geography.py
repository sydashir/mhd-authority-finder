"""Phone area-code → state geography (ADR-024, bucket B)."""

from authority_finder.contact_extractor.models import PhoneHit
from authority_finder.contact_extractor.phone_geography import (
    drop_wrong_geo_phones,
    phone_contradicts_geo,
    phone_state,
)


def _hit(number: str, source: str = "body_text") -> PhoneHit:
    return PhoneHit(number=number, raw=number, source=source, context="")  # type: ignore[arg-type]


def test_phone_state_from_bare_state_name() -> None:
    # 559 = Fresno CA; the geocoder returns "California"
    assert phone_state("+15592452529") == "california"


def test_phone_state_from_city_state_form() -> None:
    # 205 = Birmingham; the geocoder returns "Birmingham, AL"
    assert phone_state("+12053237777") == "alabama"


def test_phone_state_multiword_state() -> None:
    # 212 = New York, NY → the two-word slug new-york
    assert phone_state("+12127363100") == "new-york"


def test_toll_free_has_no_state() -> None:
    assert phone_state("+18666828446") is None


def test_unparseable_has_no_state() -> None:
    assert phone_state("not-a-number") is None


def test_contradiction_detected() -> None:
    # akleg.gov's real defect: a 559 (California) number under the Alaska geo
    assert phone_contradicts_geo("+15592452529", "alaska") is True


def test_in_state_phone_is_not_a_contradiction() -> None:
    # 907 is Alaska's area code
    assert phone_contradicts_geo("+19074655000", "alaska") is False


def test_toll_free_is_never_a_contradiction() -> None:
    assert phone_contradicts_geo("+18666828446", "alaska") is False


def test_drop_wrong_geo_phones_keeps_in_state_and_toll_free() -> None:
    phones = [
        _hit("+15592452529"),  # CA — contradicts alaska → dropped
        _hit("+19074655000"),  # AK — kept
        _hit("+18006543210"),  # toll-free — kept (neutral)
    ]
    kept = [p.number for p in drop_wrong_geo_phones(phones, "alaska")]
    assert kept == ["+19074655000", "+18006543210"]


def test_drop_all_when_only_out_of_state() -> None:
    phones = [_hit("+15592452529")]  # CA only, under alaska
    assert drop_wrong_geo_phones(phones, "alaska") == []
