"""Shared cleaning helpers: person names, e-mail classification, name keys."""
import re, unicodedata

TITLE_RE = re.compile(r"^(Herrn?|Frau|Dr\.?|Prof\.?|Dipl\.?-?\s?[A-Za-zäöü]*\.?|Kfm\.?|Ing\.?|Betriebswirt(in)?|Rechtsanwalt|RA|Immobilienkaufmann|Immobilienfachwirt(in)?|Zertifizierte[rn]?)\s*", re.I)
BAD_TOKENS = {"zertifizierter", "zertifizierte", "registerdaten", "registereintrag", "registergericht", "amtsgericht", "handelsregister", "sitz", "telefon", "tel", "fax",
              "e-mail", "email", "verwaltung", "hausverwaltung", "gmbh", "ug", "kg", "anschrift", "straße", "strasse", "berlin", "inhaber", "inhaberin", "geschäftsführer",
              "geschäftsführerin", "und", "sowie", "eingetragen", "steuernummer", "ust", "umsatzsteuer", "kontakt", "impressum", "registernummer", "komplementärin",
              "komplementär", "liegenschaften", "immobilien", "grundbesitz", "management", "datenschutz", "verantwortlich", "angaben", "vertreten", "gesellschafter",
              "gesellschafterin", "prokurist", "prokuristin", "web", "internet", "mobil", "postfach", "aufsichtsbehörde", "bezirksamt", "haftung", "geschäftsführung",
              "vorstand", "vorsitzender", "aufsichtsrat", "der", "die", "das", "den", "dem", "mit", "von der", "telefax", "copyright", "rechtsform", "hrb", "hra", "partner",
              "ihk", "kammer", "erlaubnis", "gewerbeerlaubnis", "berufsbezeichnung", "home", "startseite", "menü", "menu", "team", "gruppe", "holding", "beteiligungs",
              "verwaltungs", "unternehmensgruppe", "kontaktdaten", "registriert", "umsatzsteuer-id", "steuer", "finanzamt", "real", "estate", "property", "group", "services",
              "consulting", "invest", "capital", "projekt", "projekte", "wohnen", "haus", "grund", "ihre", "ihr", "unsere", "unser", "wir", "sie", "liebe", "sehr", "geehrte", "willkommen", "herzlich", "fragen", "objekt", "frau", "herr", "kauffrau", "kaufmann", "button", "link", "mehr", "hier", "klick", "geschäftsführender", "geschäftsführende"}
BAD_SUFFIX = ("str", "str.", "straße", "strasse", "damm", "allee", "platz", "weg", "ring", "ufer", "chaussee", "gericht", "daten", "nummer", "eintrag", "ierter", "ierte",
              "gesellschaft", "verwaltung", "management", "gmbh", "anschrift", "register", "behörde", "mbh", "immobilien", "steuer", "berlin")

