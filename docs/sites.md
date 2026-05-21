# Integration Targets

The tool monitors two client sites for new geo pages. Both run WordPress with the Rank Math SEO plugin, so sitemap structure is identical across them — only the geo URL pattern differs.

## MHD — Inpatient Mental Health Finder
- Domain: `https://inpatientmentalhealthfinder.com`
- Sitemap index: `https://inpatientmentalhealthfinder.com/sitemap_index.xml`
- Geo URL pattern: `/serving/{state}/{county}/{city}/`
- Hierarchy: State > County/Region > City/Neighborhood
- Example state page: `/serving/california/`

## AH — Addiction Hotline
- Domain: `https://addictionhotline.com`
- Sitemap index: `https://addictionhotline.com/sitemap_index.xml`
- Geo URL pattern: `/{state}/{county}/{city}/` (no prefix, state slug at root)
- Hierarchy: State > County/Region > City/Neighborhood
- Example state pages: `/washington/`, `/colorado/`, `/north-carolina/`

## Common sitemap structure (Rank Math)
- Main index: `/sitemap_index.xml`
- Geo pages live inside paginated page sitemaps (`/page-sitemap1.xml`, `/page-sitemap2.xml`, ..., `/page-sitemapN.xml`)
- Geo pages are NOT a custom post type — they're regular WordPress Pages, mixed in with About, Contact, Services, etc.
- Filtering required: geo pages are extracted from the page sitemaps using each site's URL pattern above.

## Confirmed by
Conversation with the client's WordPress team (May 21, 2026). They confirmed the Rank Math plugin, the page-sitemap structure, that geos are regular Pages, and provided the URL patterns above.
