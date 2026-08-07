"""A silently-truncated link list is an invisible recall ceiling (ADR-039).

``parse_html`` keeps at most :data:`MAX_LINKS` anchors. That cap is fine — it bounds memory on
a pathological page — but until now nothing recorded that it had FIRED, so a page whose 501st
link was the directory link looked identical to a page with no directory link at all. The flag
makes the ceiling reportable instead of silent.
"""

from authority_finder.fetching.fetcher import MAX_LINKS, parse_html


def _html(anchor_count: int) -> bytes:
    anchors = "".join(f'<a href="https://ex{i}.com/">L{i}</a>' for i in range(anchor_count))
    return f"<html><head><title>T</title></head><body>{anchors}</body></html>".encode()


def test_an_ordinary_page_is_not_flagged() -> None:
    content = parse_html(_html(10), final_url="https://county.gov/bh")
    assert len(content.links) == 10
    assert content.links_truncated is False


def test_a_page_at_the_cap_exactly_is_not_flagged() -> None:
    content = parse_html(_html(MAX_LINKS), final_url="https://county.gov/bh")
    assert len(content.links) == MAX_LINKS
    assert content.links_truncated is False


def test_a_page_over_the_cap_is_flagged() -> None:
    content = parse_html(_html(MAX_LINKS + 1), final_url="https://county.gov/bh")
    assert len(content.links) == MAX_LINKS
    assert content.links_truncated is True


def test_mailto_and_tel_do_not_count_toward_the_cap() -> None:
    """They are pulled into their own lists, so they must not consume link budget."""
    extras = '<a href="mailto:x@county.gov">M</a><a href="tel:+15551234">T</a>'
    html = f"<html><body>{extras}{_html(5).decode()}</body></html>".encode()
    content = parse_html(html, final_url="https://county.gov/bh")
    assert len(content.links) == 5
    assert content.links_truncated is False
