# Original Brief (from Jake, ClickUp task 86b9re44b)

<We need a tool that fetches all .gov and .edu sites (& any high authority resource site like ncala.org or dbhdduniversity.com if there is a way to filter for these sites as well) that are based in each geo we have a page for on MHD. List them in a Google Sheet that as new geo pages go live on MHD and AH the tool goes out and fetches the new .edu and .gov sites that are in those Cities, Counties and states.



Check ahrefs backlink data on this domain rehabnet.com/ to see the types of good local authority websites we need to fetch and get contact info for. We are going to be doing backlink reachout, to see if any of these organizations would want to list our directory page, for their geo, on their site as a resource for people to find the best mental health facilities in their area. (We will also be able to use this same list to try the same reachout for AH)



Items needed in the sheet





website



The specific health department page, probation department page, resource page, student resource page, etc



The email and phone number to any of these departments



Description of the .gov .edu organization



The population of the geo the organization is serving



If their site currently links out to any of these sites below





samhsa.gov



rehabnet.com



recovery.com



rehabs.com



drugrehabus.org



addictions.com



naatp.org



findtreatment.gov



addictioncenter.com



startyourrecovery.org



addictionresource.net



addictionresource.com



betteraddictioncare.com



rehabs.org



drugabuse.com



treatmentatlas.org

>

# Feasibility Report (Syed Ashir, May 6 2026)

<Feasibility Report: Automated Backlink Prospecting Tool

Date: May 6, 2026
Project: MHD & AH  Geo-Based Authority Site Discovery & Outreach Tool


1. Executive Summary
The client has requested an automated tool that discovers high-authority websites (.gov, .edu, and recognized health/addiction organizations) for each geographic location that Mental Health Directory (MHD) and Addiction Help (AH) have active pages for. The tool will compile contact information, organizational details, and competitor link data into a continuously updated Google Sheet  to be used as a backlink outreach list.

Verdict: Feasible.
All identified challenges have clear technical solutions. The project is well-scoped and buildable.


2. Project Objectives
Monitor MHD and AH for new geo pages (city, county, state) going live
For each geo, automatically discover:
.gov websites (health departments, probation departments, county resource pages)
.edu websites (universities, student resource pages)
High-authority health/addiction organizations (e.g., ncala.org, dbhdduniversity.com)
Identify the specific department or resource page not just the homepage
Extract contact information (email address, phone number) for each organization
Check whether each discovered site already links to any of 16 defined competitor domains
Pull population data for the geo being served
Auto-populate and update a structured Google Sheet
Apply the same output for both MHD and AH outreach campaigns


3. What the Tool Will Produce (Google Sheet Columns)
Column
Description
Website
Root domain of discovered site
Specific Page
Direct URL to the relevant dept/resource page
Email
Contact email for that department
Phone
Contact phone number
Organization Description
Summary of the .gov/.edu or authority org
Geo Served
City / County / State
Population
Population of the geo (via Census API)
Competitor Links
Which of the 16 competitor domains this site links to
Source Tag
MHD or AH (or both)
Date Added
When the row was auto-generated

Competitor Domains Being Checked
samhsa.gov, rehabnet.com, recovery.com, rehabs.com, drugrehabus.org, addictions.com, naatp.org, findtreatment.gov, addictioncenter.com, startyourrecovery.org, addictionresource.net, addictionresource.com, betteraddictioncare.com, rehabs.org, drugabuse.com, treatmentatlas.org


4. Technical Architecture
Step
Component
What It Does
Tool / API Used
1
Geo Page Monitor
Watches MHD & AH sitemaps. Detects when a new city, county, or state page goes live and triggers the pipeline
Sitemap polling (scheduled)
↓






2
Search & Discovery Engine
For each new geo, runs targeted queries to find .gov and .edu sites in that location
SerpAPI / Google Custom Search
↓






3
Authority Filter
.gov and .edu domains pass automatically. All other domains are scored by Domain Rating — only high-authority sites proceed
Ahrefs API (DR threshold)
↓






4
Department Page Detector
Finds the specific resource page (e.g. health dept page, probation resources) — not just the homepage. Flags low-confidence results for manual review
Keyword scoring + internal link crawl
↓






5
Contact Info Extractor
Scrapes email and phone number from the identified page. Falls back to Hunter.io / Apollo if not found directly. Expected coverage: 65–75%
BeautifulSoup + Hunter.io / Apollo API
↓






