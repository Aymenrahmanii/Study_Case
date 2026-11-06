"""Attach Jacasa listing data to directory companies (name/zip, street/zip, fuzzy) and add unmatched Jacasa firms."""
import json, re, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import nkey, de_ascii
comps = json.load(open(sys.argv[1], encoding="utf8")); jac = json.load(open(sys.argv[2], encoding="utf8"))
# ---------- merge Jacasa ----------
def street_key(s): return re.sub(r"[^a-z0-9]", "", de_ascii(s or "").replace("strasse", "str").replace("straße", "str"))
by_name = collections.defaultdict(list); by_addr = {}
for i, c in enumerate(comps):
    for n in c.get("names_seen", [c["name"]]): by_name[nkey(n)].append(i)
    if c.get("street") and c.get("plz"): by_addr[street_key(c["street"]) + c["plz"]] = i
matched = 0
for j in jac:
    i = None
    k = nkey(j["name"])
    cands = by_name.get(k, [])
    cands = [x for x in cands if not j["zip"] or comps[x]["plz"] == j["zip"]] or cands
    if cands: i = cands[0]
    elif j.get("street") and (street_key(j["street"]) + j["zip"]) in by_addr: i = by_addr[street_key(j["street"]) + j["zip"]]
    else:
        # fuzzy: same zip and one name contains the other
        for x, c in enumerate(comps):
            if c["plz"] == j["zip"] and k and (k in nkey(c["name"]) or nkey(c["name"]) in k) and len(min(k, nkey(c["name"]), key=len)) >= 4: i = x; break
    if i is None:
        comps.append({"name": j["name"], "street": j["street"], "plz": j["zip"], "district": "", "phone": "", "website": "", "domain": "", "email_dir": "",
                      "sources": ["Jacasa"], "categories": ["Hausverwaltung (Jacasa)"], "gs_rating": "", "gs_reviews": "", "crawl_status": "no website"})
        i = len(comps) - 1
    else: matched += 1
    c = comps[i]
    if "Jacasa" not in c["sources"]: c["sources"].append("Jacasa")
    c["jac"] = j
print("jacasa matched", matched, "added", len(jac) - matched)

json.dump(comps, open(sys.argv[3], "w", encoding="utf8"), ensure_ascii=False, indent=1)
