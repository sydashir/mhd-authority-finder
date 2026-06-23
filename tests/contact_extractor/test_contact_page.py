"""Contact-page link discovery."""

from authority_finder.contact_extractor.contact_page import find_contact_links
from tests.contact_extractor.conftest import page


def test_finds_and_ranks_contact_links() -> None:
    # Session 9: a department/staff directory is preferred over a generic contact-us
    # (a directory is more likely to carry the actual department contact).
    content = page(
        final_url="https://county.gov/dept",
        links=[
            ("Parks", "https://county.gov/parks"),
            ("Contact Us", "https://county.gov/about/contact-us"),
            ("Staff Directory", "https://county.gov/staff/directory"),
        ],
    )
    links = find_contact_links(content, domain="county.gov")
    assert links[0] == "https://county.gov/staff/directory"
    assert "https://county.gov/about/contact-us" in links
    assert "https://county.gov/parks" not in links


def test_prefers_department_directory_over_contact_us() -> None:
    content = page(
        final_url="https://county.gov/dept",
        links=[
            ("Contact Us", "https://county.gov/contact-us"),
            ("Department Directory", "https://county.gov/department-directory"),
        ],
    )
    links = find_contact_links(content, domain="county.gov")
    assert links[0] == "https://county.gov/department-directory"


def test_prefers_dept_topic_link_over_generic_contact() -> None:
    content = page(
        final_url="https://county.gov/x",
        links=[
            ("Contact Us", "https://county.gov/contact-us"),
            ("Behavioral Health Division", "https://county.gov/behavioral-health"),
        ],
    )
    links = find_contact_links(content, domain="county.gov")
    assert links[0] == "https://county.gov/behavioral-health"


def test_excludes_other_domains() -> None:
    content = page(links=[("Contact", "https://other.org/contact")])
    assert find_contact_links(content, domain="county.gov") == []


def test_excludes_junk_contact_urls() -> None:
    content = page(links=[("Contact news", "https://county.gov/news/contact-2026")])
    assert find_contact_links(content, domain="county.gov") == []


def test_respects_limit() -> None:
    content = page(
        links=[
            ("Contact Us", "https://county.gov/contact"),
            ("Staff Directory", "https://county.gov/directory"),
            ("Get in touch", "https://county.gov/touch"),
        ],
    )
    assert len(find_contact_links(content, domain="county.gov", limit=2)) == 2
