"""Deep contact pass for the top-N Tier-A firms: follow every internal link that looks like a team / contact / about /
Impressum page (up to 10 pages), collect all e-mail addresses (incl. obfuscated) with the text around them, so a reviewer
can match published personal addresses to named people."""
import json, re, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import enrich
from common import is_generic

BUILT, OUT, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = json.load(open(BUILT, encoding="utf8"))["rows"]
W = {"S_fit": 25, "S_size": 25, "S_digital": 10, "S_trigger": 15, "S_reach": 15, "S_channel": 10}
E = {"E_fit": 25, "E_size": 25, "E_trigger": 15, "E_reach": 15, "E_digital": 10, "E_channel": 10}
def score(x): return sum(x[k] * W[k] for k in W) / 100 * 10
def cov(x): return sum(x[k] * E[k] for k in E) / 100
A = [x for x in rows if not x["Disqualified reason"] and cov(x) >= 0.6 and score(x) >= 65 and x["Website"].startswith("http")]
A.sort(key=lambda x: -score(x))
A = A[:N]
KEYS = ("team", "ansprechpartner", "mitarbeiter", "kontakt", "contact", "ueber-uns", "uber-uns", "about", "wir", "unternehmen", "impressum", "geschaeftsfuehrung", "management", "personen", "menschen")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+(?:@|\s?\[at\]\s?|\s?\(at\)\s?)[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

def job(x):
    site = x["Website"]
    h, final = enrich.fetch(site)
    if not h: return {"company": x["Company"], "site": site, "status": "unreachable"}
    dom = urlparse(final).netloc.replace("www.", "")
    soup = BeautifulSoup(h, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        u = urljoin(final, a["href"]); p = urlparse(u)
        if dom not in p.netloc: continue
        low = (p.path + " " + a.get_text(" ", strip=True)).lower()
        if any(k in low for k in KEYS) and u not in links: links.append(u.split("#")[0])
    pages = {final: h}
    for u in links[:10]:
        if u in pages: continue
        hh, _ = enrich.fetch(u)
        if hh: pages[u] = hh
        time.sleep(1.0)
    found = []
    for u, hh in pages.items():
        txt = enrich.text_of(hh)
        mails = set(m.group(0) for m in EMAIL.finditer(txt)) | set(re.findall(r'mailto:([^"?]+)', hh))
        for m in mails:
            m2 = re.sub(r"\s?[\[(]at[\])]\s?", "@", m).strip().lower()
            if is_generic(m2) or "@" not in m2: continue
            i = txt.lower().find(m.lower()); ctx = txt[max(0, i - 160): i + 40] if i >= 0 else ""
            found.append({"email": m2, "page": u, "context": " ".join(ctx.split())})
    uniq = {}
    for f in found: uniq.setdefault(f["email"], f)
    return {"company": x["Company"], "site": final, "dm": x["Decision maker"], "role": x["Role"], "current_email": x["Personal email"], "status_now": x["Email status"],
            "pages": len(pages), "personal_found": list(uniq.values())[:12]}

with ThreadPoolExecutor(max_workers=4) as ex: res = list(ex.map(job, A))
json.dump(res, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
for i, r in enumerate(res, 1):
    print(f"\n## {i}. {r['company'][:50]} | DM {r.get('dm')} | now {r.get('current_email')} [{(r.get('status_now') or '')[:10]}] | pages {r.get('pages')} {r.get('status','')}")
    for f in r.get("personal_found", []): print(f"   {f['email']:<42} … {f['context'][-150:]}")
