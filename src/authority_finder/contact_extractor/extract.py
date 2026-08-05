"""Email and phone extraction. Pure functions over :class:`PageContent`.

Precision over recall — a wrong contact burns sender reputation, so every
path is guarded:

- Emails: ``mailto:`` links are trusted highest; body text is matched with a
  bounded regex and a false-positive guard list (asset filenames, placeholders,
  coordinate strings, oversized junk). Common obfuscation (``name [at] domain
  [dot] gov``) is decoded first.
- Phones: ``tel:`` links and Google's ``phonenumbers`` ``PhoneNumberMatcher``
  at ``Leniency.VALID``, each match re-checked with ``is_valid_number()`` so
  ZIP+4, dates, and random digit runs are dropped, then normalized to E.164.

Ranking exposes the full list (outreach may want alternates) but marks a single
best by confidence, then source, then address.
"""

import re
from typing import Literal
from urllib.parse import unquote

import phonenumbers
import tldextract
from phonenumbers import Leniency, PhoneNumberFormat

from authority_finder.contact_extractor.models import (
    EmailHit,
    EmailSource,
    PhoneHit,
    PhoneSource,
)
from authority_finder.fetching.models import PageContent

# National crisis/help lines are never an organisation's OWN contact — a rep working the sheet
# must not be handed the 988 Lifeline or the SAMHSA helpline as the prospect's phone (ADR-025).
_NATIONAL_HOTLINES = frozenset(
    {
        "+18002738255",  # 988 Suicide & Crisis Lifeline (legacy 1-800-273-TALK)
        "+18006624357",  # SAMHSA National Helpline (1-800-662-HELP)
        "+18007997233",  # National Domestic Violence Hotline
        # S48: all seven below were live in the delivered sheet as an organisation's own
        # phone. The list was tuned on 589 rows; at 2,269 the tail had grown.
        "+18006564673",  # RAINN National Sexual Assault Hotline (shipped at HIGH trust)
        "+18009506264",  # NAMI HelpLine
        "+18664887386",  # Trevor Project
        "+18009855990",  # SAMHSA Disaster Distress Helpline
        "+18002221222",  # Poison Control
        "+18004874889",  # SAMHSA TTY
        "+18007873224",  # National Domestic Violence Hotline TTY
    }
)


def is_national_hotline(phone: str) -> bool:
    """True when this number is a national crisis line, never an organisation's own contact."""
    return phone in _NATIONAL_HOTLINES


# Offline PSL extractor (matches discovery.classify config) — rejects emails whose
# "domain" has no real public suffix (handler@bind.call, x@secret.key, a@host.local).
_tld = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

_EMAIL_RE = re.compile(
    r"(?<![\w.+-])"
    r"([A-Za-z0-9][A-Za-z0-9._%+-]*"
    r"@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,24})"
    # Allow a trailing '.' (sentence end) — rstrip handles it, greedy grabs real multi-label TLDs.
    r"(?![\w-])",
    re.ASCII,
)

# "TLDs" that mean asset filename, not email (logo@2x.png, sprite@2x.svg).
_ASSET_EXTS = frozenset(
    {
        "png",
        "jpg",
        "jpeg",
        "gif",
        "svg",
        "webp",
        "ico",
        "bmp",
        "tiff",
        "css",
        "js",
        "mjs",
        "json",
        "map",
        "woff",
        "woff2",
        "ttf",
        "eot",
        "mp4",
        "webm",
        "mp3",
        "pdf",
        "zip",
        "xml",
        # ccTLDs that double as source-file extensions (handler@x.ts, readme@docs.md);
        # the rest (.tsx/.vue/.py/.scss/...) are non-suffixes the PSL guard rejects anyway.
        "ts",
        "py",
        "sh",
        "rs",
        "md",
    }
)
_PLACEHOLDER_LOCAL = frozenset(
    {
        "x",
        "you",
        "your",
        "name",
        "user",
        "username",
        "email",
        "someone",
        "firstname",
        "lastname",
        "first",
        "last",
        "test",
        "foo",
        "bar",
        "example",
        "sample",
        "yourname",
        "domain",
    }
)
_PLACEHOLDER_DOMAIN = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "domain.com",
        "email.com",
        "yourdomain.com",
        "sentry.io",
        "wixpress.com",
        "schema.org",
        "w3.org",
        "sentry.wixpress.com",
    }
)

_SOURCE_BASE: dict[EmailSource, float] = {"mailto": 0.9, "contact_page": 0.7, "body_text": 0.5}
_EMAIL_SOURCE_PRIORITY: dict[EmailSource, int] = {"mailto": 0, "contact_page": 1, "body_text": 2}
_MAX_EMAIL_LEN = 254

