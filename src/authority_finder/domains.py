"""Shared domain lists: competitor link-check targets and federal exclusions.

Package-level on purpose — the page detector excludes these from outreach
candidates now, and Phase 2's competitor link checker (component 6) consumes
:data:`COMPETITOR_DOMAINS` as its link-target list later.

All matching is by registrable domain (tldextract), so ``nimh.nih.gov`` and
``pmc.ncbi.nlm.nih.gov`` both match the ``nih.gov`` entry.
"""

from authority_finder.discovery.classify import registrable_domain

# The exact 16 domains from the client's brief (docs/brief.md). These are
# "does the site link to any of these?" targets — never outreach prospects.
COMPETITOR_DOMAINS: frozenset[str] = frozenset(
    {
        "samhsa.gov",
        "rehabnet.com",
        "recovery.com",
        "rehabs.com",
        "drugrehabus.org",
        "addictions.com",
        "naatp.org",
        "findtreatment.gov",
        "addictioncenter.com",
        "startyourrecovery.org",
        "addictionresource.net",
        "addictionresource.com",
        "betteraddictioncare.com",
        "rehabs.org",
        "drugabuse.com",
        "treatmentatlas.org",
    }
)

# Curated federal exclusions (ADR-006): national agencies serve no specific
# geo, so they are never per-geo outreach targets. Seeded from every federal
# domain observed in the Session 4 live run, then rounded out with the
# agencies most likely to rank for health/justice queries. samhsa.gov and
# findtreatment.gov are federal too but live in COMPETITOR_DOMAINS above.
FEDERAL_DOMAINS: frozenset[str] = frozenset(
    {
        # observed polluting Session 4 results
        "cdc.gov",
        "cms.gov",
        "ed.gov",
        "fda.gov",
        "hhs.gov",
        "house.gov",
        "justice.gov",
        "medicaid.gov",
        "medicare.gov",
        "nih.gov",
        "ojp.gov",
        "uscourts.gov",
        "ussc.gov",
        "va.gov",
        # geo-less national publishing / data / legislative portals (S19: govinfo.gov and
        # data.gov leaked in as per-geo authorities; the rest are the same class)
        "congress.gov",
        "data.gov",
        "federalregister.gov",
        "govinfo.gov",
        "gpo.gov",
        "regulations.gov",
        # S47 hand-audit of the delivered 2,291 rows: each of these shipped as a LOCAL
        # prospect for a named geo. A federal body has no geo and will never link locally.
        "macpac.gov",  # served to Hawaii and to Massachusetts
        "vaoig.gov",  # VA Inspector General, served to Pennsylvania
        "archives.gov",  # trumpwhitehouse.archives.gov, served to South Carolina
        "ntis.gov",  # a 1983 technical report, served to Brea, California
        "usbr.gov",  # Bureau of Reclamation, served to Port Hueneme, California
        # S48 pre-send review: still shipping as local prospects.
        "nrd.gov",  # DoD National Resource Directory, published across SIX geos
        "cbp.gov",
        "epa.gov",
        "noaa.gov",
        # likely to rank for health / treatment / justice queries
        "acf.gov",
        "ahrq.gov",
        "bop.gov",
        "cancer.gov",
        "childwelfare.gov",
        "dea.gov",
        "disasterassistance.gov",
        "fbi.gov",
        "fema.gov",
        "grants.gov",
        "healthcare.gov",
        "healthfinder.gov",
        "hrsa.gov",
        "hud.gov",
        "ihs.gov",
        "irs.gov",  # national agency leaking as a per-geo authority (QA audit, ADR-025)
        "mentalhealth.gov",
        "nimh.gov",
        "senate.gov",
        "ssa.gov",
        "stopbullying.gov",
        "usa.gov",
        "usda.gov",
        "whitehouse.gov",
        "womenshealth.gov",
        "youth.gov",
    }
)


def is_competitor(url: str) -> bool:
    """True when the URL's registrable domain is one of the 16 competitor domains."""
    return registrable_domain(url) in COMPETITOR_DOMAINS


def is_federal(url: str) -> bool:
    """True when the URL's registrable domain is a curated federal domain."""
    return registrable_domain(url) in FEDERAL_DOMAINS
