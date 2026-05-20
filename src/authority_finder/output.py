"""Google Sheets writer.

Appends a fully-populated row to the configured sheet, deduplicating on
``(domain, geo)``. Maintains separate tabs for MHD and AH source tags and
surfaces a ``manual_review`` column for rows the pipeline could not confirm
(low page-detector confidence, missing contact info, ambiguous geo, etc.).
"""