def strip_accents(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()

def de_ascii(s):
    s = s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return strip_accents(s)

def clean_person(n, context=""):
    if not n: return ""
    n = re.sub(r"\s+", " ", n.replace("Dr.", "Dr. ")).strip(" ,;:-–")
    prefix = ""
    m = re.match(r"^((?:Prof\.\s*)?(?:Dr\.\s*)?)", n)
    if m and m.group(1).strip(): prefix = m.group(1).strip() + " "
    for _ in range(4):
        n2 = TITLE_RE.sub("", n).strip()
        if n2 == n: break
        n = n2
    toks = n.split()
    while toks and (toks[0].lower().strip(".,") in BAD_TOKENS or toks[0].lower() in ("button", "link", "mehr", "hier", "klick")): toks = toks[1:]
    # cut at first bad token
    out = []
    for t in toks:
        tl = t.lower().strip(".,")
        if tl in BAD_TOKENS or tl.endswith(BAD_SUFFIX) or re.search(r"\d", t): break
        out.append(t.strip(",."))
    if len(out) < 2: return ""
    PART = ("von", "van", "de", "zu", "vom", "der", "den", "di", "da", "el", "al")
    # keep "First Last" (+ particle-led surname); a third capitalised token is usually a noun (job title etc.)
    if len(out) >= 3 and out[1].lower() in PART: out = out[:3] if out[2].lower() not in PART else out[:4]
    elif len(out) >= 3 and context and de_ascii(out[2]) in context and len(out[2]) > 2: out = out[:3]   # 3rd token confirmed as surname by e-mail/domain/company name
    else: out = out[:2]
    if not all(re.match(r"^[A-ZÄÖÜ][a-zäöüßéèáçñ\-]+$|^[A-ZÄÖÜ]\.$|^(von|van|de|zu|vom)$", t) for t in out): return ""
    if out[-1] in ("von", "van", "de", "zu", "vom"): out = out[:-1]
    if len(out) < 2: return ""
    return (prefix if "Dr" in prefix or "Prof" in prefix else "") + " ".join(out)

GENERIC = ("vorstand", "geschaeftsfuehrung", "geschäftsführung", "gf", "leitung", "assistenz", "sekretariat", "info", "kontakt", "contact", "office", "mail", "post", "verwaltung", "service", "hausverwaltung", "buero", "büro", "zentrale", "bewerbung", "karriere",
           "jobs", "datenschutz", "anfrage", "anfragen", "empfang", "team", "hello", "hallo", "immobilien", "vermietung", "buchhaltung", "rechnung", "rechnungen",
           "technik", "mieter", "weg", "hv", "admin", "webmaster", "support", "notfall", "sekretariat", "dsb", "privacy", "sales", "vertrieb", "kundenservice", "postfach",
           "noreply", "no-reply", "news", "newsletter", "presse", "marketing", "facebook", "einkauf", "fibu", "abrechnung", "objektverwaltung", "mietverwaltung",
           "wegverwaltung", "personal", "hr", "willkommen", "welcome", "general", "home", "firma", "mail1", "verkauf", "eigentuemer", "eigentümer", "kunden", "berlin")

def looks_personal(local):
    return bool(re.match(r"^[a-zäöü]{1,}[._-][a-zäöü\-]{2,}$", local))

def is_generic(email, company_tokens=()):
    local = email.split("@")[0].lower()
    if local in GENERIC or any(local.startswith(g) and not re.search(r"[._-]", local[len(g):][:1] or "x") is None for g in ()): return True
    if re.sub(r"[\d._-]", "", local) in GENERIC: return True
    if any(local.startswith(g + "@") for g in GENERIC): return True
    if any(local == t for t in company_tokens): return True
    if any(g in local for g in ("info", "kontakt", "office", "verwaltung", "bewerbung", "datenschutz", "service", "noreply", "karriere")): return True
    return False

def person_tokens(name):
    toks = [de_ascii(t) for t in name.replace("Dr. ", "").replace("Prof. ", "").split() if len(t.strip(".")) > 1]
    return toks

def email_matches_person(email, name):
    if not name: return False
    local = de_ascii(email.split("@")[0])
    toks = person_tokens(name)
    if not toks: return False
    last = toks[-1]
    first = toks[0]
    return (len(last) >= 3 and last in local) or (len(first) >= 4 and local.startswith(first) and len(local) <= len(first) + 2)

def infer_pattern(personal_emails, people_seen):
    """Infer the local-part pattern of a domain from personal e-mails whose owner name is known."""
    for e in personal_emails:
        local = de_ascii(e.split("@")[0])
        for n in people_seen:
            t = person_tokens(n)
            if len(t) < 2: continue
            f, l = t[0], t[-1]
            if local == f"{f}.{l}": return "vorname.nachname"
            if local == f"{f[0]}.{l}": return "v.nachname"
            if local == f"{f[0]}{l}": return "vnachname"
            if local == f"{f}{l}": return "vornamenachname"
            if local == f"{f}_{l}": return "vorname_nachname"
            if local == f"{f}-{l}": return "vorname-nachname"
            if local == l: return "nachname"
            if local == f: return "vorname"
    # pattern by shape only (name unknown)
    for e in personal_emails:
        local = e.split("@")[0].lower()
        if re.match(r"^[a-zäöü]\.[a-zäöü\-]{2,}$", local): return "v.nachname"
        if re.match(r"^[a-zäöü]{2,}\.[a-zäöü\-]{2,}$", local): return "vorname.nachname"
    return ""

def build_email(name, pattern, domain):
    t = person_tokens(name)
    if len(t) < 2 or not domain: return ""
    f, l = t[0], t[-1]
    m = {"vorname.nachname": f"{f}.{l}", "v.nachname": f"{f[0]}.{l}", "vnachname": f"{f[0]}{l}", "vornamenachname": f"{f}{l}", "vorname_nachname": f"{f}_{l}",
         "vorname-nachname": f"{f}-{l}", "nachname": l, "vorname": f}
    return (m.get(pattern) or "") + ("@" + domain if m.get(pattern) else "")

LEGAL = r"\b(gmbh|mbh|ug|haftungsbeschrankt|ohg|kg|co|e\.?k\.?|ag|gbr|und|hausverwaltung(en)?|immobilien(verwaltung)?|verwaltung|berlin|grundbesitz|management|property)\b"
def nkey(n):
    n = strip_accents(de_ascii(n))
    n = re.sub(LEGAL, " ", n); n = re.sub(r"[^a-z0-9]", "", n)
    return n
