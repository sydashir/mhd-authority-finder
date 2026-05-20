"""Pick the specific department / resource page on a discovered domain.

The outreach team wants the probation-resources or behavioral-health page, not
the county homepage. This module ranks candidate URLs on a domain by keyword
matching plus a cheap internal-link crawl and returns the best match together
with a confidence score. Rows below a confidence threshold are flagged for
manual review rather than dropped.
"""
