"""Phone extraction: tel/body, formats, E.164, and id-number false-positive guards."""

import pytest

from authority_finder.contact_extractor.extract import extract_phones, rank_phones
from tests.contact_extractor.conftest import page


def numbers(content_kwargs: dict[str, object]) -> list[str | None]:
    hits = rank_phones(extract_phones(page(**content_kwargs)))  # type: ignore[arg-type]
    return [h.number for h in hits]


def test_tel_link_normalized_to_e164() -> None:
    hits = extract_phones(page(tel=["+1 (714) 555-1234"]))
    assert hits[0].number == "+17145551234"
    assert hits[0].source == "tel"


def test_invalid_tel_link_dropped() -> None:
    assert extract_phones(page(tel=["tel-garbage", "123"])) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Call (916) 654-1954 today.", "+19166541954"),
        ("Reach us at 916-875-5881.", "+19168755881"),
        ("Phone: 916.555.1234", "+19165551234"),
        ("Dial 916 555 1234 now.", "+19165551234"),
        ("Toll free 1-800-273-8255.", "+18002738255"),
        ("Fax: 916-555-7000", "+19165557000"),
    ],
)
def test_real_phone_formats_extracted(text: str, expected: str) -> None:
    assert expected in numbers({"text": text})


@pytest.mark.parametrize(
    "text",
    [
        "Order #2026471890 confirmed.",
        "Invoice 8473920164 paid.",
        "Barcode 12026471890 scanned.",
        "Account 6505551212 open.",
        "Member 916-555-0199 record.",
        "Ref 916-555-0142 ticket.",
        "(202)5551234 listing.",
    ],
)
def test_id_number_false_positives_rejected(text: str) -> None:
    assert numbers({"text": text}) == []


def test_real_phone_kept_when_id_number_nearby() -> None:
    text = "Call our office at (916) 654-1954. Confirmation number is 7193384402."
    assert numbers({"text": text}) == ["+19166541954"]


def test_tel_links_rank_above_body() -> None:
    content = page(text="Call (916) 654-1954.", tel=["+1 415-993-0187"])
    ranked = rank_phones(extract_phones(content))
    assert ranked[0].source == "tel"
    assert ranked[0].number == "+14159930187"


def test_raw_string_preserved() -> None:
    hits = extract_phones(page(text="Reach us at (916) 654-1954 today."))
    assert hits[0].raw == "(916) 654-1954"
    assert hits[0].number == "+19166541954"