# Department relevance for MH/BH/SUD/wellness/counseling/human-services outreach
# (evidence-derived — docs/contact-quality-audit.md §3). Used to decide when a
# detected page already carries a usable department contact (so the directory hop
# can be skipped) and to rank a real department inbox ahead of generic/role inboxes.
_DEPT_EXACT = frozenset(
    {
        "health",
        "behavioralhealth",
        "mentalhealth",
        "publichealth",
        "humanservices",
        "bha",
        "bhrs",
        "dph",
        "dhs",
        "dhcs",
        "hhs",
        "mhsa",
    }
)
_DEPT_STEMS = (
    "counsel",
    "behavioral",
    "mentalhealth",
    "recovery",
    "wellness",
    "wellbeing",
    "humanserv",
    "humansvc",
    "humansvs",
    "crisis",
    "substance",
    "psych",
    "peersupport",
    "intake",
    "referral",
    "studenthealth",
    "healthservices",
)
# Checked first: 'environmentalhealth' contains 'mentalhealth'; 'developmental' contains 'mental'.
_DEPT_EXCLUDE = ("environmental", "developmental", "governmental")

# Wrong-department / role-noise local-parts → never the outreach contact, even as a
# same-domain mailto (admissions@/communications@/webmaster@ on a counseling page).
# Department matching takes precedence, so a real dept inbox is never misread as role.
_ROLE_STEMS = (
    "admission",
    "webmaster",
    "webmarketing",
    "webteam",
    "communications",
    "newsmedia",
    "media",
    "press",
    "marketing",
    "publicinformation",
    "helpdesk",
    "servicedesk",
    "postmaster",
    "mailerdaemon",
    "hostmaster",
    "noreply",
    "donotreply",
    "registrar",
    "financialaid",
    "finaid",
    "alumni",
    "advancement",
    "housing",
    "mayor",
    "citymanager",
    "cityclerk",
    "cityattorney",
    "prosecutor",
    "auditor",
    "facultycouncil",
    "titleix",
    "mdmanual",
    "smteam",
)
_ROLE_EXACT = frozenset({"pio", "pioac", "consumer", "abuse", "root", "privacy"})
_DISTRICT_RE = re.compile(r"^district\d+")
# Real inboxes that aren't department-specific: usable, but never high-trust.
_GENERIC_LOCALPARTS = frozenset({"info", "contact", "contactus", "reception", "hello", "feedback"})

ContactCategory = Literal["dept", "role", "generic", "other"]


def _norm_localpart(address: str) -> str:
    return re.sub(r"[._+-]", "", address.split("@", 1)[0].lower())


def classify_localpart(address: str) -> ContactCategory:
    """Categorise an email local-part for ranking + trust banding (audit §3).

    Department relevance is decided before role-noise, so a real department inbox is
    never misread as role; ``environmental``/``developmental`` heads are excluded from
    the mental-health stems first.
    """
    head = _norm_localpart(address)
    if any(x in head for x in _DEPT_EXCLUDE):
        return "other"
    if head in _DEPT_EXACT or any(stem in head for stem in _DEPT_STEMS):
        return "dept"
    if _DISTRICT_RE.match(head) or head in _ROLE_EXACT or any(r in head for r in _ROLE_STEMS):
        return "role"
    if head in _GENERIC_LOCALPARTS:
        return "generic"
    return "other"


def is_dept_localpart(address: str) -> bool:
    """True if the email local-part names a mental/behavioral-health-relevant department."""
    return classify_localpart(address) == "dept"


# Labels that precede record/ID numbers — phone-shaped but never a phone (ADR-007).
_PHONE_JUNK_LABEL = re.compile(
    r"\b(order|invoice|confirmation|conf|case|account|acct|tracking|track|permit|"
    r"reference|ref|barcode|loan|member|receipt|transaction|txn|ssn|ein)\b",
    re.IGNORECASE,
)
_PHONE_LABEL_WINDOW = 20

