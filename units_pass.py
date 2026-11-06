"""Unit-count pass: for promising leads without a stated portfolio size, read the 'Über uns / Unternehmen / Referenzen /
Leistungen / Zahlen' pages, collect every sentence that pairs a number with units / flats / buildings, and let Claude pick
the CURRENTLY MANAGED portfolio figure. Grounded: the returned quote must be one of the candidate sentences and contain the
number; staffing rules, sales, construction and historic figures are rejected."""
import json, os, re, sys, time, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import enrich

BUILT, OUT = sys.argv[1], sys.argv[2]
rows = json.load(open(BUILT, encoding="utf8"))["rows"]
W = {"S_fit": 25, "S_size": 25, "S_digital": 10, "S_trigger": 15, "S_reach": 15, "S_channel": 10}
def sc(x): return sum(x[k] * W[k] for k in W) / 100 * 10
todo = [x for x in rows if not x["Disqualified reason"] and sc(x) >= 35 and x["Website status"] == "ok" and x.get("Website check") == "ok"
        and not x["Size basis"].startswith(("Units stated", "Buildings stated"))]
print("firms without stated size", len(todo), flush=True)
KEYS = ("ueber", "uber", "über", "unternehmen", "wir", "referenz", "leistung", "zahlen", "portfolio", "bestand", "objekte", "verwaltung", "history", "geschichte", "profil")
UNIT = r"(Wohn- und Gewerbeeinheiten|Wohneinheiten|Gewerbeeinheiten|Mieteinheiten|Verwaltungseinheiten|Einheiten|Wohnungen|Objekte|Liegenschaften|Eigentümergemeinschaften|WEGs?|Häuser|Mietshäuser|Gebäude|Immobilien)"
CAND = re.compile(r"(\d{1,3}(?:[.\s]\d{3})+|\d{2,6})\s*\+?\s*(?:\w+\s){0,3}" + UNIT, re.I)

def candidates(x):
    h, final = enrich.fetch(x["Website"])
    if not h: return x, []
    dom = urlparse(final).netloc.replace("www.", "")
    soup = BeautifulSoup(h, "html.parser"); links = []
    for a in soup.find_all("a", href=True):
        u = urljoin(final, a["href"]); pu = urlparse(u)
        if dom in pu.netloc and any(k in (pu.path + " " + a.get_text(" ", strip=True)).lower() for k in KEYS) and u.split("#")[0] not in links:
            links.append(u.split("#")[0])
    texts = [enrich.text_of(h)]
    for u in links[:6]:
        hh, _ = enrich.fetch(u); time.sleep(0.8)
        if hh: texts.append(enrich.text_of(hh))
    out = []
    for t in texts:
        for m in CAND.finditer(t):
            s = t[max(0, m.start() - 110): m.end() + 70].strip()
            if s not in out: out.append(s)
    return x, out[:8]

SYSTEM = "You extract one fact from German property-manager websites. Reply with one JSON array and nothing else."
def prompt(batch):
    items = [{"id": i, "company": x["Company"], "sentences": c} for i, (x, c) in enumerate(batch)]
    return ("For each company, decide from its sentences how many units (Wohnungen / Einheiten) or buildings / WEGs the company CURRENTLY MANAGES. "
            "Ignore: units sold, built, renovated or brokered; 'experience with' figures; per-manager limits ('nicht mehr als … pro Verwalter'); historic or target figures; "
            "a statement about ONE building (e.g. 'Alle 28 Wohnungen haben …'); numbers about years, staff, m² or euros. "
            "If the sentences only list several reference objects with unit counts, return the SUM of those counts and kind='sum_of_references'; otherwise kind='total'. "
            "Return [{\"id\": <id>, \"units\": int|null, \"buildings\": int|null, \"kind\": \"total\"|\"sum_of_references\", "
            "\"quote\": <the exact sentence(s) you used, copied verbatim, with every double-quote character replaced by a single quote, or null>, "
            "\"scope\": \"Berlin\"|\"Germany-wide\"|\"unknown\"}]. If unsure, return nulls.\n\n" + json.dumps(items, ensure_ascii=False))

