"""Domains that are never an outreach prospect, however authoritative they are.

Component 3's source is unrestricted by necessity — a ``site:.gov OR site:.edu`` query can
never return a state addiction coalition. The cost of dropping that filter is that Google
also returns the whole open web, and the live Alabama/Texas run proved a Domain Rating
threshold cannot clean that up: facebook.com scored 100, instagram.com 100, linkedin.com
99, yelp.com 94, prnewswire.com 92, guidestar.org 91. **The failure mode is wrong TYPE,
not low authority**, so raising the DR floor actively makes it worse — it keeps every
social network and cuts the small local orgs we actually want.

So type-filtering runs FIRST, before any Ahrefs call. That is both a quality fix and a
cost fix: scoring facebook.com was money spent to learn nothing.

Every entry was observed in a real run or is the same class as one. Deliberately an
explicit list rather than a heuristic: ``txcouncil.com`` is the Texas Council of Community
Centers, so neither the TLD nor a "looks commercial" guess is safe.

NOT included, deliberately: for-profit treatment centres (``lahacienda.com``,
``discoverypointretreat.com``). They are arguably not prospects either, but they are
indistinguishable from legitimate nonprofits by domain alone, and the known ones are
already handled by ``COMPETITOR_DOMAINS``. Guessing here would drop real orgs.
"""

import tldextract

_SOCIAL = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "tiktok.com",
    "pinterest.com",
    "reddit.com",
    "threads.net",
    "nextdoor.com",
)

_REVIEWS_AND_LISTINGS = (
    "yelp.com",
    "tripadvisor.com",
    "yellowpages.com",
    "mapquest.com",
    "bbb.org",
    "foursquare.com",
    "manta.com",
    "chamberofcommerce.com",
)

_NEWSWIRES = (
    "prnewswire.com",
    "businesswire.com",
    "einpresswire.com",
    "globenewswire.com",
    "prweb.com",
    "issuu.com",
)

# They catalogue organizations; they are not organizations you pitch.
_DATA_AGGREGATORS = (
    "guidestar.org",
    "causeiq.com",
    "charitynavigator.org",
    "greatnonprofits.org",
    "idealist.org",
    "nonprofitlight.com",
    "taxexemptworld.com",
    "propublica.org",
    "crunchbase.com",
    "zippia.com",
    "opencorporates.com",
    "bizapedia.com",
    # Service-locator directories: they aggregate providers, they are not providers.
    "findhelp.org",
    "networkofcare.org",
    "agingcare.com",
    "caring.com",
    "seniorly.com",
    "aplaceformom.com",
)

_TRADE_PRESS = (
    "beckersbehavioralhealth.com",
    "beckershospitalreview.com",
    "modernhealthcare.com",
    "statnews.com",
    "healthcaredive.com",
)

_JOB_BOARDS = (
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "simplyhired.com",
    "monster.com",
    "careerbuilder.com",
)

# Generic hosts: whatever sits here belongs to someone else's namespace.
_GENERIC_HOSTS = (
    "wikipedia.org",
    "wikimedia.org",
    "fandom.com",
    "wordpress.com",
    "blogspot.com",
    "medium.com",
    "substack.com",
    "wixsite.com",
    "squarespace.com",
    "weebly.com",
    "godaddysites.com",
    "eventbrite.com",
    "meetup.com",
    "gofundme.com",
    "amazon.com",
    "google.com",
    "apple.com",
    "onlineclassadvisor.com",
)

PLATFORM_DOMAINS: frozenset[str] = frozenset(
    _SOCIAL
    + _REVIEWS_AND_LISTINGS
    + _NEWSWIRES
    + _DATA_AGGREGATORS
    + _TRADE_PRESS
    + _JOB_BOARDS
    + _GENERIC_HOSTS
)

_extract = tldextract.TLDExtract(suffix_list_urls=())


def registrable(domain: str) -> str:
    """``business.facebook.com`` -> ``facebook.com``; ``www.texashealth.org`` -> the same."""
    cleaned = domain.strip().lower()
    for prefix in ("https://", "http://"):
        cleaned = cleaned.removeprefix(prefix)
    cleaned = cleaned.split("/", 1)[0]
    return _extract(cleaned).top_domain_under_public_suffix.lower() or cleaned.removeprefix("www.")


def is_platform(domain: str) -> bool:
    """True when ``domain`` (or its parent) is a platform, aggregator, or generic host."""
    return registrable(domain) in PLATFORM_DOMAINS
