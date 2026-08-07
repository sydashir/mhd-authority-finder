"""Bucket an outbound domain: addiction directory / mental-health directory / support group.

The client asked why a directory link was missed. The answer was structural: the tool matched a
fixed list of 16 from the brief and `drugrehab.com` was not one of them, so it could never match.
This widens the seeds and adds two more buckets — but deliberately stays a LIST, not a learner.

**Why a list and not a classifier, for now.** Measured on the delivered corpus, 91.6% of observed
domains are singletons and the recognisable entities are a small, stable set: `aa.org` has been
Alcoholics Anonymous for decades. A seed list is byte-reproducible, costs nothing, and cannot
drift between runs — properties a model cannot offer. The learner earns its place on the long
tail (ADR-039 phase 3), not here.

**Exact registrable-domain matching only.** Substring matching is not merely imprecise here, it
is actively wrong: 62 domains in the delivered corpus contain "aa" and 103 contain "na" in their
label, and `aaaphx.org` / `aaact.org` are Area Agencies on Aging — the client's own target
prospects. A substring rule would misfire on 165 real rows.

**Seeds are verified, not harvested.** Every domain below was fetched live and its identity
confirmed from page content. Two that appear on the client's own resources page are deliberately
ABSENT: `alateen.org` refuses connections outright, and `recovery-inc.org` is an unrelated UK
content site rather than Recovery International (`recoveryinternational.org`). Learning domains
from client pages would have adopted both.

**Unknown is a real answer.** Crisis lines (`988lifeline.org`), general directories (`211.org`)
and advocacy bodies (`nami.org`) are left unclassified. Whether they belong in a bucket is a
specification question for the client, not something to guess at.
"""

import enum

from authority_finder.discovery.classify import registrable_domain
from authority_finder.domains import COMPETITOR_DOMAINS


class LinkClass(enum.Enum):
    """Which bucket an outbound domain falls into, or that we do not know."""

    addiction_directory = "addiction_directory"
    mental_health_directory = "mental_health_directory"
    support_group = "support_group"
    unknown = "unknown"


# The brief's contractual 16, plus directories verified live on 2026-08-07. The 16 keep their own
# column untouched — this set is a SUPERSET used for the new Addiction Directories column.
_VERIFIED_ADDITIONS = frozenset(
    {
        "drugrehab.com",  # "Addiction, Treatment & Rehab Resources" — the client's reported miss
        "detoxrehabs.net",  # "Drug and Alcohol Detox Centers Directory"
        "rehabspot.com",  # "Find Information On Alcohol And Drug Rehab And Recovery"
        "alcoholaddictioncenter.org",  # "Alcohol Addiction Resources"
        "addictionhelp.com",  # "Helping You From Addiction to Recovery"
        "alcoholrehabguide.org",  # on the client's page; 301s to alcoholhelp.com
        "alcoholhelp.com",  # the canonical successor of alcoholrehabguide.org
    }
)

ADDICTION_DIRECTORIES: frozenset[str] = COMPETITOR_DOMAINS | _VERIFIED_ADDITIONS

# Deliberately thin. Only two could be verified live — the other candidates
# (goodtherapy.org, zencare.co, whatclinic.com) answer 403/202 to any automated client, so their
# identity was never confirmed. Thin and true beats padded and guessed.
MENTAL_HEALTH_DIRECTORIES: frozenset[str] = frozenset(
    {
        "psychologytoday.com",  # "Health, Help, Happiness + Find a Therapist"
        "therapyroute.com",  # "Find a Therapist Near You | Local Psychologists & Counsellors"
    }
)

# The 19 national fellowships whose identity was confirmed from their own page content.
# NOT here, on purpose: alateen.org (dead), recovery-inc.org (wrong org), and coda.org /
# oa.org / nicotine-anonymous.org / slaafws.org (live but bot-blocked, never confirmed).
SUPPORT_GROUPS: frozenset[str] = frozenset(
    {
        "aa.org",  # Alcoholics Anonymous
        "na.org",  # Narcotics Anonymous
        "al-anon.org",  # Al-Anon Family Groups (also hosts the live Alateen content)
        "ca.org",  # Cocaine Anonymous World Services
        "co-anon.org",  # Co-Anon Family Groups
        "crystalmeth.org",  # Crystal Meth Anonymous
        "debtorsanonymous.org",  # Debtors Anonymous
        "emotionsanonymous.org",  # Emotions Anonymous
        "gamblersanonymous.org",  # Gamblers Anonymous
        "gam-anon.org",  # Gam-Anon International Service Office
        "marijuana-anonymous.org",  # Marijuana Anonymous
        "nar-anon.org",  # Nar-Anon Family Groups
        "recovering-couples.org",  # Recovering Couples Anonymous
        "eatingdisordersanonymous.org",  # Eating Disorders Anonymous
        "sa.org",  # Sexaholics Anonymous
        "saa-recovery.org",  # Sex Addicts Anonymous
        "sca-recovery.org",  # Sexual Compulsives Anonymous
        "smartrecovery.org",  # SMART Recovery USA
        "womenforsobriety.org",  # Women for Sobriety
    }
)

_BUCKETS: tuple[tuple[frozenset[str], LinkClass], ...] = (
    (SUPPORT_GROUPS, LinkClass.support_group),
    (ADDICTION_DIRECTORIES, LinkClass.addiction_directory),
    (MENTAL_HEALTH_DIRECTORIES, LinkClass.mental_health_directory),
)


def classify_domain(domain: str) -> LinkClass:
    """Bucket one domain by EXACT registrable match, or ``unknown``.

    Accepts a bare domain or a host; normalises through the same ``registrable_domain`` the
    competitor check uses, so ``www.aa.org`` matches and ``aa.org.evil.com`` does not.
    """
    cleaned = domain.strip().lower()
    if not cleaned:
        return LinkClass.unknown
    normalised = registrable_domain(f"https://{cleaned}/") or cleaned
    for seeds, bucket in _BUCKETS:
        if normalised in seeds:
            return bucket
    return LinkClass.unknown
