"""Crawl each company website (home, Impressum, Kontakt, Team, Leistungen, Über uns) and extract qualifying signals."""
import json, re, sys, time, unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
import requests, urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings()

INP, OUT = sys.argv[1], sys.argv[2]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
      "Accept-Language": "de-DE,de;q=0.9"}
LINK_KEYS = {"impressum": ["impressum", "imprint", "anbieterkennzeichnung"],
             "kontakt": ["kontakt", "contact"],
             "team": ["team", "ansprechpartner", "mitarbeiter", "wir-ueber-uns", "ueber-uns", "uber-uns", "about", "unternehmen", "wir"],
             "leistung": ["leistung", "service", "verwaltung", "weg", "mietverwaltung", "angebot"],
             "karriere": ["karriere", "jobs", "stellen", "career"]}

def fetch(url):
    try:
        r = requests.get(url, headers=UA, timeout=(6, 10), verify=False, allow_redirects=True)
        if r.status_code >= 400: return None, url
        ct = r.headers.get("content-type", "")
        if "html" not in ct and "text" not in ct: return None, r.url
        r.encoding = r.apparent_encoding if not r.encoding or r.encoding.lower() == "iso-8859-1" else r.encoding
        return r.text, r.url
    except Exception:
        return None, url

def text_of(h):
    s = BeautifulSoup(h, "html.parser")
    for t in s(["script", "style", "noscript", "svg"]): t.decompose()
    return " ".join(s.get_text(" ", strip=True).split())

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
def emails_of(h):
    h2 = h.replace("[at]", "@").replace("(at)", "@").replace(" [ät] ", "@").replace("&#64;", "@").replace("&#x40;", "@")
    out = set(m.group(0).strip(".").lower() for m in EMAIL_RE.finditer(h2))
    for m in re.finditer(r'href="mailto:([^"?]+)', h, re.I): out.add(m.group(1).strip().lower())
    return {e for e in out if not re.search(r"\.(png|jpg|jpeg|gif|webp|svg)$", e) and "sentry" not in e and "example" not in e and "wixpress" not in e and "domain.de" not in e}

NAME = r"((?:Dr\.|Prof\.|Dipl\.-[A-Za-zä]+\.?|Dipl\.)?\s?[A-ZÄÖÜ][a-zäöüßéè\-]+(?:\s[A-ZÄÖÜ]\.)?(?:\s(?:von|van|de|zu)\b)?(?:\s[A-ZÄÖÜ][a-zäöüßéè\-]+){1,2})"
ROLE_PATS = [
    (r"Geschäftsf(?:ü|ue)hr(?:er|erin|ende[rn]?|ung)\s*(?:Gesellschafter(?:in)?)?\s*[:\-–]?\s*(?:ist|sind)?\s*(?:Herr|Frau)?\s*" + NAME, "Geschäftsführung"),
    (r"(?:Vertreten|vertreten|Vertretungsberechtigt(?:er|e)?\s*(?:Geschäftsführer)?)\s*(?:durch)?\s*(?:den|die)?\s*(?:Geschäftsführer(?:in)?)?\s*[:\-–]?\s*(?:Herr|Frau)?\s*" + NAME, "Geschäftsführung"),
    (r"Inhaber(?:in)?\s*[:\-–]?\s*(?:Herr|Frau)?\s*" + NAME, "Inhaber/in"),
    (r"Vorstand\s*[:\-–]?\s*(?:Herr|Frau)?\s*" + NAME, "Vorstand"),
    (r"Verantwortlich(?:er)?\s*(?:für den Inhalt|i\.S\.d\.|im Sinne|gem\.|nach)[^:]{0,60}:\s*(?:Herr|Frau)?\s*" + NAME, "Inhaltlich verantwortlich"),
]
STOP = {"Gesellschaft", "Haftung", "Berlin", "Straße", "Strasse", "Hausverwaltung", "Immobilien", "Telefon", "Registergericht", "Amtsgericht", "Handelsregister",
        "Sitz", "Inhalt", "Gmbh", "GmbH", "Kontakt", "Steuernummer", "Umsatzsteuer", "Verwaltung", "Charlottenburg", "Datenschutz", "Impressum", "Angaben", "Tel", "Fax", "Und", "Die", "Der", "Den",
        "Postanschrift", "Anschrift", "Geschäftsführer", "Geschäftsführerin", "Vertreten", "Registernummer", "Aufsichtsbehörde", "Email", "Mail", "Ust", "Vertretungsberechtigter", "Inhaber"}
def names_from(t):
    found = []
    for pat, role in ROLE_PATS:
        for m in re.finditer(pat, t):
            n = re.sub(r"\s+", " ", m.group(1)).strip()
            parts = n.replace("Dr. ", "").replace("Prof. ", "").split()
            if any(p.strip(".") in STOP for p in parts): continue
            if len(parts) < 2 or len(n) > 45: continue
            if (n, role) not in found and n not in [f[0] for f in found]: found.append((n, role))
    return found[:4]

