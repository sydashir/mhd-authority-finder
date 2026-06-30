"""FastAPI backend over the Postgres source-of-truth (Phase B, ADR-014).

Serves the prospects/runs the pipeline persists (``authority_finder.db``) and
triggers pipeline runs as background jobs. The pipeline and the Google Sheet
output are untouched — this is an additive read/trigger layer the React UI
(Phase C) will consume.
"""
