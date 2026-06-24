"""Shared builders for link_checker tests. No network."""

from authority_finder.fetching.models import PageContent, PageLink


def page(
    *,
    final_url: str = "https://county.gov/behavioral-health",
    links: tuple[tuple[str, str], ...] = (),
    has_web_form: bool = False,
) -> PageContent:
    return PageContent(
        final_url=final_url,
        title="",
        h1s=[],
        meta_description="",
        text_sample="",
        links=[PageLink(text=t, href=h) for t, h in links],
        has_mailto=False,
        has_tel=False,
        mailto_links=[],
        tel_links=[],
        has_web_form=has_web_form,
    )
