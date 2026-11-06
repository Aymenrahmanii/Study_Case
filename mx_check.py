"""MX check: does the e-mail domain have a mail server? (DNS only – no SMTP probing of mailboxes.)"""
import json, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
BUILT, OUT = sys.argv[1], sys.argv[2]
rows = json.load(open(BUILT, encoding="utf8"))["rows"]
doms = sorted({e.split("@")[1].lower() for r in rows for e in (r["Personal email"], r["Generic email"]) if e and "@" in e})
def mx(d):
    try:
        out = subprocess.run(["nslookup", "-type=mx", d], capture_output=True, text=True, timeout=15).stdout
        hosts = re.findall(r"mail exchanger = (\S+)", out)
        if hosts: return d, hosts
        # no MX: an A record also accepts mail (RFC 5321 fallback)
        out2 = subprocess.run(["nslookup", d], capture_output=True, text=True, timeout=15).stdout
        return d, (["A-record fallback"] if re.search(r"Address(es)?:\s*\d+\.\d+", out2.split("Name:")[-1]) else [])
    except Exception:
        return d, None
with ThreadPoolExecutor(max_workers=24) as ex: res = dict(ex.map(mx, doms))
json.dump(res, open(OUT, "w", encoding="utf8"), indent=1)
print("domains", len(doms), "with MX", sum(1 for v in res.values() if v and v != ["A-record fallback"]), "A only", sum(1 for v in res.values() if v == ["A-record fallback"]), "none", sum(1 for v in res.values() if v == []), "error", sum(1 for v in res.values() if v is None))
