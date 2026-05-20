"""Domain Rating filter for non-.gov / non-.edu candidates (Phase 2).

``.gov`` and ``.edu`` domains pass automatically and never hit Ahrefs. Every
other candidate is looked up against the Ahrefs API; those at or above the
configured Domain Rating threshold are retained, the rest are dropped.
"""
