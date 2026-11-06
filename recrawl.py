"""Re-crawl a subset: entries whose crawl failed (try URL variants) or that got a newly discovered website."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import enrich

INP, OUT = sys.argv[1], sys.argv[2]
comps = json.load(open(INP, encoding="utf8"))

def variants(u):
    if not u.startswith("http"): u = "http://" + u
    d = urlparse(u).netloc.replace("www.", ""); path = urlparse(u).path
    return [f"https://www.{d}{path}", f"https://{d}{path}", f"http://www.{d}{path}", f"http://{d}{path}"]

def job(c):
    import time; time.sleep(float(os.environ.get("RECRAWL_PAUSE", "0")))   # politeness pause per site
    for v in variants(c["website"]):
        r = enrich.crawl({"website": v})
        if r.get("crawl_status") == "ok": return r
    return {"crawl_status": "website unreachable"}

idx = [i for i, c in enumerate(comps) if c.get("website") and c.get("crawl_status") != "ok"]
print("recrawl", len(idx), flush=True)
from concurrent.futures import wait
ex = ThreadPoolExecutor(max_workers=int(os.environ.get('RECRAWL_WORKERS', '24')))
futs = {ex.submit(job, comps[i]): i for i in idx}
done, pending = wait(futs, timeout=900)
for f in done:
    try: comps[futs[f]].update(f.result())
    except Exception: pass
json.dump(comps, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("now ok", sum(1 for c in comps if c.get("crawl_status") == "ok"), "of", len(comps), "timed out", len(pending), flush=True)
os._exit(0)
