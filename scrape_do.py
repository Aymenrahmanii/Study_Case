"""Scrape Das Oertliche topic pages for Berlin property managers (uses the embedded handlerData JSON)."""
import json, re, sys, time
import requests
from bs4 import BeautifulSoup

OUT = sys.argv[1]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
TERMS = ["Hausverwaltung", "Immobilienverwaltung", "WEG-Verwaltung", "Hausverwaltungen", "Mietverwaltung"]
s = requests.Session(); s.headers.update(UA)
rows, seen = [], set()
for term in TERMS:
    page = 1; empty = 0
    while page < 80:
        url = f"https://www.dasoertliche.de/Themen/{term}/Berlin.html" if page == 1 else f"https://www.dasoertliche.de/Themen/{term}/Berlin-Seite-{page}.html"
        try:
            r = s.get(url, timeout=30)
        except Exception as e:
            print("err", url, e); time.sleep(3); continue
        if r.status_code != 200: print(term, "status", r.status_code, "page", page); break
        m = re.search(r"handlerData\s*=\s*(\[\[.*?\]\]);", r.text, re.S)
        if not m: print(term, "no data page", page); break
        try: data = json.loads(m.group(1))
        except Exception: print("json fail", page); break
        soup = BeautifulSoup(r.text, "html.parser")
        cats = {h.get("id"): (h.select_one(".category").get_text(strip=True) if h.select_one(".category") else "") for h in soup.select("div.hit")}
        dist = {}
        for h in soup.select("div.hit"):
            ad = h.find("address")
            dist[h.get("id")] = " ".join(ad.get_text(" ", strip=True).split()) if ad else ""
        new = 0
        for i, d in enumerate(data):
            key = d[0]
            if key in seen: continue
            seen.add(key); new += 1
            rows.append({"do_id": d[0], "term": term, "name": d[14], "website": d[3], "zip": d[8], "street": f"{d[9]} {d[10]}".strip(),
                         "phone": d[11], "email_dir": d[17], "do_url": d[15], "address_raw": dist.get(f"entry_{i+1}", ""), "do_category": cats.get(f"entry_{i+1}", "")})
        print(term, "page", page, "items", len(data), "new", new, flush=True)
        if new == 0:
            empty += 1
            if empty >= 2: break
        else: empty = 0
        page += 1; time.sleep(0.4)
json.dump(rows, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("TOTAL", len(rows))
