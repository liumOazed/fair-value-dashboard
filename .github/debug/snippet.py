import urllib.request, xml.etree.ElementTree as ET
for url in ["https://feeds.finance.yahoo.com/rss/2.0/headline?s=APP&region=US&lang=en-US",
            "https://news.google.com/rss/search?q=AppLovin+APP+stock+when:7d&hl=en-US&gl=US&ceid=US:en"]:
    try:
        x = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read()
        items = ET.fromstring(x).findall(".//item")
        print(url[:40], len(items))
        for it in items[:5]:
            print("  ", it.findtext("pubDate"), "|", it.findtext("title"), "|", (it.findtext("source") or ""), "|", (it.findtext("link") or "")[:80])
    except Exception as e:
        print(url[:40], "ERR", e)
