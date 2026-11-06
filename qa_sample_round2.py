"""QA spot-check: draw a stratified random sample (fixed seed) and fetch the LIVE Impressum + home page of each firm,
independently of the pipeline's cached data. Prints compact evidence snippets for a reviewer to judge each field."""
import json, random, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urllib.parse import urljoin, urlparse
import enrich
from common import de_ascii

BUILT, OUT = sys.argv[1], sys.argv[2]
rows = json.load(open(BUILT, encoding="utf8"))["rows"]
W = {"S_fit": 25, "S_size": 25, "S_digital": 10, "S_trigger": 15, "S_reach": 15, "S_channel": 10}
E = {"E_fit": 25, "E_size": 25, "E_trigger": 15, "E_reach": 15, "E_digital": 10, "E_channel": 10}
def tier(x):
    sc = sum(x[k] * W[k] for k in W) / 100 * 10; cov = sum(x[k] * E[k] for k in E) / 100
    if x["Disqualified reason"]: return "Disqualified"
    if cov < 0.6 and sc >= 35: return "Research needed"
    return "A" if sc >= 65 else "B" if sc >= 50 else "C" if sc >= 35 else "D"
for x in rows: x["_tier"] = tier(x)
QUOTA = {"A": 12, "B": 10, "C": 4, "Research needed": 4, "D": 5, "Disqualified": 5}
rnd = random.Random(20261108)
prev = {q["company"] for q in json.load(open(sys.argv[3], encoding="utf8"))["rows"]} if len(sys.argv) > 3 else set()
sample = []
for t, k in QUOTA.items():
    pool = [x for x in rows if x["_tier"] == t and x["Website"].startswith("http") and x["Company"] not in prev and x.get("Directory name") not in prev]
    sample += rnd.sample(pool, min(k, len(pool)))

def snip(text, needle, w=110, maxn=2):
    out = []
    if not needle: return out
    for m in re.finditer(re.escape(needle), text, re.I):
        out.append(text[max(0, m.start() - w): m.end() + w].replace("\n", " "))
        if len(out) >= maxn: break
    return out
import time

res = []
for x in sample:
    site = x["Website"]
    h, final = enrich.fetch(site)
    home = enrich.text_of(h) if h else ""
    imp_url = x["Impressum"] if x["Impressum"].startswith("http") else urljoin(final or site, "/impressum")
    hi, _ = enrich.fetch(imp_url)
    imp = enrich.text_of(hi) if hi else ""
    alltxt = home + " " + imp
    time.sleep(1.5)
    dm = x["Decision maker"]; last = dm.replace("Dr. ", "").split()[-1] if dm else ""
    units = str(x["Est. units"] or "")
    units_fmt = f"{int(units):,}".replace(",", ".") if units.isdigit() else ""
    r = {"tier": x["_tier"], "company": x["Company"], "website": final or site, "impressum": imp_url, "live_ok": bool(h),
         "claims": {k: x[k] for k in ("PLZ", "Street", "Decision maker", "Role", "Personal email", "Email status", "Est. units", "Size basis", "Management type", "Residential focus", "Disqualified reason", "Segment", "AI summary", "VDIV member (directory)")},
         "ev": {"name": snip(alltxt, x["Company"].split()[0], 80, 1), "plz": snip(alltxt, x["PLZ"], 80, 1), "dm": snip(imp or alltxt, last, 120, 2),
                "email": snip(alltxt, (x["Personal email"] or "").split("@")[0], 60, 1), "units": snip(alltxt, units_fmt, 120, 1) or snip(alltxt, units, 120, 1),
                "weg": snip(alltxt, "WEG", 60, 1), "miet": snip(alltxt, "Mietverwaltung", 60, 1), "imp_head": [imp[:600]]}}
    res.append(r)
json.dump(res, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
for i, r in enumerate(res, 1):
    print(f"\n### {i}. [{r['tier']}] {r['company']} | {r['website']} | live={r['live_ok']}")
    c = r["claims"]
    print(f"  CLAIMS: PLZ {c['PLZ']} | DM {c['Decision maker']} ({c['Role']}) | mail {c['Personal email']} [{(c['Email status'] or '')[:10]}] | units {c['Est. units']} ({c['Size basis'][:25]}) | type {c['Management type']} | res {c['Residential focus']} | disq {c['Disqualified reason']} | VDIV {c['VDIV member (directory)']}")
    for k, v in r["ev"].items():
        if v and k != "imp_head": print(f"  {k}: " + " || ".join(s[:230] for s in v[:1]))
    if not r["ev"]["dm"] and r["ev"]["imp_head"][0]: print("  imp_head: " + r["ev"]["imp_head"][0][150:600])
