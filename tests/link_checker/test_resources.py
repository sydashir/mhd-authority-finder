"""Resources/links-page picker — finds the ONE internal page where directories live."""

from authority_finder.link_checker.resources import find_resources_link
from tests.link_checker.conftest import page


def test_finds_resources_link() -> None:
    content = page(
        final_url="https://county.gov/bh",
        links=(
            ("About", "https://county.gov/about"),
            ("Community Partners", "https://county.gov/community-partners"),
        ),
    )
    assert find_resources_link(content, domain="county.gov") == [
        "https://county.gov/community-partners"
    ]


def test_prefers_dedicated_resources_over_generic_links() -> None:
    content = page(
        links=(
            ("Quick Links", "https://county.gov/quick-links"),
            ("Helpful Links", "https://county.gov/helpful-links"),
        )
    )
    assert find_resources_link(content, domain="county.gov")[0] == (
        "https://county.gov/helpful-links"
    )


def test_excludes_other_domain_and_junk() -> None:
    content = page(
        links=(
            ("Resources", "https://other.org/resources"),
            ("News resources", "https://county.gov/news/resources-2026"),
        )
    )
    assert find_resources_link(content, domain="county.gov") == []


def test_empty_when_no_resources_link() -> None:
    content = page(
        links=(("Home", "https://county.gov/"), ("Contact", "https://county.gov/contact"))
    )
    assert find_resources_link(content, domain="county.gov") == []
