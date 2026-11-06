"""Scrape Gelbe Seiten listings for property managers in Berlin (several search terms)."""
import base64, json, re, sys, time, html as H
import requests
from bs4 import BeautifulSoup

OUT = sys.argv[1]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
TERMS = ["hausverwaltung", "immobilienverwaltung", "weg-verwaltung", "hausverwaltungen", "mietverwaltung", "grundstücksverwaltung"]
s = requests.Session(); s.headers.update(UA)

def b64(v):
    try: return base64.b64decode(v).decode("utf8", "ignore")
    except Exception: return ""

def parse(htmltext, term):
    soup = BeautifulSoup(htmltext, "html.parser")
    rows = []
    for a in soup.select("article.mod-Treffer"):
        r = {"gs_id": a.get("data-realid"), "term": term}
        n = a.select_one(".mod-Treffer__name"); r["name"] = n.get_text(strip=True) if n else ""
        b = a.select_one(".mod-Treffer--besteBranche"); r["gs_category"] = b.get_text(strip=True) if b else ""
        ad = a.select_one(".mod-AdresseKompakt__adress-text")
        if ad:
            for e in ad.select(".mod-AdresseKompakt__entfernung"): e.decompose()
            t = " ".join(ad.get_text(" ", strip=True).split())
            r["address_raw"] = t
        ph = a.select_one(".mod-TelefonnummerKompakt__phoneNumber"); r["phone"] = ph.get_text(strip=True) if ph else ""
        w = a.select_one("[data-webseiteLink]") or a.select_one("[data-webseitelink]")
        r["website"] = b64(w.get("data-webseitelink") or w.get("data-webseiteLink")) if w else ""
        rt = a.select_one(".mod-BewertungKompakt__number"); r["gs_rating"] = rt.get_text(strip=True) if rt else ""
        rc = a.select_one(".mod-BewertungKompakt__text"); r["gs_reviews"] = rc.get_text(strip=True) if rc else ""
        ch = a.select_one("[data-parameters]")
        if ch:
            try:
                g = json.loads(ch["data-parameters"])["inboxConfig"]["organizationQuery"]["generic"]
                r["email_dir"] = g.get("email", "")
            except Exception: pass
        rows.append(r)
    return rows

allrows = []
for term in TERMS:
    url = f"https://www.gelbeseiten.de/branchen/{term}/berlin"
    h = s.get(url, timeout=30).text
    m = re.search(r'id="loadMoreGesamtzahl">(\d+)<', h)
    total = int(m.group(1)) if m else 0
    rows = parse(h, term)
    pos = len(rows) + 1
    print(term, "total", total, flush=True)
    while pos <= total:
        try:
            j = s.post("https://www.gelbeseiten.de/ajaxsuche", data={"umkreis": "-1", "verwandt": "false", "WAS": term, "WO": "berlin", "position": str(pos), "anzahl": "10", "sortierung": "relevanz"}, timeout=30).json()
        except Exception as e:
            print("err", pos, e); time.sleep(2); continue
        got = parse(j.get("html", ""), term)
        if not got: break
        rows += got; pos += len(got)
        time.sleep(0.3)
    print(term, "scraped", len(rows), flush=True)
    allrows += rows

json.dump(allrows, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("TOTAL rows", len(allrows), "unique", len({r['gs_id'] for r in allrows}))