6
Competitor Link Checker
Checks if the discovered site already links out to any of the 16 defined competitor domains
Page crawler + link parser
↓






7
Population Lookup
Pulls the population figure for the geo being served
US Census API
↓






8
Google Sheets Output
Appends all data as a new row. Deduplicates. Maintains separate tabs for MHD and AH. Flags rows needing manual review
Google Sheets API



5. Component-by-Component Assessment
Component
Status
Geo page monitor (sitemap watcher)
Clean — poll sitemaps on schedule
.gov / .edu domain discovery
Easy — search API + domain suffix filter
High-authority site discovery
Handled via Ahrefs API (DR threshold)
Department/resource page detection
Solvable — keyword scoring + targeted search queries. ~70-75% auto-accuracy, remainder flagged
Contact info extraction
Handled — Hunter.io / Apollo as fallback. Realistic coverage ~65-75%
Competitor link checking
Straightforward page crawl against 16 domains
Population data
Easy — US Census API
Google Sheets auto-update
Well-documented API, standard implementation
Deduplication logic
Standard — URL + geo key matching



6. Challenges & Mitigations
Challenge 1 — Contact Info Coverage
Issue: Government and university sites frequently hide emails behind contact forms or use obfuscated addresses.
Mitigation: Layer Hunter.io or Apollo.io API on top of direct scraping. Expected coverage 65-75%. Remaining rows flagged in sheet for manual QA.
Client Acknowledgement Needed: Tool is a research accelerator, not a perfect data machine.
Challenge 2 — Specific Department Page Detection
Issue: Client needs the probation resource page, not the county homepage.
Mitigation: Use targeted search queries ("mental health resources site:dallas.gov") to land on the correct sub-page directly. Supplement with keyword-scored crawling of internal links. ~70-75% auto-accuracy.
Challenge 3 — High-Authority Non-.gov/.edu Sites
Issue: Sites like ncala.org cannot be identified as authoritative without domain metrics.
Mitigation: Ahrefs API — filter by Domain Rating above an agreed threshold (e.g., DR 40+). Also maintain a curated seed list of known org types (state addiction councils, SAMHSA affiliates).
Challenge 4 — Scale
Issue: At 500+ geo pages, volume of sites to crawl becomes significant.
Mitigation: Run in batches. Add rate limiting and retry logic. Queue new geo pages and process asynchronously. Cost scales with API usage — client to be informed of per-query costs.


7. APIs & Tools Required
Tool/API
Purpose
Pricing Model
SerpAPI or Google Custom Search API
Site discovery per geo
Per query (paid)
Ahrefs API
Domain Rating filter for authority sites
Subscription
Hunter.io or Apollo.io
Email discovery fallback
Per lookup or subscription
US Census API
Population data
Free
Google Sheets API
Output and auto-update
Free
Python (BeautifulSoup / Scrapy)
Page crawling and contact scraping
Open source



8. Labor Hour Estimate
Task
Estimated Hours
Architecture, API setup, project scaffolding
10–14
Geo page monitor (MHD + AH sitemap watcher)
8–12
Search API integration + .gov/.edu discovery
16–20
Ahrefs authority filter for non-.gov/.edu
10–16
Department page detection (keyword scoring)
20–28
Contact info scraping + Hunter.io fallback
16–24
Competitor link checker (16 domains)
14–20
Census API population lookup
4–6
Google Sheets integration + deduplication
8–14
Testing, QA, edge cases
16–22
Deployment + scheduling (automated triggers)
8–12
Total
130–188 hours


Recommended estimate to quote: 150–160 hours for MVP


9. Phased Delivery Recommendation
Phase 1 — Core MVP (Recommended Starting Point)
.gov and .edu discovery only
Department page detection
Contact info scraping (direct + Hunter.io)
Population data
Google Sheets output
Manual trigger (run on demand per geo)

Est. Hours: 80–100
Phase 2 — Automation + Authority Sites
Ahrefs-powered authority site discovery (ncala.org type)
Competitor link checking (16 domains)
Automated trigger on new geo page detection
Scheduled re-validation runs

Est. Hours: 50–60 additional


10. (Scope Boundaries)
It will not send outreach emails automatically (this is prospecting only)
It will not guarantee 100% contact info coverage
It will not manually verify every discovered page (flagging system handles this)
Data freshness maintenance beyond MVP is a separate engagement



>