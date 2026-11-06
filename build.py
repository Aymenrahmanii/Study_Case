"""Build final lead table (KPIs + sub-scores) and write the Excel workbook."""
import json, re, sys, os, collections, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import looks_personal, clean_person, is_generic, email_matches_person, infer_pattern, build_email, nkey, de_ascii
from urllib.parse import urlparse

ENR, JAC, LI, OUTX, OUTJ = sys.argv[1:6]
comps = json.load(open(ENR, encoding="utf8"))
jac = json.load(open(JAC, encoding="utf8"))
li = json.load(open(LI, encoding="utf8")) if os.path.exists(LI) else {}
TODAY = datetime.date(2026, 11, 6)
AI_DIR = os.path.join(os.path.dirname(ENR), "ai"); MX_F = os.path.join(os.path.dirname(ENR), "mx.json")
AI = {}
if os.path.isdir(AI_DIR):
    for f_ in os.listdir(AI_DIR):
        rec_ = json.load(open(os.path.join(AI_DIR, f_), encoding="utf8"))
        AI[urlparse(rec_["_website"]).netloc.lower().replace("www.", "")] = rec_
MX = json.load(open(MX_F, encoding="utf8")) if os.path.exists(MX_F) else {}
UX_F = os.path.join(os.path.dirname(ENR), "units_extra.json")
UX = json.load(open(UX_F, encoding="utf8")) if os.path.exists(UX_F) else {}
MAN_F = os.path.join(os.path.dirname(ENR), "manual_contacts.json")
MANUAL = {k: v for k, v in (json.load(open(MAN_F, encoding="utf8")) if os.path.exists(MAN_F) else {}).items() if not k.startswith("_")}
LEGAL_RE = r"GmbH|mbH|\bKG\b|e\.\s?K\.|\bUG\b|\bAG\b|GbR|OHG|eG\b|e\.G\.|Ges\.\s?mbH"
def clean_company(raw, c):
    """Display name: VDIV's official name if listed, else the directory name without appended contact persons / category words."""
    if c.get("vdiv") and c["vdiv"].get("name"): n = c["vdiv"]["name"]
    else: n = raw
    n = " ".join(n.split())
    n = re.sub(r"\s*,\s*(Inh\.\s*)?[A-ZÄÖÜ][a-zäöüß-]+(\s+[A-ZÄÖÜ][a-zäöüß.-]+){1,2}$", "", n)          # ", Hubert Hauke-Nils"
    m = re.search(r"(" + LEGAL_RE + r")(\s*&\s*Co\.?\s*KG)?", n)
    if m and m.end() < len(n):
        tail = n[m.end():].strip(" ,-")
        if re.fullmatch(r"(Hausverwaltung(en)?|Immobilien(verwaltung)?|Verwaltung|Hausverwaltung und Immobilien(service)?|Immobilienbetreuung|Grundstücksverwaltung)", tail, re.I):
            n = n[:m.end()]
    return n.strip(" ,")
print("AI records", len(AI), "MX domains", len(MX))

# ---------- attach LinkedIn results ----------
for k, v in li.items(): comps[int(k)]["_li"] = v

if not any(c.get("jac") for c in comps):
    raise SystemExit("run merge_jacasa.py first")
# ---------- PLZ -> district map from data ----------
BEZ = {"Mitte", "Friedrichshain-Kreuzberg", "Pankow", "Charlottenburg-Wilmersdorf", "Spandau", "Steglitz-Zehlendorf", "Tempelhof-Schöneberg", "Neukölln", "Treptow-Köpenick",
       "Marzahn-Hellersdorf", "Lichtenberg", "Reinickendorf"}
ORTSTEIL2BEZ = {"Mitte": "Mitte", "Tiergarten": "Mitte", "Wedding": "Mitte", "Moabit": "Mitte", "Gesundbrunnen": "Mitte", "Hansaviertel": "Mitte",
    "Friedrichshain": "Friedrichshain-Kreuzberg", "Kreuzberg": "Friedrichshain-Kreuzberg", "Prenzlauer Berg": "Pankow", "Pankow": "Pankow", "Weißensee": "Pankow",
    "Niederschönhausen": "Pankow", "Buch": "Pankow", "Französisch Buchholz": "Pankow", "Heinersdorf": "Pankow", "Karow": "Pankow", "Blankenburg": "Pankow", "Rosenthal": "Pankow", "Wilhelmsruh": "Pankow", "Blankenfelde": "Pankow",
    "Charlottenburg": "Charlottenburg-Wilmersdorf", "Wilmersdorf": "Charlottenburg-Wilmersdorf", "Schmargendorf": "Charlottenburg-Wilmersdorf", "Grunewald": "Charlottenburg-Wilmersdorf", "Halensee": "Charlottenburg-Wilmersdorf", "Westend": "Charlottenburg-Wilmersdorf", "Charlottenburg-Nord": "Charlottenburg-Wilmersdorf",
    "Spandau": "Spandau", "Siemensstadt": "Spandau", "Staaken": "Spandau", "Gatow": "Spandau", "Kladow": "Spandau", "Hakenfelde": "Spandau", "Haselhorst": "Spandau", "Wilhelmstadt": "Spandau", "Falkenhagener Feld": "Spandau",
    "Steglitz": "Steglitz-Zehlendorf", "Zehlendorf": "Steglitz-Zehlendorf", "Lichterfelde": "Steglitz-Zehlendorf", "Lankwitz": "Steglitz-Zehlendorf", "Dahlem": "Steglitz-Zehlendorf", "Nikolassee": "Steglitz-Zehlendorf", "Wannsee": "Steglitz-Zehlendorf",
    "Tempelhof": "Tempelhof-Schöneberg", "Schöneberg": "Tempelhof-Schöneberg", "Friedenau": "Tempelhof-Schöneberg", "Mariendorf": "Tempelhof-Schöneberg", "Marienfelde": "Tempelhof-Schöneberg", "Lichtenrade": "Tempelhof-Schöneberg",
    "Neukölln": "Neukölln", "Britz": "Neukölln", "Buckow": "Neukölln", "Rudow": "Neukölln", "Gropiusstadt": "Neukölln",
    "Köpenick": "Treptow-Köpenick", "Treptow": "Treptow-Köpenick", "Alt-Treptow": "Treptow-Köpenick", "Adlershof": "Treptow-Köpenick", "Johannisthal": "Treptow-Köpenick", "Baumschulenweg": "Treptow-Köpenick", "Niederschöneweide": "Treptow-Köpenick", "Oberschöneweide": "Treptow-Köpenick", "Grünau": "Treptow-Köpenick", "Friedrichshagen": "Treptow-Köpenick", "Altglienicke": "Treptow-Köpenick", "Bohnsdorf": "Treptow-Köpenick", "Müggelheim": "Treptow-Köpenick", "Rahnsdorf": "Treptow-Köpenick", "Plänterwald": "Treptow-Köpenick", "Schmöckwitz": "Treptow-Köpenick",
    "Marzahn": "Marzahn-Hellersdorf", "Hellersdorf": "Marzahn-Hellersdorf", "Biesdorf": "Marzahn-Hellersdorf", "Kaulsdorf": "Marzahn-Hellersdorf", "Mahlsdorf": "Marzahn-Hellersdorf",
    "Lichtenberg": "Lichtenberg", "Hohenschönhausen": "Lichtenberg", "Alt-Hohenschönhausen": "Lichtenberg", "Neu-Hohenschönhausen": "Lichtenberg", "Karlshorst": "Lichtenberg", "Friedrichsfelde": "Lichtenberg", "Rummelsburg": "Lichtenberg", "Fennpfuhl": "Lichtenberg", "Falkenberg": "Lichtenberg", "Malchow": "Lichtenberg", "Wartenberg": "Lichtenberg",
    "Reinickendorf": "Reinickendorf", "Tegel": "Reinickendorf", "Wittenau": "Reinickendorf", "Hermsdorf": "Reinickendorf", "Frohnau": "Reinickendorf", "Heiligensee": "Reinickendorf", "Konradshöhe": "Reinickendorf", "Waidmannslust": "Reinickendorf", "Lübars": "Reinickendorf", "Märkisches Viertel": "Reinickendorf", "Borsigwalde": "Reinickendorf"}
