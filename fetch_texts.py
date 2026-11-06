"""Fetch compact page text (Impressum, Team/Über uns, Leistungen, Home, Karriere) for the firms that get AI extraction.
Writes one JSON file per firm: {company, domain, pages: {kind: text}}."""
import json, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor, wait
from urllib.parse import urlparse
import enrich

BUILT, OUTDIR, MIN_SCORE = sys.argv[1], sys.argv[2], float(sys.argv[3])
os.makedirs(OUTDIR, exist_ok=True)
W = {"S_fit": 25, "S_size": 25, "S_digital": 10, "S_trigger": 15, "S_reach": 15, "S_channel": 10}
rows = json.load(open(BUILT, encoding="utf8"))["rows"]
LIMITS = {"impressum": 3500, "team": 3500, "leistung": 3000, "home": 2500, "kontakt": 1200, "karriere": 1200}

def key(r): return re.sub(r"[^a-z0-9]+", "_", (urlparse(r["Website"]).netloc or r["Company"]).lower()).strip("_")[:60]

def job(r):
    if os.path.exists(os.path.join(OUTDIR, key(r) + ".json")): return key(r)
    url = r["Website"]
    h, final = enrich.fetch(url)
    if not h: return None
    domain = urlparse(final).netloc.lower().replace("www.", "")
    picks, _ = enrich.pick_links(h, final, domain)
    if r.get("Impressum", "").startswith("http"): picks["impressum"] = [r["Impressum"]] + picks["impressum"]
    pages = {"home": enrich.text_of(h)}
    seen = {final}
    for k in ("impressum", "team", "leistung", "kontakt", "karriere"):
        for u in picks[k][:2]:
            if u in seen: continue
            seen.add(u)
            hh, _ = enrich.fetch(u)
            if hh:
                pages[k] = (pages.get(k, "") + " \n " + enrich.text_of(hh)).strip()
    pages = {k: v[:LIMITS[k]] for k, v in pages.items()}
    out = {"company": r["Company"], "domain": domain, "website": final, "pages": pages}
    json.dump(out, open(os.path.join(OUTDIR, key(r) + ".json"), "w", encoding="utf8"), ensure_ascii=False)
    return key(r)

sel = [r for r in rows if r["Website status"] == "ok" and sum(r[k] * W[k] for k in W) / 100 * 10 >= MIN_SCORE]
print("firms", len(sel), flush=True)
ex = ThreadPoolExecutor(max_workers=20)
futs = [ex.submit(job, r) for r in sel]
done, pending = wait(futs, timeout=600)
print("saved", sum(1 for f in done if f.result()), "timed out", len(pending), flush=True)
os._exit(0)
