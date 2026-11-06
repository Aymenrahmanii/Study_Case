"""Compute pipeline statistics for the 'Sources & Method' sheet and the approach deck."""
import json, sys, collections
R = sys.argv[1]  # raw dir
gs = json.load(open(f"{R}/gs_all.json", encoding="utf8")); do = json.load(open(f"{R}/do_all.json", encoding="utf8"))
jac = json.load(open(f"{R}/jacasa.json", encoding="utf8")); merged = json.load(open(f"{R}/merged.json", encoding="utf8"))
e2 = json.load(open(f"{R}/enriched3.json", encoding="utf8")); built = json.load(open(f"{R}/built.json", encoding="utf8"))
li = json.load(open(f"{R}/linkedin_manual.json", encoding="utf8")) if __import__("os").path.exists(f"{R}/linkedin_manual.json") else {}
rows = built["rows"]
gs_u = len({r["gs_id"] for r in gs})
guessed = sum(1 for c in e2 if (c.get("website_source") or "").startswith("domain guess"))
ok = sum(1 for c in e2 if c.get("crawl_status") == "ok")
conf = collections.Counter((r["Email confidence"] or "none").split(" ")[0] for r in rows)
s = {
 "gs_rows": len(gs), "gs_unique": gs_u, "do": len(do), "jac": len(jac), "merged": len(merged), "final": len(rows), "excluded": len(built["excluded"]),
 "crawled_ok": ok, "guessed": guessed, "dm": sum(1 for r in rows if r["Decision maker"]), "high": conf["High"], "medium": conf["Medium"], "low": conf["Low"],
 "units": sum(1 for r in rows if r["Size basis"] == "Units stated"), "vdiv": sum(1 for r in rows if "VDIV" in r["Associations"]),
 "incumbent": sum(1 for r in rows if r["Current metering provider (mentioned)"]), "linkedin": sum(1 for r in rows if r["Company social"]),
}
import os as _os
vm = json.load(open(f"{R}/vdiv_members.json", encoding="utf8"))
s["vdiv_members"] = len(vm); s["vdiv_berlin"] = sum(1 for m in vm if m["plz"].isdigit() and 10115 <= int(m["plz"]) <= 14199)
s["vdiv_rows"] = sum(1 for r in rows if r.get("VDIV member (directory)") == "Yes")
s["contacts_rows"] = sum(len(r.get("_contacts") or []) for r in rows); s["evidence_rows"] = sum(len(r.get("_evidence") or []) for r in rows)
aidir = f"{R}/ai"; ai_recs = [json.load(open(_os.path.join(aidir, f), encoding="utf8")) for f in _os.listdir(aidir)] if _os.path.isdir(aidir) else []
s["ai"] = len(ai_recs); s["ai_flags"] = sum(len(a.get("_grounding_flags") or []) for a in ai_recs)
s["disq"] = sum(1 for r in rows if r.get("Disqualified reason")); s["second"] = sum(1 for r in rows if r.get("Second contact"))
st = collections.Counter((r.get("Email status") or "none").split(" ")[0] for r in rows)
s["verified"], s["probable"], s["unverified"], s["invalid"] = st["Verified"], st["Probable"], st["Unverified"], st["Invalid"]
s["steps"] = [
 ("1 · Directory scraping", "Python (requests + BeautifulSoup) scraper for Gelbe Seiten (6 search terms: Hausverwaltung, Immobilienverwaltung, WEG-Verwaltung, Hausverwaltungen, Mietverwaltung, Grundstücksverwaltung; AJAX pagination), Das Örtliche (5 terms, embedded JSON) and Jacasa.de (all 38 Berlin pages).",
  f"Gelbe Seiten {s['gs_unique']} unique · Das Örtliche {s['do']} · Jacasa {s['jac']} listings"),
 ("1b · Association directory", "Parsed the public member directory of VDIV Berlin-Brandenburg e.V. (vdiv-bb.de/mitglieder): firm, named contact, e-mail, phone, address, website. Kept members with a Berlin postcode (10115–14199); matched to existing firms by website domain, else name + postcode.",
  f"{s['vdiv_members']} members · {s['vdiv_berlin']} in Berlin · {s['vdiv_rows']} VDIV firms in the final list"),
 ("2 · Merge & de-duplicate", "Key = website domain, else normalised company name (legal form & generic words removed) + postcode; Jacasa matched by name/postcode, street/postcode, fuzzy name; second pass de-duplicates by final (redirected) website domain.",
  f"{s['gs_unique'] + s['do'] + s['jac'] + s['vdiv_berlin']} listings → {s['final'] + s['excluded']} unique companies"),
 ("3 · Relevance filter", "Removed entries whose name/category shows another business (insurance agents, notaries, architects, software, a party HQ …).", f"{s['excluded']} excluded (sheet 'Excluded') → {s['final']} in 'Leads'"),
 ("4 · Website discovery", "For firms without a listed website: candidate domains generated from the company name (e.g. name-hausverwaltung.de), DNS-resolved and accepted only if the site shows the firm's postcode or phone number. (Search-engine lookup was tried first but is rate-limited for automated use.)",
  f"{s['guessed']} additional websites found and validated"),
 ("5 · Website + Impressum crawl", "24 parallel workers fetch home, Impressum, Kontakt, Team/Über uns, Leistungen and Karriere pages; retry with https/www variants. Regex extraction of managing directors (Impressum is legally required), e-mails (incl. obfuscated [at]), Handelsregister, units/objects managed, employees, founding year, services, associations, software/portal, metering-provider names.",
  f"{s['crawled_ok']} websites crawled successfully · {s['dm']} decision makers identified"),
 ("6 · AI qualification agent", "Claude (Haiku 4.5, run headless via the Claude Code CLI; Anthropic API supported) reads Impressum, team, services, home and careers text of the best-scoring firms and returns a typed JSON record: management type, residential focus, units/buildings, employees, metering provider, software, associations, hiring, people with role category, one-line summary. Grounding check: every number, name, e-mail, provider and software must appear in the source text, otherwise it is dropped.",
  f"{s['ai']} firms AI-extracted · {s['ai_flags']} ungrounded values dropped · {s['disq']} disqualified (broker / commercial-only / SEV-only / not a manager)"),
 ("7 · Contact enrichment", "Decision maker (Geschäftsführung) + second persona (head of WEG/rental management or technical property manager). E-mail status: Verified (published on site) / Probable (company pattern) / Unverified (default pattern), every domain DNS MX-checked → Invalid if no mail server. Company LinkedIn/Xing pages from the websites + prefilled LinkedIn people search per row.",
  f"Verified {s['verified']} · Probable {s['probable']} · Unverified {s['unverified']} · Invalid {s['invalid']} · second contacts {s['second']} · company LinkedIn/Xing {s['linkedin']}"),
 ("8 · Scoring", "Six KPI sub-scores 0–10 (segment fit, size, metering trigger, reachability, digital maturity, channel) → weighted Lead Score 0–100 → Tier A–D. Weights editable in 'Scoring Model'.", "See 'Summary' sheet"),
 ("8b · Evidence log", "Every row gets an evidence-coverage % (share of score weight backed by observed evidence) and promising rows with thin evidence are tiered 'Research needed'. Sheets 'Contacts' (one row per person) and 'Evidence' (one row per claim with source URL and quote) make each value checkable.",
  f"{s['contacts_rows']} contact rows · {s['evidence_rows']} evidence rows"),
 ("9 · Validation", "(a) cross-source agreement – firms present in 2–3 directories; (b) website accepted only if postcode/phone matches directory data; (c) extracted person names cleaned (titles, street names, nouns removed) and only from Impressum context; (d) AI output grounded against page text; unit numbers sanity-capped (10–40,000) and stored with the text evidence; (e) manual spot check of the top-ranked leads against their websites; (f) every row carries source, website status and e-mail confidence.",
  f"Units stated for {s['units']} firms · VDIV members {s['vdiv']} · incumbent provider known for {s['incumbent']}"),
]
json.dump(s, open(f"{R}/stats.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
print({k: v for k, v in s.items() if k != "steps"})
