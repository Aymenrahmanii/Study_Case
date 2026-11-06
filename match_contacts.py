"""Turn the deep contact crawl into proposed upgrades for reviewer approval:
(1) a published personal address of the decision maker → Verified;
(2) a published address of a WEG/rental/technical lead or Prokurist → second contact;
(3) a company address pattern confirmed by ≥2 published team addresses → the decision maker's address becomes Probable."""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import de_ascii, person_tokens, infer_pattern, build_email, email_matches_person

DEEP, OUT = sys.argv[1], sys.argv[2]
deep = json.load(open(DEEP, encoding="utf8"))
ROLE = re.compile(r"WEG|Miet|Verwalter|Objektbetreu|Objektmanag|Property Manag|Teamleit|Abteilungsleit|Leitung|Leiter|Prokurist|technisch|Technik|Bereichsleit|Geschäftsführ|Inhaber", re.I)
NAME = re.compile(r"((?:Dr\.\s)?[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?\s(?:von\s|van\s|de\s)?[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?)")
props = {}
for d in deep:
    if not d.get("personal_found"): continue
    dm = d.get("dm") or ""
    mails = [f["email"] for f in d["personal_found"]]
    p = {"company": d["company"], "dm": dm, "now": d.get("current_email"), "status_now": d.get("status_now")}
    # (1) DM's own published address
    for f in d["personal_found"]:
        if dm and email_matches_person(f["email"], dm):
            t = person_tokens(dm); loc = de_ascii(f["email"].split("@")[0])
            if t and (loc.startswith(t[0][:1]) or t[-1] in loc):
                p["dm_email"] = f["email"]; p["dm_evidence"] = f["context"][-120:]; break
    # (2) second contact by role keyword near the address
    for f in d["personal_found"]:
        if f["email"] == p.get("dm_email"): continue
        ctx = f["context"][-170:]
        if ROLE.search(ctx):
            names = [n for n in NAME.findall(ctx) if not re.search(r"Berlin|Telefon|E-Mail|Email|Mail|Fax|WEG|Verwaltung|Mietverwaltung|Immobilien|Gmbh|GmbH", n)]
            if names:
                nm = names[-1]
                if email_matches_person(f["email"], nm) or de_ascii(nm.split()[-1])[:3] in de_ascii(f["email"]):
                    role = ROLE.search(ctx).group(0)
                    p["second"] = {"name": nm, "role": role, "email": f["email"], "evidence": ctx[-140:]}; break
    # (3) pattern confirmation
    if "dm_email" not in p and dm:
        named = []
        for f in d["personal_found"]:
            ns = NAME.findall(f["context"][-170:])
            if ns: named.append((f["email"], ns[-1]))
        pats = {}
        for e, n in named:
            pt = infer_pattern([e], [n])
            if pt: pats[pt] = pats.get(pt, 0) + 1
        if pats:
            best, cnt = max(pats.items(), key=lambda kv: kv[1])
            dom = mails[0].split("@")[1]
            if cnt >= 2:
                p["pattern"] = best; p["pattern_n"] = cnt; p["dm_pattern_email"] = build_email(dm, best, dom)
    if any(k in p for k in ("dm_email", "second", "dm_pattern_email")): props[d["company"]] = p
json.dump(props, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("firms with proposals", len(props), "| DM published", sum(1 for p in props.values() if "dm_email" in p),
      "| second contacts", sum(1 for p in props.values() if "second" in p), "| pattern confirmed", sum(1 for p in props.values() if "dm_pattern_email" in p))
for k, p in props.items():
    line = f"- {k[:38]:<38} | DM {p['dm'][:24]:<24} now {str(p['now'])[:34]:<34} [{(p['status_now'] or '')[:8]}]"
    if "dm_email" in p: line += f"\n     DM PUBLISHED: {p['dm_email']}  «{p['dm_evidence'][-90:]}»"
    if "dm_pattern_email" in p: line += f"\n     PATTERN {p['pattern']} x{p['pattern_n']} → {p['dm_pattern_email']}"
    if "second" in p: line += f"\n     2ND: {p['second']['name']} ({p['second']['role']}) {p['second']['email']}  «{p['second']['evidence'][-80:]}»"
    print(line)