KW = {
    "weg": r"WEG[\s\-]?Verwaltung|Wohnungseigentümergemeinschaft|WEG-Verwalter|Verwaltung von Wohnungseigentum|Eigentümergemeinschaften",
    "miet": r"Mietverwaltung|Mietshausverwaltung|Miethausverwaltung|Zinshaus|Mietobjekt|Mietshäuser",
    "sev": r"Sondereigentumsverwaltung|SE-Verwaltung|Sondereigentum",
    "gewerbe": r"Gewerbeimmobilien|Gewerbeverwaltung|Gewerbeobjekte|Büroimmobilien|Commercial",
    "hk": r"Heizkostenabrechnung|Heizkosten|Verbrauchserfassung|Wärmezähler|Heizkostenverteiler|Messdienst",
    "rwm": r"Rauchwarnmelder|Rauchmelder",
    "bka": r"Betriebskostenabrechnung|Nebenkostenabrechnung|Hausgeldabrechnung",
    "facility": r"Facility Management|Hausmeisterservice|Gebäudereinigung|Winterdienst",
    "makler": r"Immobilienmakler|Maklerleistung|Verkauf von Immobilien|Vermietung und Verkauf|Makler",
    "portal": r"Kundenportal|Eigentümerportal|Mieterportal|Online-Portal|Mieter-App|Eigentümer-App|casavi|immoware24|facilioo|Allthings|Domus|Karthago|Wodis|Haufe PowerHaus|iX-Haus|DOMUS|VERSA|Hausify|Etg24|ETG24|objego|Smart Living|digitale Verwaltung|digital",
    "karriere": r"Karriere|Stellenangebote|Stellenanzeige|Jobs|Wir suchen|Verstärkung|m/w/d",
    "vdiv": r"VDIV|Verband der Immobilienverwalter",
    "bvi": r"\bBVI\b|Bundesfachverband der Immobilienverwalter",
    "ivd": r"\bIVD\b|Immobilienverband Deutschland",
    "hug": r"Haus\s?&\s?Grund|Haus und Grund",
    "bfw": r"\bBFW\b",
    "esg": r"Energieeffizien|Nachhaltig|CO2|CO₂|Klimaschutz|Sanierung|GEG|Wärmepumpe|ESG",
    "fernablesung": r"fernablesbar|Funkzähler|Funk-|Fernablesung|smart meter|Submetering|unterjährige Verbrauchsinformation|UVI",
}
METERING = ["Techem", "ista", "Brunata", "Minol", "KALO", "Kalorimeta", "Qundis", "Metrona", "Noventic", "Heidi Systems", "Wärmemessdienst", "Kalo", "Engelmann", "Lorenz"]
SOFTWARE = ["casavi", "immoware24", "facilioo", "Allthings", "Domus", "Karthago", "Wodis", "PowerHaus", "iX-Haus", "VERSA", "Hausify", "ETG24", "objego", "Aareon", "Haufe"]

def units(t):
    best = 0; ev = ""
    for m in re.finditer(r"(?:über|ca\.|rund|mehr als|insgesamt|circa|knapp|etwa|derzeit|aktuell)?\s*(\d{1,3}(?:[.\s]\d{3})+|\d{2,6})\s*\+?\s*(?:verwaltete\s*)?(Wohn-\s*und\s*Gewerbeeinheiten|Wohn- und Gewerbe-Einheiten|Wohneinheiten|Verwaltungseinheiten|Einheiten|Wohnungen|Mieteinheiten|Objekte|Liegenschaften|WEGs?|Eigentümergemeinschaften|Häuser|Immobilien|Gebäude)", t):
        n = int(re.sub(r"[.\s]", "", m.group(1)))
        kind = m.group(2)
        ctx = t[max(0, m.start() - 80): m.end() + 40]
        if n < 5 or n > 200000: continue
        if re.search(r"(19|20)\d\d$", m.group(1)) and n < 2100 and n > 1900: continue
        if re.search(r"m²|qm|Quadrat|€|Euro|Mitglieder|Kunden", ctx[ctx.find(m.group(0)) - 5: ctx.find(m.group(0)) + len(m.group(0)) + 15] if m.group(0) in ctx else ""): continue
        if re.search(r"verwalt|betreu|Bestand|Portfolio|Verwaltung|managen|bewirtschaft", ctx, re.I):
            weight = n if kind.startswith(("Wohn", "Verwaltungs", "Einheit", "Miet")) else n * (10 if kind.startswith(("Objekt", "Liegen", "WEG", "Eigent", "Häus", "Immob", "Gebäu")) else 1)
            if weight > best:
                best = weight; ev = ctx.strip()
                unit_raw = (n, kind)
    if not best: return None
    n, kind = unit_raw
    return {"value": n, "kind": kind, "evidence": ev[:220]}

def employees(t):
    for m in re.finditer(r"(\d{1,4})\s*(?:engagierte|qualifizierte|erfahrene|kompetente|motivierte|festangestellte)?\s*(Mitarbeiter(?:innen)?|Mitarbeitende|Angestellte|Kolleginnen und Kollegen|Fachkräfte|Team-?Mitglieder)", t):
        n = int(m.group(1))
        if 2 <= n <= 3000: return n
    return None