def call(p):
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        m = anthropic.Anthropic().messages.create(model="claude-haiku-4-5", max_tokens=3000, system=SYSTEM, messages=[{"role": "user", "content": p}])
        return m.content[0].text, 0.0
    mcp = os.path.join(os.path.dirname(OUT), "mcp_empty.json"); open(mcp, "w").write('{"mcpServers":{}}')
    cmd = [shutil.which("claude") or "claude", "-p", "--model", "haiku", "--output-format", "json", "--system-prompt", SYSTEM, "--tools", "",
           "--strict-mcp-config", "--mcp-config", mcp, "--setting-sources", ""]
    r = subprocess.run(cmd, input=p, capture_output=True, text=True, encoding="utf8", timeout=300)
    d = json.loads(r.stdout); return d.get("result", ""), d.get("total_cost_usd", 0.0)

with ThreadPoolExecutor(max_workers=4) as ex: cands = list(ex.map(candidates, todo))
cands = [(x, c) for x, c in cands if c]
print("firms with candidate sentences", len(cands), flush=True)
res, cost, rejected = {}, 0.0, 0
debug = []
for i in range(0, len(cands), 8):
    batch = cands[i:i + 8]
    arr = None
    for attempt in range(3):
        try:
            txt, cst = call(prompt(batch)); cost += cst
            arr = json.loads(re.search(r"\[.*\]", txt, re.S).group(0)); break
        except Exception as e:
            print("batch retry", attempt, e)
    if arr is None: continue
    for o in arr:
        if o.get("id") is None or o["id"] >= len(batch): continue
        x, c = batch[o["id"]]
        q = o.get("quote") or ""
        u, b = o.get("units"), o.get("buildings")
        val = u if isinstance(u, int) else (b if isinstance(b, int) else None)
        if val is None: continue
        src = " ".join(c)
        in_src = bool(q) and (q.strip()[:50] in src or any(sn[:50] in q for sn in c) or all(part.strip()[:30] in src for part in re.split(r"[;…]|\.\.\.", q) if len(part.strip()) > 12))
        nums_q = [int(re.sub(r"[.\s]", "", n)) for n in re.findall(r"(\d{1,3}(?:[.\s]\d{3})+|\d+)\s*(?:Wohn|Gewerbe|Einheit|Wohnung|VE\b|Miet)", q)]
        if o.get("kind") == "sum_of_references":
            # never trust the model's arithmetic: recompute the sum from the quoted numbers (a lower bound of the portfolio)
            ok = in_src and len(nums_q) >= 3 and not re.search(r"\bdem Objekt\b|\bdas Objekt\b|\bdieses Objekt", q)   # ≥3 listed objects, not one building
            if ok: val = sum(nums_q); u = val; b = None
        else:
            ok = in_src and (re.sub(r"\D", "", str(val)) in re.sub(r"[.\s]", "", q) or (len(nums_q) >= 2 and sum(nums_q) == val))
        bad = re.search(r"verkauft|vermittelt|gebaut|errichtet|saniert|modernisiert|nicht mehr als|pro Verwalter|je Verwalter|maximal|höchstens|Erfahrung|Alle \d+ Wohnungen", q, re.I)
        debug.append({"company": x["Company"], "val": val, "kind": o.get("kind"), "quote": q, "ok": bool(ok), "bad": bool(bad), "cands": c[:3]})
        if not ok or bad or not (10 <= val <= 150000): rejected += 1; continue
        res[urlparse(x["Website"]).netloc.lower().replace("www.", "")] = {"company": x["Company"], "units": u if isinstance(u, int) else None,
                                                                           "buildings": b if isinstance(b, int) else None, "quote": q[:240], "scope": o.get("scope", "unknown"), "kind": o.get("kind", "total")}
json.dump(res, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
json.dump(debug, open(OUT.replace(".json", "_debug.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("unit counts found", len(res), "| rejected by grounding", rejected, "| cost $%.2f" % cost)
