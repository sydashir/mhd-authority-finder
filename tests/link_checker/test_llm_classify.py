"""Parsing and costing for the per-domain classifier (ADR-040). No network.

The parser is the safety boundary between a language model's output and a database that
feeds a client deliverable, so it is tested for the ways models actually misbehave: prose
wrapped around the JSON, hallucinated domains nobody asked about, invented bucket names,
duplicates, and confidence values outside [0,1].
"""

from authority_finder.link_checker.llm_classify import (
    MAX_TOKENS,
    SYSTEM_PROMPT,
    THINKING,
    actual_cost,
    estimate_cost,
    parse_verdicts,
)


class TestParsing:
    def test_a_clean_array_parses(self) -> None:
        text = '[{"domain":"aa.org","bucket":"support_group","confidence":0.99,"reasoning":"AA"}]'
        [verdict] = parse_verdicts(text, expected=["aa.org"])
        assert verdict.bucket == "support_group"
        assert verdict.confidence == 0.99
        assert verdict.reasoning == "AA"

    def test_prose_around_the_array_is_tolerated(self) -> None:
        text = 'Sure!\n[{"domain":"aa.org","bucket":"support_group","confidence":1}]\nDone.'
        assert len(parse_verdicts(text, expected=["aa.org"])) == 1

    def test_a_hallucinated_domain_is_dropped(self) -> None:
        """The model must not be able to introduce a domain we never observed."""
        text = (
            '[{"domain":"aa.org","bucket":"support_group","confidence":1},'
            '{"domain":"evil.com","bucket":"support_group","confidence":1}]'
        )
        assert [v.domain for v in parse_verdicts(text, expected=["aa.org"])] == ["aa.org"]

    def test_an_invented_bucket_falls_back_to_unknown(self) -> None:
        text = '[{"domain":"x.org","bucket":"rehab_directory_probably","confidence":0.9}]'
        [verdict] = parse_verdicts(text, expected=["x.org"])
        assert verdict.bucket == "unknown"

    def test_duplicates_keep_only_the_first(self) -> None:
        text = (
            '[{"domain":"x.org","bucket":"support_group","confidence":0.9},'
            '{"domain":"x.org","bucket":"unknown","confidence":0.1}]'
        )
        [verdict] = parse_verdicts(text, expected=["x.org"])
        assert verdict.bucket == "support_group"

    def test_out_of_range_confidence_is_clamped(self) -> None:
        text = (
            '[{"domain":"a.org","bucket":"unknown","confidence":7},'
            '{"domain":"b.org","bucket":"unknown","confidence":-3}]'
        )
        got = {v.domain: v.confidence for v in parse_verdicts(text, expected=["a.org", "b.org"])}
        assert got == {"a.org": 1.0, "b.org": 0.0}

    def test_a_non_numeric_confidence_becomes_zero(self) -> None:
        """Zero keeps it below the promotion bar, so a malformed answer stays invisible."""
        text = '[{"domain":"x.org","bucket":"support_group","confidence":"very"}]'
        assert parse_verdicts(text, expected=["x.org"])[0].confidence == 0.0

    def test_case_and_whitespace_in_the_domain_are_normalised(self) -> None:
        text = '[{"domain":"  AA.ORG ","bucket":"support_group","confidence":1}]'
        assert parse_verdicts(text, expected=["aa.org"])[0].domain == "aa.org"

    def test_garbage_yields_nothing_rather_than_a_guess(self) -> None:
        for text in ("", "I cannot help with that.", "[", "[{]", "{}"):
            assert parse_verdicts(text, expected=["x.org"]) == []

    def test_unknown_survives_as_a_real_answer(self) -> None:
        """The classifier must be able to decline; unknown is not an error."""
        text = '[{"domain":"weather.gov","bucket":"unknown","confidence":0.95}]'
        assert parse_verdicts(text, expected=["weather.gov"])[0].bucket == "unknown"


class TestCosting:
    def test_the_projection_scales_with_domain_count(self) -> None:
        assert estimate_cost(10_000, per_request=40) > estimate_cost(1_000, per_request=40)

    def test_the_projection_is_in_a_sane_range_for_the_real_corpus(self) -> None:
        """10,825 domains must land in single-digit dollars or the cap is meaningless."""
        assert 0.05 < estimate_cost(10_825, per_request=40) < 5.0

    def test_the_projection_tracks_work_not_headroom(self) -> None:
        """It must scale with domains, not with max_tokens.

        The first version assumed every request emitted its full output budget. Raising
        max_tokens to fix a truncation bug then inflated the projection past the cap and would
        have aborted a run that actually costs a third of it — a projection tied to headroom
        rather than work blocks the very fix it was meant to allow.
        """
        doubled_domains = estimate_cost(20_000, per_request=40)
        same_domains_bigger_chunks = estimate_cost(10_000, per_request=80)
        assert doubled_domains > estimate_cost(10_000, per_request=40)
        # Fewer, larger requests cost slightly LESS (less repeated system prompt), never more.
        assert same_domains_bigger_chunks < estimate_cost(10_000, per_request=40)

    def test_the_projection_still_over_estimates_a_realistic_response(self) -> None:
        """45 tokens/domain is generous for a compact verdict, so we bill under projection."""
        realistic_output = 10_825 * 30
        assert estimate_cost(10_825, per_request=40) > actual_cost(250_000, realistic_output) * 0.9


class TestTheTruncationBugIsPinned:
    """A batch of 270 requests returned 108,000 tokens of thinking and ZERO answers.

    Extended thinking is on by default for this model, and max_tokens=400 was consumed
    entirely by the thinking block before any text was emitted — every response came back
    stop_reason=max_tokens with a single `thinking` block. It cost $1.17 for nothing.
    """

    def test_thinking_is_disabled(self) -> None:
        assert THINKING["type"] == "disabled"

    def test_max_tokens_covers_a_full_chunk_of_verdicts(self) -> None:
        """40 compact verdicts need roughly 1,400 tokens; 400 could never have fitted."""
        assert MAX_TOKENS >= 40 * 35

    def test_the_prompt_suppresses_reasoning_for_unknown(self) -> None:
        """Most domains are unknown, and their reason is never read — it is pure output cost."""
        assert "Omit" in SYSTEM_PROMPT and "unknown" in SYSTEM_PROMPT

    def test_batch_pricing_is_half_of_list(self) -> None:
        # 1M input tokens at Sonnet 5 list ($3) → $1.50 on the Batch API.
        assert abs(actual_cost(1_000_000, 0) - 1.5) < 1e-9
        assert abs(actual_cost(0, 1_000_000) - 7.5) < 1e-9
