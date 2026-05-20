"""Contact-info scraper with Hunter.io fallback.

For a chosen department / resource URL, attempt to extract a public email and
phone number from the page (and a small bounded set of obvious link targets
like ``/contact``). If direct scraping yields nothing, fall back to the
Hunter.io API for an email at the same domain. Expected coverage 65-75%;
rows without contact info are flagged in the output rather than discarded.
"""
