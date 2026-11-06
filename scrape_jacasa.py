"""Scrape Jacasa.de Berlin property-manager listing cards (rating, reviews, years, employees, memberships)."""
import json, re, sys, time
import requests
from bs4 import BeautifulSoup
OUT = sys.argv[1]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
rows, seen = [], set()
for page in range(1, 45):
    h = requests.get(f"https://www.jacasa.de/hausverwaltung/be/berlin?page={page}", headers=UA, timeout=30).text
    s = BeautifulSoup(h, "html.parser")
    new = 0
    for a in s.find_all("a", href=True):
        if a.get_text(strip=True) != "Details" or not re.search(r"jacasa.de/hausverwaltung/[a-z0-9\-]+$", a["href"]): continue
        url = a["href"]
        if url in seen: continue
        card, node = a, a
        for _ in range(12):
            node = node.parent
            if node is None: break
            n_details = sum(1 for x in node.find_all("a", href=True) if x.get_text(strip=True) == "Details")
            if n_details > 1: break
            card = node
        heads = card.find_all(["h2", "h3", "h4"])
        name = heads[0].get_text(" ", strip=True) if heads else ""
        t = " ".join(card.get_text(" ", strip=True).split())
        seen.add(url); new += 1
        m_addr = re.search(r"([A-ZÄÖÜa-zäöüß.\- ]+\d+[a-zA-Z]?(?:\s?-\s?\d+)?)\s+(\d{5}) Berlin", t)
        rows.append({
            "jacasa_url": url, "name": name,
            "street": m_addr.group(1).strip() if m_addr else "", "zip": m_addr.group(2) if m_addr else "",
            "jacasa_rating": (re.search(r"(\d,\d)\s+\d+\s+Bewertung", t) or [None, ""])[1],
            "jacasa_reviews": (re.search(r"\d,\d\s+(\d+)\s+Bewertung", t) or [None, ""])[1],
            "jacasa_years": (re.search(r"über (\d+) Jahre Erfahrung", t) or [None, ""])[1],
            "jacasa_employees": (re.search(r"ca\. (\d+) Mitarbeiter", t) or [None, ""])[1],
            "jacasa_membership": "; ".join(re.findall(r"Mitglied (?:im|in der|des|beim) ([^.]*?\))", t)),
            "jacasa_text": t[:400],
        })
    print("page", page, "new", new, flush=True)
    if new == 0: break
    time.sleep(0.5)
json.dump(rows, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("TOTAL", len(rows))