def bezirk_of(dist):
    if not dist: return ""
    d = dist.replace("Berlin", "").strip(" ,-()")
    for k in sorted(ORTSTEIL2BEZ, key=len, reverse=True):
        if k.lower() in d.lower(): return ORTSTEIL2BEZ[k]
    return ""
plz_votes = collections.defaultdict(collections.Counter)
for c in comps:
    b = bezirk_of(c.get("district", ""))
    if b and c.get("plz"): plz_votes[c["plz"]][b] += 1
def bezirk(c):
    return bezirk_of(c.get("district", "")) or (plz_votes[c["plz"]].most_common(1)[0][0] if c.get("plz") in plz_votes else "")

# ---------- relevance / exclusion ----------
EXCL_NAME = r"\bERGO\b|\bAXA\b|Allianz|\bHUK\b|\bDEVK\b|Generali|Signal Iduna|Debeka|\bLVM\b|Provinzial|Sozialdemokratische|Partei|Bäckerei|Notar|Rechtsanw|Steuerberat|Versicherung|Bank\b|Sparkasse|Architekt|Reinigung|Hausmeister|Funk Notruf|Schlüsseldienst|Weberei|Pharma|Verlag|Stiftung(?!.*verwalt)|Marketing|Software|Fußb|Umzug"
EXCL_CAT = {"Bäckereien", "Notare", "Versicherungen", "Banken", "Webereien", "Pharmazeutische Erzeugnisse", "Verlage", "Software", "Fußböden", "Marketingservice",
            "Reinigungsbetriebe", "Wasch- und Reinigungsmittel", "Architektur", "Ingenieurbüros", "Finanzberatung und -vermittlung", "Altersvorsorge", "Vereine", "Hausmeisterdienste", "Bauunternehmen", "Haustechnik", "Unternehmensberatung"}

BIG_LANDLORDS = r"Vonovia|Deutsche Wohnen|degewo|Gewobag|HOWOGE|GESOBAU|Stadt und Land|WBM|berlinovo|Adler Group|Grand City|Heimstaden|Covivio|Akelius|BImA|Bundesanstalt"

# ---------- websites that are portal/directory pages, not the company's own site ----------
PORTALS = r"immobilienscout24|immowelt|immonet|ebay|kleinanzeigen|facebook|instagram|google\.|linkedin|xing|gelbeseiten|dasoertliche|jacasa|11880|yelp|ergo\.de|allianz\.de|wix\.com/?$|t-online\.de/?$|meinestadt|branchen"
MISMATCH_RE = r"\bdomain\b|hosting|web ?design|wordpress agency|under (renovation|construction)|marketplace|registrar|official capital city portal|parked|automotive|import consulting|law firm and notary|cinema operator|surgical clinic|suspended metal ceiling|event locations"
MISMATCH = {d for d, a in AI.items() if re.search(MISMATCH_RE, a.get("summary") or "", re.I)}
print("websites belonging to another business (AI):", len(MISMATCH))
TEXT_DIR = os.path.join(os.path.dirname(ENR), "texts")
GENERIC_NAME = {"hausverwaltung", "hausverwaltungen", "immobilien", "immobilienverwaltung", "verwaltung", "grundstuecksverwaltung", "grundbesitz", "grundbesitzverwaltung",
                "gesellschaft", "berlin", "management", "property", "service", "services", "gmbh", "haus", "grundstuecks", "und", "fuer", "real", "estate", "group", "partner",
                "verwaltungs", "verwaltungsgesellschaft", "wohnungsverwaltung", "immobilienservice", "beteiligungsgesellschaft", "dienstleistungs", "consulting", "projekt"}
def site_text(u):
    k = re.sub(r"[^a-z0-9]+", "_", urlparse(u).netloc.lower()).strip("_")[:60]
    p_ = os.path.join(TEXT_DIR, k + ".json")
    return de_ascii(" ".join(json.load(open(p_, encoding="utf8"))["pages"].values())) if os.path.exists(p_) else None
def name_on_site(c):
    u_ = c.get("final_url") or c.get("website") or ""
    t_ = site_text(u_)
    if t_ is None: t_ = de_ascii((c.get("home_title") or "") + " " + (c.get("snippet") or ""))
    if len(t_) < 80: return True   # too little text to judge
    dom_ = de_ascii(urlparse(u_).netloc)
    names = [c["name"]] + c.get("names_seen", []) + ([c["vdiv"]["name"]] if c.get("vdiv") else []) + ([c["jac"]["name"]] if c.get("jac") else [])
    toks = {w for n in names for w in re.findall(r"[a-z0-9]{3,}", de_ascii(n)) if w not in GENERIC_NAME and not w.isdigit()}
    core = nkey(c["name"])
    if len(core) >= 2 and core in re.sub(r"[^a-z0-9]", "", dom_): return True
    return (not toks) or any(w in t_ or w in dom_ for w in toks)
