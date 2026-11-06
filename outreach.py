"""Outreach agent: for every Tier-A/B lead, Claude proposes the sales play, the hook and a German first sentence for a
phone call or LinkedIn message (not cold e-mail – § 7 UWG). Input is ONLY the lead's structured facts from the sheet plus a
fixed, verified description of Heidi Systems; outputs are checked so they cannot introduce facts that are not in the input."""
import json, os, re, sys, subprocess, shutil
from concurrent.futures import ThreadPoolExecutor

BUILT, OUT = sys.argv[1], sys.argv[2]
rows = json.load(open(BUILT, encoding="utf8"))["rows"]
W = {"S_fit": 25, "S_size": 25, "S_digital": 10, "S_trigger": 15, "S_reach": 15, "S_channel": 10}
E = {"E_fit": 25, "E_size": 25, "E_trigger": 15, "E_reach": 15, "E_digital": 10, "E_channel": 10}
def sc(x): return sum(x[k] * W[k] for k in W) / 100 * 10
def cov(x): return sum(x[k] * E[k] for k in E) / 100
leads = [x for x in rows if not x["Disqualified reason"] and cov(x) >= 0.6 and sc(x) >= 50]
leads.sort(key=lambda x: -sc(x))
print("leads", len(leads), flush=True)

HEIDI = ("Heidi Systems GmbH (Berlin) – metering service provider for property managers and owners: radio-based digital consumption metering "
         "(heat meters, hot- and cold-water meters, smoke detectors); readings flow directly into a dashboard and into the operating-cost / "
         "heating-cost billing; installation by regional master craftsmen; partner company of the VDIV (association of property managers). "
         "Regulatory context: HeizkostenV § 5 – all meters must be remotely readable by 31.12.2026; heat and water meters must be re-calibrated "
         "or replaced every 6 years (MessEV).")
SYSTEM = "You are a careful B2B sales-development assistant. You only use the facts given. Reply with one JSON array and nothing else."
FIELDS = ["Company", "Segment", "Management type", "Residential focus", "Est. units", "Units scope", "Size basis", "Current metering provider (mentioned)",
          "Software / portal seen", "Associations", "Hiring", "Heating-cost billing on site", "Bezirk", "Decision maker", "Role"]

def prompt(batch):
    items = [{"id": i, **{f: x.get(f, "") for f in FIELDS}} for i, x in batch]
    return (f"Seller:\n{HEIDI}\n\nLeads (JSON):\n{json.dumps(items, ensure_ascii=False)}\n\n"
            "For EACH lead return an object: {\"id\": <id>, \"play\": \"WEG\" | \"Rental\" | \"WEG + rental\" | \"Owner / tender\", "
            "\"hook\": <English, max 18 words, the strongest reason to talk now, using only the lead's facts and the seller/regulatory facts>, "
            "\"channel\": \"Phone\" | \"LinkedIn\" | \"VDIV intro\" (VDIV intro only if Associations contains VDIV), "
            "\"opener_de\": <one German sentence in Sie-form, max 35 words, for a phone call or LinkedIn message to the decision maker; "
            "start with 'Guten Tag <first name> <last name>,' – NEVER use Herr/Frau or guess gender; no prices, no promises, no marketing adjectives, "
            "describe Heidi only with the seller facts given (radio-based meters, dashboard, data into the billing, regional installers, VDIV partner); "
            "end with a question; mention the 31.12.2026 deadline only as a regulatory fact>}. If no decision maker is given, start with 'Guten Tag,'. "
            "If 'Size basis' is not 'Units stated', do not mention a unit number. Return a JSON array.")

def call(p):
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        m = anthropic.Anthropic().messages.create(model="claude-haiku-4-5", max_tokens=4000, system=SYSTEM, messages=[{"role": "user", "content": p}])
        return m.content[0].text, 0.0
    mcp = os.path.join(os.path.dirname(OUT), "mcp_empty.json"); open(mcp, "w").write('{"mcpServers":{}}')
    cmd = [shutil.which("claude") or "claude", "-p", "--model", "haiku", "--output-format", "json", "--system-prompt", SYSTEM, "--tools", "",
           "--strict-mcp-config", "--mcp-config", mcp, "--setting-sources", ""]
    r = subprocess.run(cmd, input=p, capture_output=True, text=True, encoding="utf8", timeout=300)
    d = json.loads(r.stdout); return d.get("result", ""), d.get("total_cost_usd", 0.0)

