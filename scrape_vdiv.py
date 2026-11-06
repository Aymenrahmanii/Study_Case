"""Parse the public member directory of VDIV Berlin-Brandenburg e.V. (https://vdiv-bb.de/mitglieder/) and merge it
into the company list: match by website domain, else normalised name + postcode; unmatched Berlin members are added."""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from common import nkey

INP, OUT, RAW = sys.argv[1], sys.argv[2], sys.argv[3]
URL = "https://vdiv-bb.de/mitglieder/"
html_path = os.path.join(RAW, "vbb.html")
if not os.path.exists(html_path):
    open(html_path, "w", encoding="utf8").write(requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text)
soup = BeautifulSoup(open(html_path, encoding="utf8", errors="ignore").read(), "html.parser")

def tx(el, sel):
    x = el.select_one(sel)
    return " ".join(x.get_text(" ", strip=True).split()) if x else ""

members = []
for li in soup.select("li[id^=cl-]"):
    name = tx(li, ".contact-list-contact-name")
    if not name: continue
    addr2 = tx(li, ".contact-list-address-country-and-state")
    m = re.match(r"(\d{5})\s*(.*)", addr2)
    plz, city = (m.group(1), m.group(2)) if m else ("", addr2)
    web = ""
    for a in li.select(".contact-list-custom-field-value a[href]"): web = a["href"].strip(); break
    members.append({"name": name, "contact": re.sub(r"^(Frau|Herr|Herrn)\s+", "", tx(li, ".contact-list-job-title")),
                    "email": tx(li, ".contact-list-email").lower(), "phone": tx(li, ".contact-list-phone a") or tx(li, ".contact-list-phone"),
                    "street": tx(li, ".contact-list-address-line-1"), "plz": plz, "city": city, "website": web})
berlin = [m for m in members if m["plz"].isdigit() and 10115 <= int(m["plz"]) <= 14199]
json.dump(members, open(os.path.join(RAW, "vdiv_members.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("members", len(members), "Berlin postcode", len(berlin))

def dom(u):
    if not u: return ""
    if not u.startswith("http"): u = "http://" + u
    return urlparse(u).netloc.lower().split(":")[0].replace("www.", "")

comps = json.load(open(INP, encoding="utf8"))
by_dom, by_nk = {}, {}
for i, c in enumerate(comps):
    for d in {dom(c.get("website", "")), (c.get("domain_final") or "").replace("www.", ""), c.get("domain", "")}:
        if d: by_dom.setdefault(d, i)
    for n in c.get("names_seen", [c["name"]]) + [c["name"]]:
        by_nk.setdefault(nkey(n) + (c.get("plz") or ""), i); by_nk.setdefault(nkey(n), i)
matched = added = 0
for m in berlin:
    d = dom(m["website"])
    i = by_dom.get(d) if d else None
    if i is None: i = by_nk.get(nkey(m["name"]) + m["plz"])
    if i is None and len(nkey(m["name"])) >= 6: i = by_nk.get(nkey(m["name"]))
    if i is None:
        comps.append({"name": m["name"], "street": m["street"], "plz": m["plz"], "district": "", "phone": m["phone"], "website": m["website"], "domain": d,
                      "email_dir": "", "sources": [], "categories": ["VDIV member"], "gs_rating": "", "gs_reviews": "", "names_seen": [m["name"]], "crawl_status": "pending" if m["website"] else "no website"})
        i = len(comps) - 1; added += 1
    else: matched += 1
    c = comps[i]
    if "VDIV-BB directory" not in c["sources"]: c["sources"].append("VDIV-BB directory")
    c["vdiv"] = m
    if not c.get("website") and m["website"]: c["website"] = m["website"]; c["domain"] = d; c["crawl_status"] = "pending"
    if not c.get("phone"): c["phone"] = m["phone"]
json.dump(comps, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("matched", matched, "added", added, "total companies", len(comps), "to crawl", sum(1 for c in comps if c.get("crawl_status") == "pending"))