_TEMPLATE_TOKEN = re.compile(r"\{\{.*?\}\}|\$\{[^}]*\}")
# A 5+ digit run in the local part means a ZIP/phone ran into the address with no
# separator (live: "80204303-315-2228spa.admissions@ucdenver.edu") — a garbled hit.
_LOCAL_DIGIT_RUN = re.compile(r"\d{5,}")
# A separated phone (303.458.3558 / 724-8859) glued to the address by missing whitespace
# in the source — the digit-run guard misses it because separators break the run (Session 9).
_LOCAL_PHONE_GLUE = re.compile(r"\d{3}[.\-]\d{3,4}")
# lxml text-glue artifacts the runs above miss: a phone tail of exactly 4 digits glued to a
# word (S19 live: "5000EmailEmailcarecoordination@"), or a doubled UI label run into the
# address. Both mean a text_content() concatenation, never a real inbox.
_LOCAL_GLUE_ARTIFACT = re.compile(r"^\d{4,}[a-z]|(?:email|phone|fax){2,}", re.IGNORECASE)
_BRACKET_AT = re.compile(r"\s*[\[({]\s*at\s*[\])}]\s*", re.IGNORECASE)
_BRACKET_DOT = re.compile(r"\s*[\[({]\s*dot\s*[\])}]\s*", re.IGNORECASE)
# Spelled-out form, multi-segment: "info at mail dot county dot gov" → info@mail.county.gov.
# The middle group absorbs interior " dot " segments so county .us / subdomain-mail hosts
# decode whole rather than truncating to a wrong address.
_SPELLED = re.compile(
    r"([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+(?:\s+dot\s+[A-Za-z0-9-]+)*)\s+dot\s+([A-Za-z]{2,24})",
    re.IGNORECASE,
)
_DOT_WORD = re.compile(r"\s+dot\s+", re.IGNORECASE)
_CONTEXT_PAD = 40


def _spelled_repl(match: re.Match[str]) -> str:
    middle = _DOT_WORD.sub(".", match.group(2))
    return f"{match.group(1)}@{middle}.{match.group(3)}"


def deobfuscate(text: str) -> str:
    """Decode the common spelled-out email obfuscations into real ``@``/``.``."""
    text = _BRACKET_AT.sub("@", text)
    text = _BRACKET_DOT.sub(".", text)
    return _SPELLED.sub(_spelled_repl, text)


def _is_junk_email(address: str) -> bool:
    if len(address) > _MAX_EMAIL_LEN:
        return True
    if any(ch.isspace() for ch in address):  # interior whitespace → never a deliverable address
        return True
    local, _, domain = address.partition("@")
    if not domain:
        return True
    labels = domain.split(".")
    placeholder_domain = domain in _PLACEHOLDER_DOMAIN or any(
        domain.endswith(f".{placeholder}") for placeholder in _PLACEHOLDER_DOMAIN
    )
    return (
        labels[-1] in _ASSET_EXTS
        or not _tld(f"http://{domain}").suffix  # not a real public suffix
        or any(label.isdigit() for label in labels[:-1])  # version pins: serde@1.0.gov
        or bool(_LOCAL_DIGIT_RUN.search(local))  # ZIP/phone glued into the local part
        or bool(
            _LOCAL_PHONE_GLUE.search(local)
        )  # formatted phone glued in (303.458.3558counseling@)
        or bool(_LOCAL_GLUE_ARTIFACT.search(local))  # 4-digit tail / doubled label glued in
        or local in _PLACEHOLDER_LOCAL
        or placeholder_domain
    )


def clean_email(raw: str) -> str | None:
    """Normalise a raw address to a single deliverable email, or ``None`` if unusable (ADR-025).

    Strips a leaked ``mailto:`` scheme, keeps only the FIRST recipient of a multi-recipient
    href, and URL-decodes (``%20`` → space, then trimmed) BEFORE the junk guard — so the garbled
    mailto values that reached the sheet (``mailto:vb311@…``, ``a@x;%20b@x``, ``%20info@…``) can
    no longer be emitted.
    """
    address = raw.strip().lower().removeprefix("mailto:")
    address = address.split(",", 1)[0].split(";", 1)[0]
    address = unquote(address).strip().rstrip(".")
    return None if not address or _is_junk_email(address) else address


def _email_confidence(address: str, source: EmailSource) -> float:
    base = _SOURCE_BASE[source]
    category = classify_localpart(address)
    if category == "role":
        base -= 0.4
    elif category == "dept":
        base += 0.1
    return round(max(0.0, min(1.0, base)), 2)


def _registrable_domain(value: str) -> str:
    target = value if "://" in value else f"http://{value}"
    return _tld(target).top_domain_under_public_suffix


