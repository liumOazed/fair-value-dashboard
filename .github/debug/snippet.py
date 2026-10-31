import sys; sys.path.insert(0, "scripts"); import drop_watch as W
for t, n in (("APP", "AppLovin Corporation"), ("FICO", "Fair Isaac Corporation"), ("RMD", "ResMed Inc.")):
    print(t, [(x["date"], x["publisher"], x["title"][:90]) for x in W.news(t, n)][:4])
