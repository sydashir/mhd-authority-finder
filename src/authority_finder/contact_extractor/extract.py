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

# Department-meaningful local-parts get a confidence bump; role accounts a penalty.
_DEPT_LOCALPARTS = frozenset(
    {
        "health",
        "info",
        "contact",
        "behavioralhealth",
        "mentalhealth",
        "publichealth",
        "dph",
        "hhs",
        "dhs",
        "dhcs",
        "recovery",
        "counseling",
        "clerk",
        "reception",
        "help",
        "intake",
        "referrals",
        "wellness",
        "bhrs",
        "mhsa",
        "services",
    }
)
_ROLE_NOISE_LOCALPARTS = frozenset(
    {
        "webmaster",
        "postmaster",
        "noreply",
        "no-reply",
        "donotreply",
        "do-not-reply",
        "mailer-daemon",
        "hostmaster",
        "abuse",
        "root",
        "support@sentry",
        "privacy",
    }
)

_SOURCE_BASE: dict[EmailSource, float] = {"mailto": 0.9, "contact_page": 0.7, "body_text": 0.5}
_EMAIL_SOURCE_PRIORITY: dict[EmailSource, int] = {"mailto": 0, "contact_page": 1, "body_text": 2}
_MAX_EMAIL_LEN = 254

# Labels that precede record/ID numbers — phone-shaped but never a phone (ADR-007).
_PHONE_JUNK_LABEL = re.compile(
    r"\b(order|invoice|confirmation|conf|case|account|acct|tracking|track|permit|"
    r"reference|ref|barcode|loan|member|receipt|transaction|txn|ssn|ein)\b",
    re.IGNORECASE,
)
_PHONE_LABEL_WINDOW = 20

_TEMPLATE_TOKEN = re.compile(r"\{\{.*?\}\}|\$\{[^}]*\}")
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
        or local in _PLACEHOLDER_LOCAL
        or placeholder_domain
    )


def _email_confidence(address: str, source: EmailSource) -> float:
    base = _SOURCE_BASE[source]
    local = address.split("@", 1)[0].lower()
    head = re.split(r"[._+-]", local, maxsplit=1)[0]
    if local in _ROLE_NOISE_LOCALPARTS or head in _ROLE_NOISE_LOCALPARTS:
        base -= 0.4
    elif local in _DEPT_LOCALPARTS or head in _DEPT_LOCALPARTS:
        base += 0.1
    return round(max(0.0, min(1.0, base)), 2)


def extract_emails(content: PageContent, *, contact_page: bool = False) -> list[EmailHit]:
    """Extract guarded emails from one page. Source is ``contact_page`` when fetched as one."""
    hits: list[EmailHit] = []
    seen: set[str] = set()

    def add(address: str, source: EmailSource, context: str) -> None:
        address = address.strip().rstrip(".").lower()
        if not address or address in seen or _is_junk_email(address):
            return
        seen.add(address)
        hits.append(
            EmailHit(
                address=address,
                source=source,
                context=context,
                confidence=_email_confidence(address, source),
            )
        )

    mailto_source: EmailSource = "contact_page" if contact_page else "mailto"
    for addr in content.mailto_links:
        add(addr, mailto_source, "mailto: link")

    body_source: EmailSource = "contact_page" if contact_page else "body_text"
    text = deobfuscate(_TEMPLATE_TOKEN.sub(" ", content.text_sample))
    for match in _EMAIL_RE.finditer(text):
        start = max(0, match.start() - _CONTEXT_PAD)
        context = text[start : match.end() + _CONTEXT_PAD].strip()
        add(match.group(1), body_source, context)

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
        start = max(0, match.start - _CONTEXT_PAD)
        context = text[start : match.start + len(match.raw_string) + _CONTEXT_PAD].strip()
        add(e164, match.raw_string, body_source, context)

    return hits


def _email_rank_key(hit: EmailHit) -> tuple[float, int, str]:
    """Best-first: confidence desc, then source trust (mailto > contact_page > body_text)."""
    return (-hit.confidence, _EMAIL_SOURCE_PRIORITY[hit.source], hit.address)


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
