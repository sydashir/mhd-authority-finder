"""Outbound-link check against the fixed list of competitor domains (Phase 2).

For a discovered site, crawl a bounded subset of pages and record which of the
16 competitor domains (samhsa.gov, rehabnet.com, recovery.com, rehabs.com,
drugrehabus.org, addictions.com, naatp.org, findtreatment.gov,
addictioncenter.com, startyourrecovery.org, addictionresource.net,
addictionresource.com, betteraddictioncare.com, rehabs.org, drugabuse.com,
treatmentatlas.org) the site already links to. Returns the matching subset
per discovered domain.
"""