def check(o, x):
    """Guardrails: no numbers except stated units / 2026 / 6; incumbent named only if given; no e-mail channel."""
    txt = (o.get("hook", "") + " " + o.get("opener_de", ""))
    allowed = {"2026", "31", "12", "31.12.2026", "6", "5"}
    if x.get("Size basis") == "Units stated" and x.get("Est. units"):
        u = int(x["Est. units"]); allowed |= {str(u), f"{u:,}".replace(",", "."), f"{u:,}"}
    nums = set(re.findall(r"(?<![A-Za-z])\d[\d.,]*\d(?![A-Za-z])|(?<![A-Za-z\d])\d(?![A-Za-z\d])", txt))
    bad = [n for n in nums if n.strip(".,") not in allowed]
    for brand in ("Techem", "ista", "Brunata", "Minol", "Kalo", "Qundis", "Metrona"):
        if re.search(r"\b" + brand + r"\b", txt) and brand not in (x.get("Current metering provider (mentioned)") or ""): bad.append(brand)
    op = o.get("opener_de", "")
    if re.search(r"\b(Herr|Frau|Herrn)\b", op): bad.append("gendered salutation")
    if re.search(r"rechtssicher|bewährt|skalierbar|günstig|kostenlos|kostenfrei|sparen|Ersparnis|garantier|nahtlos|integrier|kompatib|Schnittstelle|\bAPI\b|marktführend|beste|einzigartig|profitieren", op, re.I): bad.append("marketing claim")
    if o.get("channel") == "VDIV intro" and "VDIV" not in (x.get("Associations") or ""): o["channel"] = "Phone"
    if re.search(r"e-?mail", o.get("channel", ""), re.I): o["channel"] = "Phone"
    o["_flags"] = bad
    return o

batches = [list(enumerate(leads))[i:i + 10] for i in range(0, len(leads), 10)]
def work(b):
    for _ in range(2):
        try:
            txt, cost = call(prompt(b))
            arr = json.loads(re.search(r"\[.*\]", txt, re.S).group(0))
            return arr, cost
        except Exception as e:
            err = e
    return [], 0.0
res, total = {}, 0.0
with ThreadPoolExecutor(max_workers=5) as ex:
    for b, (arr, cost) in zip(batches, ex.map(work, batches)):
        total += cost
        idx = dict(b)
        for o in arr:
            i = o.get("id")
            if i in idx: res[idx[i]["Company"]] = check(o, idx[i])
# second pass for flagged leads with a stricter instruction; anything still ungrounded is dropped
STRICT = " IMPORTANT: do not mention ANY number except the date 31.12.2026."
flag_ids = [k for k, v in res.items() if v["_flags"]]
by_name = {x["Company"]: x for x in leads}
retry = [list(enumerate([by_name[k] for k in flag_ids]))[i:i + 10] for i in range(0, len(flag_ids), 10)]
def work2(b):
    try:
        txt, cost = call(prompt(b) + STRICT); return json.loads(re.search(r"\[.*\]", txt, re.S).group(0)), cost
    except Exception: return [], 0.0
with ThreadPoolExecutor(max_workers=5) as ex:
    for b, (arr, cost) in zip(retry, ex.map(work2, retry)):
        total += cost; idx = dict(b)
        for o in arr:
            if o.get("id") in idx: res[idx[o["id"]]["Company"]] = check(o, idx[o["id"]])
flagged = {k: v for k, v in res.items() if v["_flags"]}
for k in flagged: res[k]["opener_de"] = ""; res[k]["hook"] = re.sub(r"\d[\d.,]*\s*(units|Einheiten)", "", res[k]["hook"]) + " [opener dropped: ungrounded detail]"
print("retried", len(flag_ids))
json.dump(res, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("outreach", len(res), "of", len(leads), "flagged+dropped", len(flagged), "cost $%.2f" % total)
