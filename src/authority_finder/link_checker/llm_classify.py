"""Per-DOMAIN link classification via Claude, cached in Postgres forever (ADR-040).

Three design choices carry all the weight here.

**Per domain, never per page.** A domain's identity does not change between the pages that
link it, so `drugrehab.com` is classified once and the answer is reused for every page that
ever links it. Classifying per page would have cost 6x on the delivered corpus alone and could
return different answers for the same domain — the inconsistency being worse than the cost.

**"unknown" is a first-class answer.** The prompt says so explicitly and the schema allows it.
Forcing every domain into a bucket is how a crisis line ends up filed as an addiction
directory. On a corpus where the great majority of domains are ordinary government and
university pages, a classifier that cannot say "none of these" is worse than no classifier.

**One validation call before any batch.** Session 4's lesson: a run that discovers its
credential is wrong AFTER committing to a batch wastes both the money and the wall-clock. A
single cheap call proves the key works, and only then does the batch go out.

The Batch API is used because this is inherently offline work — half price, and the latency
does not matter for something cached forever.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import structlog
from anthropic import AsyncAnthropic
from anthropic.types.messages.batch_create_params import Request

MODEL = "claude-sonnet-5"
# Enough for ~40 compact verdicts. The first attempt used 400 and every response came back
# stop_reason=max_tokens with a SINGLE thinking block and no text at all — extended thinking is
# on by default and consumed the entire budget before the answer began. Hence both this number
# and THINKING below; the pair is what makes the batch produce anything.
MAX_TOKENS = 2500
# Classification against a fixed rubric does not need extended thinking, and paying for it
# once produced 108,000 tokens of reasoning and zero answers.
THINKING: dict[str, str] = {"type": "disabled"}

# Sonnet 5 list price per million tokens, halved for the Batch API.
_INPUT_PER_MTOK = 3.0 / 2
_OUTPUT_PER_MTOK = 15.0 / 2

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """\
You classify website domains for a backlink-prospecting tool serving mental-health and \
addiction-recovery directories.

Assign each domain to exactly one bucket:

- "addiction_directory": a site whose PURPOSE is helping people find addiction/substance-use \
treatment — rehab directories, treatment locators, recovery resource hubs.
- "mental_health_directory": a site whose PURPOSE is helping people find a therapist, \
counsellor or mental-health provider.
- "support_group": a peer recovery fellowship or mutual-aid organisation, national or local \
(Alcoholics Anonymous, SMART Recovery, a county AA intergroup, a regional Al-Anon office).
- "unknown": ANYTHING else, and anything you are not sure about.

"unknown" is the correct and expected answer for the large majority of domains. Government \
agencies, universities, hospitals, news sites, social media, vendors, general health \
information sites and crisis hotlines are all "unknown" — a crisis line is not a directory \
and not a support group.

Judge the ORGANISATION behind the domain, not whether the topic sounds related. A county \
health department that lists rehabs is still a government agency, not a directory.

Set confidence to how certain you are of the ORGANISATION's identity: 0.9+ only when you \
recognise the domain specifically, 0.5-0.8 when inferring from the name, below 0.5 when \
guessing. If you are guessing, prefer "unknown".

Respond with ONLY a JSON array, one object per domain, in the same order as the input:
[{"domain": "...", "bucket": "...", "confidence": 0.0, "reasoning": "one short sentence"}]

