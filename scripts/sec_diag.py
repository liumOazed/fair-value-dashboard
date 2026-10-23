import urllib.request, urllib.error
H = [{"User-Agent": "fair-value-dashboard liumOazed@users.noreply.github.com", "Accept-Encoding": "gzip, deflate", "Host": "www.sec.gov"},
     {"User-Agent": "Fair Value Dashboard liumOazed@users.noreply.github.com"},
     {"User-Agent": "Mozilla/5.0 (compatible; fair-value-dashboard; +liumOazed@users.noreply.github.com)"}]
for url in ["https://www.sec.gov/files/company_tickers.json", "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
            "https://data.sec.gov/submissions/CIK0000320193.json"]:
    for h in H:
        h = dict(h)
        if "data.sec.gov" in url and h.get("Host"): h["Host"] = "data.sec.gov"
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30)
            print("OK ", r.status, url, h["User-Agent"][:40], len(r.read()))
        except urllib.error.HTTPError as e:
            print("ERR", e.code, url, h["User-Agent"][:40], e.read()[:120])
        except Exception as e:
            print("EXC", url, e)
