"""Website discovery without a search engine: generate candidate domains from the company name, resolve them,
and accept a candidate only if the site (home/impressum/kontakt) contains the company's postcode or phone number."""
import json, re, sys, socket, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
import requests, urllib3
from common import de_ascii
urllib3.disable_warnings()
INP, OUT = sys.argv[1], sys.argv[2]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
socket.setdefaulttimeout(5)
GENERIC_W = {"gmbh", "mbh", "ug", "haftungsbeschrankt", "kg", "co", "ohg", "ek", "e", "k", "ag", "gbr", "und", "berlin", "der", "die", "das", "fur", "fuer", "von", "dipl", "kfm",
             "hausverwaltung", "hausverwaltungen", "immobilien", "immobilienverwaltung", "verwaltung", "verwaltungs", "verwaltungsgesellschaft", "grundstucksverwaltung",
             "grundstuecksverwaltung", "grundbesitz", "grundbesitzverwaltung", "gesellschaft", "management", "property", "service", "services", "immobilienservice", "haus",
             "grundstucks", "grundstuecks", "hausverwalter", "inh", "inhaber", "dr", "mietverwaltung", "weg", "wohnungsverwaltung", "haeuserverwaltung", "hauserverwaltung", "objektverwaltung"}

def digits(s): return re.sub(r"\D", "", s or "")

def candidates(name):
    n = de_ascii(name).replace("&", " und ")
    n = re.sub(r"[^a-z0-9 \-]", " ", n)
    toks = [t for t in n.split() if t]
    core = [t for t in toks if t not in GENERIC_W and len(t) > 1]
    if not core: return []
    a = core[0]; ab = "-".join(core[:2]); ab2 = "".join(core[:2])
    c = []
    for base in dict.fromkeys([a, ab, ab2]):
        c += [f"{base}.de", f"hausverwaltung-{base}.de", f"{base}-hausverwaltung.de", f"hv-{base}.de", f"{base}-immobilien.de", f"{base}-verwaltung.de",
              f"{base}-hausverwaltungen.de", f"hausverwaltung{base}.de", f"{base}-berlin.de", f"{base}.berlin", f"{base}-immobilienverwaltung.de", f"{base}-hv.de"]
    if "hausverwaltung" in toks or "hausverwaltungen" in toks: c.insert(0, f"{a}-hausverwaltung.de")
    return list(dict.fromkeys(c))[:20]

def resolves(d):
    try: socket.gethostbyname(d); return True
    except Exception: return False

def page(u):
    try:
        r = requests.get(u, headers=UA, timeout=(4, 6), verify=False)
        return r.text if r.status_code < 400 else ""
    except Exception: return ""

def validate(d, c):
    txt = page(f"https://{d}/") or page(f"http://{d}/")
    if not txt or len(txt) < 500: return False
    if re.search(r"domain (is|ist) (for sale|zu verkaufen)|sedo|parkingcrew|this domain|Domain kaufen", txt, re.I): return False
    txt += page(f"https://{d}/impressum") + page(f"https://{d}/kontakt")
    ph = digits(c.get("phone"))[-6:]
    return bool((c.get("plz") and c["plz"] in txt and re.search(r"verwalt|Immobil|Hausverw", txt, re.I)) or (len(ph) >= 6 and ph in digits(txt)))

def work(c):
    for d in candidates(c["name"]):
        if resolves(d) and validate(d, c): return d
    return None

comps = json.load(open(INP, encoding="utf8"))
todo = [i for i, c in enumerate(comps) if not c.get("domain")]
print("to guess", len(todo), flush=True)
found = 0
from concurrent.futures import wait
ex = ThreadPoolExecutor(max_workers=32)
futs = {ex.submit(work, comps[i]): i for i in todo}
done, pending = wait(futs, timeout=900)   # hard cap 15 min; stragglers are dropped
for f in done:
    i = futs[f]
    try: d = f.result()
    except Exception: d = None
    if d:
        comps[i]["website"] = f"https://{d}/"; comps[i]["domain"] = d; comps[i]["website_source"] = "domain guess + validated (PLZ/phone match)"; found += 1
json.dump(comps, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("found", found, "of", len(todo), "timed out", len(pending), flush=True)
os._exit(0)
