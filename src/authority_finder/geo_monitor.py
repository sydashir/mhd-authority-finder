"""Sitemap watcher for MHD and AH.

Polls the configured sitemap URLs, diffs them against the persisted set of
previously seen URLs, and emits a ``NewGeoPage`` event for each newly observed
city / county / state page. Source-of-truth for "what geos exist". Downstream
components do not read sitemaps themselves.
"""