for c in comps:
    d_ = urlparse(c.get("final_url") or c.get("website") or "").netloc.lower().replace("www.", "")
    if d_ and d_ in MISMATCH and c.get("crawl_status") == "ok":
        for k in ("people", "emails", "kw", "units", "employees", "software_mentions", "metering_mentions", "register", "impressum_url", "final_url", "domain_final", "socials"): c.pop(k, None)
        c["crawl_status"] = "listed website belongs to another business"; c["website"] = ""; c["domain"] = ""; c["email_dir"] = ""
        continue
    for f in ("website", "final_url", "domain_final"):
        if c.get(f) and re.search(PORTALS, c[f], re.I):
            for k in ("people", "emails", "kw", "units", "employees", "software_mentions", "metering_mentions", "register", "impressum_url", "final_url", "domain_final", "socials"): c.pop(k, None)
            c["crawl_status"] = "no own website (portal page listed)"; c["website"] = ""; c["domain"] = ""
            break
# ---------- de-duplicate by final website domain ----------
byd = {}
merged_comps = []
for c in comps:
    d = (c.get("domain_final") or "").replace("www.", "") if c.get("crawl_status") == "ok" else ""
    if d and d in byd:
        keep = byd[d]
        for s_ in c.get("sources", []):
            if s_ not in keep["sources"]: keep["sources"].append(s_)
        keep.setdefault("alias", []).append(c["name"])
        if not keep.get("jac") and c.get("jac"): keep["jac"] = c["jac"]
        if not keep.get("vdiv") and c.get("vdiv"): keep["vdiv"] = c["vdiv"]
        if not keep.get("phone"): keep["phone"] = c.get("phone", "")
        continue
    if d: byd[d] = c
    merged_comps.append(c)
print("dedup by domain removed", len(comps) - len(merged_comps))
comps = merged_comps
# second key: normalised name + postcode (VDIV lists some firms once per contact person)
byn, merged2 = {}, []
for c in comps:
    k = nkey(c["name"]) if len(nkey(c["name"])) >= 6 else nkey(c["name"]) + (c.get("plz") or "")
    if len(nkey(c["name"])) >= 4 and k in byn:
        keep = byn[k]
        if c.get("vdiv"):
            if keep.get("vdiv"): keep.setdefault("vdiv_more", []).append(c["vdiv"])
            else: keep["vdiv"] = c["vdiv"]
        for s_ in c.get("sources", []):
            if s_ not in keep["sources"]: keep["sources"].append(s_)
        if keep.get("crawl_status") != "ok" and c.get("crawl_status") == "ok":
            for f_ in c:
                if f_ not in ("sources", "vdiv", "vdiv_more", "jac"): keep[f_] = c[f_]
        if not keep.get("jac") and c.get("jac"): keep["jac"] = c["jac"]
        continue
    byn[k] = c; merged2.append(c)
print("dedup by name+postcode removed", len(comps) - len(merged2))
comps = merged2
rows, excluded = [], []
for c in comps:
    k = c.get("kw", {}) or {}
    name = c["name"]
    cats = set(c.get("categories", []))
    reason = ""
    if re.search(EXCL_NAME, name, re.I) and not re.search(r"verwalt", name, re.I): reason = "Name indicates non-property-management business"
    elif cats and cats <= EXCL_CAT and not re.search(r"verwalt", name, re.I) and not (k.get("weg") or k.get("miet")): reason = "Directory category not property management (" + ", ".join(cats) + ")"
    if reason:
        excluded.append({"Company": name, "Reason": reason, "Website": c.get("website", ""), "Sources": ", ".join(c.get("sources", []))}); continue
    rows.append(c)
print("rows", len(rows), "excluded", len(excluded))

# ---------- KPI derivation ----------
def kw(c, key): return (c.get("kw") or {}).get(key, 0)

def legal_form(name, reg):
    n = name + " " + (reg or "")
    for pat, lab in [(r"GmbH\s*&\s*Co\.?\s*KG", "GmbH & Co. KG"), (r"\bAG\b", "AG"), (r"GmbH|mbH", "GmbH"), (r"\bUG\b", "UG"), (r"\bKG\b", "KG"), (r"oHG|OHG", "OHG"), (r"e\.\s?K\.", "e.K."), (r"GbR", "GbR")]:
        if re.search(pat, n): return lab
    if reg.startswith("HRB"): return "GmbH/AG (HRB)"
    if reg.startswith("HRA"): return "Personengesellschaft/e.K. (HRA)"
    return "Einzelunternehmen / unbekannt"

