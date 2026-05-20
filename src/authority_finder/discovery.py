"""Per-geo search-engine discovery.

Given a geo (city, county, state), issues targeted SerpAPI queries to surface
candidate ``.gov`` and ``.edu`` sites (and any additional authority domains in
Phase 2). Returns raw candidate domains for downstream filtering and page
detection — does not crawl pages itself.
"""
