"""Write the deliverable workbook from built.json."""
import json, sys, os, datetime, collections
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import CellIsRule, FormulaRule, ColorScaleRule
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment

BUILT, OUT, STATS = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(BUILT, encoding="utf8")); rows, excluded = d["rows"], d["excluded"]
stats = json.load(open(STATS, encoding="utf8"))

F = "Arial"
H_FILL = PatternFill("solid", fgColor="1F3A5F"); H_FONT = Font(name=F, bold=True, color="FFFFFF", size=10)
SUB_FILL = PatternFill("solid", fgColor="E8EEF5"); INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
BASE = Font(name=F, size=10); BOLD = Font(name=F, size=10, bold=True); LINK = Font(name=F, size=10, color="0563C1", underline="single")
BLUE = Font(name=F, size=10, color="0000FF", bold=True)
thin = Side(style="thin", color="D0D7E2"); BORDER = Border(bottom=thin)
WRAP = Alignment(wrap_text=True, vertical="top"); TOP = Alignment(vertical="top")

KPIS = [  # key, label, weight, definition, why it matters, how measured
    ("S_fit", "Segment fit", 25, "Does the company manage residential multi-unit buildings (WEG, Miet-, SE-Verwaltung)?",
     "Heating/water metering and smoke-detector services are mandatory for residential multi-unit buildings with central heating (HeizkostenV, BauO Bln). WEG + rental management = core buyer; pure commercial/broker focus = weak fit.",
     "Keyword analysis of website pages (WEG-Verwaltung, Mietverwaltung, Sondereigentum, Gewerbe) + directory category; for the top 416 firms the AI agent's grounded management type and residential focus. 0–10."),
    ("S_size", "Size / revenue potential", 25, "Number of managed units (stated) or estimate.",
     "Revenue per customer scales with the number of apartments (meters per unit). One mid-size manager = hundreds of meters + recurring billing.",
     "Units stated on website (objects/WEGs ×12 units); else employees ×150 units/FTE (website or Jacasa); else proxy (legal form, website depth, reviews, hiring). 0–10."),
    ("S_trigger", "Metering need / switch trigger", 15, "Signals that metering is a live topic: heating-cost billing done in-house, incumbent metering provider named, radio meters/smoke detectors mentioned, hiring.",
     "HeizkostenV §5: all meters must be remotely readable by 31.12.2026 → managers on legacy devices must act now. A named incumbent (Techem, ista, Brunata, Minol…) is a concrete switch opportunity; hiring signals capacity pressure → automation pitch.",
     "Keyword hits on website (Heizkostenabrechnung, Messdienst, Funk/fernablesbar, Rauchwarnmelder, Karriere/Jobs) + brand names of metering providers. 0–10."),
    ("S_reach", "Reachability of decision maker", 15, "Is a named decision maker (Geschäftsführer/Inhaber) identified and contactable personally?",
     "Outbound conversion depends on reaching the person who signs the metering contract — usually the managing director in owner-led Hausverwaltungen.",
     "Impressum/team-page parsing (rules + AI agent): managing director, second contact; e-mail status Verified / Probable / Unverified (DNS MX-checked); phone. 0–10."),
    ("S_digital", "Digital maturity", 10, "Website quality, HTTPS, use of a customer portal or property software (casavi, Domus, Karthago, facilioo…).",
     "Heidi's offer is digital (radio meters → dashboard → Betriebskostenabrechnung). Digitally mature managers adopt faster and can integrate data exports into their ERP.",
     "Crawl result: reachable website, HTTPS, content depth, portal/software mentions. 0–10."),
    ("S_channel", "Channel / professionalism", 10, "Association memberships (VDIV, BVI, IVD, BFW, Haus & Grund), legal form.",
     "Heidi Systems is a VDIV partner company → VDIV members can be reached via the association channel (events, partner listing). Professional GmbHs have structured purchasing.",
     "Website mentions of associations + Jacasa membership badges + legal form from name/Handelsregister. 0–10."),
]
W = {k: w for k, _, w, *_ in KPIS}
def py_score(r): return round(sum(r[k] * W[k] for k in W) / sum(W.values()) * 10, 1)
for r in rows: r["_score"] = py_score(r)
_op = os.path.join(os.path.dirname(BUILT), "outreach.json")
OUTREACH = json.load(open(_op, encoding="utf8")) if os.path.exists(_op) else {}
for r in rows:
    o = OUTREACH.get(r["Company"]) or {}
    r["Sales play"] = o.get("play", ""); r["Hook"] = o.get("hook", ""); r["First touch"] = o.get("channel", ""); r["Opener (DE)"] = o.get("opener_de", "")
rows.sort(key=lambda r: (-r["_score"], r["Company"]))
TIERS = (65, 50, 35)
MIN_COV = 0.6