def founded(t):
    m = re.search(r"(?:seit|Seit|gegründet|Gründung|founded|established|im Jahr|Jahre?)\s*(?:im Jahr|in)?\s*(19[5-9]\d|20[0-2]\d)", t)
    if m: return int(m.group(1))
    m = re.search(r"(?:über|mehr als|seit)\s*(\d{2,3})\s*Jahre", t)
    if m and 3 <= int(m.group(1)) <= 120: return 2026 - int(m.group(1))
    return None

def register(t):
    m = re.search(r"(HR[AB])\s*[:\-]?\s*(?:Nr\.?|Nummer)?\s*:?\s*(\d{3,7}\s?[A-Z]?)", t)
    return f"{m.group(1)} {m.group(2).strip()}" if m else ""

def pick_links(h, base, domain):
    s = BeautifulSoup(h, "html.parser")
    picks = {k: [] for k in LINK_KEYS}
    socials = set()
    for a in s.find_all("a", href=True):
        href = a["href"].strip(); txt = a.get_text(" ", strip=True).lower()
        if "linkedin.com" in href or "xing.com" in href: socials.add(href.split("?")[0]); continue
        if href.startswith(("mailto:", "tel:", "javascript:", "#")): continue
        u = urljoin(base, href); p = urlparse(u)
        if domain and domain not in p.netloc: continue
        low = (p.path + " " + txt).lower()
        for k, keys in LINK_KEYS.items():
            if any(x in low for x in keys) and u not in picks[k] and len(picks[k]) < (2 if k != "leistung" else 3):
                picks[k].append(u)
    return picks, socials

def crawl(c):
    res = {"crawl_status": "no website"}
    url = c.get("website")
    if not url: return res
    if not url.startswith("http"): url = "http://" + url
    h, final = fetch(url)
    if not h:
        h, final = fetch(url.replace("http://", "https://"))
    if not h: res["crawl_status"] = "website unreachable"; return res
    domain = urlparse(final).netloc.lower().replace("www.", "")
    pages = {"home": (final, h)}
    picks, socials = pick_links(h, final, domain)
    if not picks["impressum"]:
        for guess in ("/impressum", "/impressum/", "/impressum.html", "/de/impressum"):
            hh, uu = fetch(urljoin(final, guess))
            if hh and "impressum" in hh.lower(): picks["impressum"] = [uu]; break
    todo = []
    for k in ("impressum", "kontakt", "team", "leistung", "karriere"):
        for u in picks[k]: todo.append((k, u))
    seen = {final}
    for k, u in todo:
        if u in seen: continue
        seen.add(u)
        hh, uu = fetch(u)
        if hh:
            pages.setdefault(k, (uu, hh)) if k not in pages else pages.__setitem__(k + str(len(pages)), (uu, hh))
            _, soc2 = pick_links(hh, uu, domain); socials |= soc2
    texts = {k: text_of(v[1]) for k, v in pages.items()}
    alltext = " ".join(texts.values())
    imp = " ".join(v for k, v in texts.items() if k.startswith("impressum")) or texts["home"]
    emails = set()
    for k, v in pages.items(): emails |= emails_of(v[1])
    res.update({
        "crawl_status": "ok", "final_url": final, "domain_final": domain, "pages_crawled": len(pages),
        "impressum_url": pages["impressum"][0] if "impressum" in pages else "",
        "people": names_from(imp) or names_from(alltext),
        "emails": sorted(emails),
        "register": register(imp),
        "kw": {k: len(re.findall(p, alltext, re.I if k not in ("vdiv", "bvi", "ivd", "bfw") else 0)) for k, p in KW.items()},
        "metering_mentions": sorted({m for m in METERING if re.search(r"\b" + re.escape(m) + r"\b", alltext)}),
        "software_mentions": sorted({m for m in SOFTWARE if re.search(r"\b" + re.escape(m) + r"\b", alltext, re.I)}),
        "units": units(alltext), "employees": employees(alltext), "founded": founded(alltext),
        "socials": sorted(socials)[:6], "has_karriere_page": any(k.startswith("karriere") for k in pages),
        "text_len": len(alltext), "home_title": (BeautifulSoup(h, "html.parser").title.get_text(strip=True) if BeautifulSoup(h, "html.parser").title else "")[:150],
        "https": final.startswith("https"),
        "snippet": texts["home"][:600],
    })
    return res

if __name__ == "__main__":
    comps = json.load(open(INP, encoding="utf8"))
    out = [None] * len(comps)
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs = {ex.submit(crawl, c): i for i, c in enumerate(comps)}
        done = 0
        for f in as_completed(futs):
            i = futs[f]
            try: out[i] = f.result()
            except Exception as e: out[i] = {"crawl_status": f"error {e}"}
            done += 1
            if done % 50 == 0: print("done", done, flush=True)
    for c, r in zip(comps, out): c.update(r)
    json.dump(comps, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print("finished", sum(1 for c in comps if c.get("crawl_status") == "ok"), "ok of", len(comps))
