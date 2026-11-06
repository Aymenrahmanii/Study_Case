"""AI qualification agent: Claude reads each firm's Impressum / Team / Leistungen / Home / Karriere text and returns a
typed JSON record. Every value is then grounded against the source text (names, e-mails, numbers must appear in it);
ungrounded values are dropped. Uses the Anthropic API if ANTHROPIC_API_KEY is set, else the Claude Code CLI headless."""
import json, os, re, sys, subprocess, time
from concurrent.futures import ThreadPoolExecutor, wait

TEXTDIR, OUTDIR = sys.argv[1], sys.argv[2]
MODEL = os.environ.get("EXTRACT_MODEL", "haiku")
os.makedirs(OUTDIR, exist_ok=True)
MCP_EMPTY = os.path.join(OUTDIR, "..", "mcp_empty.json")
open(MCP_EMPTY, "w").write('{"mcpServers":{}}')

SYSTEM = "You are a precise B2B data-extraction function for a German metering service provider (Messdienstleister). You only use facts stated in the provided website text. Reply with one JSON object and nothing else."
SCHEMA = """{
  "is_third_party_property_manager": true|false,      // manages buildings/units for third-party owners (WEG, rental owners)
  "disqualify_reason": null | "pure broker" | "commercial only" | "only single flats (SEV)" | "not a property manager" | "own portfolio only",
  "management_types": [ "WEG" | "Miet" | "SEV" | "Gewerbe" ],
  "residential_focus": "residential" | "mixed" | "commercial" | "unknown",
  "managed_units": integer|null,          // residential/commercial units (Einheiten/Wohnungen) managed, only if stated
  "managed_buildings": integer|null,      // objects/buildings/WEGs managed, only if stated
  "units_evidence": string|null,          // exact short quote from the text supporting the number
  "employees": integer|null,              // only if stated
  "current_metering_provider": [string],  // e.g. Techem, ista, Brunata, Minol, Kalo, Qundis, only if named as their provider/partner
  "property_software": [string],          // ERP / portal named, e.g. Domus, Karthago, Haufe PowerHaus, Aareon Wodis, casavi, immoware24, facilioo
  "associations": [string],               // e.g. VDIV, BVI, IVD, Haus & Grund, BFW
  "hiring": true|false,
  "hiring_roles": [string],
  "people": [ { "name": string, "role": string,
                "role_category": "Geschäftsführung" | "Leitung WEG/Miet" | "Technik/Objektmanagement" | "Abrechnung/Buchhaltung" | "Other",
                "email": string|null, "phone": string|null } ],   // max 6, decision makers first; email only if written in the text
  "summary": string                       // one sentence in English: who they are and what they manage
}"""

def prompt(doc):
    parts = [f"Company: {doc['company']}  Website: {doc['website']}"]
    for k in ("impressum", "team", "leistung", "home", "karriere", "kontakt"):
        if doc["pages"].get(k): parts.append(f"--- {k.upper()} PAGE ---\n{doc['pages'][k]}")
    return "\n\n".join(parts) + "\n\nExtract this JSON (null/[] when not stated; never guess):\n" + SCHEMA

def call_claude(p):
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        m = anthropic.Anthropic().messages.create(model=os.environ.get("EXTRACT_API_MODEL", "claude-haiku-4-5"), max_tokens=1500, system=SYSTEM,
                                                  messages=[{"role": "user", "content": p}])
        return m.content[0].text, 0.0
    import shutil
    cmd = [shutil.which("claude") or "claude", "-p", "--model", MODEL, "--output-format", "json", "--system-prompt", SYSTEM, "--tools", "",
           "--strict-mcp-config", "--mcp-config", MCP_EMPTY, "--setting-sources", ""]
    r = subprocess.run(cmd, input=p, capture_output=True, text=True, encoding="utf8", timeout=180, shell=False)
    d = json.loads(r.stdout)
    return d.get("result", ""), d.get("total_cost_usd", 0.0)

def parse(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0)) if m else None

def norm(s): return re.sub(r"\s+", " ", s or "").lower()
def digits(s): return re.sub(r"\D", "", s or "")

def ground(rec, doc):
    src = norm(" ".join(doc["pages"].values()))
    src_d = re.sub(r"[.\s]", "", src)
    flags = []
    for f in ("managed_units", "managed_buildings", "employees"):
        v = rec.get(f)
        if isinstance(v, (int, float)) and v:
            if str(int(v)) not in src_d: flags.append(f"{f} {v} not found in text → dropped"); rec[f] = None
    people = []
    for p in rec.get("people") or []:
        n = p.get("name") or ""
        last = n.replace("Dr.", "").split()[-1] if n.split() else ""
        if not last or norm(last) not in src: flags.append(f"person '{n}' not in text → dropped"); continue
        if p.get("email") and norm(p["email"]) not in src.replace("[at]", "@").replace("(at)", "@").replace(" @ ", "@"):
            flags.append(f"email {p['email']} not in text → removed"); p["email"] = None
        people.append(p)
    rec["people"] = people[:6]
    rec["current_metering_provider"] = [m for m in rec.get("current_metering_provider") or [] if norm(m) in src]
    rec["property_software"] = [m for m in rec.get("property_software") or [] if norm(m.split()[0]) in src]
    rec["_grounding_flags"] = flags
    return rec

def work(fn):
    out = os.path.join(OUTDIR, fn)
    if os.path.exists(out): return "cached", 0.0
    doc = json.load(open(os.path.join(TEXTDIR, fn), encoding="utf8"))
    for attempt in range(2):
        try:
            txt, cost = call_claude(prompt(doc))
            rec = parse(txt)
            if rec is None: raise ValueError("no json")
            rec = ground(rec, doc)
            rec["_model"] = MODEL; rec["_company"] = doc["company"]; rec["_website"] = doc["website"]
            json.dump(rec, open(out, "w", encoding="utf8"), ensure_ascii=False, indent=1)
            return "ok", cost
        except Exception as e:
            err = str(e); time.sleep(3)
    return "fail " + err[:80], 0.0

files = sorted(os.listdir(TEXTDIR))
print("firms", len(files), flush=True)
ex = ThreadPoolExecutor(max_workers=6)
futs = {ex.submit(work, f): f for f in files}
done, pending = wait(futs, timeout=1700)
res = [f.result() for f in done]
from collections import Counter
print(Counter(r[0].split()[0] for r in res), "cost $%.2f" % sum(r[1] for r in res), "timed out", len(pending), flush=True)
os._exit(0)
