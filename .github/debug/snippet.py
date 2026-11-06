# Check the fixed universe: how many Nasdaq-100 names the screener now adds beyond the S&P 500
import sys; sys.path.insert(0, "scripts")
import growth_screener as g
u = g.get_universe(); print("universe size:", len(u))
