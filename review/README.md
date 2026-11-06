# Human review files

The pipeline is human-in-the-loop in two places. The reviewer's decisions are stored as JSON files in this folder. They're copied into `data/` by `run_all.py` and read by `build.py` and `write_xlsx.py`. The real files contain names and e-mail addresses of real people, so they're **not committed** (see `.gitignore`). The pipeline runs without them; the manual upgrades and the QA tabs are then simply missing.

## `manual_contacts.json`: approved contact upgrades

Produced by reviewing the proposals of `deep_contacts.py` → `match_contacts.py`. Only addresses published on the firm's own pages may be marked `verified`.

```json
{
  "_note": "Manual contact review of all Tier-A firms, 7 Nov 2026",
  "Beispiel Hausverwaltung GmbH": {
    "email": "m.muster@beispiel-hv.de",
    "status": "verified",
    "note": "published on team page",
    "second": {"name": "Erika Beispiel", "role": "Leitung WEG-Verwaltung", "email": "e.beispiel@beispiel-hv.de"}
  },
  "Muster Immobilien GmbH": {
    "email": "muster@muster-immobilien.de",
    "status": "probable",
    "note": "surname-only pattern confirmed by 6 published team addresses"
  }
}
```

## `qa_verdicts.json` / `qa2_verdicts.json`: QA rounds

Produced from the live evidence printed by `qa_sample.py` / `qa_sample_round2.py`. The verdicts are `✓` correct, `✗` wrong, `n.c.` not checkable, `–` not applicable.

```json
{
  "method": "Stratified random sample (seed …) of N leads, live pages fetched on …",
  "rows": [
    {"n": 1, "tier": "A", "company": "Beispiel Hausverwaltung GmbH", "site": "https://www.beispiel-hv.de/",
     "id": "✓", "plz": "✓", "dm": "✓", "type": "✓", "units": "n.c.", "email": "–", "tierok": "✓",
     "finding": "Managing director and WEG focus correct.", "after": "–"}
  ],
  "residuals": ["…"]
}
```

The aggregated results of both QA rounds are in the main `README.md`.
