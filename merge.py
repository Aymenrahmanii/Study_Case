"""Merge + dedupe directory rows (Gelbe Seiten, Das Oertliche) into one company list."""
import json, re, sys, unicodedata
from urllib.parse import urlparse

gs = json.load(open(sys.argv[1], encoding="utf8"))
do = json.load(open(sys.argv[2], encoding="utf8"))
OUT = sys.argv[3]

def dom(u):
    if not u: return ""
    if not u.startswith("http"): u = "http://" + u
    d = urlparse(u).netloc.lower().split(":")[0]
    return d[4:] if d.startswith("www.") else d

LEGAL = r"\b(gmbh|mbh|ug|haftungsbeschränkt|ohg|kg|co|e\.?k\.?|ag|gbr|und|&|hausverwaltung(en)?|immobilien(verwaltung)?|verwaltung|berlin|grundbesitz|management|property)\b"
def nkey(n):
    n = unicodedata.normalize("NFKD", n.lower()).encode("ascii", "ignore").decode()
    n = re.sub(LEGAL, " ", n); n = re.sub(r"[^a-z0-9]", "", n)
    return n

def parse_addr(raw):
    # "Mexikoplatz 4, 14163 Berlin (Zehlendorf)"  /  "Heesestr. 10 12169 Berlin, Steglitz"
    m = re.search(r"(.*?)[, ]+(\d{5})\s+Berlin[, ]*\(?([^)]*)\)?", raw or "")
    if not m: return "", "", ""
    return m.group(1).strip(" ,"), m.group(2), m.group(3).strip(" ,()")

companies = {}
def add(src, r):
    street, plz, dist = parse_addr(r.get("address_raw", ""))
    plz = r.get("zip") or plz
    street = r.get("street") or street
    d = dom(r.get("website", ""))
    if d in ("facebook.com", "instagram.com", "google.com", "sites.google.com"): d = ""
    key = ("d:" + d) if d else ("n:" + nkey(r["name"]) + plz)
    c = companies.get(key)
    if not c:
        # second chance: same normalized name + zip
        alt = "n:" + nkey(r["name"]) + plz
        for k, v in companies.items():
            if v["_nk"] == alt: c = v; break
    if not c:
        c = companies[key] = {"name": r["name"], "street": street, "plz": plz, "district": dist, "phone": r.get("phone", ""),
                              "website": r.get("website", ""), "domain": d, "email_dir": r.get("email_dir", ""), "sources": [],
                              "categories": [], "gs_rating": "", "gs_reviews": "", "_nk": "n:" + nkey(r["name"]) + plz, "names_seen": []}
    if src not in c["sources"]: c["sources"].append(src)
    if r["name"] not in c["names_seen"]: c["names_seen"].append(r["name"])
    for f in ("street", "plz", "district", "phone", "website", "email_dir"):
        if not c.get(f) and r.get(f if f not in ("street", "plz", "district") else "_") : pass
    if not c["street"] and street: c["street"] = street
    if not c["plz"] and plz: c["plz"] = plz
    if not c["district"] and dist: c["district"] = dist
    if not c["phone"] and r.get("phone"): c["phone"] = r["phone"]
    if not c["website"] and r.get("website"): c["website"] = r["website"]; c["domain"] = d
    if not c["email_dir"] and r.get("email_dir"): c["email_dir"] = r["email_dir"]
    cat = r.get("gs_category") or r.get("do_category")
    if cat and cat not in c["categories"]: c["categories"].append(cat)
    if r.get("gs_rating") and not c["gs_rating"]: c["gs_rating"] = r["gs_rating"]; c["gs_reviews"] = r.get("gs_reviews", "")

for r in gs: add("Gelbe Seiten", r)
for r in do: add("Das Örtliche", r)
out = list(companies.values())
for c in out: c.pop("_nk", None)
json.dump(out, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("companies", len(out), "with website", sum(1 for c in out if c["domain"]), "both sources", sum(1 for c in out if len(c["sources"]) > 1))
