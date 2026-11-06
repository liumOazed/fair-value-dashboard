# Probe 5: IWM holdings from the SEC's public N-PORT filings (official, quarterly)
import json, os, re, gzip, urllib.request
UA = {"User-Agent": f"fair-value-dashboard {os.environ.get('SEC_CONTACT', 'liumOazed@users.noreply.github.com')}", "Accept-Encoding": "gzip"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
        b = r.read(); return gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b
j = json.loads(get("https://efts.sec.gov/LATEST/search-index?q=%22iShares%20Russell%202000%20ETF%22&forms=NPORT-P"))
hits = j["hits"]["hits"][:5]
for h in hits:
    s = h["_source"]; print(h["_id"], s.get("display_names"), s.get("file_date"), s.get("period_ending"))
# open the newest hit's primary doc
hid = hits[0]["_id"]; adsh, fn = hid.split(":"); cik = hits[0]["_source"]["ciks"][0]
url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/{fn}"
x = get(url).decode("utf-8", "replace"); print(url, len(x))
print("series:", re.findall(r"<seriesName>(.*?)</seriesName>", x)[:2], "n holdings:", x.count("<invstOrSec>"))
m = re.search(r"<invstOrSec>.*?</invstOrSec>", x, re.S); print(m.group(0)[:1500] if m else x[:1500])