Omit "reasoning" entirely when the bucket is "unknown" — that is most domains, \
and the reason is never read. Keep every reasoning under 12 words. \
Output nothing but the array."""


@dataclass(frozen=True)
class DomainVerdict:
    domain: str
    bucket: str
    confidence: float
    reasoning: str


class LlmUnavailableError(RuntimeError):
    """The key is absent or rejected — the caller must not proceed to a batch."""


def estimate_cost(domain_count: int, *, per_request: int) -> float:
    """Rough projected USD for classifying ``domain_count`` domains.

    Deliberately an over-estimate: it assumes every request emits its full output budget.
    A projection that runs under is a projection that blows a cap.
    """
    requests = -(-domain_count // per_request)
    system_tokens = len(SYSTEM_PROMPT) // 4
    input_tokens = requests * (system_tokens + per_request * 12)
    # Per DOMAIN, not per request: assuming every request emits its full max_tokens made the
    # projection scale with headroom rather than with work, which would abort a run that
    # actually costs a third of the cap. 45 tokens/domain is generous for a compact verdict.
    output_tokens = domain_count * 45 + requests * 20
    return (input_tokens / 1e6) * _INPUT_PER_MTOK + (output_tokens / 1e6) * _OUTPUT_PER_MTOK


def actual_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1e6) * _INPUT_PER_MTOK + (output_tokens / 1e6) * _OUTPUT_PER_MTOK


def parse_verdicts(text: str, *, expected: list[str]) -> list[DomainVerdict]:
    """Parse the model's JSON array, keeping only domains we actually asked about.

    Tolerates prose around the array and a stray trailing comma, because a malformed wrapper
    is not a reason to throw away 40 good answers. Anything unparseable yields nothing rather
    than a guess.
    """
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        raw: Any = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []

    wanted = set(expected)
    seen: set[str] = set()
    out: list[DomainVerdict] = []
    for item in raw:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain", "")).strip().lower()  # pyright: ignore[reportUnknownArgumentType]
        if domain not in wanted or domain in seen:
            continue
        bucket = str(item.get("bucket", "unknown")).strip()  # pyright: ignore[reportUnknownArgumentType]
        if bucket not in {
            "addiction_directory",
            "mental_health_directory",
            "support_group",
            "unknown",
        }:
            bucket = "unknown"
        try:
            confidence = float(item.get("confidence", 0.0))  # pyright: ignore[reportUnknownArgumentType]
        except (TypeError, ValueError):
            confidence = 0.0
        seen.add(domain)
        out.append(
            DomainVerdict(
                domain=domain,
                bucket=bucket,
                confidence=max(0.0, min(1.0, confidence)),
                reasoning=str(item.get("reasoning", ""))[:300],  # pyright: ignore[reportUnknownArgumentType]
            )
        )
    return out


async def validate_key(client: AsyncAnthropic) -> DomainVerdict:
    """One real call before any batch, on a domain whose answer we already know.

    Proves the credential works AND that the prompt produces parseable output. Session 4 spent
    a run discovering its key was empty only after committing to the work; this is that lesson
    made mechanical.
    """
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            thinking=THINKING,  # pyright: ignore[reportArgumentType]
            messages=[{"role": "user", "content": "aa.org"}],
        )
    except Exception as exc:
        raise LlmUnavailableError(f"validation call failed: {type(exc).__name__}: {exc}") from exc

    text = "".join(block.text for block in response.content if block.type == "text")
    if not text:
        # The exact failure that wasted a batch: only a thinking block came back.
        blocks = [block.type for block in response.content]
        raise LlmUnavailableError(
            f"validation call returned no text blocks (got {blocks}, "
            f"stop_reason={response.stop_reason}) — check MAX_TOKENS and THINKING"
        )
    verdicts = parse_verdicts(text, expected=["aa.org"])
    if not verdicts:
        raise LlmUnavailableError(f"validation call returned unparseable output: {text[:200]!r}")
    verdict = verdicts[0]
    if verdict.bucket != "support_group":
        raise LlmUnavailableError(
            f"validation sanity check failed: aa.org classified as {verdict.bucket!r}"
        )
    _log.info("llm.validated", model=MODEL, confidence=verdict.confidence)
    return verdict


DOMAINS_PER_REQUEST = 40


async def classify_domains_batch(
    client: AsyncAnthropic, domains: list[str]
) -> tuple[list[DomainVerdict], float]:
    """Classify ``domains`` through the Batch API, returning verdicts and the ACTUAL cost.

    Polls until the batch ends. Half price and higher rate limits, at the cost of latency
    that does not matter for an answer cached forever.
    """
    chunks = [
        domains[i : i + DOMAINS_PER_REQUEST] for i in range(0, len(domains), DOMAINS_PER_REQUEST)
    ]
    batch = await client.messages.batches.create(
        requests=[
            Request(
                custom_id=f"chunk-{i}",
                params={
                    "model": MODEL,
                    "max_tokens": MAX_TOKENS,
                    "system": SYSTEM_PROMPT,
                    "thinking": THINKING,
                    "messages": [{"role": "user", "content": "\n".join(chunk)}],
                },
            )
            for i, chunk in enumerate(chunks)
        ]
    )
    _log.info("llm.batch_submitted", batch_id=batch.id, requests=len(chunks))

    while True:
        status = await client.messages.batches.retrieve(batch.id)
        if status.processing_status == "ended":
            break
        await asyncio.sleep(20)

    by_id = {f"chunk-{i}": chunk for i, chunk in enumerate(chunks)}
    verdicts: list[DomainVerdict] = []
    in_tokens = out_tokens = 0
    async for result in await client.messages.batches.results(batch.id):
        if result.result.type != "succeeded":
            continue
        message = result.result.message
        in_tokens += message.usage.input_tokens
        out_tokens += message.usage.output_tokens
        text = "".join(block.text for block in message.content if block.type == "text")
        verdicts.extend(parse_verdicts(text, expected=by_id.get(result.custom_id, [])))

    spent = actual_cost(in_tokens, out_tokens)
    _log.info(
        "llm.batch_done",
        verdicts=len(verdicts),
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        cost_usd=round(spent, 4),
    )
    return verdicts, spent