wb = Workbook()
# ======================= README =======================
ws0 = wb.active; ws0.title = "README"
ws0.sheet_view.showGridLines = False
ws0.column_dimensions["A"].width = 3; ws0.column_dimensions["B"].width = 34; ws0.column_dimensions["C"].width = 110
ws0["B2"] = "Berlin Property Management Companies – Lead List for Heidi Systems"; ws0["B2"].font = Font(name=F, size=16, bold=True, color="1F3A5F")
ws0["B3"] = f"Case study by Aymen Rahmani · data collected {datetime.date(2026,11,6):%d %b %Y} · fully automated pipeline (Python) + manual spot checks"; ws0["B3"].font = Font(name=F, size=10, italic=True, color="666666")
info = [
    ("What is this?", "Every property management company (Hausverwaltung) in Berlin that I could find in public directories and the VDIV Berlin-Brandenburg member list, de-duplicated, enriched from each company's own website and Impressum, and scored as a lead for a metering service provider."),
    ("Companies in list", f"{len(rows)} companies (sheet 'Leads'); {len(excluded)} directory entries were removed as not property management (sheet 'Excluded')."),
    ("How to use", "Start with sheet 'Sales view' (Tier A–C and Research needed, 24 columns incl. sales play and opener, ready for outreach). Sheet 'Leads' holds every company and all fields, sorted by Lead Score; filter on 'Tier' or 'Bezirk'. Column 'Why' explains each score in one line. Six KPI sub-scores (0–10) sit next to the score."),
    ("AI qualification agent", "For the 416 best firms with a website (score ≥ 35), Claude (Haiku 4.5, via Claude Code headless) read the Impressum, team, services, home and careers pages and returned a typed record: management type, residential focus, units/buildings, employees, metering provider, software, associations, hiring, people with roles. Every number, name and e-mail is grounded: if it does not appear in the page text it is dropped. Column 'Data basis' shows which rows are AI-verified; 'AI summary' gives a one-line description."),
    ("Disqualified", "Firms the AI agent found to be pure brokers, commercial-only, single-flat (SEV-only) managers or not third-party managers get Tier 'Disqualified' with the reason in column 'Disqualified reason' (they stay visible for transparency)."),
    ("Adjust the model", "Change the yellow weight cells or tier thresholds in sheet 'Scoring Model' – Lead Score and Tier are live formulas and update automatically."),
    ("Tiers", f"A ≥ {TIERS[0]} · B ≥ {TIERS[1]} · C ≥ {TIERS[2]} · D < {TIERS[2]} (score 0–100) · Research needed = would reach C or better, but less than {int(MIN_COV*100)}% of the score weight is backed by evidence (verify before calling) · Disqualified = evidence that the firm is not a buyer of building-level metering."),
    ("Evidence coverage", "Share of the score weight that rests on observed evidence (stated units, crawled website, named person, directory membership) rather than defaults or proxies. Shown next to every score; the six evidence flags are at the far right of 'Leads'."),
    ("Outreach plan", "For every Tier A/B lead a second AI step proposes the sales play (WEG / rental / owner-tender), the first touch (phone, LinkedIn or VDIV intro – no cold e-mail, § 7 UWG), the hook and a German opening sentence. It sees only the lead's facts from this sheet plus a fixed, verified description of Heidi; guardrails reject numbers that are not stated facts, gendered salutations and marketing claims. Drafts – review before use."),
    ("Contacts & Evidence tabs", "'Contacts' = one row per person (role, e-mail, e-mail status, source URL). 'Evidence' = one row per key claim (field, value, source URL, quoted evidence, confidence) so every important value can be checked independently."),
    ("Contact data", "Decision maker = managing director / owner named in the Impressum (legally required in Germany, § 5 DDG). Second contact = head of WEG/rental management or technical property manager where the team page names one. Email status: Verified = published on the company website; Probable = built from the address pattern seen on the same domain; Unverified = default vorname.nachname@ guess; Invalid = the domain has no mail server (DNS MX check). No SMTP mailbox probing was done – run Probable/Unverified addresses through an e-mail verifier before a campaign."),
    ("Size numbers", "'Est. units' is the number stated on the company website where available; otherwise an estimate (see 'Size basis'). Estimates are marked and should be read as an order of magnitude."),
    ("Sources", "VDIV Berlin-Brandenburg member directory (vdiv-bb.de/mitglieder), Gelbe Seiten, Das Örtliche, Jacasa.de + each company's website / Impressum / Kontakt / Team / Leistungen / Karriere pages. See sheet 'Sources & Method'. Pages were fetched politely (public pages only, parallel but rate-limited, no logins)."),
    ("Legal note (GDPR / UWG)", "Only business contact data published by the companies themselves or by their association is used (legitimate interest, Art. 6(1)(f) GDPR, data minimised). § 7 UWG: advertising e-mails – also to businesses – generally need prior express consent; a published address is not consent. B2B phone calls are allowed with presumed consent. So: first touch by phone, LinkedIn or via the VDIV partner channel; e-mail after consent."),
]
r0 = 5
for k, v in info:
    ws0.cell(r0, 2, k).font = BOLD; c = ws0.cell(r0, 3, v); c.font = BASE; c.alignment = WRAP
    ws0.cell(r0, 2).alignment = TOP
    ws0.row_dimensions[r0].height = max(15, 15 * (len(v) // 105 + 1)); r0 += 1

# ======================= Scoring Model =======================
wm = wb.create_sheet("Scoring Model"); wm.sheet_view.showGridLines = False
wm["B2"] = "Qualifying KPIs and scoring model"; wm["B2"].font = Font(name=F, size=14, bold=True, color="1F3A5F")
wm["B3"] = "Edit the yellow cells (weights, thresholds). Lead Score = weighted average of the six KPI sub-scores (each 0–10) × 10 → 0–100."; wm["B3"].font = Font(name=F, size=10, italic=True)
hdr = ["KPI", "Weight", "Definition", "Why it matters for Heidi Systems", "How it is measured (data source)"]
for i, h in enumerate(hdr): c = wm.cell(4, 2 + i, h); c.font = H_FONT; c.fill = H_FILL; c.alignment = WRAP
for i, (k, lab, w, de, why, how) in enumerate(KPIS):
    r = 5 + i
    wm.cell(r, 2, lab).font = BOLD
    c = wm.cell(r, 3, w); c.font = BLUE; c.fill = INPUT_FILL; c.alignment = Alignment(horizontal="center", vertical="top")
    for j, v in enumerate((de, why, how)): c = wm.cell(r, 4 + j, v); c.font = BASE; c.alignment = WRAP
    wm.row_dimensions[r].height = 92
    wm.cell(r, 2).alignment = WRAP
wm.cell(11, 2, "Total weight").font = BOLD; wm.cell(11, 3, "=SUM(C5:C10)").font = BOLD
wm.cell(13, 2, "Tier thresholds (score ≥)").font = BOLD
for i, (t, v, desc) in enumerate((("A", TIERS[0], "Contact first – strong fit, sizeable, reachable"), ("B", TIERS[1], "Good fit – nurture / second wave"), ("C", TIERS[2], "Possible – needs more research"))):
    wm.cell(14 + i, 2, f"Tier {t}").font = BASE; c = wm.cell(14 + i, 3, v); c.font = BLUE; c.fill = INPUT_FILL; c.alignment = Alignment(horizontal="center")
    wm.cell(14 + i, 4, desc).font = BASE
wm.cell(17, 2, "Tier D").font = BASE; wm.cell(17, 4, "Below C threshold – low priority / micro managers / no data").font = BASE
wm.cell(18, 2, "Min. evidence coverage").font = BASE; c = wm.cell(18, 3, MIN_COV); c.font = BLUE; c.fill = INPUT_FILL; c.number_format = "0%"; c.alignment = Alignment(horizontal="center")
wm.cell(18, 4, "Below this, a lead that would be A–C is shown as 'Research needed' instead").font = BASE
wm.cell(20, 2, "Additional KPIs captured (not scored)").font = BOLD
extra = [("Residential focus", "Residential / mixed / commercial (AI). Residential adds +1 to Segment fit, commercial-only −3 and disqualifies: building-level heat metering is a residential multi-family topic (HeizkostenV)."),
         ("WEG vs. rental", "Both are buyers but sell differently: a WEG switches metering provider by owners' resolution (Beschluss in der Eigentümerversammlung) → pitch the manager to put it on the agenda; in rental management the owner/asset manager decides directly → shorter cycle."),
         ("Second contact", "Head of WEG/rental management or technical property manager – feels the pain of late or wrong metering bills and prepares the decision."),
         ("Bezirk", "Route planning for installers; clustering of field-sales visits."), ("Founded", "Company age; long-established firms often have long-running metering contracts (renewal timing)."),
         ("Rating / Reviews", "Google-like reputation on directories; review count is a rough proxy for number of tenants/owners served."),
         ("Current metering provider", "Competitive intelligence; tailor pitch (e.g. remote-reading deadline, price, transparency)."),
         ("Commercial register", "HRB/HRA number for verification (Handelsregister / North Data)."),
         ("Est. units method", "Objects/WEGs × 12 units (typical Berlin multi-family building); employees × 150 units per FTE (residential management rule of thumb). Both are assumptions – stated numbers always take precedence.")]
for i, (a, b) in enumerate(extra):
    wm.cell(21 + i, 2, a).font = BASE; c = wm.cell(21 + i, 4, b); c.font = BASE; c.alignment = WRAP
for col, wdt in zip("ABCDEF", (3, 30, 9, 45, 60, 55)): wm.column_dimensions[col].width = wdt

# ======================= Leads =======================
ws = wb.create_sheet("Leads", 1)
cols = [("Company", 38), ("Tier", 11), ("Lead Score", 8), ("Evidence coverage", 9), ("Why (score rationale)", 48),
        ("Segment fit", 7), ("Size", 7), ("Metering trigger", 8), ("Reachability", 8), ("Digital", 7), ("Channel", 7),
        ("Disqualified reason", 22), ("Segment", 24), ("Management type", 16), ("Residential focus", 11), ("Est. units", 9), ("Units scope", 16), ("Size class", 16), ("Size basis", 30), ("Employees", 9), ("Founded", 8),
        ("Heating-cost billing on site", 10), ("Current metering provider (mentioned)", 16), ("Smoke detectors / radio meters mentioned", 18),
        ("Digital maturity", 18), ("Software / portal seen", 18), ("Associations", 14), ("VDIV member (directory)", 9), ("Hiring", 7), ("Rating", 7), ("Reviews", 8), ("Legal form", 16), ("Commercial register", 14),
        ("Decision maker", 22), ("Role", 16), ("Personal email", 32), ("Email status", 26), ("Email confidence", 34), ("Generic email", 28), ("Phone", 16),
        ("Second contact", 22), ("Second contact role", 22), ("Second contact email", 30), ("VDIV contact", 20),
        ("Sales play", 14), ("First touch", 11), ("Hook", 44), ("Opener (DE)", 70), ("Further people (Impressum)", 26),
        ("LinkedIn search", 14), ("Company social", 24), ("Website", 30), ("Impressum", 14), ("AI summary", 60),
        ("Street", 24), ("PLZ", 7), ("Bezirk", 22), ("Directory name", 30), ("Sources", 26), ("Data basis", 26), ("Website status", 14), ("Website check", 22), ("Website found via", 22),
        ("Ev: Segment fit", 6), ("Ev: Size", 6), ("Ev: Trigger", 6), ("Ev: Reach", 6), ("Ev: Digital", 6), ("Ev: Channel", 6)]
COL = {h: get_column_letter(i) for i, (h, _) in enumerate(cols, 1)}
def rng(h): return f"Leads!${COL[h]}$2:${COL[h]}${len(rows) + 1}"
key_of = {"Why (score rationale)": "Why", "Segment fit": "S_fit", "Size": "S_size", "Metering trigger": "S_trigger", "Reachability": "S_reach", "Digital": "S_digital", "Channel": "S_channel",
          "Ev: Segment fit": "E_fit", "Ev: Size": "E_size", "Ev: Trigger": "E_trigger", "Ev: Reach": "E_reach", "Ev: Digital": "E_digital", "Ev: Channel": "E_channel"}
SUBS = ["Segment fit", "Size", "Metering trigger", "Reachability", "Digital", "Channel"]
EVS = ["Ev: Segment fit", "Ev: Size", "Ev: Trigger", "Ev: Reach", "Ev: Digital", "Ev: Channel"]
for i, (h, wdt) in enumerate(cols, 1):
    c = ws.cell(1, i, h); c.font = H_FONT; c.fill = H_FILL; c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.column_dimensions[get_column_letter(i)].width = wdt
for h in SUBS + ["Evidence coverage"]: ws[COL[h] + "1"].fill = PatternFill("solid", fgColor="3C6E9F")
for h in EVS: ws[COL[h] + "1"].fill = PatternFill("solid", fgColor="7F7F7F")
ws.row_dimensions[1].height = 54
ws.cell(1, 3).comment = Comment(f"=weighted average of the six KPI sub-scores (cols {COL[SUBS[0]]}–{COL[SUBS[-1]]}) using weights in 'Scoring Model'!C5:C10, scaled to 0–100", "Aymen")
ws[COL["Evidence coverage"] + "1"].comment = Comment(f"Share of score weight backed by evidence = Σ(evidence flag × weight) / total weight; flags in cols {COL[EVS[0]]}–{COL[EVS[-1]]}", "Aymen")
ws[COL["Email status"] + "1"].comment = Comment("Verified = published on the company website; Probable = built from the address pattern of the same domain; Unverified = default vorname.nachname@ guess; Invalid = domain has no mail server (DNS MX check). No SMTP mailbox probing was done.", "Aymen")
ws[COL["Disqualified reason"] + "1"].comment = Comment("Set when the AI agent (grounded in the website text) finds the firm is a pure broker, commercial-only, single-flat (SEV-only) or not a third-party manager. Tier then shows 'Disqualified'.", "Aymen")
SM = "'Scoring Model'"
URLCOLS = {"LinkedIn search", "Website", "Impressum"}
DQ = COL["Disqualified reason"]
for ri, r in enumerate(rows, 2):
    for ci, (h, _) in enumerate(cols, 1):
        if h == "Tier":
            CV = COL["Evidence coverage"]
            v = f'=IF({DQ}{ri}<>"","Disqualified",IF(AND({CV}{ri}<{SM}!$C$18,C{ri}>={SM}!$C$16),"Research needed",IF(C{ri}>={SM}!$C$14,"A",IF(C{ri}>={SM}!$C$15,"B",IF(C{ri}>={SM}!$C$16,"C","D")))))'
        elif h == "Lead Score":
            v = "=ROUND((" + "+".join(f"{COL[x]}{ri}*{SM}!$C${5 + k}" for k, x in enumerate(SUBS)) + f")/{SM}!$C$11*10,1)"
        elif h == "Evidence coverage":
            v = "=ROUND((" + "+".join(f"{COL[x]}{ri}*{SM}!$C${5 + k}" for k, x in enumerate(EVS)) + f")/{SM}!$C$11,2)"
        else:
            v = r.get(key_of.get(h, h), "")
        c = ws.cell(ri, ci, v); c.font = BASE
        if h in URLCOLS and isinstance(v, str) and v.startswith("http"):
            c.hyperlink = v; c.font = LINK
            if h in ("LinkedIn search", "Impressum"): c.value = "open"
        if h in ("Est. units", "Reviews", "Employees"): c.number_format = "#,##0"
        if h == "Founded": c.number_format = "0"
        if h in SUBS: c.number_format = "0.0"; c.alignment = Alignment(horizontal="center")
        if h == "Evidence coverage": c.number_format = "0%"; c.alignment = Alignment(horizontal="center")
        if h in EVS: c.alignment = Alignment(horizontal="center"); c.font = Font(name=F, size=9, color="7F7F7F")
    ws.cell(ri, 1).font = BOLD
n = len(rows) + 1
last = get_column_letter(len(cols))
ws.freeze_panes = "C2"; ws.auto_filter.ref = f"A1:{last}{n}"
def tier_cf(sheet, ref):
    sheet.conditional_formatting.add(ref, CellIsRule(operator="equal", formula=['"A"'], fill=PatternFill("solid", fgColor="C6EFCE"), font=Font(name=F, bold=True, color="006100")))
    sheet.conditional_formatting.add(ref, CellIsRule(operator="equal", formula=['"B"'], fill=PatternFill("solid", fgColor="DDEBF7"), font=Font(name=F, bold=True, color="1F4E78")))
    sheet.conditional_formatting.add(ref, CellIsRule(operator="equal", formula=['"C"'], fill=PatternFill("solid", fgColor="FFF2CC"), font=Font(name=F, color="7F6000")))
    sheet.conditional_formatting.add(ref, CellIsRule(operator="equal", formula=['"Disqualified"'], fill=PatternFill("solid", fgColor="E7E6E6"), font=Font(name=F, color="595959")))
    sheet.conditional_formatting.add(ref, CellIsRule(operator="equal", formula=['"Research needed"'], fill=PatternFill("solid", fgColor="FCE4D6"), font=Font(name=F, color="833C0B")))
tier_cf(ws, f"B2:B{n}")
ws.conditional_formatting.add(f"C2:C{n}", ColorScaleRule(start_type="num", start_value=15, start_color="F8696B", mid_type="num", mid_value=45, mid_color="FFEB84", end_type="num", end_value=80, end_color="63BE7B"))
ws.conditional_formatting.add(f"{COL[SUBS[0]]}2:{COL[SUBS[-1]]}{n}", ColorScaleRule(start_type="num", start_value=0, start_color="FFFFFF", end_type="num", end_value=10, end_color="9BC2E6"))
ES = COL["Email status"]
ws.conditional_formatting.add(f"{ES}2:{ES}{n}", FormulaRule(formula=[f'LEFT({ES}2,8)="Verified"'], font=Font(name=F, color="006100", bold=True)))
ws.conditional_formatting.add(f"{ES}2:{ES}{n}", FormulaRule(formula=[f'LEFT({ES}2,7)="Invalid"'], font=Font(name=F, color="C00000")))
ws.conditional_formatting.add(f"{ES}2:{ES}{n}", FormulaRule(formula=[f'LEFT({ES}2,10)="Unverified"'], font=Font(name=F, color="9C5700")))

# ======================= Sales view =======================
wv = wb.create_sheet("Sales view", 1)
SV = ["Company", "Tier", "Lead Score", "Evidence coverage", "Why (score rationale)", "Bezirk", "Est. units", "Management type", "Residential focus", "Current metering provider (mentioned)",
      "Software / portal seen", "Associations", "Decision maker", "Role", "Personal email", "Email status", "Phone", "Second contact", "Second contact role", "Sales play", "First touch", "Opener (DE)", "LinkedIn search", "Website"]
SVW = {"Company": 38, "Tier": 11, "Lead Score": 8, "Evidence coverage": 9, "Why (score rationale)": 55, "Bezirk": 22, "Est. units": 9, "Management type": 16, "Residential focus": 11,
       "Current metering provider (mentioned)": 14, "Software / portal seen": 16, "Associations": 12, "Decision maker": 22, "Role": 16, "Personal email": 32, "Email status": 24,
       "Phone": 16, "Second contact": 22, "Second contact role": 20, "Sales play": 13, "First touch": 11, "Opener (DE)": 70, "LinkedIn search": 12, "Website": 30}
sv_rows = [i for i, r in enumerate(rows) if r["_score"] >= TIERS[2] and not r.get("Disqualified reason")]
for j, h in enumerate(SV, 1):
    c = wv.cell(1, j, h); c.font = H_FONT; c.fill = H_FILL; c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    wv.column_dimensions[get_column_letter(j)].width = SVW[h]
wv.row_dimensions[1].height = 40
for k, i in enumerate(sv_rows, 2):
    src = i + 2
    for j, h in enumerate(SV, 1):
        c = wv.cell(k, j, f'=IF(Leads!{COL[h]}{src}="","",Leads!{COL[h]}{src})'); c.font = BOLD if h == "Company" else BASE
        if h in ("LinkedIn search", "Website"):
            url = rows[i].get(h, "")
            if isinstance(url, str) and url.startswith("http"):
                c.value = "open" if h == "LinkedIn search" else url; c.hyperlink = url; c.font = LINK
        if h == "Est. units": c.number_format = "#,##0"
        if h == "Lead Score": c.number_format = "0.0"
        if h == "Evidence coverage": c.number_format = "0%"
wv.freeze_panes = "B2"; wv.auto_filter.ref = f"A1:{get_column_letter(len(SV))}{len(sv_rows) + 1}"
tier_cf(wv, f"B2:B{len(sv_rows) + 1}")

# ======================= Summary =======================
wsS = wb.create_sheet("Summary", 3); wsS.sheet_view.showGridLines = False
wsS["B2"] = "Summary (live formulas over sheet 'Leads')"; wsS["B2"].font = Font(name=F, size=14, bold=True, color="1F3A5F")
def hdrrow(r, labels):
    for i, h in enumerate(labels): c = wsS.cell(r, 2 + i, h); c.font = H_FONT; c.fill = H_FILL
hdrrow(4, ["Tier", "Companies", "with decision maker", "with Verified/Probable email", "Avg. score"])
L = rng("Tier")
for i, t in enumerate(["A", "B", "C", "Research needed", "D", "Disqualified"]):
    r = 5 + i
    wsS.cell(r, 2, t).font = BOLD
    wsS.cell(r, 3, f'=COUNTIF({L},"{t}")')
    wsS.cell(r, 4, f'=COUNTIFS({L},"{t}",{rng("Decision maker")},"?*")')
    wsS.cell(r, 5, f'=COUNTIFS({L},"{t}",{rng("Email status")},"Verified*")+COUNTIFS({L},"{t}",{rng("Email status")},"Probable*")')
    wsS.cell(r, 6, f'=IFERROR(AVERAGEIF({L},"{t}",{rng("Lead Score")}),0)').number_format = "0.0"
wsS.cell(11, 2, "Total").font = BOLD
for col in "CDE": wsS[f"{col}11"] = f"=SUM({col}5:{col}10)"; wsS[f"{col}11"].font = BOLD
hdrrow(12, ["Bezirk", "Companies", "Tier A", "Tier B", "Avg. score"])
bez = [b for b, _ in collections.Counter(r["Bezirk"] or "(unknown)" for r in rows).most_common()]
for i, b in enumerate(bez):
    r = 13 + i
    wsS.cell(r, 2, b)
    crit = '""' if b == "(unknown)" else f'"{b}"'
    wsS.cell(r, 3, f'=COUNTIF({rng("Bezirk")},{crit})')
    wsS.cell(r, 4, f'=COUNTIFS({rng("Bezirk")},{crit},{L},"A")')
    wsS.cell(r, 5, f'=COUNTIFS({rng("Bezirk")},{crit},{L},"B")')
    wsS.cell(r, 6, f'=IFERROR(AVERAGEIF({rng("Bezirk")},{crit},{rng("Lead Score")}),0)').number_format = "0.0"
r = 13 + len(bez) + 1
hdrrow(r, ["Data coverage", "Companies", "Share"]); r += 1
cov = [("Website crawled successfully", f'=COUNTIF({rng("Website status")},"ok")'),
       ("AI-extracted (Claude, grounded)", f'=COUNTIF({rng("Data basis")},"*AI*")'),
       ("VDIV Berlin-Brandenburg members (directory)", f'=COUNTIF({rng("VDIV member (directory)")},"Yes")'),
       ("Evidence coverage ≥ min. threshold", f'=COUNTIF({rng("Evidence coverage")},">="&{SM}!$C$18)'),
       ("Decision maker identified", f'=COUNTIF({rng("Decision maker")},"?*")'),
       ("Second contact (WEG/rental lead, technical PM)", f'=COUNTIF({rng("Second contact")},"?*")'),
       ("Email – Verified (published)", f'=COUNTIF({rng("Email status")},"Verified*")'), ("Email – Probable (company pattern)", f'=COUNTIF({rng("Email status")},"Probable*")'),
       ("Email – Unverified (default pattern)", f'=COUNTIF({rng("Email status")},"Unverified*")'), ("Email – Invalid domain (no MX)", f'=COUNTIF({rng("Email status")},"Invalid*")'),
       ("Company LinkedIn/Xing page found", f'=COUNTIF({rng("Company social")},"?*")'),
       ("Units stated on website", f'=COUNTIF({rng("Size basis")},"Units stated")'), ("VDIV members", f'=COUNTIF({rng("Associations")},"*VDIV*")'),
       ("Incumbent metering provider known", f'=COUNTIF({rng("Current metering provider (mentioned)")},"?*")'),
       ("Property software / portal known", f'=COUNTIF({rng("Software / portal seen")},"?*")')]
for lab, f in cov:
    wsS.cell(r, 2, lab); wsS.cell(r, 3, f); c = wsS.cell(r, 4, f"=C{r}/{len(rows)}"); c.number_format = "0%"; r += 1
for col, wdt in zip("ABCDEF", (3, 44, 12, 20, 26, 12)): wsS.column_dimensions[col].width = wdt
for row in wsS.iter_rows(min_row=4, max_row=r):
    for c in row:
        if c.value is not None and c.font != H_FONT and not c.font.bold: c.font = BASE

# ======================= Sources & Method =======================
wq = wb.create_sheet("Sources & Method"); wq.sheet_view.showGridLines = False
wq["B2"] = "Sources, automation and validation"; wq["B2"].font = Font(name=F, size=14, bold=True, color="1F3A5F")
for i, h in enumerate(["Step", "What", "Result"]): c = wq.cell(4, 2 + i, h); c.font = H_FONT; c.fill = H_FILL
for i, (a, b, cc) in enumerate(stats["steps"]):
    wq.cell(5 + i, 2, a).font = BOLD
    for j, v in enumerate((b, cc)): c = wq.cell(5 + i, 3 + j, v); c.font = BASE; c.alignment = WRAP
    wq.row_dimensions[5 + i].height = 46
for col, wdt in zip("ABCD", (3, 28, 80, 48)): wq.column_dimensions[col].width = wdt

# ======================= Contacts =======================
from openpyxl.chart import BarChart, Reference
wc = wb.create_sheet("Contacts", 3)
CH = [("Company", 38), ("Tier", 11), ("Name", 26), ("Role", 30), ("Role category", 22), ("Email", 34), ("Email status", 30), ("Phone (company)", 16),
      ("LinkedIn search", 12), ("Source URL", 40), ("Verified on", 11)]
for j, (h, wdt) in enumerate(CH, 1):
    c = wc.cell(1, j, h); c.font = H_FONT; c.fill = H_FILL; c.alignment = Alignment(wrap_text=True, vertical="center")
    wc.column_dimensions[get_column_letter(j)].width = wdt
k = 2
for i, r in enumerate(rows):
    for p in r.get("_contacts") or []:
        li = "https://www.linkedin.com/search/results/people/?keywords=" + (p["Name"] + " " + r["Company"]).replace(" ", "%20")
        vals = [r["Company"], f"=Leads!B{i + 2}", p["Name"], p["Role"], p["Role category"], p["Email"], p["Email status"], r.get("Phone", ""), "open", p["Source"], "2026-11-06"]
        for j, v in enumerate(vals, 1):
            c = wc.cell(k, j, v); c.font = BASE
        wc.cell(k, 9).hyperlink = li; wc.cell(k, 9).font = LINK
        if str(p["Source"]).startswith("http"): wc.cell(k, 10).hyperlink = p["Source"]; wc.cell(k, 10).font = LINK
        k += 1
wc.freeze_panes = "C2"; wc.auto_filter.ref = f"A1:{get_column_letter(len(CH))}{max(k - 1, 2)}"
tier_cf(wc, f"B2:B{max(k - 1, 2)}")
N_CONTACTS = k - 2

# ======================= Evidence =======================
we2 = wb.create_sheet("Evidence", 4)
EH = [("Company", 38), ("Field", 22), ("Value", 30), ("Source URL", 40), ("Evidence (quote / note)", 70), ("Confidence", 28), ("Date", 11)]
for j, (h, wdt) in enumerate(EH, 1):
    c = we2.cell(1, j, h); c.font = H_FONT; c.fill = H_FILL
    we2.column_dimensions[get_column_letter(j)].width = wdt
k = 2
for r in rows:
    for e in r.get("_evidence") or []:
        vals = [r["Company"], e["Field"], e["Value"], e["Source URL"], e["Evidence"], e["Confidence"], "2026-11-06"]
        for j, v in enumerate(vals, 1): c = we2.cell(k, j, v); c.font = BASE
        if str(e["Source URL"]).startswith("http"): we2.cell(k, 4).hyperlink = e["Source URL"]; we2.cell(k, 4).font = LINK
        k += 1
we2.freeze_panes = "B2"; we2.auto_filter.ref = f"A1:G{max(k - 1, 2)}"
N_EVIDENCE = k - 2

# ======================= Summary charts =======================
ch1 = BarChart(); ch1.type = "bar"; ch1.style = 10; ch1.title = "Companies by tier"; ch1.y_axis.title = None; ch1.legend = None
ch1.add_data(Reference(wsS, min_col=3, min_row=4, max_row=10), titles_from_data=True); ch1.set_categories(Reference(wsS, min_col=2, min_row=5, max_row=10))
ch1.height = 7.5; ch1.width = 15
wsS.add_chart(ch1, "H4")
nb = min(len(bez), 13)
ch2 = BarChart(); ch2.type = "bar"; ch2.grouping = "stacked"; ch2.overlap = 100; ch2.style = 10; ch2.title = "Tier A and B leads by Bezirk"
ch2.add_data(Reference(wsS, min_col=4, max_col=5, min_row=12, max_row=12 + nb), titles_from_data=True); ch2.set_categories(Reference(wsS, min_col=2, min_row=13, max_row=12 + nb))
ch2.height = 10; ch2.width = 15
wsS.add_chart(ch2, "H21")

# ======================= QA sample =======================
for qa_file, qa_tab, qa_pos in (("qa_verdicts.json", "QA round 1", 5), ("qa2_verdicts.json", "QA round 2", 6)):
  qa_path = os.path.join(os.path.dirname(BUILT), qa_file)
  if os.path.exists(qa_path):
      qa = json.load(open(qa_path, encoding="utf8"))
      wq2 = wb.create_sheet(qa_tab, qa_pos); wq2.sheet_view.showGridLines = False
      wq2["A1"] = f"{qa_tab}: {len(qa['rows'])} random leads re-checked against the live websites"; wq2["A1"].font = Font(name=F, size=14, bold=True, color="1F3A5F")
      c = wq2["A2"]; c.value = qa["method"]; c.font = Font(name=F, size=10, italic=True); c.alignment = WRAP
      wq2.merge_cells("A2:M2"); wq2.row_dimensions[2].height = 62
      QH = [("#", 4), ("Tier at QA", 13), ("Company", 34), ("Website checked", 28), ("Identity", 9), ("Postcode", 9), ("Decision maker", 10), ("Mgmt type", 10),
            ("Units", 8), ("E-mail label", 10), ("Tier plausible", 10), ("Finding", 70), ("After fix", 55)]
      FIELDS = [("Identity", "id"), ("Postcode", "plz"), ("Decision maker", "dm"), ("Mgmt type", "type"), ("Units", "units"), ("E-mail label", "email"), ("Tier plausible", "tierok")]
      # summary block (live formulas over the verdict rows)
      top = 4; first = top + len(FIELDS) + 4; last = first + len(qa["rows"]) - 1
      for j, h in enumerate(["Field", "Correct (✓)", "Wrong (✗)", "Accuracy", "Not checkable"], 1):
          c = wq2.cell(top, j + 2, h); c.font = H_FONT; c.fill = H_FILL
      for i, (lab, _) in enumerate(FIELDS):
          r = top + 1 + i; col = get_column_letter(5 + i)
          wq2.cell(r, 3, lab).font = BOLD
          wq2.cell(r, 4, f'=COUNTIF({col}{first}:{col}{last},"✓")').font = BASE
          wq2.cell(r, 5, f'=COUNTIF({col}{first}:{col}{last},"✗")').font = BASE
          c = wq2.cell(r, 6, f'=IFERROR(D{r}/(D{r}+E{r}),"")'); c.number_format = "0%"; c.font = BOLD
          wq2.cell(r, 7, f'=COUNTIF({col}{first}:{col}{last},"n.c.")').font = BASE
      for j, (h, wdt) in enumerate(QH, 1):
          c = wq2.cell(first - 1, j, h); c.font = H_FONT; c.fill = H_FILL; c.alignment = Alignment(wrap_text=True, vertical="center")
          wq2.column_dimensions[get_column_letter(j)].width = wdt
      for k, q in enumerate(qa["rows"]):
          r = first + k
          vals = [q["n"], q["tier"], q["company"], q["site"]] + [q[f] for _, f in FIELDS] + [q["finding"], q["after"]]
          for j, v in enumerate(vals, 1):
              c = wq2.cell(r, j, v); c.font = BASE; c.alignment = Alignment(wrap_text=j >= 12, vertical="top", horizontal="center" if 5 <= j <= 11 else None)
          wq2.cell(r, 4).hyperlink = q["site"]; wq2.cell(r, 4).font = LINK
          wq2.row_dimensions[r].height = 44
      rng_v = f"E{first}:K{last}"
      wq2.conditional_formatting.add(rng_v, CellIsRule(operator="equal", formula=['"✓"'], font=Font(name=F, color="006100", bold=True), fill=PatternFill("solid", fgColor="E2EFDA")))
      wq2.conditional_formatting.add(rng_v, CellIsRule(operator="equal", formula=['"✗"'], font=Font(name=F, color="C00000", bold=True), fill=PatternFill("solid", fgColor="FCE4D6")))
      r = last + 2
      wq2.cell(r, 3, "Residual issues (not fixed)").font = BOLD
      for i, t in enumerate(qa["residuals"]):
          c = wq2.cell(r + 1 + i, 3, "• " + t); c.font = BASE
      wq2.freeze_panes = wq2.cell(first, 4)

# ======================= Excluded =======================
we = wb.create_sheet("Excluded")
for i, h in enumerate(["Company", "Reason", "Website", "Sources"], 1):
    c = we.cell(1, i, h); c.font = H_FONT; c.fill = H_FILL
for ri, e in enumerate(excluded, 2):
    for ci, k in enumerate(["Company", "Reason", "Website", "Sources"], 1): we.cell(ri, ci, e[k]).font = BASE
for col, wdt in zip("ABCD", (50, 60, 35, 30)): we.column_dimensions[col].width = wdt

wb.calculation.fullCalcOnLoad = True
wb.save(OUT)
print("saved", OUT, len(rows), "rows; tiers (py):", collections.Counter("A" if r["_score"] >= TIERS[0] else "B" if r["_score"] >= TIERS[1] else "C" if r["_score"] >= TIERS[2] else "D" for r in rows))
