import yfinance as yf, json
print(yf.__version__)
tk = yf.Ticker("APP")
n = tk.news
print(type(n), len(n) if n else n)
if n: print(json.dumps(n[0], default=str)[:1500])
try:
    g = tk.get_news(count=5, tab="news"); print("get_news", len(g)); print(json.dumps(g[0], default=str)[:800] if g else "")
except Exception as e: print("get_news err", e)
