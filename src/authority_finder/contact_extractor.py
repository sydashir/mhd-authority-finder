"""Contact-info scraper.

For a chosen department / resource URL, attempts to extract a public email and
phone number from the page itself plus a small bounded set of obvious link
targets like ``/contact``. Handles common obfuscation patterns such as
``name [at] domain``. Rows without contact info are flagged in the output
rather than discarded; MVP uses direct scraping only (see ADR-003).
"""