def extract_emails(content: PageContent, *, contact_page: bool = False) -> list[EmailHit]:
    """Extract guarded emails from one page. Source is ``contact_page`` when fetched as one.

    Body-text-regex emails are kept only when same-registrable-domain as the page
    (drops third-party orgs mentioned in body text, e.g. info@frsn.org on a county
    page). ``mailto:`` and contact-page hits are intentional and kept regardless.
    """
    page_domain = _registrable_domain(content.final_url)
    hits: list[EmailHit] = []
    seen: set[str] = set()

    def add(raw: str, source: EmailSource, context: str, *, constrain: bool) -> None:
        address = clean_email(raw)
        if address is None or address in seen:
            return
        same_domain = _registrable_domain(address.split("@", 1)[-1]) == page_domain
        if constrain and not same_domain:
            return
        seen.add(address)
        hits.append(
            EmailHit(
                address=address,
                source=source,
                context=context,
                confidence=_email_confidence(address, source),
                same_domain=same_domain,
            )
        )

    mailto_source: EmailSource = "contact_page" if contact_page else "mailto"
    for addr in content.mailto_links:
        add(addr, mailto_source, "mailto: link", constrain=False)

    body_source: EmailSource = "contact_page" if contact_page else "body_text"
    text = deobfuscate(_TEMPLATE_TOKEN.sub(" ", content.text_sample))
    for match in _EMAIL_RE.finditer(text):
        start = max(0, match.start() - _CONTEXT_PAD)
        context = text[start : match.end() + _CONTEXT_PAD].strip()
        add(match.group(1), body_source, context, constrain=not contact_page)

    return hits


def extract_phones(content: PageContent, *, contact_page: bool = False) -> list[PhoneHit]:
    """Extract valid US phone numbers (E.164) from tel: links and body text."""
    hits: list[PhoneHit] = []
    seen: set[str] = set()

    def add(number: str | None, raw: str, source: PhoneSource, context: str) -> None:
        key = number or raw
        if key in seen:
            return
        seen.add(key)
        hits.append(PhoneHit(number=number, raw=raw, source=source, context=context))

    tel_source: PhoneSource = "contact_page" if contact_page else "tel"
    for raw in content.tel_links:
        try:
            parsed = phonenumbers.parse(raw, "US")
        except phonenumbers.NumberParseException:
            continue
        if not phonenumbers.is_valid_number(parsed):
            continue
        e164 = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
        if e164 in _NATIONAL_HOTLINES:
            continue
        add(e164, raw, tel_source, "tel: link")

    body_source: PhoneSource = "contact_page" if contact_page else "body_text"
    text = content.text_sample
    # EXACT_GROUPING + the guards below: an order/case/ID number is phone-shaped but
    # is an unformatted digit run and/or sits behind a record label — drop both.
    for match in phonenumbers.PhoneNumberMatcher(text, "US", leniency=Leniency.EXACT_GROUPING):
        if not phonenumbers.is_valid_number(match.number):
            continue
        if match.raw_string.isdigit():
            continue
        if _PHONE_JUNK_LABEL.search(text[max(0, match.start - _PHONE_LABEL_WINDOW) : match.start]):
            continue
        e164 = phonenumbers.format_number(match.number, PhoneNumberFormat.E164)
        if e164 in _NATIONAL_HOTLINES:
            continue
        start = max(0, match.start - _CONTEXT_PAD)
        context = text[start : match.start + len(match.raw_string) + _CONTEXT_PAD].strip()
        add(e164, match.raw_string, body_source, context)

    return hits


def _email_rank_key(hit: EmailHit) -> tuple[int, float, int, str]:
    """Best-first: same-domain department inbox, then confidence desc, then source trust."""
    dept = 0 if (hit.same_domain and is_dept_localpart(hit.address)) else 1
    return (dept, -hit.confidence, _EMAIL_SOURCE_PRIORITY[hit.source], hit.address)


def rank_emails(hits: list[EmailHit]) -> list[EmailHit]:
    """Dedupe by lowercased address (keep best) and sort best-first."""
    by_address: dict[str, EmailHit] = {}
    for hit in hits:
        key = hit.address.lower()
        existing = by_address.get(key)
        if existing is None or _email_rank_key(hit) < _email_rank_key(existing):
            by_address[key] = hit
    return sorted(by_address.values(), key=_email_rank_key)


def rank_phones(hits: list[PhoneHit]) -> list[PhoneHit]:
    """Dedupe by E.164 (or raw) and sort tel: links ahead of body-text matches."""
    _priority: dict[PhoneSource, int] = {"tel": 0, "contact_page": 1, "body_text": 2}
    by_key: dict[str, PhoneHit] = {}
    for hit in hits:
        key = hit.number or hit.raw
        existing = by_key.get(key)
        if existing is None or _priority[hit.source] < _priority[existing.source]:
            by_key[key] = hit
    return sorted(by_key.values(), key=lambda h: (_priority[h.source], h.number or h.raw))
