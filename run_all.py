"""Re-run the whole Heidi Systems lead pipeline with one command.

    python run_all.py                  # full run (≈ 1.5–2 h, ≈ $4 of Claude Haiku usage)
    python run_all.py --from build     # only re-score + re-write the workbook from existing data (seconds)
    python run_all.py --only build,stats,workbook   # re-score without new crawling or AI calls
    python run_all.py --list           # show the steps

All intermediate files go to ./data, the workbook to ../Heidi_Systems_Berlin_Hausverwaltungen_Leads.xlsx.
Human review inputs (manual contact review, QA verdicts) live in ./review and are copied into ./data before scoring.
AI steps use ANTHROPIC_API_KEY if set, otherwise the Claude Code CLI in headless mode (`claude -p`).
"""
import os, sys, shutil, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
OUT_XLSX = os.path.join(HERE, "..", "Heidi_Systems_Berlin_Hausverwaltungen_Leads.xlsx")
def p(name): return os.path.join(D, name)

STEPS = [
    # name,            script,               args                                                             what it does
    ("gelbeseiten",    "scrape_gs.py",       [p("gs_all.json")],                                              "Gelbe Seiten, 6 search terms (AJAX pagination)"),
    ("oertliche",      "scrape_do.py",       [p("do_all.json")],                                              "Das Örtliche, 5 search terms (embedded JSON)"),
    ("jacasa",         "scrape_jacasa.py",   [p("jacasa.json")],                                              "Jacasa.de Berlin listing (reviews, staff, IVD)"),
    ("merge",          "merge.py",           [p("gs_all.json"), p("do_all.json"), p("merged.json")],          "merge + de-duplicate directories"),
    ("crawl",          "enrich.py",          [p("merged.json"), p("enriched.json")],                          "crawl websites + Impressum, rule-based extraction"),
    ("jacasa_merge",   "merge_jacasa.py",    [p("enriched.json"), p("jacasa.json"), p("enriched_j.json")],    "attach Jacasa data / add Jacasa-only firms"),
    ("domains",        "guess_domains.py",   [p("enriched_j.json"), p("enriched_sites.json")],                "find missing websites (validated by postcode/phone)"),
    ("recrawl",        "recrawl.py",         [p("enriched_sites.json"), p("enriched2.json")],                 "crawl newly found + retry failed sites"),
    ("vdiv",           "scrape_vdiv.py",     [p("enriched2.json"), p("enriched3_pre.json"), D],               "VDIV Berlin-Brandenburg member directory"),
    ("recrawl_vdiv",   "recrawl.py",         [p("enriched3_pre.json"), p("enriched3.json")],                  "crawl websites of new VDIV firms"),
    ("prebuild",       "build.py",           [p("enriched3.json"), p("jacasa.json"), p("none.json"), "x", p("built.json")], "first scoring pass (selects AI candidates)"),
    ("texts",          "fetch_texts.py",     [p("built.json"), p("texts"), "35"],                             "fetch page text of firms with score ≥ 35"),
    ("ai",             "ai_extract.py",      [p("texts"), p("ai")],                                           "AI qualification agent (Claude, grounded)"),
    ("mx",             "mx_check.py",        [p("built.json"), p("mx.json")],                                 "DNS MX check of every e-mail domain"),
    ("build",          "build.py",           [p("enriched3.json"), p("jacasa.json"), p("none.json"), "x", p("built.json")], "scoring with AI, MX, VDIV, manual review"),
    ("units",          "units_pass.py",      [p("built.json"), p("units_extra.json")],                        "unit-count pass for leads without a stated size (AI pick, grounded)"),
    ("rebuild",        "build.py",           [p("enriched3.json"), p("jacasa.json"), p("none.json"), "x", p("built.json")], "final scoring incl. unit counts"),
    ("outreach",       "outreach.py",        [p("built.json"), p("outreach.json")],                           "AI outreach plan for Tier A/B (guard-railed)"),
    ("stats",          "make_stats.py",      [D],                                                             "pipeline statistics for the method tab"),
    ("workbook",       "write_xlsx.py",      [p("built.json"), OUT_XLSX, p("stats.json")],                    "write the Excel deliverable"),
]
# Optional human-in-the-loop review steps (not run automatically):
#   deep_contacts.py + match_contacts.py → proposals; a reviewer approves them into review/manual_contacts.json
#   qa_sample.py / qa_sample_round2.py   → live evidence; a reviewer records verdicts in review/qa*_verdicts.json

def main():
    if "--list" in sys.argv:
        for i, (n, s, _, w) in enumerate(STEPS, 1): print(f"{i:2}. {n:<13} {s:<18} {w}")
        return
    start = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else STEPS[0][0]
    names = [s[0] for s in STEPS]
    if start not in names: sys.exit(f"unknown step {start}; use --list")
    os.makedirs(D, exist_ok=True)
    for f in os.listdir(os.path.join(HERE, "review")):          # human review inputs
        shutil.copy(os.path.join(HERE, "review", f), D)
    env = dict(os.environ, PYTHONIOENCODING="utf8", MAX_THINKING_TOKENS="0")
    todo = STEPS[names.index(start):]
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].split(",")
        todo = [s for s in STEPS if s[0] in only]
    for n, script, args, what in todo:
        t0 = time.time(); print(f"\n▶ {n}: {what}", flush=True)
        r = subprocess.run([sys.executable, os.path.join(HERE, script)] + args, cwd=HERE, env=env)
        if r.returncode != 0: sys.exit(f"step {n} failed (exit {r.returncode})")
        print(f"  ✓ {n} in {time.time() - t0:.0f}s", flush=True)
    print("\nDone →", os.path.abspath(OUT_XLSX))

if __name__ == "__main__":
    main()
