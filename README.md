# Berlin Hausverwaltung lead pipeline (Heidi Systems case study)

Finds every property management company (Hausverwaltung) in Berlin that public sources list, enriches each one from its own website, qualifies it with six KPIs for a metering service provider, and writes a scored, evidence-backed lead workbook.

**Result (run of 6–7 Nov 2026):** 1,335 firms · 157 Tier A · 174 Tier B · 49 Tier C · 108 "Research needed" · 46 disqualified · 289 VDIV members · 483 named decision makers · 95 verified personal e-mails · 79 second contacts · 146 stated portfolio sizes · 1,004 contact rows · 2,213 sourced evidence rows · 317 outreach openers · two QA rounds (60 random leads checked live).

## Deliverables
- **Lead sheet (Google Sheets):** `[add link]`
- **Approach presentation:** `[add link]`

The lead sheet isn't stored in this repository, because it contains business contact data of real people.

## Run it

```bash
pip install -r requirements.txt
python run_all.py                            # full run, ≈ 1.5–2 h, ≈ $4 of Claude Haiku usage
python run_all.py --only build,stats,workbook   # re-score from existing data in ~10 s
python run_all.py --list                     # all 20 steps
```

AI steps use `ANTHROPIC_API_KEY` if set, otherwise the Claude Code CLI in headless mode (`claude -p --model haiku`, no tools, empty MCP config).
Intermediate files go to `data/` (git-ignored: it contains scraped contact data). Human review inputs live in `review/`.

## Architecture

| # | Step | Script | Notes |
|---|------|--------|-------|
| 1–3 | Discover | `scrape_gs.py`, `scrape_do.py`, `scrape_jacasa.py` | Gelbe Seiten (6 terms, AJAX), Das Örtliche (5 terms, embedded JSON), Jacasa (38 pages) |
| 4, 6 | Merge | `merge.py`, `merge_jacasa.py` | key = website domain, else normalised name + postcode; fuzzy match for Jacasa |
| 5, 8 | Crawl | `enrich.py`, `recrawl.py` | home, Impressum, Kontakt, Team, Leistungen, Karriere; regex extraction of directors, e-mails, register, units, staff, software, associations |
| 7 | Website discovery | `guess_domains.py` | candidate domains from the name, accepted only if the site shows the firm's postcode or phone |
| 9–10 | Association list | `scrape_vdiv.py` | VDIV Berlin-Brandenburg member directory (Heidi is a VDIV partner) – 584 Berlin members |
| 11–13 | **AI qualification agent** | `fetch_texts.py`, `ai_extract.py` | Claude reads the pages of the best ~400 firms and returns typed JSON; **every number, name, e-mail and brand must appear in the source text or it is dropped** |
| 14 | E-mail domains | `mx_check.py` | DNS MX lookup (no mailbox probing) → "Invalid" if no mail server |
| 16 | **Unit-count pass** | `units_pass.py` | collects sentences pairing a number with units/flats/buildings on 'Über uns / Referenzen / Leistungen' pages; Claude picks the currently managed figure; the quote must be one of the sentences; sums of listed references are recomputed in code and labelled as a lower bound |
| 15, 17 | Scoring | `build.py` | 6 KPI sub-scores → weighted score → tier; evidence coverage; disqualification rules; website-identity check; manual review overrides |
| 18 | **AI outreach agent** | `outreach.py` | sales play, first touch, hook and German opener per Tier A/B lead; sees only the sheet's facts + a fixed, verified description of Heidi; guardrails reject unstated numbers, gendered salutations and marketing claims |
| 19–20 | Output | `make_stats.py`, `write_xlsx.py` | workbook with live formulas (weights editable), Sales view, Contacts, Evidence, QA, Summary with charts |

**Human in the loop** (not run automatically):
- `deep_contacts.py` → `match_contacts.py`: crawls team pages of all Tier-A firms and *proposes* contact upgrades. A reviewer approves them in `review/manual_contacts.json`. Only addresses published on the firm's own pages are marked Verified.
- `qa_sample.py`, `qa_sample_round2.py`: draw a stratified random sample and fetch the live pages. A reviewer records the verdicts in `review/qa*_verdicts.json`.

## Scoring model

| KPI | Weight | Why it qualifies a lead for a metering provider |
|-----|-------:|---------------------------------------------------|
| Segment fit | 25 | WEG and rental management of residential buildings need heat, water and smoke-detector metering (HeizkostenV) |
| Size | 25 | Units managed drive meter count and recurring revenue |
| Metering trigger | 15 | Heating-cost billing in-house, incumbent named, radio meters, hiring; deadline 31.12.2026 (HeizkostenV § 5) |
| Reachability | 15 | Named decision maker, e-mail status, second contact, phone |
| Digital maturity | 10 | Portal or property software → faster adoption of a digital dashboard |
| Channel | 10 | VDIV membership (Heidi's partner network), other associations, legal form |

Guards: **Disqualified** (broker-only, commercial-only, facility services, not a manager) and **Research needed**: a lead that would reach C or better, but where less than 60% of the score weight rests on evidence.

## Validation

| Field | QA round 1 (n=20, before fixes) | QA round 2 (n=40, after fixes) |
|-------|------|------|
| Company identity | 13/14 | 31/33 |
| Postcode | 12/13 | 27/27 |
| Decision maker | 10/12 | 25/25 |
| Management type | 10/13 | 24/24 |
| Stated units | 3/3 | 4/6 |
| E-mail label | 1/6 | 2/2 |
| Tier plausible | 11/14 | 31/32 |

Every error found became a rule in the code. The bugs fixed include:
- info@ mailboxes counted as personal addresses;
- company names taken as persons;
- facility-services firms scored as managers;
- parked or unrelated websites (a domain for sale, a cosmetics studio, scientology.org…), now caught by a website-identity check;
- "flats sold" and "max. 350 units per manager" read as portfolio size;
- buildings × 12 labelled as stated units.

**Known limits:**
- Most firms publish no unit count; size is often an estimate, and it's labelled as such.
- Only about 1 in 5 Tier-A firms publishes any personal e-mail address. The rest are pattern guesses and are labelled "Unverified".
- Market coverage can't be expressed as a percentage: the Berlin Senate states that the number of commercial property administrations "is not exactly determinable" (written parliamentary question, Drucksache 18/19932).

## Legal and ethics
- **Data:** only business contact data published by the firms themselves (Impressum, team pages) or by their association. Legitimate interest under Art. 6(1)(f) GDPR (B2B prospecting, data minimised, purpose-bound). Contacts must be informed at first contact and can object at any time.
- **§ 7 UWG:** advertising e-mails, B2B included, need prior consent. That's why the outreach plan proposes phone, LinkedIn or a VDIV introduction, never cold e-mail.
- **Crawling:** public pages only, no logins, rate-limited. One shared host (Strato) still rate-limited the reviewer's IP after the bulk crawl, so the retry crawl runs with 4 workers and a 2-second pause per site (`RECRAWL_WORKERS`, `RECRAWL_PAUSE`).

## Cost and runtime
Full run: about 1.5–2 hours. Claude Haiku usage: about $3.50 for AI qualification, $0.05 for the unit-count pass and about $0.40 for the outreach plan. Re-scoring from existing data takes about 10 seconds.