out = []
for idx, c in enumerate(rows):
    k = c.get("kw") or {}
    ok = c.get("crawl_status") == "ok"
    j = c.get("jac") or {}
    name = re.sub(r"\s+,\s+", ", ", " ".join(c["name"].split()))
    # --- management type ---
    types = []
    if kw(c, "weg"): types.append("WEG")
    if kw(c, "miet"): types.append("Miet")
    if kw(c, "sev"): types.append("SEV")
    if kw(c, "gewerbe"): types.append("Gewerbe")
    if re.search(r"WEG|Wohnungseigentum", name): types.append("WEG") if "WEG" not in types else None
    makler_heavy = kw(c, "makler") >= 3 and not (kw(c, "weg") or kw(c, "miet"))
    if re.search(BIG_LANDLORDS, name, re.I): segment = "Large landlord / housing company"
    elif re.search(r"Grundstücksgemeinschaft|Grundstücksgesellschaft .* GbR|Erbengemeinschaft|^GbR|\bGbR\b", name) and not re.search(r"verwalt", name, re.I): segment = "Property-owning entity (Objektgesellschaft)"
    elif makler_heavy: segment = "Broker-led (Makler + Verwaltung)"
    elif types or re.search(r"verwalt|Hausverw|Property|Immobilienservice", name, re.I) or "Haus- und Grundstücksverwaltungen" in c.get("categories", []): segment = "Property manager (Hausverwaltung)"
    else: segment = "Real-estate company (unclear focus)"
    # --- size ---
    units = c.get("units") if ok else None
    rejected_units = set()
    u_val = units["value"] if units and 10 <= units["value"] <= 40000 else None
    if u_val:
        ev = units.get("evidence", "")
        num_txt = f"{u_val:,}".replace(",", ".")
        pos = ev.find(num_txt) if num_txt in ev else ev.find(str(u_val))
        after = ev[pos: pos + len(num_txt) + 35] if pos >= 0 else ""
        before = ev[max(0, pos - 45): pos] if pos >= 0 else ""
        if re.search(r"verkauft|vermittelt|gebaut|modernisiert|saniert|vermietet|errichtet|projektiert", after, re.I) or re.search(r"nicht mehr als|höchstens|maximal|pro Verwalter|je Verwalter|pro Mitarbeiter", before + after, re.I): rejected_units.add(u_val); u_val = None
    u_kind = units["kind"] if units else ""
    if u_val and re.match(r"(Objekt|Liegen|WEG|Eigent|Häus|Immob|Gebäu)", u_kind):
        u_est = u_val * 12  # ~12 units per building / WEG (Berlin multi-family average assumption)
        u_note = f"{u_val} {u_kind} stated → ≈{u_est} units (×12 per building)"
    elif u_val:
        u_est = u_val; u_note = f"{u_val} {u_kind} stated on website"
    else: u_est = None; u_note = ""
    emp = c.get("employees") or (int(j["jacasa_employees"]) if j.get("jacasa_employees") else None)
    if emp and (emp > 1500 or 1900 <= emp <= 2100): emp = None
    emp_src = "website" if c.get("employees") else ("Jacasa" if j.get("jacasa_employees") else "")
    if not u_est and emp:
        u_est_emp = emp * 150  # assumption: ~150 units per FTE in residential management
    else: u_est_emp = None
    reviews = max([int(x) for x in [re.sub(r"\D", "", c.get("gs_reviews") or "") or 0, j.get("jacasa_reviews") or 0] if str(x).isdigit()] or [0])
    size_basis = ""
    if u_est: size_basis = "Buildings stated (×12 estimate)" if re.match(r"(Objekt|Liegen|WEG|Eigent|Häus|Immob|Gebäu)", u_kind or "") else "Units stated"; size_units = u_est
    elif u_est_emp: size_basis = f"Estimated from {emp} employees ({emp_src}) × 150 units/FTE"; size_units = u_est_emp
    else: size_units = None
    lf = legal_form(name, c.get("register", ""))
    if size_units:
        size_class = "XL (>5,000)" if size_units > 5000 else "L (1,000–5,000)" if size_units >= 1000 else "M (300–999)" if size_units >= 300 else "S (<300)"
    else:
        # proxy: legal form, website depth, reviews
        pts = (2 if lf.startswith(("GmbH", "AG", "UG")) else 0) + (1 if ok and c.get("text_len", 0) > 6000 else 0) + (1 if reviews >= 20 else 0) + (1 if kw(c, "karriere") else 0)
        size_class = "M (300–999) – proxy" if pts >= 4 else "S–M – proxy" if pts >= 2 else "S (<300) – proxy"
        size_basis = "Proxy: legal form, website depth, review count, hiring"
    # --- founded ---
    founded = c.get("founded") if ok else None
    if not founded and j.get("jacasa_years"): founded = 2026 - int(j["jacasa_years"])
    if founded and (founded < 1900 or founded > 2026): founded = None
    # --- associations ---
    assoc = []
    if kw(c, "vdiv"): assoc.append("VDIV")
    if kw(c, "bvi"): assoc.append("BVI")
    if kw(c, "ivd") or "IVD" in (j.get("jacasa_membership") or ""): assoc.append("IVD")
    if kw(c, "hug"): assoc.append("Haus & Grund")
    if kw(c, "bfw"): assoc.append("BFW")
    # --- digital ---
    sw = c.get("software_mentions", []) if ok else []
    portal = ok and bool(re.search(r"portal|App|casavi|facilioo|immoware|ETG24|Allthings", " ".join(sw), re.I) or kw(c, "portal") >= 2)
    dig = 0
    if ok: dig += 1
    if ok and c.get("https"): dig += 0.5
    if portal or sw: dig += 1
    if ok and c.get("text_len", 0) > 8000: dig += 0.5
    dig = min(3, dig)
    dig_label = ["None (no website)", "Basic website", "Website + portal/software", "Digital-first"][int(round(dig))] if dig else "None (no website)"
    if c.get("crawl_status") == "website unreachable": dig_label = "Website listed but unreachable"
    # --- metering relevance ---
    meter = c.get("metering_mentions", []) if ok else []
    meter = [m for m in meter if m not in ("Lorenz", "Engelmann") or kw(c, "hk")]  # device makers only count with heating context
    meter = sorted(set("Kalo" if m in ("KALO", "Kalo", "Kalorimeta") else m for m in meter if m != "Wärmemessdienst"))
    hk = ok and (kw(c, "hk") > 0)
    rwm = ok and kw(c, "rwm") > 0
    funk = ok and kw(c, "fernablesung") > 0
    # --- hiring ---
    hiring = ok and (c.get("has_karriere_page") or kw(c, "karriere") >= 2)
    # --- people & email ---
    people = []
    ctx_ = de_ascii(" ".join((c.get("emails") or []) + [c.get("domain_final") or "", name]))
    for n, role in (c.get("people") or []):
        cn = clean_person(n, ctx_)
        if cn and cn not in [p[0] for p in people]: people.append((cn, role))
    dm, dm_role = (people[0] if people else ("", ""))
    domain = (c.get("domain_final") or c.get("domain") or "").replace("www.", "")
    base_dom = ".".join(domain.split(".")[-2:]) if domain.count(".") >= 1 else domain
    emails = [e for e in (c.get("emails") or []) if "@" in e and base_dom and e.split("@")[1].endswith(base_dom)] if ok else []
    # also keep company e-mails on a different own domain if they contain a person's last name
    if ok:
        for e in (c.get("emails") or []):
            if "@" in e and e not in emails and not re.search(r"gmail|web\.de|gmx|t-online|yahoo|hotmail|outlook|freenet|arcor|aol", e) and any(email_matches_person(e, clean_person(p[0])) for p in (c.get("people") or [])):
                emails.append(e)
    if c.get("email_dir") and c["email_dir"].lower() not in emails: emails.append(c["email_dir"].lower())
    all_people = [p[0] for p in people]
    dom_label = re.sub(r"[^a-z0-9]", "", (domain.split(".")[0] if domain else "zzzz"))
    def personal_q(e):
        if is_generic(e): return False
        loc = de_ascii(e.split("@")[0])
        if len(dom_label) >= 4 and dom_label in re.sub(r"[^a-z0-9]", "", loc): return False
        if re.search(r"berlin|hamburg|bonn|rhein|main|muenchen|koeln|leipzig|dresden|potsdam|frankfurt|stuttgart|duesseldorf|nord|sued|west|ost|miete|wohnen|senioren|objekt|kunden|gewerbe|vermiet|verkauf|abrechnung|technik|haus|grund", loc) and not any(email_matches_person(e, n) for n in all_people): return False
        return any(email_matches_person(e, n) for n in all_people) or looks_personal(e.split("@")[0])
    personal = [e for e in emails if personal_q(e)]
    generic = [e for e in emails if e not in personal]
    p_email, conf = "", ""
    # exact first+last match for any Impressum person → that person becomes the contact
    for n_, r_ in people:
        t_ = [de_ascii(x) for x in n_.replace("Dr. ", "").replace("Prof. ", "").split()]
        for e in personal:
            loc = de_ascii(e.split("@")[0])
            if len(t_) >= 2 and t_[-1] in loc and (loc.startswith(t_[0]) or loc.startswith(t_[0][0] + ".") or loc.startswith(t_[0][0] + t_[-1])):
                dm, dm_role, p_email, conf = n_, r_, e, "High – published on company website, matches decision maker"; break
        if p_email: break
    for e in ([] if p_email else personal):
        if email_matches_person(e, dm):
            loc = de_ascii(e.split("@")[0]); first = de_ascii(dm.replace("Dr. ", "").replace("Prof. ", "").split()[0])
            m_ = re.match(r"^([a-z]+)[._-]", loc)
            if m_ and len(m_.group(1)) > 1 and not first.startswith(m_.group(1)) and not m_.group(1).startswith(first):
                p_email, conf = e, f"High – published; address of family member/colleague '{m_.group(1).capitalize()}' with same surname"
            else:
                p_email, conf = e, "High – published on company website, matches decision maker"
            break
    if not p_email and dm:
        for n, _ in people[1:]:
            for e in personal:
                if email_matches_person(e, n): p_email, conf = e, f"High – published, belongs to {n}"; break
            if p_email: break
    if not p_email and dm and domain:
        pat = infer_pattern(personal, [p[0] for p in people])
        if pat:
            p_email, conf = build_email(dm, pat, domain), f"Medium – built from pattern '{pat}' observed on {domain}"
    if not p_email and personal:
        p_email, conf = personal[0], "Medium – personal address published on website (owner not confirmed)"
    if not p_email and dm and domain:
        p_email, conf = build_email(dm, "vorname.nachname", domain), "Low – default pattern vorname.nachname, unverified"
    gen_email = (generic[0] if generic else "")
    li_ = c.get("_li") or {}
    li_url = li_.get("linkedin", "") if li_.get("person") == dm else ""
    xing_url = li_.get("xing", "") if li_.get("person") == dm else ""
    _soc = {}
    for s_ in (c.get("socials") or []):
        if "/company/" in s_ or "/companies/" in s_ or "/pages/" in s_:
            k_ = re.sub(r"^https?://([a-z]{2,3}\.)?(www\.)?", "", s_.lower()).rstrip("/")
            _soc.setdefault(k_, "https://www." + k_)
    comp_social = "; ".join(_soc.values())
    li_search = f"https://www.linkedin.com/search/results/people/?keywords={(dm + ' ' + name).replace(' ', '%20')}" if dm else f"https://www.linkedin.com/search/results/companies/?keywords={name.replace(' ', '%20')}"
    # ---------- AI qualification agent (Claude) – grounded facts override / extend regex results ----------
    site_mismatch = ok and not name_on_site(c)
    ai = AI.get(urlparse(c.get("final_url") or c.get("website") or "").netloc.lower().replace("www.", "")) if ok else None
    residential = "unknown"; disq = ""; second = ("", "", ""); ai_summary = ""; data_basis = "Directory only" if not ok else "Website crawl (rule-based)"
    if ai:
        data_basis = "Website crawl + AI extraction (Claude, grounded)"
        ai_summary = ai.get("summary") or ""
        at = [t for t in (ai.get("management_types") or []) if t in ("WEG", "Miet", "SEV", "Gewerbe")]
        types = list(dict.fromkeys(at + types))
        residential = ai.get("residential_focus") or "unknown"
        mu, mb = ai.get("managed_units"), ai.get("managed_buildings")
        if re.search(r"verkauft|vermittelt|gebaut|errichtet|modernisiert|saniert|projektiert|sold|built|developed", ai.get("units_evidence") or "", re.I): mu = mb = None
        if mu in rejected_units: mu = None
        if re.search(r"nicht mehr als|höchstens|maximal|pro Verwalter|je Verwalter|per manager", ai.get("units_evidence") or "", re.I): mu = None
        if isinstance(mu, int) and 10 <= mu <= 40000:
            size_units, size_basis = mu, "Units stated"; u_val = mu; u_note = f"AI: {ai.get('units_evidence') or mu}"[:200]
        elif isinstance(mb, int) and 2 <= mb <= 4000 and not u_val:
            size_units, size_basis = mb * 12, "Buildings stated (×12 estimate)"; u_val = mb; u_note = f"AI: {mb} buildings stated → ≈{mb*12} units (×12) – {ai.get('units_evidence') or ''}"[:200]
        if isinstance(ai.get("employees"), int) and 1 <= ai["employees"] <= 1500:
            emp = ai["employees"]
            if size_basis.startswith(("Proxy", "Estimated")):
                size_units, size_basis = emp * 150, f"Estimated from {emp} employees (website, AI) × 150 units/FTE"
        if size_units:
            size_class = "XL (>5,000)" if size_units > 5000 else "L (1,000–5,000)" if size_units >= 1000 else "M (300–999)" if size_units >= 300 else "S (<300)"
        meter = sorted(set(meter) | set(ai.get("current_metering_provider") or []))
        sw = list(dict.fromkeys(sw + (ai.get("property_software") or [])))
        if sw: portal = True
        for a_ in ai.get("associations") or []:
            a2 = "VDIV" if "VDIV" in a_.upper() or "IMMOBILIENVERWALTER" in a_.upper() else "Haus & Grund" if "HAUS" in a_.upper() else a_.strip()
            if a2 in ("VDIV", "BVI", "IVD", "BFW", "Haus & Grund") and a2 not in assoc: assoc.append(a2)
        if ai.get("hiring"): hiring = True
        reason_map = {"pure broker": "Pure broker (no property management)", "commercial only": "Commercial properties only", "only single flats (SEV)": "Only single flats (SEV) – no building-level metering decision",
                      "not a property manager": "Not a property manager", "own portfolio only": "Manages only own portfolio (no third-party clients)"}
        if ai.get("disqualify_reason") == "own portfolio only" or (ai.get("is_third_party_property_manager") is False and re.search(r"cooperative|genossenschaft|own portfolio|housing company|housing association|landlord|Wohnungsbau", ai.get("summary") or "", re.I)):
            segment = "Housing company / cooperative (own portfolio)"
        elif ai.get("disqualify_reason") == "pure broker" and (set(types) & {"WEG", "Miet"}) and re.search(r"manag|verwalt", ai.get("summary") or "", re.I):
            pass
        elif ai.get("disqualify_reason") in reason_map: disq = reason_map[ai["disqualify_reason"]]
        elif ai.get("is_third_party_property_manager") is False and segment != "Housing company / cooperative (own portfolio)": disq = "Not a third-party property manager (AI)"
        if residential == "commercial" and not disq: disq = "Commercial properties only"
        if not disq and re.search(r"facility management|facility services|caretaking|janitorial|cleaning services|Hauswart|Gebäudereinigung|building services provider", ai.get("summary") or "", re.I) and "WEG" not in (ai.get("management_types") or []):
            disq = "Facility services provider, not a property manager"
        # people: decision maker + second persona
        ppl = [p for p in (ai.get("people") or []) if p.get("name")]
        gf = [p for p in ppl if p.get("role_category") == "Geschäftsführung"]
        ops = [p for p in ppl if p.get("role_category") in ("Leitung WEG/Miet", "Technik/Objektmanagement")]
        for p_ in ppl:
            if p_.get("email") and is_generic(p_["email"]): p_["email"] = None   # info@, kontakt@ … are shared mailboxes, not personal
        gf = [p for p in gf if clean_person(p["name"].replace(".", ". "), de_ascii(" ".join(c.get("emails") or []))) or len(p["name"].split()) >= 2 and not re.search(r"gmbh|management|verwaltung|immobilien|gesellschaft", p["name"], re.I)]
        if gf:
            g = gf[0]
            same_dm = bool(dm) and de_ascii(g["name"].split()[-1]) == de_ascii(dm.split()[-1])
            if g.get("email"):
                if not (same_dm and conf.startswith("High")):
                    dm, dm_role, p_email, conf = g["name"], g.get("role") or "Geschäftsführung", g["email"].lower(), "High – published on company website, matches decision maker (AI-extracted, grounded)"
            elif not same_dm:
                dm, dm_role = g["name"], g.get("role") or "Geschäftsführung"
                pat = infer_pattern(personal, [dm])
                p_email, conf = (build_email(dm, pat, domain), f"Medium – built from pattern '{pat}' observed on {domain}") if pat and domain else ((build_email(dm, "vorname.nachname", domain), "Low – default pattern vorname.nachname, unverified") if domain else ("", ""))
        if ops:
            o = ops[0]
            o_mail = (o.get("email") or "").lower()
            if not o_mail and domain:
                pat = infer_pattern(personal, [o["name"]])
                o_mail = build_email(o["name"], pat, domain) + " (pattern)" if pat else ""
            second = (o["name"], o.get("role") or o.get("role_category"), o_mail)
    # ---------- unit-count pass (AI pick from candidate sentences, grounded) ----------
    ux = UX.get(urlparse(c.get("final_url") or c.get("website") or "").netloc.lower().replace("www.", "")) if ok else None
    if ux and not size_basis.startswith(("Units stated", "Buildings stated")):
        scope_note = " – Germany-wide" if ux.get("scope") == "Germany-wide" else ""
        if ux.get("units"):
            lb = ux.get("kind") == "sum_of_references"
            size_units, size_basis, u_val = ux["units"], ("Units stated (lower bound: sum of listed references)" if lb else "Units stated"), ux["units"]
            u_note = f"AI (units pass){' – sum of listed reference objects' if lb else ''}: {ux['quote']}{scope_note}"[:240]
        elif ux.get("buildings") and 2 <= ux["buildings"] <= 4000:
            size_units, size_basis, u_val = ux["buildings"] * 12, "Buildings stated (×12 estimate)", ux["buildings"]; u_note = f"AI (units pass): {ux['quote']}{scope_note}"[:240]
        size_class = "XL (>5,000)" if size_units > 5000 else "L (1,000–5,000)" if size_units >= 1000 else "M (300–999)" if size_units >= 300 else "S (<300)"
        size_s = None  # recomputed below
    # ---------- VDIV Berlin-Brandenburg member directory (authoritative, published by the association) ----------
    vd = c.get("vdiv")
    vdiv_contact = ""
    if vd:
        if "VDIV" not in assoc: assoc.insert(0, "VDIV")
        vdiv_contact = clean_person(vd.get("contact", ""), de_ascii(vd.get("email", ""))) or ""
        v_mail = (vd.get("email") or "").lower()
        v_personal = bool(v_mail) and not is_generic(v_mail) and (email_matches_person(v_mail, vdiv_contact) or looks_personal(v_mail.split("@")[0]))
        if not conf.startswith("High"):
            same = bool(dm and vdiv_contact and de_ascii(dm.split()[-1]) == de_ascii(vdiv_contact.split()[-1]))
            if vdiv_contact and v_personal and (not dm or same):
                dm, dm_role, p_email, conf = vdiv_contact, dm_role or "Contact person (VDIV directory)", v_mail, "High – published in VDIV Berlin-Brandenburg member directory"
            elif vdiv_contact and not dm:
                dm, dm_role = vdiv_contact, "Contact person (VDIV directory)"
                dom_ = v_mail.split("@")[1] if "@" in v_mail else domain
                pat = infer_pattern(personal, [dm])
                p_email, conf = (build_email(dm, pat, dom_), f"Medium – built from pattern '{pat}' observed on {dom_}") if pat else ((build_email(dm, "vorname.nachname", dom_), "Low – default pattern vorname.nachname, unverified") if dom_ else ("", ""))
            elif vdiv_contact and not same and not second[0]:
                second = (vdiv_contact, "Contact person (VDIV directory)", v_mail if v_personal else "")
        if v_mail and not v_personal and not gen_email: gen_email = v_mail
    # ---------- manual contact review (top Tier-A, 7 Nov 2026) ----------
    man = MANUAL.get(name) or MANUAL.get(c["name"])
    if not man:
        cands_ = [nkey(x_) for x_ in (name, c["name"], clean_company(name, c)) if x_]
        for k_, v_ in MANUAL.items():
            kk = nkey(k_)
            if any(len(cn) >= 8 and (cn.startswith(kk[:16]) or kk.startswith(cn[:16])) for cn in cands_): man = v_; break
    manual_note = ""
    if man:
        if man.get("email") and man.get("status") == "verified":
            p_email, conf = man["email"], "High – published on company website, manually verified 2026-11-07"
        elif man.get("email") and man.get("status") == "probable":
            p_email, conf = man["email"], "Medium – company pattern confirmed on team page (manual review 2026-11-07)"
        elif man.get("status") == "probable" and conf.startswith("Low"):
            conf = "Medium – company pattern confirmed on team page (manual review 2026-11-07)"
        if man.get("second"):
            s2 = man["second"]; second = (s2["name"], s2["role"], s2["email"])
        manual_note = man.get("note_segment") or man.get("note") or ""
    # ---------- e-mail status incl. MX check ----------
    def mx_ok(e):
        if not e or "@" not in e: return None
        v = MX.get(e.split("@")[1].split()[0].lower())
        return None if v is None else bool(v)
    em_mx = mx_ok(p_email)
    if not p_email: email_status = ""
    elif em_mx is False: email_status = "Invalid – domain has no mail server"; p_email_note = conf
    elif conf.startswith("High"): email_status = "Verified – published on website" if "VDIV" not in conf else "Verified – published in VDIV directory"
    elif conf.startswith("Medium – personal address published"): email_status = "Published – person/role unknown"
    elif conf.startswith("Medium"): email_status = "Probable – company pattern, MX ok" if em_mx else "Probable – company pattern"
    else: email_status = "Unverified – default pattern, MX ok" if em_mx else "Unverified – default pattern"
    if mx_ok(gen_email) is False: gen_email = ""
    if not ok and segment == "Broker-led (Makler + Verwaltung)" and not types: disq = disq or "Broker-led, no property management evidence"
    # ---------- sub-scores (0–10 each) ----------
    # 1 Segment fit
    fit = {"Property manager (Hausverwaltung)": 6, "Property-owning entity (Objektgesellschaft)": 5, "Broker-led (Makler + Verwaltung)": 3,
           "Large landlord / housing company": 4, "Real-estate company (unclear focus)": 3, "Housing company / cooperative (own portfolio)": 6}[segment]
    if "WEG" in types: fit += 2
    if "Miet" in types: fit += 1.5
    if "SEV" in types: fit += 0.5
    if types == ["Gewerbe"]: fit -= 2
    if residential == "residential": fit += 1
    elif residential == "commercial": fit -= 3
    fit = max(0, min(10, fit))
    # 2 Size / revenue potential
    if size_units:
        size_s = 10 if size_units >= 2000 else 9 if size_units >= 1000 else 7 if size_units >= 500 else 5 if size_units >= 300 else 3
    else:
        size_s = {"M (300–999) – proxy": 5, "S–M – proxy": 3.5, "S (<300) – proxy": 2}[size_class]
    # 3 Digital readiness
    dig_s = round(dig / 3 * 10, 1)
    # 4 Metering need / trigger
    trig = 0
    if hk: trig += 4
    if meter: trig += 3     # incumbent named → switch case (HKVO remote-reading deadline 31.12.2026)
    if rwm: trig += 1.5
    if funk: trig += 1.5
    if hiring: trig += 2    # growth / capacity pressure → automation pitch
    trig = min(10, trig) if ok else 2  # unknown → neutral-low
    # 5 Reachability
    reach = 0
    if dm: reach += 4
    if email_status.startswith("Verified"): reach += 4
    elif email_status.startswith("Probable"): reach += 2.5
    elif email_status.startswith("Unverified"): reach += 1
    if second[0]: reach += 1
    if li_url or xing_url: reach += 1
    if c.get("phone"): reach += 1
    if gen_email and not p_email: reach += 1
    reach = min(10, reach)
    # 6 Channel / professionalism
    ch = 0
    if "VDIV" in assoc: ch += 7          # Heidi Systems is a VDIV partner → warm channel
    if any(a in assoc for a in ("BVI", "IVD", "BFW", "Haus & Grund")): ch += 3
    if ok and re.search(r"zertifizierte[rn]? Verwalter", c.get("snippet", "") + " ".join(str(x) for x in c.get("people", [])), re.I): ch += 1
    if lf.startswith(("GmbH", "AG")): ch += 1.5
    ch = min(10, ch)
    rating = j.get("jacasa_rating") or c.get("gs_rating") or ""
    reasons = []
    if "WEG" in types or "Miet" in types: reasons.append("/".join(t for t in types if t in ("WEG", "Miet", "SEV")) + " management")
    if size_units: reasons.append(f"≈{size_units:,} units".replace(",", "."))
    if "VDIV" in assoc: reasons.append("VDIV member (partner channel)")
    if meter: reasons.append("incumbent: " + ", ".join(meter))
    if hk: reasons.append("handles heating-cost billing")
    if hiring: reasons.append("hiring")
    if portal or sw: reasons.append("uses portal/software" + (f" ({', '.join(sw[:2])})" if sw else ""))
    if email_status.startswith("Verified"): reasons.append("personal email published")
    if second[0]: reasons.append("2nd contact: " + (second[1] or ""))
    if disq: reasons.insert(0, "DISQUALIFIED: " + disq)
    if not ok: reasons.append("no crawlable website – data from directories only")
    if segment in ("Large landlord / housing company", "Housing company / cooperative (own portfolio)"): reasons.append("owner – buys metering directly, often via tender")
    # ---------- evidence coverage flags (1 = KPI backed by observed evidence, 0 = default/proxy) ----------
    if site_mismatch: reasons.insert(0, "VERIFY WEBSITE: company name not found on listed site")
    E = {"E_fit": 1 if (types or residential != "unknown" or vd or (ai and disq == "")) else 0,
         "E_size": 1 if size_basis.startswith(("Units stated", "Buildings stated", "Estimated")) else 0,
         "E_trigger": 1 if ok else 0, "E_reach": 1 if dm else 0, "E_digital": 1 if ok else 0, "E_channel": 1 if (ok or vd) else 0}
    if site_mismatch: E.update({"E_fit": 1 if vd else 0, "E_size": 0, "E_trigger": 0, "E_digital": 0})
    if vd and "VDIV" in conf: reasons.append("contact e-mail from VDIV directory")
    units_scope = ""
    if size_units and re.search(r"Deutschland|bundesweit|deutschlandweit|nationwide|across Germany|throughout Germany|Standorten|Städten|mehreren Städten|Germany-wide", (u_note or "") + " " + (ai_summary or ""), re.I):
        units_scope = "Germany-wide (not Berlin only)"; reasons.append("units are Germany-wide")
    if man and man.get("note_segment"): reasons.append(man["note_segment"])
    if man: reasons.append("contacts manually reviewed")
    # ---------- contacts (one row per person) + evidence log (one row per claim) ----------
    site = c.get("final_url") or c.get("website") or ""
    imp_url = c.get("impressum_url") or site
    VDIV_URL = "https://vdiv-bb.de/mitglieder/"
    contacts, seen_p = [], set()
    def add_contact(nm, role, cat, email, status, src):
        if not nm: return
        k_ = de_ascii(nm.replace("Dr. ", "").replace("Prof. ", ""))
        if k_ in seen_p:
            for x_ in contacts:
                if x_["key"] == k_ and email and not x_["Email"]: x_["Email"], x_["Email status"] = email, status
            return
        seen_p.add(k_); contacts.append({"key": k_, "Name": nm, "Role": role, "Role category": cat, "Email": email, "Email status": status, "Source": src})
    if dm: add_contact(dm, dm_role, "Geschäftsführung / owner" if "VDIV" not in (dm_role or "") else "Contact person", p_email, email_status, VDIV_URL if "VDIV" in conf or "VDIV" in (dm_role or "") else imp_url)
    if second[0]: add_contact(second[0], second[1], "Second contact", second[2], ("Verified – published on website" if second[2] and "(pattern)" not in second[2] else ("Probable – company pattern" if second[2] else "Not publicly available")), VDIV_URL if "VDIV" in (second[1] or "") else site)
    if ai:
        for p_ in ai.get("people") or []:
            em_ = (p_.get("email") or "").lower()
            add_contact(p_.get("name"), p_.get("role") or "", p_.get("role_category") or "", em_, ("Shared mailbox – not personal" if is_generic(em_) else "Verified – published on website") if em_ else "Not publicly available", site)
    for n_, r_ in people: add_contact(n_, r_, "Impressum", "", "Not publicly available", imp_url)
    for vm_ in c.get("vdiv_more") or []:
        nm_ = clean_person(vm_.get("contact", ""), de_ascii(vm_.get("email", "")))
        if nm_: add_contact(nm_, "Contact person (VDIV directory)", "Contact person", (vm_.get("email") or "").lower(), "Verified – published in VDIV directory" if vm_.get("email") and not is_generic(vm_["email"]) else "Shared mailbox – not personal", VDIV_URL)
    if vdiv_contact: add_contact(vdiv_contact, "Contact person (VDIV directory)", "Contact person", (vd.get("email") or "").lower() if vd else "", "Verified – published in VDIV directory" if vd and vd.get("email") and not is_generic(vd["email"]) else "Shared mailbox – not personal", VDIV_URL)
    for x_ in contacts: x_.pop("key", None)
    evidence = []
    def ev(field, value, src, quote, confd):
        if value not in ("", None, []): evidence.append({"Field": field, "Value": str(value), "Source URL": src, "Evidence": (quote or "")[:300], "Confidence": confd})
    if size_basis.startswith(("Units stated", "Buildings stated")): ev("Managed units" + (" (buildings ×12)" if size_basis.startswith("Buildings") else ""), size_units, site, u_note, "Medium – AI-extracted, grounded" if u_note.startswith("AI") else "High – company website")
    elif size_basis.startswith("Estimated"): ev("Managed units (estimate)", size_units, site if "website" in size_basis else (j.get("jacasa_url") or ""), size_basis, "Low – estimate from employees")
    ev("Management type", ", ".join(dict.fromkeys(types)), site, ai_summary or "keyword match on website", "Medium – AI-extracted, grounded" if ai else "Medium – keyword match")
    if dm: ev("Decision maker", f"{dm} ({dm_role})", VDIV_URL if "VDIV" in (dm_role or "") or "VDIV" in conf else imp_url, "Named in Impressum (§ 5 DDG)" if "VDIV" not in (dm_role or "") else "Listed as contact in association directory", "High – official source")
    if p_email: ev("Personal e-mail", p_email, VDIV_URL if "VDIV" in conf else imp_url, conf, "High – published" if email_status.startswith("Verified") else "Low – pattern, not published")
    if vd: ev("VDIV membership", "Yes", VDIV_URL, f"Listed: {vd.get('name')}, {vd.get('street')}, {vd.get('plz')} {vd.get('city')}", "High – association directory")
    elif "VDIV" in assoc: ev("VDIV membership", "Yes (stated by company)", site, "VDIV mentioned on company website", "Medium – self-reported")
    if meter: ev("Current metering provider", ", ".join(meter), site, "Named on company website", "Medium – mentioned on website")
    if disq: ev("Disqualification", disq, site, ai_summary, "Medium – AI-extracted, grounded")
    if hiring: ev("Hiring signal", "Yes", site, ", ".join((ai or {}).get("hiring_roles") or []) or "careers/jobs page found", "Medium – website")
    out.append({**E, "_contacts": contacts, "_evidence": evidence,
        "VDIV member (directory)": "Yes" if vd else "", "VDIV contact": vdiv_contact,
        "Company": clean_company(name, c), "Directory name": name if clean_company(name, c) != name else "", "Units scope": units_scope, "Segment": segment, "Management type": ", ".join(dict.fromkeys(types)) or ("unknown" if not ok else "not stated"),
        "Units (stated)": u_val or "", "Units basis": u_note, "Est. units": size_units or "", "Size class": size_class, "Size basis": size_basis,
        "Employees": emp or "", "Founded": founded or "", "Heating-cost billing on site": "Yes" if hk else ("No" if ok else "n/a"),
        "Current metering provider (mentioned)": ", ".join(meter), "Smoke detectors / radio meters mentioned": ", ".join(x for x, f in (("Rauchwarnmelder", rwm), ("Funk/Fernablesung", funk)) if f),
        "Digital maturity": dig_label, "Software / portal seen": ", ".join(sw) or ("Portal mentioned" if portal else ""), "Associations": ", ".join(assoc),
        "Hiring": "Yes" if hiring else ("No" if ok else "n/a"), "Rating": rating, "Reviews": reviews or "", "Legal form": lf, "Commercial register": c.get("register", ""),
        "Decision maker": dm, "Role": dm_role, "Further people (Impressum)": "; ".join(p[0] for p in people[1:3]),
        "Personal email": p_email, "Email status": email_status, "Email confidence": conf,
        "Second contact": second[0], "Second contact role": second[1], "Second contact email": second[2],
        "Residential focus": residential, "Disqualified reason": disq, "Website check": "Company name not found on listed site – verify" if site_mismatch else ("ok" if ok else ""), "AI summary": ai_summary, "Data basis": data_basis, "Generic email": gen_email, "Phone": c.get("phone", ""),
        "LinkedIn (person)": li_url, "Xing (person)": xing_url, "LinkedIn search": li_search, "Company social": comp_social,
        "Website": c.get("final_url") or c.get("website", ""), "Impressum": c.get("impressum_url", ""), "Street": c.get("street", ""), "PLZ": c.get("plz", ""),
        "Bezirk": bezirk(c), "Sources": ", ".join(c.get("sources", [])), "Website status": c.get("crawl_status", ""), "Website found via": c.get("website_source", "directory" if c.get("website") else ""),
        "S_fit": fit, "S_size": size_s, "S_digital": dig_s, "S_trigger": trig, "S_reach": reach, "S_channel": ch, "Why": "; ".join(reasons),
    })
json.dump({"rows": out, "excluded": excluded}, open(OUTJ, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("built", len(out))
