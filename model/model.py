"""
Fair-value model (modern Graham framework) – shared by the Google Sheet and the dashboard.
All $ figures in billions unless noted. Inputs sourced from Q2-2026 filings / price history as of 2026-10-14 close.
"""
import json, math

AS_OF = "2026-11-10"   # valuation date of the latest update (method: FCF before interest at the required return, minus net debt; advantage period per moat class from November 2026)
GT = 0.025            # terminal growth
PROBS = {"bear": 0.30, "base": 0.50, "bull": 0.20}
import pathlib
_ROOT = pathlib.Path(__file__).resolve().parent.parent
RR = json.load(open(_ROOT / "data/required_returns.json"))     # single source of truth for required returns
def req_return(t):
    if t not in RR["stocks"]: raise SystemExit(f"Add {t} to data/required_returns.json (with a reason)")
    return RR["stocks"][t]["r"]
RATE_GRID = [0.08, 0.09, 0.10, 0.11, 0.12]                     # rate table shown in the drawer (+ the chosen rate)

# ---------------------------------------------------------------- inputs
STOCKS = {
 "AAPL": dict(name="Apple Inc.", price=350.69, shares=14.63, rev=478.834, fcf=136.056, sbc=13.789,
              net_cash=56.824, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=.06,g10=.03,m=.225), base=dict(g1=.09,g10=.04,m=.245), bull=dict(g1=.12,g10=.05,m=.265)),
              notes="TTM to Sep-2026 (= fiscal 2026, year to 26 Sep 2026). Revenue $478.8B, +15.1% (iPhone +21% to $254.1B, Services +13% to $123.3B, Mac +13%, iPad and Wearables flat; Greater China +28%); September quarter +11.7% with iPhone +17% and Services +10%. Guidance for the December quarter: revenue +7-10%, Services +8-9%, gross margin 45-46% (down, mostly higher memory costs, which also limit Mac/iPad supply). FCF = OCF $145.1B - capex $9.0B = $136.1B; SBC $13.8B. FCF margin is flattered by low cash taxes; normalised SBC-adjusted margin 24.5% base (actual TTM 25.5%). Net cash $56.8B = cash $36.3B + marketable securities $100.6B (incl. $80.2B non-current) - commercial paper $2.0B - term debt $78.1B (leases excluded). Shares = Q4 diluted 14.63B; $86.4B bought back in FY26. Tax rate 17.0%. Risks: memory-cost squeeze on margins, App Store fee rulings (EU DMA, US Epic case), China and tariffs."),
 "MSFT": dict(name="Microsoft Corp.", price=530.14, shares=7.446, rev=346.445, fcf=59.957, sbc=12.556,
              net_cash=7.3, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=.12,g10=.035,m=.18), base=dict(g1=.17,g10=.05,m=.25), bull=dict(g1=.20,g10=.06,m=.29)),
              notes="TTM to Sep-2026 (FY27 Q1). Revenue +19% in the quarter (Azure +48%). Cash capex $136B TTM ($39B in the quarter, double a year ago) crushes current FCF (OCF minus cash capex; finance-lease principal not deducted, as before); margin recovers as the build-out matures. Data-centre useful life extended to 25 years, so more new capacity comes via operating leases. Net cash = cash + investments minus bonds and non-current operating leases ($7B, down from $20B). FIN debt incl. leases is an ESTIMATE."),
 "GOOGL": dict(name="Alphabet Inc. (Class A)", price=283.82, shares=12.368, rev=471.098, fcf=19.747, sbc=30.409,
              net_cash=139.996, extra=67.615, mos=0.30,
              scen=dict(bear=dict(g1=.14,g10=.035,m=.13), base=dict(g1=.20,g10=.05,m=.19), bull=dict(g1=.24,g10=.06,m=.24)),
              notes="TTM to Sep-2026. Revenue +25% in Q3 (Cloud +103% to $30.7B). FCF = OCF - capex (company definition); TTM FCF fell to $19.7B as capex hit $51.4B in Q3 (FY26 capex guide $195-205B, 2027 reportedly >$300B), so the starting margin is very low and the value leans on the margin recovering. SBC $30.4B (actual; was estimated at $24.5B). 2026 financing: $42.9B new stock, $19.1B mandatory convertible preferred, $85B new debt. Net cash = cash + marketable securities - long-term debt. 'extra' = $135.2B non-marketable securities at a 50% haircut. Interest is the Q3 run-rate."),
 "AMZN": dict(name="Amazon.com Inc.", price=243.79, shares=10.929, rev=797.455, fcf=-42.357, sbc=19.873,
              net_cash=-157.72, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.09,g10=.035,m=.05), base=dict(g1=.13,g10=.05,m=.085), bull=dict(g1=.16,g10=.06,m=.12)),
              notes="TTM to Sep-2026. FCF (Amazon's own definition: operating cash flow minus net capex) is -$42B on $211B net capex; margin recovers as the AI build-out matures. Q3 revenue +12%, Q4 guide +12-16%. SBC actual ($19.9B; was estimated at $22B). Net debt $158B incl. $99B long-term leases after ~$44B of new bonds in Q3. Interest is the Q3 run-rate; current debt portions estimated. Anthropic stake NOT valued (upside not counted)."),
 "NVDA": dict(name="NVIDIA Corp.", price=217.23, shares=24.147, rev=302.97, fcf=127.01, sbc=7.0,
              net_cash=23.61, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.08,g10=.03,m=.32), base=dict(g1=.22,g10=.04,m=.42), bull=dict(g1=.35,g10=.06,m=.50)),
              notes="TTM to Jul-2026 (FY27 Q2). SBC is an ESTIMATE (about 2.3% of revenue). Data-centre demand is highly cyclical and concentrated: lower confidence. Base case is deliberately below consensus growth. Base case is deliberately below consensus growth."),
 "AVGO": dict(name="Broadcom Inc.", price=344.33, shares=4.774, rev=89.10, fcf=39.40, sbc=8.9,
              net_cash=-35.44, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.12,g10=.03,m=.30), base=dict(g1=.25,g10=.05,m=.38), bull=dict(g1=.35,g10=.06,m=.43)),
              notes="TTM to Aug-2026 (FY26 Q3). SBC is an ESTIMATE (about 10% of revenue). Net debt from acquisitions. AI custom-chip demand drives growth."),
 "LLY": dict(name="Eli Lilly and Co.", price=1373.7, shares=0.8934, rev=86.462, fcf=19.661, sbc=0.698,
              net_cash=-44.544, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=.08,g10=.03,m=.26), base=dict(g1=.20,g10=.04,m=.32), bull=dict(g1=.28,g10=.05,m=.38)),
              notes="TTM to Sep-2026. Q3 revenue +39% on Mounjaro/Zepbound; FY26 revenue guide $85-87B (as of Q2). SBC from filings (~$0.7B; the earlier $2.2B was an estimate). FCF = operating cash flow minus $11.0B PP&E capex on new plants; margin rises as the build-out matures. FCF excludes ~$18B of 2026 cash spent on acquired IPR&D and acquisitions. Interest expense is an ESTIMATE. Growth rests on obesity drugs; pricing and patent risk."),
 "ADBE": dict(name="Adobe Inc.", price=251.67, shares=0.3892, rev=25.97, fcf=10.59, sbc=2.1,
              net_cash=-1.15, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=-.03,g10=.02,m=.26), base=dict(g1=.07,g10=.03,m=.32), bull=dict(g1=.11,g10=.045,m=.36)),
              notes="TTM to Aug-2026 (FY26 Q3). SBC is an ESTIMATE (about 8% of revenue). The bear case assumes generative-AI tools erode its creative-software moat (sales shrink first, then recover slowly); the market price looks close to that view."),
 "APP": dict(name="AppLovin Corp.", price=410.0, shares=0.3348, rev=7.609, fcf=4.878, sbc=0.334,
              net_cash=-0.342, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.15,g10=0.03,m=0.45), base=dict(g1=0.3,g10=0.05,m=0.55), bull=dict(g1=0.45,g10=0.06,m=0.62)),
              notes="TTM to Sep-2026. Revenue $7.61B TTM (FY25 $5.48B + 9M-26 $5.95B - 9M-25 $3.82B), all advertising since the Apps business was sold in mid-2025. Q3 revenue +55% to $2.18B, adjusted EBITDA margin 84%, net income +72%. Q4 guide: revenue $2.365-2.395B (+43-44%), adjusted EBITDA margin 84-85%. The Q4 run-rate alone is ~25% above TTM revenue, so base year-1 growth raised from 25% to 30% (bear 10% -> 15%, bull 40% -> 45%); margins kept. FCF = operating cash flow - capex - finance-lease principal (company definition) $4.88B TTM (sum of Q4'25-Q3'26 releases), 64% of revenue. Stock pay $0.33B TTM (actual, from the adjusted EBITDA reconciliations; replaces the earlier estimate). Net debt $0.34B = $3.17B cash - $3.52B notes. Diluted shares 334.8M (Q3 average), down ~2% a year from buybacks ($1.4B in Q3, authorisation raised to $3.6B). Very high margins, reliance on one ad engine (AXON), platform rules at Apple and Google, short-seller and regulatory scrutiny, and heavy reliance on terminal value: lower confidence. Higher required return (11%) and 35% safety margin."),
 "FICO": dict(name="Fair Isaac Corp.", price=723.98, shares=0.0216, rev=2.5349, fcf=1.0344, sbc=0.1855,
              net_cash=-5.0086, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.01,g10=.025,m=.30), base=dict(g1=.07,g10=.035,m=.38), bull=dict(g1=.11,g10=.045,m=.42)),
              notes="TTM to Sep-2026 (fiscal year FY26 = TTM). Revenue $2.53B, up 27% (scores $1.65B, up 41%, from a higher mortgage-originations score price despite high-single-digit lower mortgage volumes; software up, ARR +14% with platform ARR +72%, net retention 112%). Q4 revenue +27%. FCF = operating cash flow $1.07B minus capex $0.04B (incl. capitalised software) = $1.03B; actual stock pay $0.19B (was an 8%-of-revenue estimate), so FCF after stock pay is 33% of revenue, about 40% before interest. Net debt $5.0B = cash and marketable securities $0.27B less $5.26B of debt (term loan, revolver, senior notes; FY26 buybacks of $3.0B, ~10% of shares, were debt-funded) and $0.02B of leases; net interest $0.22B; tax rate 24% (less excess tax benefit from stock pay). Buybacks paused in Q4 to repay the term loan. NO FY27 GUIDANCE: management withdrew it while it moves to custom (bespoke) mortgage pricing; the FICO Preferred Program freezes the 2027 wholesale score price for enrolled lenders. Scenarios CUT after the Oct-2026 price-drop review (lasting cause) and kept: the FHFA lets all lenders deliver VantageScore to Fannie/Freddie (Sep 2026), FHA accepts it from Jan 2027, Rocket made VantageScore its preferred score and FICO froze its mortgage score price, ending the price rises behind its margin gains (mortgage ~60% of scores revenue). Management says no meaningful volume lost to competition yet, but the price effect shows only in calendar 2027. Base growth 7% (consensus was ~8% before the guidance was withdrawn) with the cash margin held at ~38% instead of expanding; bear: mortgage share loss and price cuts, ~1% growth and a 30% margin; bull 11% / 42%."),
 "APA": dict(name="APA Corporation", price=44.55, shares=0.338, rev=9.46, fcf=2.105, sbc=0.15,
              net_cash=-3.246, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-.08,g10=.00,m=.10), base=dict(g1=-.04,g10=.02,m=.15), bull=dict(g1=.02,g10=.025,m=.20)),
              notes="TTM to Sep-2026. Revenue $9.46B (statement total revenues: 9M26 $7,469M + FY25 $8,920M - 9M25 $6,929M), earned at an average realised oil price of about $82.5/bbl over the four quarters ($61 / $79 / $98 / $92); the September quarter was up 31% on a year earlier purely on price (oil $92.02 vs $67.43) while production fell 3% (450k BOE/d). Brent is still ~$93 on Middle East / Strait of Hormuz risk and fell ~5% on 9 Nov on hopes of an Iran deal, so prices remain near a cycle high: every case still assumes revenue falls and the cash margin shrinks from today's ~21% (after SBC) toward 10-20%. FCF $2.1B = operating cash flow $4.44B - additions to oil and gas property $2.34B (TTM); company raised its own 2026 FCF outlook to ~$2.9B and set a preliminary 2027 capital budget of $2.5B (2026 ~$2.1B). SBC kept at ~$0.15B/yr: expensed stock- and cash-settled pay was $0.19B TTM, but the jump is cash-settled awards marked up with the share price, which are already in operating cash flow. Net debt $3.2B (debt $3.30B + finance leases $0.03B - cash $0.08B), after $450M of buybacks in the quarter (shares 336M at 31 Oct). Egypt oil output keeps slipping (116k b/d gross). Oil-price dependent: lower confidence, 10% required return and 35% safety margin."),
 "DECK": dict(name="Deckers Outdoor Corp.", price=82.76, shares=0.1353, rev=5.577, fcf=1.053, sbc=0.046,
              net_cash=0.67, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.00,g10=.02,m=.15), base=dict(g1=0.05,g10=.03,m=.18), bull=dict(g1=0.08,g10=.04,m=.20)),
              notes="TTM to Sep-2026 (FY27 Q2). Growth slowing: Q2 sales +3.5% (HOKA +6.8%, UGG +3.5%). FY27 guidance CUT to revenue $5.700-5.725B (+4-5%; was $5.86-5.91B), HOKA high-single-digit, UGG low-single-digit, operating margin ~23% incl. ~150bp IEEPA tariff refunds, EPS $7.80-7.95. Base growth cut to 5% and bull to 8% (from 6% / 10%) after the guidance cut. SBC now from filings (~$46M). TTM FCF $1.05B includes ~$46M one-off tariff refunds (~$1.02B without). Net cash $0.67B (cash $1.21B less $0.54B leases) at the seasonal low after $638M of buybacks in H1. Fashion/brand risk: the bear case assumes HOKA growth stalls."),
 "INCY": dict(name="Incyte Corp.", price=116.8, shares=0.206, rev=5.765, fcf=1.952, sbc=0.263,
              net_cash=3.823, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-.02,g10=.02,m=.18), base=dict(g1=.03,g10=.03,m=.24), bull=dict(g1=.08,g10=.04,m=.30)),
              notes="TTM to Sep-2026, revenue cut by the one-off $246M Opzelura settlement benefit (Q2-26). FCF NORMALISED to $1.95B: the one-off $1.27B Vega (latarcibart) upfront, paid in Q3-2026 through operating cash flow and expensed as IPR&D, is excluded (reported TTM FCF $0.69B). Net cash $3.85B cash and securities less finance leases; Vega already paid. 2026 net sales guidance raised to $5.21-5.30B (Opzelura +36%, other Heme/Onc +42% in Q3, Jakafi +4%). SBC ~$0.26B/yr. Diluted shares estimated (~206M). Jakafi is ~60% of sales and faces loss of exclusivity later this decade, so the bear case has shrinking sales and lower margins; 35% safety margin."),
 "MKC": dict(name="McCormick & Co.", price=46.35, shares=0.26906, rev=7.69, fcf=0.926, sbc=0.05,
              net_cash=-4.69, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.01,g10=.02,m=.10), base=dict(g1=.04,g10=.03,m=.125), bull=dict(g1=.06,g10=.035,m=.14)),
              notes="TTM to Aug-2026. Trailing P/E is distorted by a one-off $867M gain on taking control of McCormick de Mexico (Jan-2026), so this model uses free cash flow. Organic growth ~3-6%. STANDALONE value only: the pending Unilever Foods combination (McCormick holders to own 35%, $15.7B cash to Unilever, close expected mid-2027) would change the per-share value substantially. Lower confidence."),
 "EXPE": dict(name="Expedia Group Inc.", price=259.16, shares=0.121, rev=16.226, fcf=3.72, sbc=0.442,
              net_cash=-0.119, extra=0.119, mos=0.35,
              scen=dict(bear=dict(g1=0,g10=0.01,m=0.12), base=dict(g1=0.06,g10=0.03,m=0.17), bull=dict(g1=0.09,g10=0.04,m=0.2)),
              notes="TTM to Sep-2026. Revenue $16.2B (+12% in the September quarter to $4.94B); gross bookings +11% to $34.0B, room nights +7%, B2B bookings +19% vs B2C +7%. Full-year 2026 guidance raised to revenue $16.37-16.43B (+11-12%) and bookings +10%, but the December quarter is guided to only +4-6% revenue and +3-5% bookings. FCF NORMALISED at $3.72B (the same ~23% margin as before): reported TTM FCF is $3.75B (9M26 $3,627M + FY25 $3,110M - 9M25 $2,991M), so at September, after the seasonal outflow of customer prepayments, the normalised and reported figures agree; at mid-year the TTM figure is swollen by merchant bookings. Cash ($5.0B + $0.5B short-term investments) is mostly customers' money (deferred merchant bookings $12.6B), so net cash is set to zero (net debt $0.1B incl. $0.2B leases offset). Shares 121M (118.6M class A + B outstanding plus ~2.4M dilution); buybacks $1.7B in 9M26. SBC $0.44B TTM. Main risk: AI agents (e.g. Meta's Muse) booking directly with hotels and airlines and bypassing aggregators; the bear case has flat sales and margins squeezed to 12%. 35% safety margin."),
 "BKNG": dict(name="Booking Holdings Inc.", price=163.49, shares=0.753, rev=29.026, fcf=9.237, sbc=0.594,
              net_cash=-4.99, extra=-1.0, mos=0.3,
              scen=dict(bear=dict(g1=0.03,g10=0.02,m=0.26), base=dict(g1=0.07,g10=0.04,m=0.3), bull=dict(g1=0.11,g10=0.05,m=0.32)),
              notes="TTM to Sep-2026 (prices and shares after the April 2026 25-for-1 split). Reported Q3 revenue fell 1% only because of a one-off FTC charge (Priceline / Guest Reservations case): a $900M revenue reduction plus a $100M accrued loss, not yet settled. Revenue here is adjusted ($29.0B TTM, Q3 adjusted +8.7%); the expected ~$1.0B payment is taken off the value via 'extra' (-$1.0B; the FTC may seek more). Q3: room nights +6.7%, gross bookings +9.6% (+11% cc). Guidance: Q4 slows sharply (room nights +1-3%, adjusted revenue +0-2%, +2-4% cc, EBITDA about flat) on softer international travel and the Middle East; FY26 high single digits; margin-expansion goal dropped. Base year-1 growth cut from 8% to 7% for the Q4 slowdown. FCF = OCF $9.56B - capex $0.32B = $9.24B, SBC $0.59B; SBC-adjusted cash margin ~30% of adjusted revenue. Net debt $5.0B = cash $15.8B - debt $20.1B - leases ~$0.7B. Shares = Q3 diluted 753M ($9.9B bought back in 9M). Main risk: AI agents bypassing online travel agencies; Booking's direct traffic and hotel supply make it less exposed than Expedia, so the bear case still grows slowly with margins down to 26%. Also regulators (FTC, EU DMA)."),
 "INTU": dict(name="Intuit Inc.", price=343.39, shares=0.26724, rev=21.448, fcf=7.3, sbc=2.056,
              net_cash=-1.221, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.05,g10=0.03,m=0.21), base=dict(g1=0.095,g10=0.045,m=0.26), bull=dict(g1=0.12,g10=0.055,m=0.3)),
              notes="FY to Jul-2026. FCF NORMALISED to $7.3B: FY26 reported $8.6B vs $6.1B in FY25 (timing). Stock pay is large (~10% of revenue), so the SBC-adjusted margin is ~24%. FY27 guidance: revenue +9-10% ($23.3-23.5B), GAAP EPS $20.12-20.36. Shares are down sharply in 2026 on fears that AI tax and bookkeeping agents erode TurboTax and QuickBooks; the bear case halves growth and trims margins."),
 "ADSK": dict(name="Autodesk Inc.", price=252.2, shares=0.209, rev=7.79, fcf=2.804, sbc=0.706,
              net_cash=0.45, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.06,g10=0.03,m=0.22), base=dict(g1=0.11,g10=0.05,m=0.27), bull=dict(g1=0.14,g10=0.06,m=0.31)),
              notes="TTM to Jul-2026. Revenue growing ~15% (helped by the shift to annual billing and the new transaction model); analysts expect ~11% next year. SBC is heavy (~9% of revenue). FY26 SBC-adjusted margin was 22%, TTM 27%; base target 27%. Small net cash. Risk: AI-native design tools and a construction slowdown."),
 "TPR": dict(name="Tapestry Inc.", price=136.11, shares=0.2045, rev=8.193, fcf=1.881, sbc=0.114,
              net_cash=-3.447, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.02,g10=0.01,m=0.13), base=dict(g1=0.05,g10=0.03,m=0.17), bull=dict(g1=0.08,g10=0.035,m=0.2)),
              notes="TTM to Sep-2026 (fiscal Q1 FY27, quarter to 26 Sep 2026). Coach brand still strong: Q1 Coach sales +16% (constant currency), Kate Spade -10%, total sales +11% to $1.89B; GAAP gross margin 78.6% (+230 bp), operating margin 22.4%. FY27 outlook raised: sales $8.5-8.6B (+6-7% constant currency), EPS $8.25-8.35, adjusted FCF approaching $1.7B, $1.7B of buybacks; Q2 guided +5-6%, so the base case's 5% growth stands. FCF = operating cash flow - capex (statement) $1.88B TTM, stock pay $0.11B; SBC-adjusted cash margin ~21.6% (history ~15%), so the base target is 17%, not today's peak. Inventory +4% vs sales +11%. Net debt $3.4B = $0.78B cash and short-term investments - $2.56B borrowings - $1.67B store lease liabilities. Diluted shares 204.5M (Q1 average; ~200M guided for FY27 after buybacks). Fashion and tariff risk, Kate Spade still shrinking, one-brand reliance: the bear case has sales falling and margins back to 13%. 35% safety margin."),
 "VEEV": dict(name="Veeva Systems Inc.", price=323.04, shares=0.16191, rev=3.458, fcf=1.665, sbc=0.495,
              net_cash=7.091, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.07,g10=0.04,m=0.28), base=dict(g1=0.12,g10=0.055,m=0.33), bull=dict(g1=0.15,g10=0.065,m=0.36)),
              notes="TTM to Jul-2026. Life-sciences cloud software; $7.1B net cash (~14% of market value). Stock pay ~14% of revenue, so the SBC-adjusted margin is ~34%. Analysts expect ~12% growth. Risks: customers moving CRM back to Salesforce and pharma budget cuts; bear case 7% growth."),
 "MNST": dict(name="Monster Beverage Corp.", price=45.64, shares=1.98011, rev=9.585, fcf=1.921, sbc=0.133,
              net_cash=3.611, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.18), base=dict(g1=0.09,g10=0.045,m=0.21), bull=dict(g1=0.12,g10=0.055,m=0.23)),
              notes="TTM to Sep-2026 (prices after the 2-for-1 stock split). Energy drinks; Q3 net sales +16.7% to a record $2.56B (+16.3% currency-adjusted), 9M +20.9%; international now ~47% of sales (+28.1%, LATAM +48.8%). Gross margin slipped to 54.7% (55.7%) on higher aluminium can costs, mix and freight, partly offset by price increases. No formal guidance; analysts expect ~10% next year. FCF = operating cash flow minus capex ($1.92B TTM, down from $2.08B because receivables rose $362M and inventories $127M with the fast growth). SBC-adjusted cash margin ~19% (base target 21% as working capital normalises). No debt; net cash $3.6B = cash $2.15B + short-term investments $1.56B less ~$0.09B leases ($0.93B long-term investments not counted). Risk: competition (Celsius, Red Bull), aluminium/tariff costs; bear case 4% growth."),
 "ALLE": dict(name="Allegion plc", price=187.06, shares=0.0852, rev=4.391, fcf=0.74, sbc=0.03,
              net_cash=-1.836, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.01,g10=0.02,m=0.13), base=dict(g1=0.06,g10=0.035,m=0.155), bull=dict(g1=0.08,g10=0.045,m=0.17)),
              notes="TTM to Sep-2026. Locks and access control; Q3 revenue +9.6% (organic +7.2%). FY26 guidance raised: revenue +9.5-10.5% reported / +5-6% organic, adjusted EPS $9.05-9.10. TTM FCF $0.74B incl. ~$20M one-off IEEPA tariff refunds. SBC is an ESTIMATE (~$30M; FY25 $29.8M). Net debt $1.84B now includes $0.19B operating leases (was $1.71B excl. leases). Buybacks $280M YTD. Risk: non-residential construction cycle."),
 "FTNT": dict(name="Fortinet Inc.", price=139.1, shares=0.7426, rev=7.881, fcf=2.85, sbc=0.304,
              net_cash=4.302, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.06,g10=0.03,m=0.26), base=dict(g1=0.11,g10=0.05,m=0.3), bull=dict(g1=0.15,g10=0.06,m=0.33)),
              notes="TTM to Sep-2026. FCF NORMALISED to $2.85B (~36% of revenue, same margin as before): reported TTM $3.43B is inflated by prepaid service contracts (billings +29% vs revenue +20% in Q3; deferred revenue $7.9B); FY25 was $2.2B. Firewall refresh lifted FY26 revenue growth to ~20% (guide $8.13-8.22B); analysts expect ~11% next year as it fades. $4.3B net cash (cash + ST investments - $0.5B notes). Risk: hardware cycle and competition (Palo Alto, cloud security)."),
 "RMD": dict(name="ResMed Inc.", price=252.83, shares=0.14341, rev=5.53, fcf=1.55, sbc=0.112,
              net_cash=0.4, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.02,m=0.22), base=dict(g1=0.06,g10=0.035,m=0.26), bull=dict(g1=0.09,g10=0.045,m=0.28)),
              notes="TTM to Sep-2026 (FY27 Q1), PRO FORMA excluding MatrixCare (sold for $490M, closed in the quarter; ~$220M/yr revenue): revenue ~$5.53B, FCF ~$1.55B (reported TTM $5.73B / $1.59B; the split is estimated). Sleep-apnoea devices and masks; SBC-adjusted cash margin ~26%, small net cash after a $0.94B buyback in the quarter. FY27 guidance 5-7% core constant-currency growth ($5.75-5.85B reported). Interest is an estimate. Risk: GLP-1 weight-loss drugs shrinking the apnoea patient pool (so far demand has held up); bear case 2% growth."),
 "V": dict(name="Visa Inc.", price=410.54, shares=1.882, rev=45.903, fcf=22.057, sbc=0.928,
              net_cash=-7.988, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.07,g10=0.04,m=0.41), base=dict(g1=0.105,g10=0.05,m=0.45), bull=dict(g1=0.13,g10=0.06,m=0.47)),
              notes="FY to Sep-2026 (fiscal Q4 reported 27 Oct 2026). Network with ~46% SBC-adjusted cash margin; FY26 net revenue +15% (Q4 +13%), FCF $22.1B. FY27 guidance: adjusted net revenue growth low double digits, adjusted EPS growth low double digits to low teens. Net debt $8.0B (excl. $0.6B litigation escrow). Shares now = diluted class-A as-converted (1.882B, includes class B/C); the previous 1.704B was class A only, which overstated value per share by ~10%. Risks: US interchange regulation (Credit Card Competition Act), real-time payments and stablecoins; bear case 7% growth and margin 41%."),
 "FIX": dict(name="Comfort Systems USA Inc.", price=1326.23, shares=0.03515, rev=12.543, fcf=1.5, sbc=0.037,
              net_cash=1.784, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0,g10=0.02,m=0.07), base=dict(g1=0.18,g10=0.04,m=0.1), bull=dict(g1=0.25,g10=0.05,m=0.12)),
              notes="TTM to Sep-2026. Mechanical and electrical contractor riding the AI data-centre build-out: Q3 revenue +54%, backlog $17.8B (+90% YoY; $14.1B in June). FCF NORMALISED to $1.50B (~12% of sales, same approach as before): TTM $2.44B is inflated by customer advance payments (billings in excess of costs +$1.69B in 9M26); FY25 was $1.0B (11%). Analysts expect ~24% growth in 2027. Highly cyclical, at a cyclical peak: the bear case has data-centre spending stalling (flat sales, 7% margin). 11% required return and 35% safety margin."),
 "MA": dict(name="Mastercard Inc.", price=635.7, shares=0.876, rev=36.288, fcf=15.43, sbc=0.637,
              net_cash=-13.474, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.08,g10=0.04,m=0.4), base=dict(g1=0.12,g10=0.055,m=0.44), bull=dict(g1=0.14,g10=0.065,m=0.46)),
              notes="TTM to Sep-2026. Network with a ~41-42% SBC-adjusted cash margin (TTM FCF $15.4B dipped on higher capex and ~$0.5B of merchant-litigation payments; base target 44% kept). Q3 revenue +14%; 2026 net revenue growth guided to low teens. Net debt $13.5B (debt up this year to fund buybacks: $11.9B in 9M). Slightly faster growth than Visa (more cross-border and value-added services). Same regulatory and new-payment-rail risks as Visa."),
 "CTAS": dict(name="Cintas Corp.", price=224.1, shares=0.39708, rev=11.561, fcf=1.881, sbc=0.128,
              net_cash=-2.417, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.14), base=dict(g1=0.075,g10=0.045,m=0.16), bull=dict(g1=0.09,g10=0.055,m=0.17)),
              notes="Revenue TTM to Aug-2026; cash flow FY to May-2026. Uniform rental and facility services: very steady (FCF up every year). Analysts expect ~7.5% growth. Net debt $2.4B. Expensive on earnings (P/E ~44); the risk is valuation and a jobs slowdown, not the business."),
 "DXCM": dict(name="DexCom Inc.", price=79.93, shares=0.37295, rev=5.104, fcf=1.2, sbc=0.154,
              net_cash=0.425, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.16), base=dict(g1=0.11,g10=0.05,m=0.21), bull=dict(g1=0.14,g10=0.06,m=0.25)),
              notes="TTM to Sep-2026. Continuous glucose monitors. Revenue +11% in Q3 (US +14%, international +5%); 2026 guidance $5.20-5.25B (+12-13%), non-GAAP operating margin ~24%. FCF NORMALISED to $1.2B: reported TTM $1.1B (FY25 also ~$1.1B) is held back by working capital and the G6 wind-down, while earnings-based cash flow excluding the G6 inventory charges is ~$1.2B. Big buybacks ($1.0B in 9M) cut shares to 373M; net cash $0.4B after $1.24B convertibles and leases. Risks: Abbott competition, pricing in type-2 / over-the-counter CGM, and the 2025 product-quality issues. 35% safety margin."),
 "IDXX": dict(name="IDEXX Laboratories Inc.", price=706.65, shares=0.07905, rev=4.662, fcf=1.304, sbc=0.065,
              net_cash=-0.775, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.22), base=dict(g1=0.085,g10=0.045,m=0.25), bull=dict(g1=0.11,g10=0.055,m=0.27)),
              notes="TTM to Sep-2026. Revenue $4.66B; Q3 revenue +10% reported and organic, CAG Diagnostics recurring revenue +11% organic (US +9.6%, international +14%) even though US same-store vet visits fell ~1.8%; 5,780 premium instrument placements, over 1,900 inVue Dx analysers placed (installed base ~11,000). Q3 operating margin 33.1%. 2026 guidance raised: revenue $4.741-4.767B (+9.3-10.0% organic), EPS $14.96-15.16, operating margin 32.1-32.3%, FCF 95-100% of net income. FCF = OCF $1.42B - capex $0.12B = $1.30B; SBC $0.065B; SBC-adjusted cash margin ~26.6% (base 25%). Net debt $0.78B = cash $0.20B - credit facility $0.47B - notes $0.37B - leases ~$0.12B. Shares = Q3 diluted 79.0M (buybacks $0.81B in 9M). Risk: fewer US vet visits; Zoetis and Antech in diagnostics; bear case 4% growth."),
 "VRSN": dict(name="VeriSign Inc.", price=300.32, shares=0.0897, rev=1.732, fcf=1.024, sbc=0.077,
              net_cash=-1.316, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.01,m=0.5), base=dict(g1=0.06,g10=0.03,m=0.55), bull=dict(g1=0.09,g10=0.04,m=0.58)),
              notes="TTM to Sep-2026. Sole registry for .com and .net: a regulated near-monopoly with a ~55% SBC-adjusted cash margin; growth comes from contractual price increases and domain volumes. Negative equity from buybacks; net debt $1.3B. Risk: falling domain registrations and price-cap changes at contract renewal (bear case 2% growth)."),
 "NDAQ": dict(name="Nasdaq Inc.", price=102.56, shares=0.559, rev=5.78, fcf=2.258, sbc=0.177,
              net_cash=-8.381, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.03,g10=0.03,m=0.32), base=dict(g1=0.08,g10=0.045,m=0.36), bull=dict(g1=0.11,g10=0.055,m=0.39)),
              notes="TTM to Sep-2026. Revenue = NET revenue (after transaction rebates and brokerage fees, $5.78B), the basis margins are measured on; gross revenue $9.2B. Exchanges plus financial technology (Adenza, Verafin) and index licensing. Net debt $8.4B (Adenza deal) is the main risk; the Growth Screen flags it High risk on debt."),
 "MCO": dict(name="Moody's Corp.", price=483.45, shares=0.17242, rev=8.176, fcf=2.977, sbc=0.233,
              net_cash=-5.871, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.03,m=0.29), base=dict(g1=0.07,g10=0.045,m=0.33), bull=dict(g1=0.1,g10=0.055,m=0.36)),
              notes="TTM to Sep-2026. Credit ratings (a duopoly with S&P) plus Moody's Analytics data and software. SBC-adjusted cash margin ~34%. Analysts expect ~7% growth. Risk: bond-issuance downturns hit ratings revenue (bear case 2%), and AI pressure on analytics."),
 "SPGI": dict(name="S&P Global Inc.", price=460.66, shares=0.2916, rev=14.546, fcf=5.035, sbc=0.192,
              net_cash=-11.024, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.03,g10=0.03,m=0.3), base=dict(g1=0.07,g10=0.045,m=0.34), bull=dict(g1=0.09,g10=0.055,m=0.37)),
              notes="TTM to Sep-2026, continuing operations only (Mobility spun off 1 Jul 2026; 2025 figures recast by the company, so valued WITHOUT Mobility). Q3 revenue +7%, nine months +9%; 2026 guidance raised to revenue +7.4-8.4% and adjusted EPS $17.70-17.95. FCF = company adjusted free cash flow (after minority distributions, excluding one-offs); the Q4-25 Mobility share of cash flow and SBC is estimated (~$0.19B). Net debt $11.0B. Ratings, indices, market data; strategic review of a possible Capital IQ separation."),
 "NFLX": dict(name="Netflix Inc.", price=65.85, shares=4.164, rev=49.735, fcf=11.375, sbc=0.54,
              net_cash=-6.909, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.06,g10=0.03,m=0.2), base=dict(g1=0.11,g10=0.05,m=0.26), bull=dict(g1=0.14,g10=0.06,m=0.3)),
              notes="TTM to Sep-2026 (prices after the 10-for-1 split). 2026 guidance: revenue ~$51.1B (+13%), operating margin 31.5%, free cash flow ~$12B (cut from $12.5B). Net income is boosted by a one-off break-up fee, so the model uses free cash flow. Base case lifts the SBC-adjusted cash margin from ~22% to 26% as content spend grows slower than revenue. Risks: ad growth (forecast cut), competition for viewing time."),
 "CBOE": dict(name="Cboe Global Markets Inc.", price=344.28, shares=0.1047, rev=5.278, fcf=1.50, sbc=0.055,
              net_cash=1.152, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.04,g10=0.025,m=0.26), base=dict(g1=0.04,g10=0.04,m=0.30), bull=dict(g1=0.08,g10=0.05,m=0.34)),
              notes="TTM to Sep-2026 (gross revenue $5.28B, net revenue $2.84B; margins on the gross basis). Options exchanges (SPX, VIX, licence with S&P extended to 2051). Q3 total revenue +19% on record index-option volumes (index ADV +24%); 2026 organic net revenue guidance raised to high teens, adjusted opex cut to $830-845M. Reported operating cash flow ($2.63B TTM) is swollen by ~$1.4B of clearing margin-deposit inflows, so FCF is NORMALISED to $1.50B (net income + D&A + SBC - capex, excluding the $72M Cboe Australia gain). That is ~27% of gross revenue after SBC in a record year, so scenario margins were cut 4 points (base 30%, was 34%, which had leaned on the inflated cash flow); growth kept (volumes expected to fade from the peak; the 2027 S&P royalty step-up raises cost of revenue). Net cash $1.15B (cash $2.70B less $1.44B notes and $0.11B leases)."),
 "GRMN": dict(name="Garmin Ltd.", price=279.94, shares=0.1936, rev=7.887, fcf=1.468, sbc=0.1745,
              net_cash=2.166, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.03,g10=0.03,m=0.15), base=dict(g1=0.1,g10=0.045,m=0.19), bull=dict(g1=0.13,g10=0.055,m=0.21)),
              notes="TTM to Sep-2026. Fitness, outdoor, marine, aviation and auto devices; no debt (only $0.17B leases) and $2.2B net cash (cash + current securities; $1.7B long-term securities not counted). Revenue +12% in Q3 (outdoor +20%, fitness +16%, auto OEM -20%); FY26 outlook raised to ~$8.15B (+12.5%), 29% operating margin. SBC-adjusted cash margin ~16% TTM (higher capex and working capital in Q3; ~19% before), base target kept at 19%. Risk: consumer-spending slowdown and tariffs (bear case 3% growth)."),
 "FDS": dict(name="FactSet Research Systems Inc.", price=331.32, shares=0.03557, rev=2.476, fcf=0.707, sbc=0.084,
              net_cash=-1.277, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.02,m=0.21), base=dict(g1=0.06,g10=0.035,m=0.25), bull=dict(g1=0.08,g10=0.045,m=0.28)),
              notes="FY to Aug-2026. Financial data and analytics subscriptions; very steady (FCF rose every year). Analysts expect ~6% growth. Shares have de-rated on fears that AI tools commoditise financial data and research workflows; the bear case has 2% growth and lower margins. Net debt $1.3B."),
 "CRM": dict(name="Salesforce Inc.", price=248.57, shares=0.823, rev=43.938, fcf=14.4, sbc=3.665,
              net_cash=-30.34, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.2), base=dict(g1=0.095,g10=0.045,m=0.25), bull=dict(g1=0.12,g10=0.055,m=0.28)),
              notes="TTM to Jul-2026. In May-2026 Salesforce borrowed ~$25B for a $25B accelerated buyback, so net debt is $30B; FCF is set to $14.4B (reported $15.2B less the extra after-tax interest at the new run-rate) and interest to ~$1.5B a year. FY27 revenue guidance $45.9-46.2B (~+10%). Stock pay is large (~8% of revenue). Risk: AI agents changing seat-based CRM pricing (bear case 4% growth)."),
 "HWM": dict(name="Howmet Aerospace Inc.", price=205.94, shares=0.4, rev=9.731, fcf=1.93, sbc=0.094,
              net_cash=-4.099, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.03,g10=0.025,m=0.14), base=dict(g1=0.14,g10=0.045,m=0.19), bull=dict(g1=0.18,g10=0.055,m=0.22)),
              notes="TTM to Sep-2026. Jet-engine and airframe components; Q3 revenue +29% (+25% organic) on the aircraft build-up, spares and gas turbines; CAM and Brunner acquired in 2026. 2026 guidance raised to $10.3B revenue and $2.0B FCF; management sees ~$11.5B (+12%) in 2027 and higher capex beyond 2027. Analysts expect ~14% next year. Aerospace is cyclical: the bear case has deliveries stalling (3% growth, margin 14%). Net debt $4.1B (lease figure estimated)."),
 "ADP": dict(name="Automatic Data Processing Inc.", price=286.08, shares=0.3976, rev=22.263, fcf=4.756, sbc=0.251,
              net_cash=-2.195, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.18), base=dict(g1=0.06,g10=0.04,m=0.21), bull=dict(g1=0.08,g10=0.05,m=0.23)),
              notes="TTM to Sep-2026 (FY27 Q1). Payroll and HR outsourcing; ~$1.6B of revenue is interest earned on client funds (FY27 guide $1.59-1.61B), which falls if rates drop. Q1 revenue +6%, adj EPS +13%; FY27 guidance raised to ~6% revenue growth and 10-12% adj EPS growth, margin +70-90bp. Very steady: 50+ years of dividend increases. FCF = operating cash flow minus capex and capitalised software. Corporate net debt $2.2B at Sep (seasonally high; client funds excluded; includes $0.2B quarter-end repo and ~$0.3B leases, lease figure estimated). Risk: weaker hiring and lower interest rates (bear case 2%)."),
 "AME": dict(name="AMETEK Inc.", price=238.29, shares=0.23004, rev=8.192, fcf=1.932, sbc=0.05,
              net_cash=-6.3, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.03,m=0.19), base=dict(g1=0.1,g10=0.045,m=0.22), bull=dict(g1=0.14,g10=0.055,m=0.24)),
              notes="TTM to Sep-2026. Electronic instruments and electromechanical devices; grows by steady bolt-on acquisitions. Q3 sales +17% to a record $2.22B (organic +10%, acquisitions +7 pts); orders +35% to $2.65B (organic +17%), record backlog $4.54B; adjusted operating margin 26.8%. 2026 guidance raised: sales up mid-teens, organic high single digits, adjusted EPS $8.53-8.57 (+15%). In Aug-2026 it bought Indicor Instrumentation ($5.15B; ~$1.1B sales, ~30% EBITDA margin), funded with $4.0B of term loans plus revolver and commercial paper; only ~2 months of Indicor are in TTM revenue, which supports the 10% first-year base growth. FCF = operating cash flow minus capex ($2.08B - $0.15B); SBC-adjusted cash margin ~23%. Net debt $6.3B (debt $6.67B + $0.30B operating leases - $0.67B cash), up from $1.5B; net debt/EBITDA 2.1x. Interest set at a ~$0.275B run-rate (~4.1% on $6.7B, mostly floating-rate) instead of the TTM $0.11B, which barely includes the new debt. Risk: industrial slowdown (bear case 2% growth), integrating a large deal, higher floating rates."),
 "AXP": dict(name="American Express Co.", price=319.63, shares=0.671, rev=72.85, fcf=11.445, sbc=0.0,
              net_cash=0.0, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.13), base=dict(g1=0.09,g10=0.045,m=0.155), bull=dict(g1=0.11,g10=0.05,m=0.17)),
              notes="TTM to Sep-2026. Card issuer AND network that lends to card members, so it is valued like a lender: cash flow = NET INCOME ($11.4B, stock pay already deducted), revenue = total revenues net of interest expense ($72.9B), and debt/interest are treated as part of the business (net cash set to zero, no interest add-back). Analysts expect ~9% revenue growth. Risks: consumer credit losses in a downturn and competition for premium cardholders."),
 "SHOP": dict(name="Shopify Inc.", price=153.03, shares=1.2907, rev=14.167, fcf=2.661, sbc=0.515,
              net_cash=5.063, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.15,g10=0.04,m=0.14), base=dict(g1=0.24,g10=0.06,m=0.19), bull=dict(g1=0.3,g10=0.07,m=0.22)),
              notes="TTM to Sep-2026. E-commerce platform with integrated payments (Shopify Payments, 68% of GMV). Q3 revenue +32%, GMV +29% to $119B, FCF margin 22%; Q4 guide: revenue growth low-thirties %, FCF margin about Q4-25's 19%. FCF $2.66B (sum of the four quarterly releases; Yahoo had $2.56B), SBC-adjusted margin ~15% today; the base case assumes 19% with scale. Shares CORRECTED to 1.291B diluted (Class A + B; the model had Class A only, which overstated value per share ~7%). Net cash $5.06B = cash and current + non-current debt securities less $0.19B leases, no borrowings; the ~$4.9B of equity stakes (Affirm, Global-E, Klaviyo) is not counted. Very high expectations in the price: 11% required return and 35% safety margin."),
 "PYPL": dict(name="PayPal Holdings Inc.", price=57.36, shares=0.831, rev=34.295, fcf=6.299, sbc=0.977,
              net_cash=-3.192, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.04,g10=0.01,m=0.11), base=dict(g1=0.04,g10=0.03,m=0.155), bull=dict(g1=0.07,g10=0.04,m=0.18)),
              notes="TTM to Sep-2026. Digital wallet and online checkout (PayPal, Venmo, Braintree). Slow growth (~4% expected) but cheap (forward P/E ~10) with heavy buybacks. SBC-adjusted cash margin ~16%. Net debt $3.2B (customer balances excluded). Risks: losing branded-checkout share to Apple Pay and others; the bear case has sales shrinking 4% and margins down to 11% (the price implies roughly that)."),
 "XYZ": dict(name="Block Inc.", price=88.56, shares=0.6148, rev=12.182, fcf=3.454, sbc=1.165,
              net_cash=0.908, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.06,g10=0.03,m=0.18), base=dict(g1=0.15,g10=0.05,m=0.24), bull=dict(g1=0.2,g10=0.06,m=0.28)),
              notes="TTM to Sep-2026. Valued on GROSS PROFIT, not revenue: TTM gross profit $12.18B (Q4'25-Q3'26 from the shareholder letters: 2,872 + 2,909 + 3,166 + 3,235 $M); ~$7B of reported revenue is low-margin bitcoin sales passed through Cash App. Q3 gross profit +22% (Cash App +27%, Square +14%), Square payment volume +14%, Cash App 60M monthly transacting actives (+4%); adjusted operating income $923M (+92%). 2026 guidance raised again: gross profit $12.626B (+22%), adjusted operating income $3.519B (28% margin); Q4 guided to gross profit $3.315B (+15%), a slowdown, so the base case's 15% year-1 growth stands. FCF = operating cash flow - capex (statement, not adjusted for loan flows) $3.45B TTM; Q3 FCF fell to $0.97B from $1.40B. Stock pay is heavy: $1.16B TTM incl. $0.13B restructuring awards (~9.6% of gross profit). Net cash $0.9B = $7.86B cash + $0.58B marketable debt securities - $7.54B debt ($5.72B notes, $1.54B warehouse facilities funding consumer loans, ~$0.27B leases); customer funds ($5.36B, owed to customers) and the $0.77B bitcoin holding are not counted (the earlier $5-6B figure wrongly included customer funds). Diluted shares 614.8M (Class A + B; the earlier 541M counted only Class A). Risks: consumer credit (Borrow, Afterpay), bitcoin swings, fierce point-of-sale and fintech competition. High beta (~2.5): 11% required return, 35% safety margin."),
 "ADYEY": dict(name="Adyen N.V. (ADR)", price=9.14, shares=3.157, rev=3.19, fcf=1.15, sbc=0.046,
              net_cash=0.0, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.1,g10=0.04,m=0.3), base=dict(g1=0.2,g10=0.06,m=0.36), bull=dict(g1=0.25,g10=0.07,m=0.4)),
              notes="Per US ADR (ADYEY; 100 ADRs = 1 Amsterdam share; shares = ADR equivalents). Reports in EUR, converted at 1.117 USD/EUR (27 Oct 2026). TTM to Jun-2026 net revenue ~EUR 2.86B (2025 EUR 2.65B + H1-26 EUR 1.30B, +19%); EBITDA margin 49%; capex ~7% of revenue in 2026. FCF is an ESTIMATE (~36% of net revenue: net income + depreciation - capex), because reported cash flow swings with merchant settlement funds. Its large cash balance is mostly merchants' money, so net cash is set to zero (conservative). 2026 guidance (Q3 update, Oct 2026): net revenue +21-23% (constant currency) but EBITDA margin cut to ~50% (2025: 53%) and the >55% medium-term margin target withdrawn to invest faster; new 2027 targets in Feb 2027. The base FCF margin (36%) already equals today's, so no expansion is assumed. FX moves the USD value."),
 "FISV": dict(name="Fiserv Inc.", price=63.52, shares=0.532, rev=20.799, fcf=3.158, sbc=0.4,
              net_cash=-27.63, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.02,g10=0.015,m=0.13), base=dict(g1=0.02,g10=0.025,m=0.16), bull=dict(g1=0.04,g10=0.035,m=0.18)),
              notes="TTM to Sep-2026 (ticker FISV since the Nasdaq move). Banking technology and merchant acquiring (Clover). Q3 revenue -1% to $5.2B, organic flat (Merchant -2%, Financial +2%; 9M organic -3%); Clover revenue +1%; adjusted operating margin 31.2% (37.0% a year ago); adjusted EPS $1.75 vs $2.04. A $6.45B non-cash goodwill impairment (triggered by the share-price fall) made the quarter a GAAP loss. Guidance, already cut twice since the 2025 reset, was held: 2026 organic revenue -1% to 0%, adjusted EPS $7.20-7.40, adjusted margin 31-31.5%; Project Elevate savings target doubled to $1B; $500M buyback in Q4; 2027 guidance comes in February. FCF = operating cash flow minus capex incl. capitalised software ($5.04B - $1.88B = $3.16B, down from $3.93B on lower profits and working capital). SBC-adjusted cash margin ~13%, so the 16% base margin needs a recovery towards the 37% long-term operating-margin target. Net debt $27.6B (debt $27.1B incl. $2.4B finance leases/other + ~$0.76B operating leases, less $0.19B available cash; settlement cash excluded); gross leverage 3.1x. Very cheap (P/E ~9 on guidance) but equity value is very sensitive to the business value: 35% safety margin. Risks: further Clover/banking share loss, debt, and reported SEC/DOJ inquiries into its 2025 guidance."),
 "CRCL": dict(name="Circle Internet Group", price=67.59, shares=0.2678, rev=2.848, fcf=0.425, sbc=0.208,
              net_cash=1.824, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.1,g10=0.02,m=0.1), base=dict(g1=0.06,g10=0.05,m=0.17), bull=dict(g1=0.3,g10=0.07,m=0.25)),
              notes="TTM to Sep-2026, EXCLUDING the one-off ARC token presale ($182M of Q3 revenue; ~$242M cash received May-Jun 2026, held in net cash). Issuer of the USDC stablecoin: earns interest on the reserves backing USDC (Q3-26 reserve income $658M, -8% YoY, as the reserve return rate fell to 3.5% from 4.1%) and pays ~60% of reserve income to distributors (mainly Coinbase). USDC in circulation $73.9B at Sep-2026, flat YoY (average $73.3B, +8%), down from $77B in Q1. Reported Q3 revenue $865M (+17%) and adjusted EBITDA $317M are flattered by the presale. Guidance: USDC circulation +40% a year through the cycle (unchanged), 2026 other revenue $310-330M incl. the presale, RLDC margin 41.7-43.7%. Base next-year growth cut to 6% (from 12%) because circulation is flat and rates are falling. FCF = operating cash flow - capex - capitalised software, less the presale cash (~$0.43B TTM, ESTIMATE). Corporate net cash $1.8B (cash $1.70B + investments $0.12B, no debt after the convertible was retired; USDC reserves and $1.0B cash for corporate-held stablecoins excluded). Shares = Q3 diluted 268M. Income falls when interest rates fall; growth depends on stablecoin adoption, regulation and the Coinbase deal. Short public history: 12% required return, 35% safety margin."),
 "SPG": dict(name="Simon Property Group", price=233.11, shares=0.3791, rev=7.154, fcf=3.355, sbc=0.04,
              net_cash=-28.579, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0,g10=0.015,m=0.38), base=dict(g1=0.04,g10=0.025,m=0.44), bull=dict(g1=0.06,g10=0.03,m=0.47)),
              notes="TTM to Sep-2026. Largest US mall REIT (premium malls and outlets). Q3 revenue +13% (partly from consolidating acquired stakes), domestic property NOI +6.6%, occupancy 96.5%, base rent/sq ft +6.1%; Real Estate FFO $3.37/share (+4.7%). FY26 Real Estate FFO guidance raised to $13.30-13.40; dividend $2.30 (+4.5%). Analysts expect ~4% revenue growth next year. Cash flow = operating cash flow minus capital spending ($4.30B - $0.95B = $3.36B TTM; development included); stock pay is an ESTIMATE (~$40M). REIT: almost no income tax, so the tax rate is ~0. Shares include operating-partnership units (379M). Net debt $28.6B = $28.4B mortgages and notes + $0.7B ground/operating leases - $0.57B cash; new debt in Q3 cost 5.45-6.33%, above the ~3.8% average, so interest costs are rising. Equity value is very sensitive to rents and interest rates; the bear case has flat sales and lower margins."),
 "META": dict(name="Meta Platforms Inc.", price=614.99, shares=2.5568, rev=241.6, fcf=28.65, sbc=26.94,
              net_cash=-32.39, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.12,g10=0.035,m=0.12), base=dict(g1=0.2,g10=0.05,m=0.2), bull=dict(g1=0.25,g10=0.06,m=0.26)),
              notes="TTM to Sep-2026. Facebook, Instagram, WhatsApp ads plus Reality Labs. Revenue +26% in Q3 (analysts ~22% next year). FCF fell to $28.7B (Q3 negative) on record AI capex, so after $26.9B of stock pay the starting cash margin is ~1%: the value rests on margins recovering toward the 2024 level (~23%) as the build-out matures (base 20%, bear 12%). Net debt $32B incl. leases after large bond issues. Shares = all classes (2.56B). Risks: capex overshoot, regulation, Reality Labs losses."),
 "TT": dict(name="Trane Technologies plc", price=410.0, shares=0.2189, rev=23.2, fcf=3.82, sbc=0.1,
              net_cash=-2.99, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.03,g10=0.03,m=0.12), base=dict(g1=0.1,g10=0.045,m=0.15), bull=dict(g1=0.14,g10=0.055,m=0.17)),
              notes="TTM to Sep-2026. HVAC and climate systems; data-centre cooling demand lifted Q3 revenue +18%. Analysts expect ~10% next year. SBC-adjusted cash margin ~16%. Net debt $3.0B. Cyclical (commercial construction, residential HVAC): bear case 3% growth and 12% margin."),
 "RL": dict(name="Ralph Lauren Corp.", price=398.74, shares=0.0609, rev=8.538, fcf=1.302, sbc=0.114,
              net_cash=-1.16, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0,g10=0.02,m=0.08), base=dict(g1=0.05,g10=0.03,m=0.11), bull=dict(g1=0.08,g10=0.04,m=0.13)),
              notes="TTM to Sep-2026 (FY27 Q2, quarter to 26 Sep 2026). Premium apparel brand repositioning upmarket. Q2 revenue +9% (+10% in constant currency): Asia +28%, North America +6.5%, Europe +2.5%; prices per item (AUR) +9%. Reported gross margin 74.2% includes an $82M refund of IEEPA tariffs (70.5% without it; part of the refund was given to charity); adjusted operating margin 15.7% (14.1% a year earlier). FY27 guidance raised: constant-currency revenue +6-7% plus ~1 point from the 53rd week, operating margin +80-100bp; analysts expect ~7% this year and ~5% next. FCF = operating cash flow - capex: TTM $1.30B ($1.54B - $0.24B), flattered by low capex (H1 $114M vs guidance of 4-5% of revenue for the year) and the tariff refund; FY26 was $0.75B, so the base keeps an 11% margin after stock pay (TTM 13.9%). Net debt $1.16B incl. leases (cash and short-term investments $1.82B; notes $1.24B, leases $1.74B). Diluted shares 60.9M (all classes); $500M bought back in H1, completing the FY27 plan. Fashion and tariff risk: bear case flat sales, 8% margin."),
 "ROST": dict(name="Ross Stores Inc.", price=228.28, shares=0.3208, rev=24.5, fcf=2.79, sbc=0.2,
              net_cash=-0.45, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.03,g10=0.03,m=0.085), base=dict(g1=0.07,g10=0.04,m=0.105), bull=dict(g1=0.09,g10=0.045,m=0.115)),
              notes="TTM to Jul-2026 (FY26 Q2). Off-price apparel and home retailer: steady store growth, thin but stable margins (SBC-adjusted cash margin ~10.6%). Analysts expect ~7% growth. Net debt $0.45B incl. store leases. Risks: tariffs and consumer slowdown (off-price usually holds up)."),
 "GDDY": dict(name="GoDaddy Inc.", price=116.61, shares=0.1257, rev=5.181, fcf=1.744, sbc=0.29,
              net_cash=-2.76, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0,g10=0.02,m=0.2), base=dict(g1=0.05,g10=0.03,m=0.26), bull=dict(g1=0.08,g10=0.04,m=0.29)),
              notes="TTM to Sep-2026. Domains, hosting and small-business software. Q3 revenue +6% (Applications & Commerce +9%, bookings +5.7%), normalized EBITDA margin 33.5%. FY26 guidance: revenue $5.215-5.255B toward the high end (~6%), A&C ~+10%, core ~+4%, FCF ~$1.8B (company FCF adds back restructuring; OCF - capex used here, $1.74B). Very cash-generative (SBC-adjusted margin ~28%) with heavy buybacks ($1.4B YTD, ~12% gross share reduction). Airo AI site builder passed $100M annualised bookings. Cheap because of fears that AI site builders erode the core: the bear case has flat sales and a 20% margin. Net debt $2.76B (total debt $3.81B + leases - $1.12B cash)."),
 "FAST": dict(name="Fastenal Co.", price=51.91, shares=1.1473, rev=9.08, fcf=1.18, sbc=0.01,
              net_cash=-0.24, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.03,g10=0.03,m=0.11), base=dict(g1=0.09,g10=0.045,m=0.13), bull=dict(g1=0.11,g10=0.055,m=0.145)),
              notes="TTM to Sep-2026. Industrial and construction supplies distributor with on-site vending; Q3 sales +15%, analysts expect ~9% next year. SBC-adjusted cash margin ~13%; almost no debt. Expensive (forward P/E ~37): the risk is valuation and an industrial slowdown."),
 "SYK": dict(name="Stryker Corp.", price=306.81, shares=0.3847, rev=26.30, fcf=4.573, sbc=0.256,
              net_cash=-11.66, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.05,g10=0.035,m=0.15), base=dict(g1=0.09,g10=0.05,m=0.18), bull=dict(g1=0.11,g10=0.055,m=0.2)),
              notes="TTM to Sep-2026. Orthopaedics, surgical equipment and neurotech. Q3 net sales +7.7% (organic +7.7%; hips -1%, knees +1%); adjusted EPS $3.52 (+10%). FY26 guidance: organic growth 6.5-7.0%, adjusted EPS $14.80-14.90 (trimmed). Base growth 9% kept (analysts ~9% next year; organic has run 7-9%), but it is now at the top of the range: watch 2027 guidance. Q3 had $0.29B of goodwill impairments and other charges (non-cash). SBC-adjusted cash margin ~16.5%. Net debt $11.7B excl. leases (debt $14.9B - cash $3.3B); $1.0B buyback in Q3 and $3B added to the authorisation. FY25 SBC from a data site (~$0.24B), so TTM SBC is approximate."),
 "CMG": dict(name="Chipotle Mexican Grill", price=31.89, shares=1.265, rev=12.71, fcf=1.51, sbc=0.11,
              net_cash=-4.7, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.09), base=dict(g1=0.1,g10=0.045,m=0.115), bull=dict(g1=0.13,g10=0.055,m=0.13)),
              notes="TTM to Sep-2026. Fast-casual restaurants growing mainly through new units (~8%/yr) plus same-store sales; analysts expect ~11% next year. SBC-adjusted cash margin ~11%. No borrowings: the $5.6B 'debt' is store lease liabilities, deducted here for consistency (conservative, since rent is already in cash flow). Risks: traffic slowdown and cost inflation."),
 "KLAC": dict(name="KLA Corp.", price=157.91, shares=1.303, rev=14.51, fcf=4.04, sbc=0.32,
              net_cash=-1.25, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.02,g10=0.03,m=0.23), base=dict(g1=0.14,g10=0.05,m=0.30), bull=dict(g1=0.2,g10=0.06,m=0.34)),
              notes="TTM to Sep-2026 (FY27 Q1; prices after the 2026 stock split). Leader in chip inspection and process control (~45% operating margin). Revenue +29% on AI and advanced-node spending; analysts expect ~18% next year. SBC-adjusted cash margin ~26% (FY26 ~25%; historically ~30%). Net debt $1.3B. Semiconductor equipment is cyclical: 10.5% required return and 35% safety margin; bear case 2% growth."),
 "CME": dict(name="CME Group Inc.", price=303.14, shares=0.3579, rev=6.96, fcf=4.33, sbc=0.1,
              net_cash=-1.09, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.02,g10=0.03,m=0.54), base=dict(g1=0.06,g10=0.04,m=0.58), bull=dict(g1=0.08,g10=0.05,m=0.61)),
              notes="TTM to Sep-2026. World's largest derivatives exchange (rates, equity index, energy, ags) with its own clearing house: near-monopoly products and a ~60% SBC-adjusted cash margin. Analysts expect ~5% growth; volumes rise with volatility. Net cash uses corporate cash only ($2.3B; clearing members' performance bonds are excluded) less $3.4B debt. Low beta: 25% safety margin."),
 "STE": dict(name="STERIS plc", price=256.99, shares=0.0976, rev=6.166, fcf=0.937, sbc=0.063,
              net_cash=-1.519, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.03,g10=0.03,m=0.12), base=dict(g1=0.07,g10=0.04,m=0.15), bull=dict(g1=0.09,g10=0.05,m=0.17)),
              notes="TTM to Sep-2026 (FY27 Q2). Sterilisation equipment, consumables and outsourced sterilisation services for hospitals and medical-device makers: highly recurring (~70% consumables and services). September-quarter revenue +9% to $1.59B, constant-currency organic +8% (Healthcare +9%, AST +5%, Life Sciences +18%); backlog $549M. FY27 guidance: revenue +7-8% reported (6-7% organic), adjusted EPS raised to $11.35-11.55; free cash flow guided to only ~$800M because capex steps up to ~$450M (from $369M) for capacity. FCF $0.94B = operating cash flow - capex, TTM (H1 FY27 $492.5M + FY26 $972.4M - H1 FY26 $527.7M); SBC-adjusted cash margin ~14%. Net debt $1.5B (debt $1.89B + leases $0.16B - cash $0.53B) after selling the dental business. Risks: ethylene-oxide rules, hospital capital spending, heavier capex holding back cash."),
 "WDAY": dict(name="Workday Inc.", price=197.82, shares=0.241, rev=10.15, fcf=2.84, sbc=1.65,
              net_cash=-0.37, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.05,g10=0.03,m=0.12), base=dict(g1=0.1,g10=0.04,m=0.17), bull=dict(g1=0.13,g10=0.05,m=0.22)),
              notes="TTM to Jul-2026 (FY27 Q2). HR and finance cloud software for large enterprises; subscription revenue ~13%. Stock pay is very heavy ($1.65B, 16% of revenue), so the SBC-adjusted cash margin is only ~12%: the base case assumes it rises to 17% as stock pay falls. Cheap vs history (forward P/E ~15) on fears that AI agents reduce seat counts: bear case 5% growth, 12% margin. Shares = all classes (241M)."),
 "BR": dict(name="Broadridge Financial Solutions", price=192.37, shares=0.1143, rev=7.556, fcf=1.297, sbc=0.102,
              net_cash=-3.32, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.13), base=dict(g1=0.05,g10=0.035,m=0.16), bull=dict(g1=0.07,g10=0.045,m=0.18)),
              notes="TTM to Sep-2026 (FY27 Q1). Investor communications (proxy and shareholder mail) and trading/post-trade technology: ~75% recurring revenue under multi-year contracts. Q1 revenue +5% to $1.67B; recurring revenue +11% in constant currency (9 pts organic), helped by equity positions +16%; event-driven revenue -41% as mutual fund proxies fell; GTO +12% (Capital Markets +17%). Adjusted margin 13.8% (seasonally low quarter); GAAP EPS fell 41% on a $40M digital-asset loss and restructuring. FY27 guidance reaffirmed: recurring revenue +6-8% cc, adjusted EPS +8-12%, adjusted margin ~21%, FCF conversion 100%+, closed sales $290-330M. FCF = operating cash flow minus capex and capitalised software ($1.40B - $0.10B). SBC-adjusted cash margin ~16%. Net debt $3.3B (debt $3.35B + ~$0.26B operating leases - $0.28B cash). Bought back $200M of shares in the quarter. Risks: proxy-rule changes, slower trading volumes; event-driven revenue swings year to year."),
 "MSI": dict(name="Motorola Solutions Inc.", price=528.06, shares=0.1674, rev=12.597, fcf=2.534, sbc=0.387,
              net_cash=-9.891, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.17), base=dict(g1=0.08,g10=0.045,m=0.2), bull=dict(g1=0.1,g10=0.055,m=0.22)),
              notes="TTM to Sep-2026 (2025 + 9 months 2026 - 9 months 2025). Mission-critical radios (LMR), command-centre software and video security for police and public safety: sticky government customers and a record backlog of $16.6B (+14%). Q3-26 sales $3.38B (+12%; Products and Systems Integration +12%, Software and Services +13%), non-GAAP operating margin 32.5% (+200bp). 2026 guidance raised to ~$13.05B revenue (+12%, part acquisitions) and non-GAAP EPS $17.94-17.99; operating cash flow ~$3.05B. FCF = operating cash flow - capex ($2.53B TTM); SBC-adjusted cash margin ~17%. Net debt $9.9B incl. $0.55B leases ($10.1B borrowings less $0.77B cash), up after the $1.3B D-Fend (counter-drone) purchase, funded with $950M new notes, on top of Silvus. Risks: government budgets, acquisition integration, FirstNet/broadband alternatives to radio."),
 "BKR": dict(name="Baker Hughes Co.", price=55.23, shares=0.9931, rev=28.74, fcf=3.23, sbc=0.21,
              net_cash=-14.19, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.02,g10=0.02,m=0.08), base=dict(g1=0.12,g10=0.03,m=0.11), bull=dict(g1=0.15,g10=0.04,m=0.13)),
              notes="TTM to Sep-2026. Oilfield services plus gas and LNG technology (turbines, compressors; data-centre power). Q3 revenue jumped to $8.0B as the Chart Industries acquisition was consolidated, so TTM revenue understates the run-rate (~$32B): base growth 12% next year includes Chart's full year. Net debt rose to $14.2B to fund Chart. Energy-cycle exposure: 10% required return, 35% safety margin, bear case 2% growth and 8% margin."),
 "RSG": dict(name="Republic Services Inc.", price=245.97, shares=0.3065, rev=17.238, fcf=2.56, sbc=0.05,
              net_cash=-14.18, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.02,g10=0.03,m=0.13), base=dict(g1=0.05,g10=0.04,m=0.155), bull=dict(g1=0.07,g10=0.045,m=0.17)),
              notes="TTM to Sep-2026. Number-two US waste collector and landfill owner: essential service, pricing above inflation, very steady. Q3 revenue +8.2% (incl. acquisitions; core price ~2.9%, volume -0.6%). FY26 guidance raised: revenue $17.425-17.475B, adjusted EBITDA $5.55-5.575B, adjusted FCF $2.565-2.585B. FCF = OCF - capex purchases ($2.56B TTM). SBC is an ESTIMATE (~$50M). SBC-adjusted cash margin ~14.6%. Net debt $14.2B incl. $0.2B operating leases (restricted cash excluded); $1.1B spent on acquisitions and $0.86B on buybacks in 9M."),
 "WAB": dict(name="Wabtec Corp.", price=279.6, shares=0.1689, rev=12.21, fcf=1.78, sbc=0.1,
              net_cash=-5.89, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.03,m=0.11), base=dict(g1=0.07,g10=0.04,m=0.145), bull=dict(g1=0.1,g10=0.05,m=0.16)),
              notes="TTM to Sep-2026. Locomotives, rail equipment and freight/transit services; multi-year backlog. Analysts expect ~7% growth. SBC-adjusted cash margin ~14%. Net debt $5.9B. Rail capital spending is cyclical: bear case 2% growth."),
 "MRVL": dict(name="Marvell Technology Inc.", price=196.4, shares=0.8987, rev=9.45, fcf=1.72, sbc=0.83,
              net_cash=-1.36, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.08,g10=0.03,m=0.12), base=dict(g1=0.35,g10=0.05,m=0.2), bull=dict(g1=0.55,g10=0.06,m=0.26)),
              notes="TTM to Jul-2026 (FY27 Q2). Data-centre chips: custom AI accelerators for hyperscalers, optical interconnect and networking. Revenue +37%; analysts expect ~60% next year on custom AI programmes, so the base case uses 35% (fading to 5%) and the bull 55%. Stock pay is heavy (~9% of revenue): SBC-adjusted cash margin ~10% today, 20% in the base case as revenue scales. Very volatile (beta ~2.3) and dependent on a few hyperscaler programmes: 11% required return, 35% safety margin."),
 "LULU": dict(name="lululemon athletica inc.", price=107.24, shares=0.1158, rev=11.09, fcf=1.36, sbc=0.09,
              net_cash=-0.75, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.08,g10=0.02,m=0.09), base=dict(g1=-0.03,g10=0.03,m=0.12), bull=dict(g1=0.02,g10=0.04,m=0.15)),
              notes="TTM to Jul-2026 (FY26 Q2). Premium athletic apparel. US sales are shrinking under competition (Alo, Vuori) and tariffs while international grows; analysts expect revenue to fall ~1% next year. SBC-adjusted cash margin ~12% (FY24-25 ~15%). Cheap (forward P/E ~12) because the brand may be fading: bear case -4% and a 10% margin. Net cash after store leases ~-$0.75B (cash $1.4B, leases $2.1B). Shares = all classes. Scenarios CUT after the Nov-2026 price-drop review (lasting cause): Americas comparable sales -12% in Q2 and FY26 revenue guided down 5-7%, with gross margin ~360bp and operating margin ~750bp lower excluding a one-off tariff refund; base year-1 growth -3% (was +1%) with a 12% margin (was 13%), bear -8% / 9% (was -4% / 10%), bull +2% / 15% (was +5% / 16%)."),
 "RDDT": dict(name="Reddit Inc.", price=90.97, shares=0.2019, rev=3.089, fcf=1.198, sbc=0.386,
              net_cash=3.0, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.06,g10=0.03,m=0.18), base=dict(g1=0.24,g10=0.05,m=0.28), bull=dict(g1=0.36,g10=0.06,m=0.34)),
              notes="TTM to Sep-2026. Online communities monetised through ads and data licensing to AI companies. Q3 revenue +53%, adjusted EBITDA margin 45%; Q4 guide revenue $1.00-1.03B (+38-42%). But search referral traffic (Google AI answers) fell sharply: US daily uniques -2% (logged-out -4%), >1M fewer referrals a week in October, and management warned daily users may fall by a low double-digit percent in Q4. Growth assumptions CUT after the Nov 2026 price-drop review (lasting cause): base 24% (was 28%), bear 6% (was 10%), bull 36% (was 40%). SBC-adjusted cash margin ~26%. Net cash $3.0B (cash + marketable securities, no debt). Shares = all classes (diluted). 11.5% required return, 35% safety margin."),
 "CF": dict(name="CF Industries Holdings", price=119.27, shares=0.147, rev=7.94, fcf=2.025, sbc=0.039,
              net_cash=-1.134, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.15,g10=0.015,m=0.13), base=dict(g1=-0.08,g10=0.02,m=0.2), bull=dict(g1=0,g10=0.03,m=0.25)),
              notes="TTM to Sep-2026. Largest North American nitrogen fertiliser producer (ammonia, urea, UAN) with cheap US natural gas as its edge. Q3 sales $1.86B (+12%) on ~7% higher volumes and higher ammonia prices (urea and UAN slightly lower than a year ago); adjusted EBITDA $833M vs $667M. Gross ammonia output is guided at ~9.5M tons for 2026 because of the Yazoo City outage (restart H1 2027). Analysts expect revenue of ~$8.3B in 2026 and ~11% less in 2027 as nitrogen prices normalise. FCF uses the company definition, which replaces the old CHS estimate: operating cash flow - capex - distributions to minority partners (CHS, Blue Point partners) + their contributions = $2.03B TTM ($3.08B - $1.00B - $0.45B + $0.39B). It is after ~$0.31B of Canadian tax deposits in 2026 (transfer-pricing dispute; CF holds $1.35B of tax receivables vs $0.68B of tax liabilities, and booked a $131M interest charge in Q3, excluded from the interest cost used here). Capex rises with the Blue Point low-carbon ammonia JV (CF 40%, JERA 35%, Mitsui 25%; ~$3.7B plant, start-up 2029; 2026 capex ~$1.3B, CF's share ~$0.95B). Net debt $1.13B: cash $2.82B less the partners' 60% of the JV's $0.50B, minus debt $3.22B and leases $0.44B. Shares ~147M (146.3M outstanding on 2 Nov plus dilution; heavy buybacks, $367M in Q3). Commodity cycle: 35% safety margin, bear case -15% and a 13% margin."),
 "EME": dict(name="EMCOR Group Inc.", price=679.55, shares=0.0438, rev=19.84, fcf=1.48, sbc=0.02,
              net_cash=0.21, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0,g10=0.03,m=0.05), base=dict(g1=0.12,g10=0.045,m=0.07), bull=dict(g1=0.16,g10=0.055,m=0.08)),
              notes="TTM to Sep-2026. Electrical and mechanical contractor (data centres, healthcare, manufacturing). Q3 revenue +29% with record backlog; analysts expect ~13% next year. SBC-adjusted cash margin ~7.4% (normal for contractors). Small net cash. Like FIX, near a cyclical peak in data-centre construction: 10.5% required return, 35% safety margin, bear case flat sales and a 5% margin."),
 "HST": dict(name="Host Hotels & Resorts", price=25.28, shares=0.6873, rev=6.235, fcf=1.151, sbc=0.029,
              net_cash=-4.153, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.03,g10=0.015,m=0.11), base=dict(g1=0.02,g10=0.025,m=0.155), bull=dict(g1=0.04,g10=0.03,m=0.18)),
              notes="TTM to Sep-2026. Largest US lodging REIT (upscale hotels run by Marriott, Hyatt, Hilton). Q3 comparable RevPAR +8.8% (rate +5.7%, occupancy +2.1 pts), Total RevPAR +7.3%, hotel EBITDA margin 25.2% (+90bp); AFFO/share $0.39 (+11%). FY26 guidance raised for the fourth time: comparable RevPAR ~+6.75%, Total RevPAR ~+6.0%, AFFO/share $2.21. Reported revenue only +1% because of $1.16B of 2026 hotel sales (Four Seasons Jackson Hole and Orlando, St. Regis Houston), partly replaced by 1 Hotel Brooklyn Bridge and Renaissance Dallas bought after quarter end; so revenue roughly flat next year. Cash flow = operating cash flow minus hotel capex ($1.73B - $0.58B = $1.15B TTM); OCF includes condo-unit sales at Four Seasons Orlando (one-off) and FY26 capex guide is $550-600M. REIT: almost no income tax. Net debt $4.15B = $5.08B debt + $0.56B operating leases - $1.49B cash (cash ~ $1.0B after the acquisitions and dividend). Hotel demand is cyclical (business and group travel): bear case -3% and an 11% margin."),
 "LII": dict(name="Lennox International", price=344.08, shares=0.0342, rev=5.45, fcf=0.84, sbc=0.02,
              net_cash=-2.03, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0,g10=0.03,m=0.12), base=dict(g1=0.055,g10=0.04,m=0.15), bull=dict(g1=0.08,g10=0.05,m=0.17)),
              notes="TTM to Sep-2026. Residential and light-commercial HVAC (US). SBC-adjusted cash margin ~15%. Analysts expect ~5% growth after a weak 2025 (refrigerant transition, housing slowdown). Net debt $2.0B. Cyclical: bear case flat sales."),
 "NEM": dict(name="Newmont Corp.", price=106.61, shares=1.0392, rev=26.61, fcf=10.07, sbc=0.1,
              net_cash=3.25, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.15,g10=0.01,m=0.15), base=dict(g1=0,g10=0.02,m=0.25), bull=dict(g1=0.05,g10=0.025,m=0.33)),
              notes="TTM to Sep-2026. World's largest gold miner. Record FCF ($10.1B, ~38% of revenue) is earned at a gold price near $3,900/oz: like APA's oil, the base case assumes the cash margin falls to 25% (a more normal gold price) and the bear case to 15% with revenue down 15%. SBC is an ESTIMATE. Net cash $3.3B. The value moves with gold: 35% safety margin."),
 "REGN": dict(name="Regeneron Pharmaceuticals", price=973.36, shares=0.1056, rev=16.896, fcf=3.826, sbc=1.006,
              net_cash=6.594, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.02,m=0.14), base=dict(g1=0.14,g10=0.04,m=0.2), bull=dict(g1=0.18,g10=0.05,m=0.25)),
              notes="TTM to Sep-2026. Q3 revenue +36%: Dupixent +35% to $6.5B and, structurally, the Sanofi development balance was fully repaid in Q2-26, so Regeneron keeps its full antibody profit share from Q3 (collaboration revenue +68%). Three of the four TTM quarters still carry the repayment drag, so the run-rate (~$20B a year) is above TTM: year-1 growth raised to 14% base / 4% bear / 18% bull (was 10 / 0 / 14), kept below the run-rate for EYLEA 2mg erosion (-41%; EYLEA HD +62%), the April-2026 US MFN pricing deal and Dupixent's later patent expiry. FCF $3.83B (OCF $4.85B - capex $1.02B; Yahoo had $3.63B), held down by a $1.85B receivables build; Sanofi's $1.0B upfront for the expanded deal lands in Q4-26 and must be stripped out at the next roll. Stock pay ~$1B. Diluted shares 105.6M. Net cash $6.59B = cash and short-term securities $9.30B less $2.71B debt and finance lease; $9.56B of long-term securities NOT counted (upside). Pipeline and pricing risk."),
 "ZTS": dict(name="Zoetis Inc.", price=82.31, shares=0.408, rev=9.494, fcf=2.235, sbc=0.1,
              net_cash=-7.704, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=-0.04,g10=0.025,m=0.19), base=dict(g1=0.01,g10=0.04,m=0.23), bull=dict(g1=0.05,g10=0.05,m=0.26)),
              notes="TTM to Sep-2026. World's largest animal-health company (pet and livestock medicines, vaccines, diagnostics). September-quarter revenue fell 1% to $2.39B (organic -1%): companion animal -5% (US -8%: key dermatology -16% to $396M as competitors took share, Librela adoption hurt by safety perceptions, US vet visits down 3% this year) while livestock grew 7%. 2026 guidance: revenue $9.22-9.32B, organic -2% to -1%, which is below the $9.49B TTM; management gives no 2027 guidance yet but expects competitive pressure for most of 2027 and little from new launches. So year-1 growth is cut: base 3% -> 1% (analysts ~1%), bear -2% -> -4%, bull 6% -> 5%. Still cheap vs history (forward P/E ~13). FCF $2.24B = operating cash flow - capex, TTM; SBC-adjusted cash margin ~23%. Net debt $7.7B (debt $9.05B + leases $0.19B - cash and investments $1.53B) after debt- and convertible-funded buybacks ($1.7B in 9M26; 406M shares at 30 Oct)."),
 "MO": dict(name="Altria Group Inc.", price=78.03, shares=1.6634, rev=20.63, fcf=9.07, sbc=0.08,
              net_cash=-21.36, extra=9.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.04,g10=-0.02,m=0.36), base=dict(g1=0,g10=0,m=0.4), bull=dict(g1=0.02,g10=0.01,m=0.43)),
              notes="TTM to Sep-2026. US cigarettes (Marlboro), cigars and nicotine pouches (on!). Revenue net of excise taxes. Cigarette volumes fall ~8-10% a year, offset by price increases; analysts expect ~1% growth. The model's terminal growth (2.5% after year 10) is too generous for a declining business, so the scenario margins (36-43%) sit below today's ~44% to compensate. SBC is an ESTIMATE. Net debt $21.4B. 'extra' = ~8% stake in AB InBev (~$11B) less ~20% tax = $9B (ESTIMATE). Regulatory and litigation risk."),
 "HAS": dict(name="Hasbro Inc.", price=119.09, shares=0.1399, rev=5.18, fcf=1.11, sbc=0.09,
              net_cash=-2.12, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0,g10=0.02,m=0.13), base=dict(g1=0.07,g10=0.035,m=0.18), bull=dict(g1=0.1,g10=0.045,m=0.21)),
              notes="TTM to Sep-2026. Toys (Nerf, Transformers, Peppa Pig) plus the highly profitable Wizards of the Coast (Magic: The Gathering, digital games). Analysts expect ~7% growth. SBC-adjusted cash margin ~20%. Net debt $2.1B. Risks: toy demand and tariffs; bear case flat sales, 13% margin."),
 "BMY": dict(name="Bristol-Myers Squibb", price=62.48, shares=2.0441, rev=50.03, fcf=9.29, sbc=0.55,
              net_cash=-32.23, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.08,g10=0.01,m=0.15), base=dict(g1=-0.03,g10=0.02,m=0.2), bull=dict(g1=0.02,g10=0.03,m=0.25)),
              notes="TTM to Sep-2026. Large pharma facing a patent cliff: Eliquis and Opdivo lose exclusivity around 2028, while newer drugs (Cobenfy, Camzyos, Breyanzi, Opdualag) grow. Analysts expect revenue to fall ~3% next year. SBC-adjusted cash margin ~17.5% (FCF $9.3B, historically ~$12-14B). Net debt $32B (Karuna, RayzeBio acquisitions). Very cheap (forward P/E ~9): the question is whether the new drugs replace the old ones."),
 "NRG": dict(name="NRG Energy Inc.", price=98.05, shares=0.21, rev=34.956, fcf=1.9, sbc=0.16,
              net_cash=-22.982, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0,g10=0.02,m=0.035), base=dict(g1=0.08,g10=0.03,m=0.055), bull=dict(g1=0.12,g10=0.04,m=0.07)),
              notes="TTM to Sep-2026 (FY2025 + 9 months 2026 - 9 months 2025). Power generation plus retail electricity and home services (Reliant, Direct Energy, Vivint): ~8 million customers, 2.8 million in Texas (over 80% on term contracts). Revenue $34.96B TTM; Q3 revenue +24% to $9.47B because the LS Power plants and CPower bought in January 2026 ($7.1B paid in 9 months) are now consolidated, plus higher East capacity prices and Texas retail margins. Q3 adjusted EBITDA $2.01B (vs $1.21B) and free cash flow before growth (FCFbG) $1.24B (vs $0.83B). 2026 guidance reaffirmed (adjusted EBITDA $5.33-5.83B, FCFbG $2.8-3.3B); 2027 guidance initiated: EBITDA $5.5-6.0B, FCFbG $2.9-3.4B, with $1B debt reduction and $1B buybacks, before the agreed sale of 4.9 GW of gas plants to LS Power for $4B (closing Q2 2027; $2B more debt reduction). FCF NORMALISED to $1.9B (5.4% of sales, ESTIMATE): reported TTM operating cash flow less capex is only $0.7B after working-capital and collateral swings, hedge terminations ($172M in Q3) and deal costs, while FCFbG is ~$2.4B TTM (it excludes growth capex). Base-case growth kept at 8%: the Q3 jump is the acquisition, not organic growth, and 2027 guidance implies low single digits. Net debt $23.0B (debt incl. finance leases $22.9B + operating leases $0.2B, cash only $0.15B); Q3 interest $302M vs $187M. Diluted shares 210M. 1.2 GW data-centre power deal on track, terms agreed, not yet signed. LOW CONFIDENCE (thin margins, heavy debt, commodity-linked cash flow): 10% required return, 35% safety margin."),
 "FIS": dict(name="Fidelity National Information Services", price=28.32, shares=0.517, rev=12.938, fcf=2.295, sbc=0.191,
              net_cash=-20.11, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.02,g10=0.02,m=0.12), base=dict(g1=0.04,g10=0.03,m=0.17), bull=dict(g1=0.06,g10=0.04,m=0.2)),
              notes="TTM to Sep-2026 (2025 + 9 months 2026 - 9 months 2025), so it includes 3 quarters of the Issuer Solutions business (now Total Issuing Solutions) bought from Global Payments in early 2026 in exchange for the Worldpay stake plus cash ($7.9B paid). That is why Q3 revenue rose 27% to $3.45B; pro forma growth was only 3.7% (recurring +2.5%; Banking +3.9% pro forma, Capital Markets +3%). Adjusted EBITDA margin 42.9%. Guidance cut again: 2026 revenue $13.45-13.51B (pro forma +3.1-3.6%), adjusted EPS $5.82-5.89; preliminary 2027: adjusted revenue -0.5% to +1% (organic 2.5-3.5% less lost one-off licence/termination fees and an exit from low-margin equipment), margin flat to -100bp, adjusted EPS down high-single to low-double digits. Shares fell 23% on 4 Nov; CFO left, whole-company strategic review to report in early 2027. Base next-year growth cut to 4% (from 10%): the deal's extra quarter (Q4) plus a flat 2027. FCF = operating cash flow - capex incl. capitalised software, EXCLUDING $477M one-off cash taxes on the Worldpay sale ($2.30B TTM; 2026 guide ~$2.2B on the same basis). Net debt $20.1B ($20.8B debt incl. leases less $0.74B cash), leverage 3.5x vs 2.8x target, buybacks paused. Equity is very sensitive to the business value: LOW CONFIDENCE, 35% safety margin. Risks: bank conversions delayed, bank mergers, licence-to-SaaS shift, integration."),

 # ---- Dow Jones top 10 by Growth Screen score (Nov 2026): the five not modelled before
 "PG": dict(name="Procter & Gamble Co.", price=167.1, shares=2.44, rev=87.923, fcf=15.34, sbc=0.501,
              net_cash=-23.56, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.01,g10=0.02,m=0.155), base=dict(g1=0.035,g10=0.03,m=0.17), bull=dict(g1=0.05,g10=0.035,m=0.185)),
              notes="TTM to Sep-2026 (FY27 Q1). Household and personal-care brands (Tide, Pampers, Gillette, Pantene). Analysts expect ~3% sales growth (FY27 ~$89.8B, FY28 ~$92.6B); volumes are flat to slightly up and growth comes mostly from price and mix. FCF after stock pay ~17% of sales, steady for four years (16.8% FY26), so the base holds 17%. Net debt $23.6B (cash $15.4B, debt $38.9B). Shares 2.44B is an ESTIMATE of diluted shares (2.32B basic plus the ESOP convertible preferred). Very stable demand: 8% required return."),
 "KO": dict(name="The Coca-Cola Company", price=95.73, shares=4.32, rev=51.054, fcf=14.282, sbc=0.269,
              net_cash=-25.02, extra=8.0, mos=0.25,
              scen=dict(bear=dict(g1=0.01,g10=0.025,m=0.21), base=dict(g1=0.04,g10=0.035,m=0.24), bull=dict(g1=0.06,g10=0.04,m=0.265)),
              notes="TTM to Sep-2026. Q3 revenue +7% (organic +7%); FY26 outlook raised to organic growth of at least 5%, comparable EPS +11% and free cash flow of at least $13.0B (Q3 release). TTM FCF $14.3B (27% of sales) is clean of the fairlife milestone paid in March 2025 (2025 FCF was only $5.3B because of it), but sits above the ~21% of the years before refranchising finished, so the base margin is set at 24% and the bear at 21%. Analysts see revenue ~3% LOWER next year (more bottlers sold), hence base growth 4%. Net debt $25.0B = debt $41.6B less cash, short-term investments and marketable securities $16.6B. 'extra' $8.0B = ESTIMATE for the equity stakes in bottlers and Monster (~$19B book) at a haircut, since part of their dividends is already in FCF. Diluted shares ~4.32B (ESTIMATE). 8% required return."),
 "SHW": dict(name="Sherwin-Williams Co.", price=349.01, shares=0.2436, rev=24.912, fcf=3.078, sbc=0.117,
              net_cash=-14.54, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.01,g10=0.025,m=0.10), base=dict(g1=0.05,g10=0.04,m=0.12), bull=dict(g1=0.08,g10=0.05,m=0.135)),
              notes="TTM to Sep-2026. Largest US paint and coatings company (company-owned stores for contractors, plus Valspar and industrial coatings); TTM sales +7.9% include the Suvinil (Brazil) acquisition. Analysts expect ~4% sales growth next year (~$26.2B) as housing turnover stays weak. FCF after stock pay 11.9% of sales TTM, 8-11% in 2022-2025 (heavy spending on the new Cleveland HQ and R&D centre), so the base is 12%. Net debt $14.5B; operating leases (~$2.2B) not deducted. Diluted shares ~0.2436B (ESTIMATE). Housing and industrial cycle: 9% required return and 30% safety margin."),
 "JNJ": dict(name="Johnson & Johnson", price=272.32, shares=2.42, rev=99.335, fcf=19.595, sbc=1.424,
              net_cash=-27.42, extra=-4.3, mos=0.25,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.165), base=dict(g1=0.055,g10=0.035,m=0.19), bull=dict(g1=0.075,g10=0.045,m=0.21)),
              notes="TTM to Sep-2026. Q3 sales $25.4B, +6.0% operational (Innovative Medicine +7.9% despite a ~690bp Stelara biosimilar drag, MedTech +2.5%); FY26 sales guide raised to $101.0-101.4B (+7.4%), adjusted EPS $11.05-11.15 (Q3 release). Growth drugs: Tremfya, Darzalex, Carvykti, Tecvayli, Rybrevant, Spravato, Caplyta. FCF after stock pay ~18-19% of sales for four years; YTD FCF ~$15.1B vs $14.2B. GAAP EPS of $0.09 in Q3 reflects the charge for the proposed $5.5B talc settlement (July 2026): 'extra' = -$4.3B, the settlement after tax (ESTIMATE), as it is not yet in debt. Net debt $27.4B. Diluted shares ~2.42B (ESTIMATE). AAA balance sheet, very low beta: 8% required return."),
 "AMGN": dict(name="Amgen Inc.", price=460.28, shares=0.546, rev=38.903, fcf=9.581, sbc=0.493,
              net_cash=-40.82, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.01,g10=0.02,m=0.19), base=dict(g1=0.04,g10=0.035,m=0.24), bull=dict(g1=0.08,g10=0.05,m=0.28)),
              notes="TTM to Sep-2026. Q3 revenue $10.37B, +8%: Repatha +37%, Evenity +39%, Tezspire +43% and biosimilars offset Prolia (-45%) and Xgeva (-47%) losing exclusivity. FY26 revenue guide $38.9-39.7B, non-GAAP EPS $22.90-23.70, capex ~$2.6B, buybacks up to $3.0B (Q3 release). Analysts expect ~3.5% growth next year as the Prolia/Xgeva erosion continues. FCF after stock pay 20-30% of sales in 2022-2025 (23% TTM), base 24%. MariTide (obesity, Phase 3) is the bull case and is NOT in the base. Net debt $40.8B (debt $54.0B from the Horizon deal, cash $13.2B). Diluted shares 546M (Q3). Patent and pricing risk: 8.5% required return, 30% safety margin."),

 # ---- Requested Nov 2026 (VLTO, AMP, PPG, EOG) and the Growth Screen's consumer-staples sector picks not modelled before (PM, DLTR)
 "VLTO": dict(name="Veralto Corp.", price=116.55, shares=0.2440, rev=5.801, fcf=1.093, sbc=0.074,
              net_cash=-1.135, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.16), base=dict(g1=0.055,g10=0.04,m=0.18), bull=dict(g1=0.08,g10=0.05,m=0.195)),
              notes="TTM to Sep-2026. Water quality (Hach, Trojan, ChemTreat) and product quality and innovation (Videojet, X-Rite, Esko), spun off from Danaher in 2023; ~60% recurring revenue (consumables, service, software). Analysts expect ~8% sales growth this year (incl. small acquisitions) and ~5% next year. Very light capex (~1% of sales): FCF after stock pay 17.6% of sales TTM, 13-17% in 2022-2025, so the base is 18%. Net debt $1.1B (cash $1.8B, debt $2.9B after a repayment in Q3). Diluted shares ~0.244B (ESTIMATE). Risk: industrial slowdown hitting the product-quality half (bear case 2% growth)."),
 "AMP": dict(name="Ameriprise Financial Inc.", price=509.32, shares=0.0875, rev=19.829, fcf=4.162, sbc=0.0,
              net_cash=0.0, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.05,g10=0.02,m=0.17), base=dict(g1=0.06,g10=0.04,m=0.20), bull=dict(g1=0.09,g10=0.05,m=0.22)),
              notes="TTM to Sep-2026. Wealth management (~10,000 advisers, the bulk of profit), asset management (Columbia Threadneedle) and retirement and protection (annuities, life insurance). Its cash flow mixes in client cash and insurance reserves, so it is valued like AXP: cash flow = NET INCOME ($4.2B, stock pay already deducted), revenue = total net revenues ($19.8B), and debt is treated as part of the business (net cash set to zero, no interest add-back). Returns nearly all earnings through buybacks ($3.5B TTM) and dividends ($0.6B). Analysts expect ~9% revenue growth this year and ~5% next. Fees move with stock and bond markets, and the TTM margin (21%) comes after strong markets, so the base margin is 20% and a bear market cuts revenue quickly (bear case -5% and a 17% margin). Diluted shares ~0.0875B (ESTIMATE)."),
 "PPG": dict(name="PPG Industries Inc.", price=123.27, shares=0.2215, rev=16.692, fcf=1.28, sbc=0.048,
              net_cash=-5.82, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.07), base=dict(g1=0.03,g10=0.03,m=0.09), bull=dict(g1=0.05,g10=0.04,m=0.105)),
              notes="TTM to Sep-2026. Paints and coatings: aerospace, automotive refinish, protective and marine, industrial and packaging coatings, plus architectural paint in Latin America (US/Canada architectural sold in Dec 2024). Analysts expect ~6% sales growth this year and ~3% next. FCF is uneven (3-12% of sales in 2022-2025) because capex is high (~$0.77B TTM for new plants) and working capital swings; FCF after stock pay 7.4% TTM, so the base is 9%, assuming capex eases. Net debt $5.8B incl. leases. Diluted shares ~0.2215B (ESTIMATE). Industrial and auto cycle: 9.5% required return and 30% safety margin."),
 "EOG": dict(name="EOG Resources Inc.", price=148.39, shares=0.522, rev=29.728, fcf=7.382, sbc=0.233,
              net_cash=-2.515, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.18,g10=0.0,m=0.14), base=dict(g1=-0.08,g10=0.02,m=0.2), bull=dict(g1=0.03,g10=0.025,m=0.24)),
              notes="TTM to Sep-2026. Low-cost US oil and gas producer (Delaware Basin, Eagle Ford, Dorado gas, Utica after the Encino deal in Aug 2025). Revenue follows the oil price: WTI averaged $85.68 in Q3 after $92.85 in Q2 (far above 2025), so Q3 revenue was $8.5B vs $5.8B a year earlier and TTM revenue is $29.7B. Record volumes: total production 1,433 MBoe/d (+10%), oil 550 MBbl/d (+3%), both above guidance; cash operating cost $10.49/Boe. 2026 capex guidance $6.3-6.7B. Analysts expect ~$30.5B revenue for 2026 and ~$27.4B for 2027, about 8% below this TTM as oil prices ease, so the base case now starts at -8% (was flat when the TTM was below the 2027 estimate) and the bear case at -18% (was -10%); the bull case (+3%) is oil staying near today's level. The cash margin (24% after stock pay TTM, 15% in 2025, ~23% in 2023-2024) settles at 14-24%. FCF = operating cash flow - capex (oil and gas plus other PP&E) = $7.38B TTM ($14.06B - $6.68B); company FCF in Q3 $2.18B. Net debt $2.5B (cash $5.75B; debt $7.92B plus $0.34B current operating leases, as before). Diluted shares 522M ($1.0B of buybacks in Q3; 518.5M outstanding on 29 Oct); dividend raised 8% to $1.10 a quarter. Oil-price dependent: 35% safety margin."),
 "PM": dict(name="Philip Morris International Inc.", price=201.5, shares=1.56, rev=43.138, fcf=13.595, sbc=0.26,
              net_cash=-40.88, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.02,m=0.25), base=dict(g1=0.055,g10=0.035,m=0.28), bull=dict(g1=0.075,g10=0.045,m=0.30)),
              notes="TTM to Sep-2026. International cigarettes (Marlboro outside the US) and smoke-free products (IQOS heated tobacco, ZYN nicotine pouches), now over 40% of revenue and growing double digits; revenue net of excise taxes. Analysts expect ~7% sales growth this year and ~5% next. FCF $13.6B TTM (32% of sales) is above 2023-2025 (22-28%), so the base margin is 28% after stock pay. SBC is an ESTIMATE (~$0.26B). Net debt $40.9B. Risks: regulation and excise taxes, currency (most sales outside the US), ZYN supply and competition. Growth Screen consumer-staples top-5 pick (4 of 5 checks)."),
 "DLTR": dict(name="Dollar Tree Inc.", price=137.94, shares=0.189, rev=20.069, fcf=1.977, sbc=0.068,
              net_cash=-6.613, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.065), base=dict(g1=0.055,g10=0.035,m=0.085), bull=dict(g1=0.075,g10=0.04,m=0.095)),
              notes="TTM to Jul-2026 (FY26 Q2), continuing operations only: Family Dollar was sold in July 2025. ~9,000 Dollar Tree stores moving to multi-price ($1.25 to $7) items. Analysts expect ~6.5% sales growth this year and ~6% next (new stores plus same-store sales). FCF after stock pay 9.5% of sales TTM, ~7% in the last fiscal year, so the base is 8.5%. Net debt $6.6B incl. $4.7B store leases (as for ROST). Diluted shares ~0.189B (ESTIMATE). Risks: tariffs on imported goods, low-income shoppers under pressure, execution of the multi-price rollout. Growth Screen consumer-staples top-5 pick (4 of 5 checks)."),

 # ---- Russell 2000 small caps that pass all 5 checks (Nov 2026): INVA, CTRE, CVSA, QLYS, LAUR, IDCC, LMAT, BOX, ACIW
 "INVA": dict(name="Innoviva Inc.", price=19.1, shares=0.0711, rev=0.4383, fcf=0.1825, sbc=0.0135,
              net_cash=0.3202, extra=0.0, mos=0.4,
              scen=dict(bear=dict(g1=-0.05,g10=-0.03,m=0.3), base=dict(g1=0.05,g10=0.0,m=0.36), bull=dict(g1=0.09,g10=0.025,m=0.4)),
              notes="TTM to Sep-2026. Two businesses: royalties from GSK's Relvar/Breo and Anoro Ellipta inhalers (the bulk of profit) and a growing specialty-hospital drug business (Giapreza, Xerava, Zevtera), plus stakes in small biotechs (Innoviva Strategic Investments, NOT counted: 'extra' = 0). Analysts expect ~10% revenue growth this year and ~9% next as the hospital drugs grow, but the inhaler royalties shrink as generics and patent expiries arrive around the end of the decade, so the base fades growth to 0% by year 10 and the bear case shrinks. FCF after stock pay 39% of sales TTM (36-55% in 2022-2025), base 36%. The 81% net margin includes gains on its investments and is not used. Net cash $0.32B = cash $0.59B less $0.27B of convertible notes, counted as debt (basic shares 71.1M; conversion would add shares instead, so this is an ESTIMATE either way). Russell 2000 small cap (passes all 5 checks). LOW-MEDIUM CONFIDENCE (royalty cliff): 11% required return, 40% safety margin."),
 "CTRE": dict(name="CareTrust REIT Inc.", price=38.87, shares=0.2577, rev=0.5378, fcf=0.5405, sbc=0.0119,
              net_cash=-1.925, extra=1.007, mos=0.35,
              scen=dict(bear=dict(g1=0.02,g10=0.02,m=0.75), base=dict(g1=0.08,g10=0.03,m=0.85), bull=dict(g1=0.11,g10=0.035,m=0.88)),
              notes="TTM to Sep-2026 (Q3 2026). Healthcare REIT: skilled-nursing, seniors-housing and care homes in the US and UK on long triple-net leases (tenants pay upkeep, so cash flow is close to rent) plus mortgage and other loans to operators, and a growing seniors-housing operating (SHOP) book. Revenue grows fast through acquisitions ($2.9B invested in 2026 to September, $0.74B in Q3 at an 8.3% yield), so TTM figures understate the properties it owns today: revenue = Q3 2026 property revenue (rent plus resident fees) x 4 ($0.54B, run-rate ESTIMATE; total revenue incl. loan interest income was $176M in Q3, up 33%) and cash flow = TTM operating cash flow minus capital spending ($0.49B, before acquisitions) scaled to that run-rate ($0.54B, about 100% of property revenue because interest income on loans is in cash flow), stock pay ~$12M; REIT, so almost no income tax. Normalized FFO per share $0.54 in Q3, up 20%; 2026 guidance raised at the low end to $2.08-2.09. Revenue grows ~30% a year because it buys properties with NEW SHARES AND DEBT, so the base uses PER-SHARE growth (8% fading to 3%: rent escalators plus accretive buying), not revenue growth. Shares 257.7M outstanding (Nov 2026; Q3 diluted average 241M after the forward equity settlement and ATM sales). Net debt $1.93B at 4 Nov 2026 = $2.03B of debt (4.7% average rate) less $0.10B cash, after the first 23 LNT UK care homes (GBP 552M, $733M, 1 Oct) and $274M of other deals after the quarter; those $1.01B of investments are not yet in the Q3 run-rate, so they are added back at cost as 'extra' (ESTIMATE: valued at what was paid). 22 more LNT homes (GBP 528M) come through 2027; pipeline $1.2B. Net debt / run-rate EBITDA 1.4x (Sep). Rent coverage (EBITDARM) 2.89x. Risks: tenant (operator) failures, Medicaid and Medicare rates, UK care-home operating risk as LNT moves to SHOP, dilution. Russell 2000 small cap (passes all 5 checks): 9.5% required return, 35% safety margin."),
 "CVSA": dict(name="Covista Inc. (formerly Adtalem Global Education)", price=110.32, shares=0.034, rev=2.0033, fcf=0.3546, sbc=0.0411,
              net_cash=-0.5314, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.01,g10=0.02,m=0.12), base=dict(g1=0.065,g10=0.035,m=0.16), bull=dict(g1=0.09,g10=0.045,m=0.18)),
              notes="TTM to Sep-2026 (FY27 Q1). US healthcare education: Chamberlain (nursing), Walden (online graduate degrees) and the medical and veterinary schools (Ross, American University of the Caribbean). Analysts expect ~6.5% revenue growth this fiscal year and ~7% next (enrolment growth, nursing shortage). FCF after stock pay 15.7% of sales TTM, 10-18% in FY23-FY26 and rising, so the base is 16%. Net debt $0.53B incl. $0.25B of leases. Diluted shares ~34.0M (ESTIMATE). Risks: US student-aid rules (Title IV, gainful employment), enrolment cycles and lawsuits (Walden). Russell 2000 small cap (passes all 5 checks): 11% required return, 35% safety margin."),
 "QLYS": dict(name="Qualys Inc.", price=173.09, shares=0.0353, rev=0.721, fcf=0.324, sbc=0.079,
              net_cash=0.469, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.04,g10=0.025,m=0.28), base=dict(g1=0.08,g10=0.04,m=0.33), bull=dict(g1=0.11,g10=0.05,m=0.36)),
              notes="TTM to Sep-2026. Cloud security and compliance software (vulnerability management, the Qualys cloud platform), sold as subscriptions. Q3 revenue $188.0M, +11% (86% of this year's growth from existing customers); net dollar expansion 105% (104% a year earlier), customers spending $500K+ up 15% to 243; channel now 55% of revenue. Full-year 2026 guidance raised for the third time to $736.9-738.9M (~10%); Q4 guide $191-193M (+9-10%) and Q4 billings guided to ~8%, so growth is steady at ~10% rather than accelerating; competition from CrowdStrike, Palo Alto, Tenable and Rapid7 remains the main risk. Very light capex: FCF $324M TTM ($304M in 2025 + $250M in 9 months 2026 - $229M), after stock pay ($79M) 33.9% of sales. Net cash $0.47B = cash $0.36B + short-term securities $0.16B - leases $0.05B, no borrowings (a further $0.29B of long-term securities is not counted). Buys back ~3-4% of shares a year ($186M in 9 months). Diluted shares 35.3M (Q3). Scenarios from the rules (analysts ~8.7% next year). Russell 2000 small cap (passes all 5 checks): 12% required return, 35% safety margin."),
 "LAUR": dict(name="Laureate Education Inc.", price=33.59, shares=0.137, rev=1.9149, fcf=0.2876, sbc=0.0142,
              net_cash=-0.5927, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.0,g10=0.025,m=0.1), base=dict(g1=0.06,g10=0.04,m=0.14), bull=dict(g1=0.09,g10=0.05,m=0.16)),
              notes="TTM to Sep-2026. Private universities in Mexico (UVM, UNITEC) and Peru (UPC, UPN, Cibertec), ~500,000 students, campus and online. Revenue is seasonal (Q1 is small) and reported in US dollars, so it swings with the peso and sol: this year's ~13% growth includes currency; analysts expect ~6% next year. FCF after stock pay 14.3% of sales TTM (10-15% in 2022-2025), base 14%. Net debt $0.59B, of which $0.58B is campus leases. Diluted shares ~137M (ESTIMATE). Risks: currency, Mexican and Peruvian economies and education rules. Russell 2000 small cap (passes all 5 checks): 12% required return (11% plus 1 point for emerging-market currency and politics), 35% safety margin."),
 "IDCC": dict(name="InterDigital Inc.", price=285.28, shares=0.0275, rev=0.8172, fcf=0.252, sbc=0.0603,
              net_cash=0.8042, extra=0.0, mos=0.4,
              scen=dict(bear=dict(g1=-0.15,g10=0.02,m=0.24), base=dict(g1=-0.05,g10=0.04,m=0.33), bull=dict(g1=0.05,g10=0.05,m=0.40)),
              notes="TTM to Sep-2026. Licenses wireless (4G/5G) and video-coding patents to phone, TV and PC makers (Apple, Samsung, Xiaomi and others) and is expanding into streaming and consumer electronics. Revenue is lumpy: catch-up payments from settled disputes and arbitration lift some years (2024-2026), so analysts expect revenue ~13% LOWER next year ($0.71B) and the base starts at -5% before recurring licence growth of ~4-5%. FCF after stock pay 23% of sales TTM; over 2022-2025 FCF was ~40% of sales before stock pay (~34% after; 2025 had a large catch-up), so the base is 33%. Net cash $0.80B (cash and investments $1.12B, convertible notes $0.32B). Diluted shares ~27.5M (ESTIMATE, includes some dilution from the convertible notes). Risks: licence renewals and litigation with large phone makers, which can delay cash for years. Russell 2000 small cap (passes all 5 checks): 12.5% required return, 40% safety margin."),
 "LMAT": dict(name="LeMaitre Vascular Inc.", price=80.89, shares=0.0233, rev=0.2694, fcf=0.067, sbc=0.0082,
              net_cash=0.2008, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.05,g10=0.03,m=0.16), base=dict(g1=0.1,g10=0.05,m=0.2), bull=dict(g1=0.13,g10=0.06,m=0.23)),
              notes="TTM to Sep-2026. Devices and human-tissue grafts for vascular surgeons (shunts, patches, valvulotomes, bovine and cadaver grafts, Artegraft), sold through its own sales force in niches too small for large med-tech companies; grows by raising prices, adding reps and buying small product lines. Analysts expect ~11% revenue growth this year and ~10% next. FCF after stock pay 21.8% of sales TTM, up from 11-14% in 2022-2024 as capex on the new tissue plant ended, so the base is 20%. Net cash $0.20B (cash $0.39B, $0.17B convertible notes plus leases). Diluted shares ~23.3M (ESTIMATE). Risks: product recalls, hospital budgets, acquisition prices. Russell 2000 small cap (passes all 5 checks): 11% required return, 35% safety margin."),
 "BOX": dict(name="Box Inc.", price=41.95, shares=0.148, rev=1.2341, fcf=0.3497, sbc=0.2357,
              net_cash=-0.0813, extra=-0.5, mos=0.35,
              scen=dict(bear=dict(g1=0.04,g10=0.025,m=0.08), base=dict(g1=0.08,g10=0.04,m=0.12), bull=dict(g1=0.1,g10=0.05,m=0.16)),
              notes="TTM to Jul-2026 (FY27 Q2). Cloud content management for businesses (file sharing, workflow, e-signature and AI search on company documents), sold as subscriptions. Analysts expect ~9.5% revenue growth this fiscal year and ~9% next. Stock pay is very high (19% of sales), so FCF after stock pay is only 9.2% of sales TTM (8-9% in FY23-FY26) vs 28% before it; the base assumes stock pay falls slowly as a share of sales (12%). Net debt $0.08B (convertible notes and leases $0.53B, cash $0.44B). 'extra' = -$0.50B for the Series A convertible preferred stock issued to KKR in 2021 (ESTIMATE; Yahoo shows $15M of preferred dividends TTM). Diluted shares ~148M (ESTIMATE, includes RSUs). Risks: Microsoft (SharePoint, OneDrive) and Google bundles, seat cuts. Russell 2000 small cap (passes all 5 checks): 12% required return, 35% safety margin."),
 "ACIW": dict(name="ACI Worldwide Inc.", price=61.45, shares=0.1013, rev=1.7646, fcf=0.3316, sbc=0.0792,
              net_cash=-0.6163, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.1), base=dict(g1=0.07,g10=0.035,m=0.15), bull=dict(g1=0.09,g10=0.045,m=0.18)),
              notes="TTM to Sep-2026. Payments software for banks, merchants and billers: real-time payments, card processing (BASE24) and fraud tools (Payment Software), plus bill-payment processing (Biller, Speedpay). Licence sales are recognised up front, so quarters are lumpy: Q3 revenue fell 12% to $427M (Payment Software -24% as 2026 renewals are concentrated in Q4; Biller +6%), and Q4 is guided at $612-642M. 2026 guidance: revenue $1.895-1.925B (+8-9%, reiterated), adjusted EBITDA raised to $550-565M; analysts expect ~7.5% growth next year. New ARR bookings $24M in Q3 (+86%), $79M TTM (-3%). FCF = operating cash flow - capex (equipment and capitalised software) = $0.33B TTM ($0.376B - $0.044B); after stock pay 14.3% of sales TTM and 7-16% in 2022-2025, base 15%. Net debt $0.62B (debt $0.82B incl. $18M leases, cash $0.22B). Diluted shares 101.3M ($157M of buybacks YTD). Risks: bank IT budgets, lumpy licence deals (Q4 must deliver the year), competition from FIS, Fiserv and newer cloud vendors. Russell 2000 small cap (passes all 5 checks): 12% required return, 35% safety margin."),

 # ---- Added Nov 2026 from the Growth Screen (CPRT, AOS, TPL, VICI, LIN, CL, ALGN, ANET, WSM) and the Russell 2000 screen (LRN, MCRI, CARG, USLM, EPAC)
 "CPRT": dict(name="Copart Inc.", price=31.75, shares=0.9263, rev=4.666, fcf=1.267, sbc=0.039,
              net_cash=4.4014, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.22), base=dict(g1=0.07,g10=0.045,m=0.26), bull=dict(g1=0.1,g10=0.055,m=0.29)),
              notes="TTM to Jul-2026 (fiscal year 2026). Online auctions of wrecked and used vehicles for insurers, dealers and fleets in 11 countries; it owns most of its storage yards, which rivals cannot easily copy. Revenue grew only 0.4% in fiscal 2026 after 9-10% a year before (fewer insured cars and lower used-car prices). In September 2026 it agreed to buy ACV Auctions (dealer-to-dealer online auctions) for $1.9B in cash, closing around the end of 2026; analysts' +18% and +13% revenue forecasts include ACV, which adds sales but almost no profit at first (the company expects no effect on earnings per share in year one). So scenarios are hand-written for Copart alone (base 7% growth fading to 4.5%) and the purchase price is treated as worth what is paid: the $1.9B stays in net cash (ESTIMATE; if ACV is worth less, fair value is up to $2 a share lower). FCF after stock pay 26.3% of sales (21-26% in fiscal 2023-2025). Net cash $4.40B before the deal (cash $4.49B, leases $0.09B, no borrowings); the $0.19B a year of interest earned on it is taken out of cash flow. Basic shares 926M. Growth Screen pick (Industrials). 9% required return, 25% safety margin."),
 "AOS": dict(name="A. O. Smith Corporation", price=63.46, shares=0.1385, rev=3.28, fcf=0.485, sbc=0.015,
              net_cash=-0.4803, extra=0.4, mos=0.3,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.115), base=dict(g1=0.035,g10=0.03,m=0.14), bull=dict(g1=0.055,g10=0.04,m=0.155)),
              notes="TTM to Sep-2026, restated without China. Water heaters and boilers (North America, about 40% of US residential) and water treatment. In October 2026 it agreed to sell 81% of its shrinking China business to CPE (closing in the first half of 2027); China becomes a discontinued operation from Q4, which is why analysts show sales 13% lower this year. So revenue here is the company's 2026 guidance without China ($3.28B, +4% on the same basis) and cash flow is the TTM figure scaled down by the same share ($0.485B, ESTIMATE: China's own cash flow is not disclosed); 'extra' = +$0.40B for the sale proceeds and the 19% stake kept (ESTIMATE from the ~$400M valuation; a brand licence could add ~$100M). Analysts expect +4% next year, which the rule uses. FCF after stock pay 14.3% of sales (8-15% in 2022-2025, with China). Net debt $0.48B (debt $0.71B incl. leases, cash $0.23B). Shares 138.5M (common plus Class A, balance sheet). Growth Screen pick (Industrials). 9% required return, 30% safety margin."),
 "TPL": dict(name="Texas Pacific Land Corporation", price=282.71, shares=0.069, rev=0.968, fcf=0.541, sbc=0.017,
              net_cash=0.3543, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.45), base=dict(g1=0.1,g10=0.04,m=0.52), bull=dict(g1=0.16,g10=0.05,m=0.57)),
              notes="TTM to Sep-2026. Owns ~880,000 acres in the Permian Basin of West Texas: oil and gas royalties (others drill, TPL collects a share), water sales and produced-water disposal, and surface fees (easements, pipelines, power lines, now data-centre land). Revenue +21% TTM. Reported free cash flow is only $0.12B because Yahoo's capital spending ($0.52B) includes buying more royalty acreage and land; ordinary capital spending (water plants) is put at ~$0.10B a year (ESTIMATE), giving cash flow of $0.54B (operating cash flow $0.64B - $0.10B), 54% of sales after stock pay. The purchases (~$0.2B a year, ESTIMATE from 2022-2025) are charged as growth investment instead. One analyst on Yahoo, so scenarios are hand-written: base 10% growth fading to 4%, bear flat (lower oil price or slower drilling). Net cash $0.35B, no borrowings. Shares 69.0M. Growth Screen pick (Energy). 9% required return, 30% safety margin. MEDIUM-LOW CONFIDENCE: value follows oil and gas prices."),
 "VICI": dict(name="VICI Properties Inc.", price=24.785, shares=1.1011, rev=4.156, fcf=2.703, sbc=0.018,
              net_cash=-17.5554, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.01,g10=0.015,m=0.6), base=dict(g1=0.03,g10=0.025,m=0.64), bull=dict(g1=0.045,g10=0.03,m=0.66)),
              notes="TTM to Sep-2026. Owns casino resorts (Caesars Palace, MGM Grand, the Venetian) and other leisure property, leased back to the operators for decades on triple-net leases with rent escalators (tenants pay upkeep, taxes and insurance, so almost all rent becomes cash); also lends to leisure developers. Cash flow = operating cash flow minus capital spending ($2.70B, 65% of revenue after interest). REIT: almost no income tax. Revenue rises ~2-3% a year from escalators; faster growth needs buying property with new shares and debt, so scenarios are hand-written at per-share rates (base 3% fading to 2.5%) and its typical yearly purchases are charged as growth investment. Analysts expect +5% revenue this year and +3% next. Net debt $17.6B incl. $0.9B ground leases. Shares 1,101M (operating-partnership units not included). Growth Screen pick (Real Estate). 8.5% required return, 30% safety margin."),
 "LIN": dict(name="Linde plc", price=523.75, shares=0.4591, rev=36.238, fcf=5.08, sbc=0.135,
              net_cash=-22.755, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.125), base=dict(g1=0.05,g10=0.04,m=0.155), bull=dict(g1=0.065,g10=0.045,m=0.18)),
              notes="TTM to Sep-2026. World's largest industrial-gas company (oxygen, nitrogen, hydrogen, helium) for steel, chemicals, electronics, healthcare and food; plants sit on or next to customer sites under long contracts. Analysts expect ~8% sales growth this year (price, currency and new plants) and ~5% next. Capital spending is high ($5.6B, a record project backlog incl. clean-hydrogen and chip-fab plants), so FCF after stock pay is 13.6% of sales TTM (14-17% in 2022-2025) against an after-tax operating margin of ~21%. Net debt $22.8B. Shares 459M. Growth Screen pick (Materials). 8.5% required return, 25% safety margin."),
 "CL": dict(name="Colgate-Palmolive Company", price=97.64, shares=0.795, rev=21.284, fcf=3.789, sbc=0.169,
              net_cash=-6.189, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.01,g10=0.02,m=0.15), base=dict(g1=0.035,g10=0.03,m=0.17), bull=dict(g1=0.05,g10=0.04,m=0.18)),
              notes="TTM to Sep-2026. Toothpaste (about 40% of the world market), soap, home care and Hill's pet food; ~70% of sales outside the US, much of it in emerging markets. Analysts expect ~5% sales growth this year and ~2% next. FCF after stock pay 17.0% of sales TTM (10-17% in 2022-2025, rising). Net income ($2.05B TTM) is held down by a write-down; the tax rate used is 24%. Net debt $6.2B. Shares 795M. Growth Screen pick (Consumer Staples). 8% required return, 25% safety margin."),
 "ALGN": dict(name="Align Technology Inc.", price=171.09, shares=0.0707, rev=4.159, fcf=0.603, sbc=0.17,
              net_cash=0.9985, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.08), base=dict(g1=0.04,g10=0.04,m=0.12), bull=dict(g1=0.07,g10=0.05,m=0.15)),
              notes="TTM to Sep-2026. Invisalign clear aligners (about 80% of sales) and iTero scanners and dental software. Sales have grown only 2-4% a year since 2022 as consumers delay treatment and cheaper aligners spread; analysts expect ~2% this year and ~3% next. Stock pay is heavy (4% of sales), so FCF after stock pay is 10.4% of sales TTM (4-12% in 2022-2025). Net cash $1.0B (cash $1.14B, leases $0.15B). Shares 70.7M. Growth Screen pick (Health Care). 10% required return, 30% safety margin."),
 "ANET": dict(name="Arista Networks Inc.", price=197.02, shares=1.2634, rev=11.89, fcf=5.017, sbc=0.512,
              net_cash=14.359, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.15,g10=0.04,m=0.3), base=dict(g1=0.3,g10=0.06,m=0.35), bull=dict(g1=0.4,g10=0.07,m=0.38)),
              notes="TTM to Sep-2026. Ethernet switches and its EOS software for cloud and AI data centres and large companies. Q3 revenue +59%; analysts expect ~49% growth this year and ~40% next as AI back-end networks move to Ethernet. FCF after stock pay 37.9% of sales TTM, helped by customer prepayments (deferred revenue); the after-tax operating margin is ~36%, so the base is 35%. Net cash $14.4B, no debt; the $0.45B a year of interest earned on it is taken out of cash flow. Shares 1,263M. Risks: two customers are ~40% of sales, Nvidia's own networking, white-box switches. Growth Screen pick (Information Technology). 10.5% required return, 30% safety margin."),
 "WSM": dict(name="Williams-Sonoma Inc.", price=261.94, shares=0.1178, rev=8.005, fcf=1.343, sbc=0.121,
              net_cash=-0.499, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.02,g10=0.02,m=0.1), base=dict(g1=0.045,g10=0.035,m=0.13), bull=dict(g1=0.065,g10=0.045,m=0.15)),
              notes="TTM to Jul-2026 (FY26 Q2). Pottery Barn, West Elm, Williams Sonoma and Rejuvenation: about 70% of sales online, own design and sourcing. Sales fell from $8.7B (2022) to $7.7B and are growing again (+6.7% last quarter); analysts expect ~6% this year and ~5% next. FCF after stock pay 15.3% of sales TTM (7-18% in fiscal 2022-2025). Net debt $0.5B: store leases $1.53B counted as debt (as for ROST), cash $1.03B, no borrowings. Shares 117.8M. Risks: tariffs on imported furniture, housing market. Growth Screen pick (Consumer Discretionary). 9.5% required return, 30% safety margin."),
 "LRN": dict(name="Stride Inc.", price=77.105, shares=0.044, rev=2.537, fcf=0.423, sbc=0.04,
              net_cash=0.1701, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.03,g10=0.02,m=0.1), base=dict(g1=0.03,g10=0.035,m=0.13), bull=dict(g1=0.07,g10=0.045,m=0.16)),
              notes="TTM to Sep-2026 (FY27 Q1). Runs online public schools (K12) and career-learning programmes for US states and charter boards, paid per enrolled student. Revenue grew 10-18% a year to fiscal 2025, then stalled (+3% last quarter) after enrolment limits and platform problems in 2025; analysts expect ~2% this fiscal year and ~5% next. FCF after stock pay 15.1% of sales TTM (6-14% in fiscal 2023-2026); stock pay uses the last fiscal year's $40M (Yahoo's TTM figure of $23M looks incomplete). Net cash $0.17B (cash $0.79B; $0.42B convertible notes and $0.20B leases counted as debt). Shares 44.0M (ESTIMATE: 41.5M basic plus dilution from the notes). Interest earned on cash is not in Yahoo's data and is estimated at 4% of cash. Russell 2000 small cap. 12% required return, 35% safety margin."),
 "MCRI": dict(name="Monarch Casino & Resort Inc.", price=110.25, shares=0.018, rev=0.565, fcf=0.143, sbc=0.009,
              net_cash=0.1248, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.19), base=dict(g1=0.03,g10=0.03,m=0.22), bull=dict(g1=0.05,g10=0.035,m=0.24)),
              notes="TTM to Sep-2026. Two casino resorts it owns outright: Atlantis in Reno, Nevada and Monarch Black Hawk near Denver, Colorado (rebuilt and expanded by 2021, now the market leader there). Sales grow ~4% a year; analysts expect ~4% this year and ~2% next. FCF after stock pay 23.7% of sales TTM (16-23% in 2022-2025). Net cash $0.12B, no borrowings; buys back shares and pays a small dividend. Shares 18.0M (ESTIMATE incl. options; 17.6M basic). Russell 2000 small cap. 11% required return, 35% safety margin."),
 "CARG": dict(name="CarGurus Inc.", price=34.635, shares=0.09, rev=0.962, fcf=0.301, sbc=0.052,
              net_cash=-0.0174, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.04,g10=0.025,m=0.19), base=dict(g1=0.08,g10=0.045,m=0.24), bull=dict(g1=0.11,g10=0.055,m=0.27)),
              notes="TTM to Sep-2026. Most-visited US car-shopping site; dealers pay monthly subscriptions for listings and leads (also Canada and the UK). The wholesale business (CarOffer) was wound down, so revenue fell from $1.66B in 2022 while the marketplace kept growing ~12% a year; that distorts the history, so scenarios are hand-written. Analysts expect ~8% growth this year and next. FCF after stock pay 25.9% of sales TTM (3-13% in 2022-2024, when CarOffer lost money). Net income is below pre-tax profit less tax because of the wind-down. Net debt $0.02B (leases $0.18B, cash $0.16B, no borrowings); buys back ~8% of shares a year. Shares 90.0M (ESTIMATE: Class A plus Class B, with dilution). Russell 2000 small cap. 11.5% required return, 35% safety margin."),
 "USLM": dict(name="United States Lime & Minerals Inc.", price=114.28, shares=0.02878, rev=0.381, fcf=0.0987, sbc=0.0073,
              net_cash=0.4349, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.2), base=dict(g1=0.06,g10=0.04,m=0.25), bull=dict(g1=0.1,g10=0.05,m=0.29)),
              notes="TTM to Sep-2026 (FY2025 + 9 months 2026 - 9 months 2025). Lime and limestone quarries and kilns in Texas, Oklahoma, Arkansas, Colorado and Louisiana for construction, steel, power-plant scrubbers, roofing and oilfield use; lime is too heavy to ship far, so each plant has a local market. Revenue grew ~16% a year in 2022-2025, mostly from price rises, and has slowed: Q3 2026 +4.1% to $106.2M (prices +2.5%, volumes +1.6%: more steel, less construction), 9 months +2.9%; Q3 gross margin fell to 47.8% from 51.2% (9-month gross profit flat). Only one analyst on Yahoo and no company guidance, so scenarios are hand-written (base 6% fading to 4%). The new Texas kiln (~$65M, $61M spent) began producing in Q3, final commissioning in Q4. FCF TTM = operating cash flow $168.9M - capex $70.1M = $98.7M; after stock pay ($7.3M) 24.0% of sales (15-30% in 2022-2025); base 25%. Net cash $0.43B = cash $0.44B - leases $0.004B, no debt; interest earned on it (in other income, $10.4M in 9 months) is estimated at 4% of cash. Tax rate 20% (ESTIMATE). Diluted shares 28.8M. Russell 2000 small cap. 11% required return, 35% safety margin."),
 "EPAC": dict(name="Enerpac Tool Group Corp.", price=39.66, shares=0.052, rev=0.652, fcf=0.12, sbc=0.012,
              net_cash=-0.0463, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.13), base=dict(g1=0.05,g10=0.035,m=0.165), bull=dict(g1=0.08,g10=0.045,m=0.19)),
              notes="TTM to Aug-2026 (fiscal year 2026). High-pressure hydraulic tools: cylinders, pumps, torque wrenches and heavy-lifting systems for industrial maintenance, energy, infrastructure and mining, sold under the Enerpac brand through distributors. Revenue +6% in fiscal 2026. On 28 October 2026 it bought SFE Group for $472M ($452M cash, of which $312M borrowed); analysts' +28% revenue forecast for this year includes it. SFE's profit is not in the data yet, so scenarios are hand-written for Enerpac alone (base 5% growth fading to 3.5%) and the deal is treated as worth what was paid: the balance sheet is the one before the purchase (ESTIMATE; update when the first quarter with SFE is reported). FCF after stock pay 16.6% of sales (10-13% in fiscal 2023-2025, rising after a cost programme). Net debt $0.05B before the deal (debt and leases $0.22B, cash $0.17B). Shares 52.0M (ESTIMATE incl. dilution; 51.2M basic). Russell 2000 small cap. 11% required return, 35% safety margin."),

 # ---- Insurance brokers and claims services (Nov 2026): fee businesses, so the normal free-cash-flow model. Underwriters are in INSURERS below.
 "MRSH": dict(name="Marsh & McLennan Companies Inc. (Marsh)", price=204.82, shares=0.48, rev=28.459, fcf=4.154, sbc=0.418,
              net_cash=-20.49, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.03,g10=0.03,m=0.14), base=dict(g1=0.055,g10=0.04,m=0.165), bull=dict(g1=0.07,g10=0.045,m=0.185)),
              notes="TTM to Sep-2026 (ticker MRSH since the 2026 rename). The largest insurance broker (Marsh, Guy Carpenter) plus consulting (Mercer, Oliver Wyman). A broker earns commissions and fees and carries no underwriting risk, so it is valued like any fee business on free cash flow, not with the insurer (book value and ROE) model. Fiduciary cash held for clients and insurers is not counted. Analysts expect ~6.5% revenue growth this year (~4% organic plus the McGriff acquisition) and ~5% next. FCF after stock pay 13% of sales TTM (the March 2026 quarter was negative: bonuses and integration costs) and 15-17% in 2023-2025, so the base is 16.5%. Net debt $20.5B after the McGriff purchase (debt $22.3B, cash $1.8B). Diluted shares ~480M (ESTIMATE). Risks: softer insurance prices slow commission growth, lower interest on fiduciary funds, consulting demand. Growth Screen insurance top-5 pick: 8.5% required return, 25% safety margin."),
 "WTW": dict(name="Willis Towers Watson plc (WTW)", price=328.86, shares=0.0935, rev=10.274, fcf=1.743, sbc=0.228,
              net_cash=-5.12, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.025,g10=0.03,m=0.13), base=dict(g1=0.055,g10=0.04,m=0.165), bull=dict(g1=0.07,g10=0.045,m=0.19)),
              notes="TTM to Sep-2026. Insurance broker (Risk & Broking) and benefits, pension and HR consulting (Health, Wealth & Career). A fee business with no underwriting risk, so it is valued on free cash flow; fiduciary cash is not counted. Analysts expect ~8% revenue growth this year and ~5.5% next. FCF after stock pay 14.7% of sales TTM, up from 6-13% in 2022-2024 as the transformation programme ended; management targets about 1 point of FCF margin a year, so the base is 16.5%. 2024 net income was negative from the sale of the TRANZACT business (a write-down; cash flow was not hit). Net debt $5.1B. Diluted shares ~93.5M (ESTIMATE). Risks: softer insurance prices, pension-consulting demand, the Gallagher and Aon combinations taking share. Growth Screen insurance top-5 pick: 8.5% required return, 25% safety margin."),
 "CRVL": dict(name="CorVel Corp.", price=82.23, shares=0.0507, rev=1.0112, fcf=0.1279, sbc=0.0052,
              net_cash=0.2369, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.095), base=dict(g1=0.08,g10=0.045,m=0.115), bull=dict(g1=0.1,g10=0.05,m=0.13)),
              notes="TTM to Sep-2026 (fiscal Q2 FY27). Claims administration and managed care for workers' compensation, auto and health plans (bill review, case management, pharmacy networks), paid by employers and insurers as fees: it takes no insurance risk (Yahoo files it under insurance brokers), so it is valued on free cash flow. Revenue $1.01B TTM; the September quarter grew 11.5% (patient management +11%, network solutions +12%) and the first half 11%, after 7% in the fiscal year to March 2026; gross margin 27.1% vs 24.3% a year earlier. New wins in workers' compensation and liability, and CERIS (health-plan payment integrity) added another top-10 national health plan. No guidance and no analyst estimates on Yahoo, so the base stays at 8% fading to 4.5% (recent growth 7-13% a year). FCF = operating cash flow $0.165B minus capex $0.037B (mostly its software) = $0.128B; after stock pay 12.1% of sales TTM, 7-12% in recent years, base 11.5%. Net cash $0.24B = cash $0.27B less $0.03B of leases, no borrowings; bought back $41M of shares in six months (~1% a year). Diluted shares 50.7M (September quarter). Tax rate ~25%. Risks: workers' compensation claim volumes fall with employment, health-plan contracts, a P/E of ~34 that leaves little room. Russell 2000 small cap (passes all 5 checks under the Insurance filter): 9.5% required return, 35% safety margin."),
}

# ---------------------------------------------------------------- scenarios: rules by default, hand overrides with a reason
# From November 2026 each stock's bear / base / bull growth and margin come from fixed rules (scripts/scenario_rules.py ->
# data/scenarios_rule.json: analysts' growth inside S&P 500 base rates, margins from the company's own history). The
# hand-written scenarios above are used only for stocks listed in data/scenario_overrides.json, each with a written
# reason. s["scen"] is what the model uses, s["scen_hand"] the hand-written set, s["scen_source"] = "rule" or "override".
_RULE = _ROOT / "data/scenarios_rule.json"
RULE_SCEN = json.load(open(_RULE))["stocks"] if _RULE.exists() else {}
OVERRIDES = json.load(open(_ROOT / "data/scenario_overrides.json"))["stocks"]
for _t, _s in STOCKS.items():
    _s["scen_hand"] = _s["scen"]
    if _t in OVERRIDES: _s["scen_source"] = "override"
    elif _t in RULE_SCEN: _s["scen"] = RULE_SCEN[_t]["scen"]; _s["scen_source"] = "rule"
    elif __name__ == "scenario_rules": _s["scen_source"] = "hand"          # the rules script itself: builds the file
    else: raise SystemExit(f"{_t}: no rule-based scenarios (run scripts/scenario_rules.py) and no entry in data/scenario_overrides.json")

# ---------------------------------------------------------------- capital structure (for WACC)
# Gross debt and after-tax cost of debt make the DCF consistent: free cash flow BEFORE interest (FCFF) is discounted at
# WACC, then net debt is subtracted. Source: yfinance annual statements via the screener run of 2026-10-23.
# debt = total debt incl. leases ($B); rd = interest expense / average debt (clipped to 2-10% when used); tax = effective rate.
FIN = {
 "AAPL": dict(debt=80.111, interest=3.933, rd=0.0491, tax=0.17), "MSFT": dict(debt=133.1, interest=3.223, rd=0.0242, tax=0.197),
 "GOOGL": dict(debt=141.917, interest=3.868, rd=0.0273, tax=0.181), "AMZN": dict(debt=300.35, interest=6.764, rd=0.0225, tax=0.223),
 "NVDA": dict(debt=38.86, interest=0.259, rd=0.0246, tax=0.151), "AVGO": dict(debt=59.42, interest=3.210, rd=0.0484, tax=0.256),
 "LLY": dict(debt=49.503, interest=1.3, rd=0.0263, tax=0.207), "ADBE": dict(debt=6.79, interest=0.263, rd=0.0414, tax=0.180),
 "APP": dict(debt=3.516, interest=0.205, rd=0.0583, tax=0.155), "FICO": dict(debt=5.278, interest=0.2233, rd=0.0423, tax=0.241),
 "APA": dict(debt=3.321, interest=0.259, rd=0.078, tax=0.35), "DECK": dict(debt=0.54, interest=0.0047, rd=0.0087, tax=0.228),
 "INCY": dict(debt=0.032, interest=0.0024, rd=0.0757, tax=0.21), "MKC": dict(debt=5.02, interest=0.196, rd=0.0452, tax=0.214),
 "EXPE": dict(debt=5.686, interest=0.356, rd=0.0626, tax=0.19),
 "BKNG": dict(debt=20.804, interest=1.113, rd=0.0535, tax=0.21),
 "INTU": dict(debt=8.421, interest=0.256, rd=0.0304, tax=0.24),
 "ADSK": dict(debt=3.705, interest=0.13, rd=0.0351, tax=0.22),
 "TPR": dict(debt=4.229, interest=0.055, rd=0.013, tax=0.18),
 "VEEV": dict(debt=0.152, interest=0.0, rd=0.0500, tax=0.23),
 "MNST": dict(debt=0.093, interest=0.0, rd=0.05, tax=0.242),
 "ALLE": dict(debt=2.224, interest=0.098, rd=0.0441, tax=0.188),
 "FTNT": dict(debt=0.497, interest=0.015, rd=0.0298, tax=0.18),
 "RMD": dict(debt=0.611, interest=0.022, rd=0.036, tax=0.21),
 "V": dict(debt=22.071, interest=0.758, rd=0.0343, tax=0.163),
 "FIX": dict(debt=0.374, interest=0.0059, rd=0.0157, tax=0.224),
 "MA": dict(debt=23.938, interest=1.0, rd=0.0418, tax=0.196),
 "CTAS": dict(debt=2.706, interest=0.106, rd=0.0392, tax=0.2),
 "DXCM": dict(debt=1.393, interest=0.013, rd=0.0093, tax=0.215),
 "IDXX": dict(debt=0.973, interest=0.0316, rd=0.0325, tax=0.2),
 "VRSN": dict(debt=1.792, interest=0.078, rd=0.0435, tax=0.236),
 "NDAQ": dict(debt=9.216, interest=0.335, rd=0.0363, tax=0.2),
 "MCO": dict(debt=7.492, interest=0.258, rd=0.0344, tax=0.22),
 "SPGI": dict(debt=13.465, interest=0.322, rd=0.0239, tax=0.227),
 "NFLX": dict(debt=15.132, interest=0.857, rd=0.0566, tax=0.166),
 "CBOE": dict(debt=1.552, interest=0.0529, rd=0.034, tax=0.285),
 "GRMN": dict(debt=0.173, interest=0.0, rd=0.05, tax=0.166),
 "FDS": dict(debt=1.542, interest=0.055, rd=0.0357, tax=0.179),
 "CRM": dict(debt=41.743, interest=1.5, rd=0.0359, tax=0.222),
 "HWM": dict(debt=4.606, interest=0.192, rd=0.0417, tax=0.19),
 "ADP": dict(debt=5.472, interest=0.472, rd=0.0863, tax=0.23),
 "AME": dict(debt=6.966, interest=0.275, rd=0.0395, tax=0.182),
 "AXP": dict(debt=0.0, interest=0.0, rd=0.0500, tax=0.225),
 "SHOP": dict(debt=0.188, interest=0.0, rd=0.05, tax=0.18),
 "PYPL": dict(debt=13.472, interest=0.486, rd=0.0361, tax=0.17),
 "XYZ": dict(debt=7.535, interest=0.211, rd=0.028, tax=0.21),
 "ADYEY": dict(debt=0.409, interest=0.0, rd=0.0500, tax=0.23),
 "FISV": dict(debt=27.823, interest=1.425, rd=0.0512, tax=0.17),
 "CRCL": dict(debt=0.0, interest=0.0, rd=0.05, tax=0.21),
 "SPG": dict(debt=29.149, interest=1.117, rd=0.0383, tax=0.02),
 "META": dict(debt=114.84, interest=2.78, rd=0.0242, tax=0.15),
 "TT": dict(debt=4.22, interest=0.22, rd=0.0521, tax=0.18),
 "RL": dict(debt=2.982, interest=0.053, rd=0.0178, tax=0.215),
 "ROST": dict(debt=4.74, interest=0.03, rd=0.0063, tax=0.24),
 "GDDY": dict(debt=3.88, interest=0.15, rd=0.0387, tax=0.22),
 "FAST": dict(debt=0.45, interest=0.005, rd=0.0111, tax=0.24),
 "SYK": dict(debt=14.93, interest=0.586, rd=0.0393, tax=0.2),
 "CMG": dict(debt=5.6, interest=0.0, rd=0.0500, tax=0.25),
 "KLAC": dict(debt=5.99, interest=0.28, rd=0.0467, tax=0.14),
 "CME": dict(debt=3.42, interest=0.17, rd=0.0497, tax=0.235),
 "STE": dict(debt=2.05, interest=0.0569, rd=0.0278, tax=0.26),
 "WDAY": dict(debt=3.77, interest=0.11, rd=0.0292, tax=0.2),
 "BR": dict(debt=3.604, interest=0.12, rd=0.0333, tax=0.22),
 "MSI": dict(debt=10.665, interest=0.425, rd=0.0398, tax=0.21),
 "BKR": dict(debt=18.26, interest=0.39, rd=0.0214, tax=0.25),
 "RSG": dict(debt=14.27, interest=0.605, rd=0.0424, tax=0.24),
 "WAB": dict(debt=6.38, interest=0.3, rd=0.0470, tax=0.25),
 "MRVL": dict(debt=5.29, interest=0.44, rd=0.0832, tax=0.14),
 "LULU": dict(debt=2.14, interest=0.0, rd=0.0500, tax=0.29),
 "RDDT": dict(debt=0.03, interest=0.0, rd=0.0500, tax=0.15),
 "CF": dict(debt=3.656, interest=0.167, rd=0.0457, tax=0.2),
 "EME": dict(debt=0.56, interest=0.01, rd=0.0179, tax=0.26),
 "HST": dict(debt=5.645, interest=0.236, rd=0.0418, tax=0.05),
 "LII": dict(debt=2.08, interest=0.07, rd=0.0337, tax=0.21),
 "NEM": dict(debt=5.58, interest=0.14, rd=0.0251, tax=0.35),
 "REGN": dict(debt=2.707, interest=0.0467, rd=0.0173, tax=0.16),
 "ZTS": dict(debt=9.237, interest=0.242, rd=0.0262, tax=0.2),
 "MO": dict(debt=24.06, interest=1.19, rd=0.0495, tax=0.24),
 "HAS": dict(debt=3.55, interest=0.17, rd=0.0479, tax=0.21),
 "BMY": dict(debt=44.81, interest=1.65, rd=0.0368, tax=0.18),
 "NRG": dict(debt=23.13, interest=1.135, rd=0.0491, tax=0.24),
 "FIS": dict(debt=20.85, interest=0.684, rd=0.0328, tax=0.22),
 "PG": dict(debt=38.93, interest=0.902, rd=0.0249, tax=0.208), "KO": dict(debt=41.62, interest=1.529, rd=0.0367, tax=0.179),
 "SHW": dict(debt=14.8, interest=0.538, rd=0.0374, tax=0.231),
 "VLTO": dict(debt=2.92, interest=0.096, rd=0.033, tax=0.20), "AMP": dict(debt=0.0, interest=0.0, rd=0.0500, tax=0.215),
 "PPG": dict(debt=7.463, interest=0.257, rd=0.035, tax=0.233), "EOG": dict(debt=8.262, interest=0.266, rd=0.0322, tax=0.222),
 "PM": dict(debt=47.562, interest=1.518, rd=0.032, tax=0.21), "DLTR": dict(debt=7.671, interest=0.074, rd=0.026, tax=0.246), "JNJ": dict(debt=44.65, interest=0.984, rd=0.023, tax=0.177),
 "AMGN": dict(debt=54.01, interest=2.636, rd=0.048, tax=0.141),
 "INVA": dict(debt=0.2699, interest=0.0197, rd=0.065, tax=0.14),
 "CTRE": dict(debt=2.025, interest=0.0557, rd=0.0472, tax=0.02),
 "CVSA": dict(debt=0.7536, interest=0.0388, rd=0.065, tax=0.22),
 "QLYS": dict(debt=0.051, interest=0.0, rd=0.05, tax=0.21),
 "LAUR": dict(debt=0.7826, interest=0.0147, rd=0.03, tax=0.22),
 "IDCC": dict(debt=0.3184, interest=0.0371, rd=0.05, tax=0.16),
 "LMAT": dict(debt=0.1889, interest=0.0052, rd=0.025, tax=0.23),
 "BOX": dict(debt=0.5254, interest=0.0101, rd=0.02, tax=0.21),
 "ACIW": dict(debt=0.8351, interest=0.0505, rd=0.0605, tax=0.22),
 "MRSH": dict(debt=22.332, interest=0.973, rd=0.044, tax=0.233),
 "WTW": dict(debt=7.098, interest=0.301, rd=0.043, tax=0.2),
 "CRVL": dict(debt=0.0331, interest=0.0, rd=0.05, tax=0.246), "CPRT": dict(debt=0.0884, interest=0.0, rd=0.05, tax=0.193),
 "AOS": dict(debt=0.7148, interest=0.025, rd=0.045, tax=0.227),
 "TPL": dict(debt=0.0152, interest=0.0, rd=0.05, tax=0.206),
 "VICI": dict(debt=17.8257, interest=0.845, rd=0.05, tax=0.01),
 "LIN": dict(debt=26.702, interest=0.467, rd=0.03, tax=0.232),
 "CL": dict(debt=7.716, interest=0.25, rd=0.035, tax=0.24),
 "ALGN": dict(debt=0.1465, interest=0.0, rd=0.05, tax=0.24),
 "ANET": dict(debt=0.0, interest=0.0, rd=0.05, tax=0.185),
 "WSM": dict(debt=1.5279, interest=0.0, rd=0.05, tax=0.251),
 "LRN": dict(debt=0.619, interest=0.012, rd=0.03, tax=0.24),
 "MCRI": dict(debt=0.0126, interest=0.0, rd=0.05, tax=0.218),
 "CARG": dict(debt=0.1823, interest=0.0, rd=0.05, tax=0.235),
 "USLM": dict(debt=0.0043, interest=0.0, rd=0.05, tax=0.2),
 "EPAC": dict(debt=0.221, interest=0.009, rd=0.05, tax=0.24),
}

# DCF_METHOD: "equity" = original (FCF after interest at the required return, minus net debt; double-counts debt cost)
#             "fcff_re" = FCF before interest at the required return (hurdle for the whole business), minus net debt
#             "fcff_wacc" = textbook: FCF before interest at WACC, minus net debt (rewards leverage unless the equity rate is re-levered)
DCF_METHOD = "fcff_re"

def wacc_of(t, s, re):
    """Blended cost of capital: market-value equity at the required return + debt at the after-tax cost of debt."""
    f = FIN[t]
    E, D = s["price"] * s["shares"], f["debt"]
    rd = min(max(f["rd"], 0.02), 0.10)
    return (E * re + D * rd * (1 - f["tax"])) / (E + D)

# Cash-flow separation (from November 2026, data/cash_separation.json): value only the cash the business itself produces
# and pays for, and handle financing once, outside the cash flows (the 'isolate the project's cash flows' rule).
#   interest income  cash and securities are added to equity value at the end, so the after-tax interest they earn is
#                    taken out of free cash flow (it was counted twice); kept as a constant share of revenue, like the
#                    interest added back
#   acquisitions     free cash flow (operating cash flow - capex) leaves out money spent buying businesses, while the
#                    growth forecast includes what those purchases add. Recurring acquisition spend (median of 4 years,
#                    so one-off mega deals drop out) is charged as reinvestment in proportion to growth above 2.5%:
#                    full at the base year-1 growth rate, less as growth fades, none at the terminal rate (whose
#                    reinvestment the value-driver factor already charges) or when growth is at or below 2.5%
#   lenders          (AXP, AMP: valued on net income) a growing lender must keep part of its profit as equity to back
#                    new loans, so cash to shareholders = net income x (1 - growth / ROE); after the advantage period
#                    new equity earns the moat class's terminal return (ROE, halfway to the required return, or it)
#   debt tax saving  interest is deductible, so debt saves tax that the business's own (before-interest) cash flow does
#                    not contain: added as tax rate x debt (permanent debt), the debt implied by interest / cost of debt
SEP = json.load(open(_ROOT / "data/cash_separation.json"))
LENDERS = {"AXP", "AMP"}
def stock_setup(tk, s):
    """Starting margin, scenario margins, net cash and extra dcf() arguments for one stock, with the cash-flow
    separation applied. Shared by the main loop and scripts/durability.py, duration.py and framework.py."""
    f = FIN[tk]; e = SEP["stocks"].get(tk, {})
    aint = 0.0 if DCF_METHOD == "equity" else f["interest"] * (1 - f["tax"])     # after-tax interest added back: FCF -> FCFF
    iinc = e.get("interest_income_used", 0.0) * (1 - f["tax"])                  # after-tax interest earned on cash
    add = (aint - iinc) / s["rev"]                                               # constant share of revenue in every year
    m0 = (s["fcf"] - s["sbc"] + aint - iinc) / s["rev"]                          # starting FCFF margin (after SBC)
    rd = min(max(f["rd"], 0.02), 0.10)
    shield = 0.0 if DCF_METHOD == "equity" else f["tax"] * min(f["interest"] / rd, f["debt"])
    nc = s["net_cash"] + s["extra"] + shield
    S2 = {k: dict(v, m=v["m"] + add) for k, v in s["scen"].items()}              # scenario margins stated to equity, + interest share
    a = e.get("acq", 0.0) / s["rev"]
    kw = dict(acq=(a, max(s["scen"]["base"]["g1"], GT)) if a > 0 else None, roe=e.get("roe") if tk in LENDERS else None)
    return dict(aint=aint, iinc=iinc, add=add, m0=m0, nc=nc, shield=shield, S2=S2, acq_share=a, kw=kw)

def acq_charge(acq, g, gt=GT):
    """Acquisition spend as a share of revenue at growth g (acq = (share at the reference growth, reference growth)):
    in proportion to growth above the terminal rate, so none once growth has faded to 2.5% (the terminal value already
    charges the reinvestment that growth needs through the value-driver factor)."""
    if not acq or acq[1] <= gt: return 0.0
    return acq[0] * min(1.0, max(g - gt, 0.0) / (acq[1] - gt))

def lender_k(mo, r, roe, g_last, gt=GT):
    """Terminal factor for a lender: last year keeps 1 - g_last/ROE of net income, the terminal value 1 - gt/ROE_new."""
    rt = (mo or {}).get("ronic_terminal"); rq = (mo or {}).get("r_req", r)
    rn = rq if rt == "r" else (roe + rq) / 2 if rt == "mid" else roe
    return (1 - gt / rn) / (1 - g_last / roe)

# Competitive Advantage Period (stage 2 of the Durand/CAP review, from November 2026): each stock's moat class
# (data/moat.json) sets how many years growth takes to fade to the 2.5% terminal rate (years 1-10 as before, g1 -> g10,
# then g10 -> 2.5% by the last year) and the return on new investment after that (value-driver terminal value).
MOAT = json.load(open(_ROOT / "data/moat.json"))
def moat_of(t):
    if t not in MOAT["stocks"]: raise SystemExit(f"Add {t} to data/moat.json (with a reason)")
    c = MOAT["stocks"][t]["moat"]
    return dict(MOAT["classes"][c], cls=c)

def tv_factor(mo, r, g_last, gt=GT):
    """Terminal cash flow vs the last year's, from the value-driver formula FCF = NOPAT x (1 - g / RONIC): the last
    explicit year reinvests for g_last at ronic_forecast, the terminal value reinvests for gt at ronic_terminal
    ('r' = the discount rate: growth adds nothing; 'mid' = halfway between ronic_forecast and r). 1 = unchanged."""
    if not mo or mo.get("ronic_forecast") is None: return 1.0
    rf = mo["ronic_forecast"]; rt = mo["ronic_terminal"]; rq = mo.get("r_req", r)   # 'r' = the stock's required return
    rt = rq if rt == "r" else (rf + rq) / 2 if rt == "mid" else rt
    return (1 - gt / rt) / (1 - min(g_last, 0.9 * rf) / rf)

# Growth engines (stage 3): a few companies' revenue is split into reported segments (data/segments.json), each with
# its own growth path. Year-1 growth across segments still adds up to the scenario g1; all fade to g10 by year 10.
SEGS = json.load(open(_ROOT / "data/segments.json"))
def segments_of(t):
    e = SEGS["stocks"].get(t)
    if not e: return None
    now = {k: v[0] for k, v in e["segments"].items()}; tot = sum(now.values())
    rt = tot / sum(v[1] for v in e["segments"].values()) - 1
    out = dict(names=list(now), share=[now[k] / tot for k in now],
               ratio=[(v[0] / v[1] - 1) / rt for v in e["segments"].values()], cap=SEGS["cap_multiple"], reported=rt)
    en = e.get("engines")
    if en:                       # per-engine valuation (stage 4): own cash margin and own advantage period per engine
        x = [float((en.get(k) or {}).get("margin_x", 1.0)) for k in out["names"]]
        nx = sum(w * v for w, v in zip(out["share"], x))
        out["engines"] = dict(x=[v / nx for v in x], moat=[(en.get(k) or {}).get("moat") for k in out["names"]],
                              why={k: (en.get(k) or {}).get("why", "") for k in out["names"]})
    return out

def seg_g1s(g1, sg):
    """Segment year-1 growth: company g1 x (segment growth / company growth), capped at cap x g1, then shifted so the
    revenue-weighted average is exactly g1."""
    if g1 <= 0: return [g1] * len(sg["share"])
    x = [min(g1 * q, sg["cap"] * g1) for q in sg["ratio"]]
    d = g1 - sum(w * v for w, v in zip(sg["share"], x))
    return [v + d for v in x]

# Per-engine valuation (stage 4, from November 2026; data/segments.json "engines"). Each engine keeps its year-1 growth
# from seg_g1s and fades to the scenario g10 by year 10 as before, but then fades to 2.5% over ITS OWN advantage period
# (the engine's moat class, default the company's) and earns its own share of the cash margin: engine margin = company
# margin path x margin_x, with margin_x scaled so today's revenue-weighted margin is unchanged (so the company margin
# moves only as the mix shifts). After an engine's advantage period ends its growth is 2.5% and its cash flow carries
# its class's value-driver factor (tv_factor), exactly what the single-engine model applies to the terminal value.
# fail=(engine index, year): that engine's growth drops to 2.5% after `year` and from then on new investment earns only
# the required return (the 'Growth fails' stress test, scripts/duration.py). With one engine and no fail this equals dcf().
ENG_RANK = {"wide": 3, "narrow": 2, "none": 1}
def eng_mo(c, mo):
    """An engine's class settings. In the duration.py stress tests (mo["stress"]: one class lower, edge ends at year 10)
    no engine outlasts the stressed company class."""
    mc = (mo or {}).get("cls")
    if c is None or c == mc or ((mo or {}).get("stress") and ENG_RANK.get(c, 0) > ENG_RANK.get(mc, 0)): return mo or {}
    return dict(MOAT["classes"][c], cls=c, r_req=(mo or {}).get("r_req"))

def dcf_eng(rev0, m0, g1, g10, m_target, r, net_cash_plus, shares, gt=GT, ramp=5, detail=False, mo=None, sg=None, fail=None, acq=None, roe=None):
    E = (sg or {}).get("engines")
    if sg:
        W, G1 = sg["share"], seg_g1s(g1, sg)
        X = E["x"] if E else [1.0] * len(W)
        MO = [eng_mo(c, mo) for c in E["moat"]] if E else [mo or {}] * len(W)
    else:
        W, G1, X, MO = [1.0], [g1], [1.0], [mo or {}]
    caps = [m_.get("cap_years", 10) for m_ in MO]
    n = max(caps + [(mo or {}).get("cap_years", 10)])
    def path(i, t):
        if fail and fail[0] == i and t > fail[1]: return gt
        c, a = caps[i], G1[i]
        if t <= 10: return a + (g10 - a) * (t - 1) / 9
        return g10 + (gt - g10) * (t - 10) / (c - 10) if t <= c else gt
    def kfail(i):              # same cash margin, but the 2.5% growth now earns only the required return (as 'end10')
        rf = MO[i].get("ronic_forecast") or 0.20
        return (1 - gt / r) / (1 - gt / rf)
    rn = None
    if roe:                    # lender: retained equity instead of the value-driver factors (see stock_setup)
        rt_ = (mo or {}).get("ronic_terminal"); rq_ = (mo or {}).get("r_req", r)
        rn = rq_ if rt_ == "r" else (roe + rq_) / 2 if rt_ == "mid" else roe
        def R(i, t): return r if (fail and fail[0] == i and t > fail[1]) else rn if t > caps[i] else roe
    revs, pv, rows, k_on = [rev0 * w for w in W], 0.0, [], [None] * len(W)
    f_last = [0.0] * len(W)
    for t in range(1, n + 1):
        mt = m0 + (m_target - m0) * min(t, ramp) / ramp
        g_all, fcf = 0.0, 0.0
        rev_prev = sum(revs)
        for i in range(len(W)):
            revs[i] *= 1 + path(i, t)
            if roe: k_on[i] = 1 - path(i, t) / R(i, t)
            elif fail and fail[0] == i and t > fail[1] and k_on[i] is None: k_on[i] = kfail(i)
            elif t > caps[i] and k_on[i] is None: k_on[i] = tv_factor(MO[i], r, path(i, caps[i]), gt)
            f_last[i] = revs[i] * mt * X[i] * (k_on[i] if k_on[i] is not None else 1.0)
            fcf += f_last[i]
        rev = sum(revs); g = rev / rev_prev - 1
        ac = acq_charge(acq, g, gt) * rev; fcf -= ac          # acquisition spend (company level)
        df = 1 / (1 + r) ** t
        pv += fcf * df
        rows.append(dict(t=t, g=g, rev=rev, m=fcf / rev, fcf=fcf, df=df, pv=fcf * df, **({"seg": [round(v, 3) for v in revs]} if sg else {})))
    # terminal: engines still inside their advantage period at year n get their class's factor now
    if roe: term = sum(revs[i] * mt * X[i] * (1 - gt / R(i, n + 1)) for i in range(len(W)))
    else: term = sum(f_last[i] * (tv_factor(MO[i], r, path(i, n), gt) if k_on[i] is None else 1.0) for i in range(len(W)))
    term -= acq_charge(acq, gt, gt) * rows[-1]["rev"]
    k = term / rows[-1]["fcf"] if rows[-1]["fcf"] else 1.0
    tv = term * (1 + gt) / (r - gt)
    pv_tv = tv * rows[-1]["df"]
    ev = pv + pv_tv; eq = ev + net_cash_plus; ps = eq / shares
    if detail:
        return dict(rows=rows, pv_fcf=pv, tv=tv, pv_tv=pv_tv, ev=ev, equity=eq, per_share=ps, tv_share=pv_tv / ev, tv_factor=k)
    return ps

def dcf(rev0, m0, g1, g10, m_target, r, net_cash_plus, shares, gt=GT, ramp=5, detail=False, mo=None, sg=None, fail=None, acq=None, roe=None):
    if fail is not None or (sg and sg.get("engines")):
        return dcf_eng(rev0, m0, g1, g10, m_target, r, net_cash_plus, shares, gt, ramp, detail, mo, sg, fail, acq, roe)
    n = (mo or {}).get("cap_years", 10)
    rev, pv, rows = rev0, 0.0, []
    segrev = [rev0 * w for w in sg["share"]] if sg else None
    gs1 = seg_g1s(g1, sg) if sg else None
    path = lambda a, t: a + (g10 - a) * (t - 1) / 9 if t <= 10 else g10 + (gt - g10) * (t - 10) / (n - 10)
    for t in range(1, n + 1):
        if sg:
            segrev = [v * (1 + path(a, t)) for v, a in zip(segrev, gs1)]
            g = sum(segrev) / rev - 1
            rev = sum(segrev)
        else:
            g = path(g1, t)
            rev *= 1 + g
        m = m0 + (m_target - m0) * min(t, ramp) / ramp
        fcf = rev * m * (1 - g / roe if roe else 1.0) - rev * acq_charge(acq, g, gt)   # lenders retain equity; acquisitions
        m = fcf / rev
        df = 1 / (1 + r) ** t
        pv += fcf * df
        rows.append(dict(t=t, g=g, rev=rev, m=m, fcf=fcf, df=df, pv=fcf * df, **({"seg": [round(v, 3) for v in segrev]} if sg else {})))
    gn = rows[-1]["g"]
    if roe or acq:          # terminal cash flow built from the last year's sales and margin before these charges
        ml = m0 + (m_target - m0) * min(n, ramp) / ramp
        base = rows[-1]["rev"] * ml
        kk = lender_k(mo, r, roe, gn, gt) * (1 - gn / roe) if roe else tv_factor(mo, r, path(g1, n), gt)
        term = base * kk - rows[-1]["rev"] * acq_charge(acq, gt, gt)
        k = term / rows[-1]["fcf"] if rows[-1]["fcf"] else 1.0
    else:
        k = tv_factor(mo, r, path(g1, n), gt)    # last-year growth (all segments end on the same path)
    tv = rows[-1]["fcf"] * (1 + gt) * k / (r - gt)
    pv_tv = tv * rows[-1]["df"]
    ev = pv + pv_tv
    eq = ev + net_cash_plus
    ps = eq / shares
    if detail:
        return dict(rows=rows, pv_fcf=pv, tv=tv, pv_tv=pv_tv, ev=ev, equity=eq, per_share=ps, tv_share=pv_tv / ev, tv_factor=k)
    return ps

def solve(f, lo, hi, tol=1e-6):
    flo = f(lo)
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm > 0) == (flo > 0): lo, flo = mid, fm
        else: hi = mid
        if hi - lo < tol: break
    return (lo + hi) / 2

# ----------------------------------------------------------------- diagnostics (do NOT change any fair value)
# Competitive Advantage Period (CAP, Mauboussin): how long a company keeps earning above its required return.
# The valuation itself keeps the fixed 10-year horizon; these numbers only show what the price assumes and
# whether each scenario's growth is paid for by reinvestment.
CAP_MAX = 80          # search limit for the CAP the price implies (years)
RONIC_HIGH = 0.50     # forecast return on new investment above this: growth looks close to free -> check
SNAP_RAW = _ROOT / "data/snapshot_raw.json"
_SNAP = json.load(open(SNAP_RAW))["stocks"] if SNAP_RAW.exists() else {}

def dcf_cap(rev0, m0, g1, m_target, r, net_cash_plus, shares, n, gt=GT, ramp=5, acq=None, roe=None):
    """Same cash-flow model as dcf(), but growth fades in a straight line from g1 to the terminal rate over n years
    (the competitive advantage period), then grows at gt forever."""
    rev, pv, fcf, df = rev0, 0.0, 0.0, 1.0
    for t in range(1, n + 1):
        g = g1 + (gt - g1) * (t - 1) / max(n - 1, 1) if n > 1 else g1
        rev *= 1 + g
        fcf = rev * (m0 + (m_target - m0) * min(t, ramp) / ramp) * (1 - g / roe if roe else 1.0) - rev * acq_charge(acq, g, gt)
        df = 1 / (1 + r) ** t
        pv += fcf * df
    return (pv + fcf * (1 + gt) / (r - gt) * df + net_cash_plus) / shares

def implied_cap(price, rev0, m0, g1, m_target, r, nc, shares, **kw):
    """Years of above-terminal growth (fading to 2.5%) that today's price needs, with the base growth and margin.
    None when base growth is at or below the terminal rate (a longer period would not add value)."""
    if g1 <= GT + 1e-9: return None
    for n in range(1, CAP_MAX + 1):
        if dcf_cap(rev0, m0, g1, m_target, r, nc, shares, n, **kw) >= price:
            return n
    return CAP_MAX + 1          # read as "more than CAP_MAX years"

def nopat_margin(t, tax):
    """After-tax operating margin, latest fiscal year (data/snapshot_raw.json), taxed at the model's rate."""
    inc = (_SNAP.get(t) or {}).get("annual", {}).get("inc") or {}
    rows = [v for _, v in sorted(inc.items()) if v.get("op") is not None and v.get("rev")]
    if not rows: return None
    m = rows[-1]["op"] / rows[-1]["rev"] * (1 - tax)
    return m if m > 0 else None

def growth_check(d, rev0, nm, m_target, r, gt=GT):
    """Return on new investment implied by a scenario. NOPAT = revenue x today's after-tax operating margin (held flat);
    reinvestment = NOPAT - FCFF. Forecast: extra NOPAT in year 10 / total reinvested over years 1-10.
    Terminal: the return on new investment that 2.5% growth with the target margin implies (FCF = NOPAT x (1 - g/RONIC))."""
    if nm is None: return None
    reinv = sum(x["rev"] * nm - x["fcf"] for x in d["rows"])
    gain = (d["rows"][-1]["rev"] - rev0) * nm
    fc = gain / reinv if reinv > 0 else None
    tm = gt / (1 - m_target / nm) if m_target < nm else None
    if gain <= 0: flag, fc = "shrinking", None             # sales lower in year 10: no growth to pay for
    elif reinv <= 0 or m_target >= nm: flag = "free"       # cash flow at or above operating profit while growing
    elif fc is not None and fc < r: flag = "below_hurdle"  # growth earns less than the required return
    elif fc is not None and fc > RONIC_HIGH: flag = "high"
    else: flag = None
    return dict(forecast=fc, terminal=tm, reinvest_share=reinv / sum(x["rev"] * nm for x in d["rows"]), flag=flag)

# ---------------------------------------------------------------- insurers (underwriters): excess return on equity
# An underwriter's free cash flow mixes in premiums it holds for future claims, so the free-cash-flow DCF above doesn't
# fit. Underwriters are valued on book value and return on equity instead (residual income / excess return):
#   each year   net income = ROE x book value at the start of the year; book value grows with the business (g);
#               cash to shareholders = net income - the increase in book value (what is paid out as dividends and
#               buybacks, or could be);
#   value       = those cash flows at the required return + a value after the last year of
#               book value x (terminal ROE - 2.5%) / (required return - 2.5%),
#   which is the same as book value today + the present value of (ROE - required return) x book value each year.
# Scenarios use the same keys as the stocks above: g1 / g10 = book-value growth in year 1 / year 10 (fading to 2.5% over
# the advantage period, at least 11 years), m = long-run ROE (reached from roe0, the starting ROE, over 5 years).
# The moat class sets how long the excess return lasts: wide and short keep the long-run ROE after the last year,
# narrow fades it halfway to the required return, none to the required return (a ROE at or below the required return
# stays where it is). Book value = common equity (preferred stock excluded); 'extra' = other adjustments ($B).
INSURERS = {
 "ALL": dict(name="The Allstate Corp.", price=254.81, shares=0.2474, bv=30.31, roe0=0.21, ni=11.639, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.11), base=dict(g1=0.045,g10=0.035,m=0.15), bull=dict(g1=0.06,g10=0.04,m=0.18)),
              notes="TTM to Sep-2026. Personal auto and home insurance (Allstate, National General, Esurance) plus protection plans. Valued as an insurer on book value and return on equity, not free cash flow. ROE was about 40% TTM after large rate increases, a light catastrophe year and gains from selling the group and voluntary benefits businesses; it was negative in 2022-2023 when claim costs outran prices. 10-year median ROE ~12%. Analysts expect EPS to fall from $44 TTM to ~$28 next year (ROE ~23%), so the starting ROE is 21%, fading to 15% in the base case (11% bear, 18% bull). Book value grows with premiums: 4.5% fading to 3.5%. Common book value $30.3B ($2.0B preferred stock excluded). Risks: catastrophes (wildfires, hurricanes, convective storms), auto claim inflation, state rate regulators. Growth Screen insurance top-5 pick: 9% required return, 30% safety margin."),
 "HIG": dict(name="The Hartford Insurance Group Inc.", price=133.99, shares=0.2735, bv=18.539, roe0=0.18, ni=4.608, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.115), base=dict(g1=0.05,g10=0.035,m=0.15), bull=dict(g1=0.065,g10=0.04,m=0.175)),
              notes="TTM to Sep-2026. Commercial insurance (small business, middle market, specialty), personal lines and group benefits, plus Hartford Funds (asset management). Valued as an insurer on book value and return on equity. ROE rose from ~11% in 2021-2022 to ~22% in 2025 and ~25% TTM on firm commercial prices and a better personal-auto result; the 10-year median is ~12% (2017 included the loss on selling the life business). Analysts expect EPS of ~$13.60 next year (ROE ~20%), so the starting ROE is 18%, fading to 15% in the base case (11.5% bear, 17.5% bull). Book value grows 5% fading to 3.5%. Common book value $18.5B ($0.33B preferred excluded); diluted shares ~273.5M (ESTIMATE). Risks: softer commercial prices, reserve charges on older liability years, catastrophes. Growth Screen insurance top-5 pick: 8.5% required return, 25% safety margin."),
 "AIZ": dict(name="Assurant Inc.", price=317.17, shares=0.0497, bv=5.992, roe0=0.18, ni=1.0731, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.12), base=dict(g1=0.05,g10=0.035,m=0.155), bull=dict(g1=0.065,g10=0.04,m=0.18)),
              notes="TTM to Sep-2026. Two businesses: Global Lifestyle (phone and car protection plans and extended warranties sold through carriers, retailers and car dealers; mostly fee-like) and Global Housing (lender-placed and renters insurance, exposed to hurricanes). Valued as an insurer on book value and return on equity. ROE 14-16% in 2023-2025 and ~18% TTM (net income $1.07B; 18.2% annualised in the September quarter). September quarter: Global Lifestyle adjusted EBITDA +15% to $237M (Connected Living +23% on mobile trade-in and device protection; 7.6M mobile devices serviced vs 4.8M a year earlier), Global Housing adjusted EBITDA ex catastrophes +11% to $288M; catastrophes $20M. Nine-month adjusted EPS $18.47 (+30%). The company raised its 2026 outlook: adjusted EBITDA ex catastrophes up ~10% and adjusted EPS up low double digits; Global Lifestyle EBITDA up mid-to-high teens; buybacks $350M. The starting ROE is 18%, fading to 15.5% in the base case (12% bear, 18% bull): Global Lifestyle's fee-like protection plans earn more on their capital than the housing book. Book value grows 5% fading to 3.5%. Book value $6.0B (down slightly from June on unrealised investment losses in AOCI; $6.9B excluding AOCI) includes ~$3.1B of goodwill and intangibles from acquisitions. Diluted shares 49.7M (September-quarter weighted average). Risks: hurricanes in Global Housing, losing a large carrier or retail partner, lower phone upgrades. Growth Screen insurance top-5 pick: 9% required return, 30% safety margin."),
 "NMIH": dict(name="NMI Holdings Inc.", price=38.87, shares=0.0761, bv=2.703, roe0=0.145, ni=0.3928, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.09), base=dict(g1=0.06,g10=0.03,m=0.135), bull=dict(g1=0.08,g10=0.035,m=0.155)),
              notes="TTM to Sep-2026. US private mortgage insurance (National MI): it pays the lender part of the loss when a borrower with less than 20% down defaults. Valued as an insurer on book value and return on equity. ROE 16-18% in 2022-2025 and ~15% TTM (13.8% annualised in the September quarter: claims rose to $29.1M from $18.6M a year earlier and the default rate to 1.23% from 1.05%) as excess capital builds. Net income $393M TTM; insurance in force $229.7B, up 5%. Analysts expect EPS of ~$5.10-5.30 this year and ~$5.50 next (ROE ~14.5%), so the starting ROE is 14.5%, base 13.5% (9% bear: a housing downturn with falling prices raises claims; 15.5% bull). Book value grows 6% fading to 3% (insurance in force grows with mortgage lending). Book value $2.70B ($36.13 a share, up 11% in a year); PMIERs available assets $3.8B vs $2.2B required. No dividend, buys back ~2-3% of shares a year ($27M in the quarter). Diluted shares 76.1M (Q3 weighted average). Risks: house prices and unemployment (defaults are edging up), Fannie Mae and Freddie Mac capital rules (PMIERs) and their possible privatisation, price competition among the six US mortgage insurers. Russell 2000 small cap (passes all 5 checks under the Insurance filter): 10% required return, 35% safety margin."),
 "UVE": dict(name="Universal Insurance Holdings Inc.", price=46.75, shares=0.0285, bv=0.646, roe0=0.22, ni=0.2326, extra=0.0, mos=0.4,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.06), base=dict(g1=0.04,g10=0.03,m=0.14), bull=dict(g1=0.06,g10=0.035,m=0.18)),
              notes="TTM to Sep-2026. Homeowners insurance, mostly in Florida (Universal Property & Casualty, American Platinum), plus its own claims and policy services. Valued as an insurer on book value and return on equity. ROE swings with hurricanes: -8% in 2022 (Hurricane Ian), 16-21% in 2023-2024 and ~40% in 2025 and TTM after Florida's 2022-2023 legal reforms cut litigation and two quiet storm seasons. Analysts expect EPS to fall from $8.0 TTM to ~$5.60 next year (ROE ~24%). Starting ROE 22%, base 14% over a full storm cycle (6% bear: a major Florida hurricane every few years; 18% bull). Book value grows 4% fading to 3%. Book value $0.65B. Diluted shares ~28.5M (ESTIMATE). Risks: a major Florida hurricane, reinsurance costs (it buys reinsurance for most of a 1-in-100-year storm), Florida politics. Russell 2000 small cap (passes all 5 checks under the Insurance filter): 12% required return (9.5% plus 2.5 points for a single-state hurricane exposure), 40% safety margin."),
 "PLMR": dict(name="Palomar Holdings Inc.", price=156.78, shares=0.027, bv=0.985, roe0=0.24, ni=0.217, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.1,g10=0.03,m=0.14), base=dict(g1=0.2,g10=0.04,m=0.19), bull=dict(g1=0.25,g10=0.045,m=0.23)),
              notes="TTM to Sep-2026. Specialty property insurance (earthquake, commercial and residential property, inland marine, builders' risk, crop, surety) and fronting, mostly in the US. Valued as an insurer on book value and return on equity. ROE rose from 14% in 2022 to 24% in 2025 (~23% TTM, net income $217M; 26.6% annualised in the September quarter, 33% on the company's adjusted basis that adds back stock pay, intangibles amortisation and deal costs). September quarter: gross written premiums +28% to $767M, net written premiums +41%, combined ratio 80.8% (78.1% a year earlier), catastrophe losses only $4.5M. The company raised 2026 guidance to adjusted net income of $280-285M (~$10.40-10.55 per share, incl. $8-12M of catastrophe losses). Starting ROE 24% (raised from 23% on the stronger run-rate), base 19% (14% bear, 23% bull). Book value grows 20% next year fading to 4% (bear 10%, bull 25%): fast growth needs capital, so little cash is paid out in the early years. Book value $0.985B incl. $0.23B goodwill and intangibles (Gray Surety, First Indemnity); tangible equity $0.76B. Now carries a term loan (interest $5M in the quarter). Diluted shares 27.0M (September-quarter weighted average). Risks: a large California earthquake (reinsured up to a 1-in-250-year event), reinsurance prices, competition in commercial earthquake, crop-loss swings. P/B is ~4.2, so the price needs high ROE for a long time. Russell 2000 small cap (passes all 5 checks under the Insurance filter): 10.5% required return, 35% safety margin."),
 "PLGO": dict(name="Pelagos Insurance Capital Ltd.", price=28.83, shares=0.0805, bv=2.141, roe0=0.13, ni=0.3319, extra=0.0, mos=0.4,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.07), base=dict(g1=0.04,g10=0.03,m=0.12), bull=dict(g1=0.06,g10=0.035,m=0.15)),
              notes="TTM to Sep-2026 (FY2025 + 9 months 2026 - 9 months 2025). Bermuda-based specialty insurance and reinsurance group, formerly Fidelis Insurance Group (NYSE: FIHL, listed 2023), renamed Pelagos; it writes business sourced by The Fidelis Partnership and a wider partner network. Valued as an insurer on book value and return on equity. Q3 2026: net income $61.7M (vs $130.5M), operating net income $83.3M (annualised operating ROE 15.3%), combined ratio 91.5% (79.0% a year earlier) with $116M of catastrophe and large losses; net premiums written +17.5% to $592M, gross +5%. Nine months: net income $214M (operating ROE 11.8%), combined ratio 92.4% (99.5%). TTM net income $332M (includes a $21M UK tax reversal); TTM operating income ~$310M, ~13.6% of average equity, so starting ROE stays 13% (base 12%, 7% bear, 15% bull). Book value $2.14B, diluted $26.60 a share (+14% in a year) while it shrinks the share count fast: 17.7M shares bought back in 9 months ($363M, ~18%), $400M authorisation renewed; dividend raised to $0.22 a quarter. Diluted shares 80.5M. Price ~1.08x diluted book. Book value grows 4% fading to 3%. LOW CONFIDENCE (lumpy catastrophe results, few analysts). Risks: catastrophes, reinsurance pricing cycle, reserve charges. Russell 2000 small cap (passes all 5 checks under the Insurance filter): 11% required return, 40% safety margin."),
 "SLDE": dict(name="Slide Insurance Holdings Inc.", price=25.94, shares=0.1172, bv=1.303, roe0=0.26, ni=0.583, extra=0.0, mos=0.4,
              scen=dict(bear=dict(g1=0.02,g10=0.02,m=0.07), base=dict(g1=0.08,g10=0.03,m=0.16), bull=dict(g1=0.12,g10=0.035,m=0.21)),
              notes="TTM to Sep-2026. Florida homeowners and condominium insurer founded in 2021 that grew by taking over policies from Citizens (the state insurer of last resort) and from failed insurers (St. Johns, United P&C); listed in June 2025. Valued as an insurer on book value and return on equity. ROE 47-60% in 2023-2025 and ~51% TTM, earned in years without a major Florida hurricane landfall on its book; analysts expect EPS to fall from $4.42 TTM to ~$3.77 next year (ROE ~34%). Starting ROE 26%, base 16% over a full storm cycle (7% bear: a major hurricane every few years; 21% bull). Book value grows 8% fading to 3%. Book value $1.3B. Only 4-5 years of history, none through a major storm. Risks: a major Florida hurricane, reinsurance costs, Florida politics and Citizens depopulation slowing. Russell 2000 small cap (passes 4 of 5 checks under the Insurance filter): 12% required return (9.5% plus 2.5 points for single-state hurricane exposure and a short record), 40% safety margin."),
 "HG": dict(name="Hamilton Insurance Group Ltd.", price=36.94, shares=0.1, bv=2.936, roe0=0.15, ni=0.531, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.08), base=dict(g1=0.07,g10=0.035,m=0.13), bull=dict(g1=0.1,g10=0.04,m=0.16)),
              notes="TTM to Sep-2026. Bermuda specialty insurer and reinsurer (Hamilton Global Specialty at Lloyd's, Hamilton Select in the US, Hamilton Re); part of its investments are run by Two Sigma. Valued as an insurer on book value and return on equity. ROE -6% in 2022, then 14-22% in 2023-2025 and ~19% TTM in good reinsurance markets; analysts expect EPS of ~$4.90 next year (ROE ~16%). Starting ROE 15%, base 13% (8% bear, 16% bull). Book value grows 7% fading to 3.5%. Book value $2.9B. Shares ~100M across Class A and B (market value / price; Yahoo's share count shows one class only). Risks: catastrophes, softening reinsurance prices, the Two Sigma fund's returns. Russell 2000 small cap (passes 4 of 5 checks under the Insurance filter): 10.5% required return, 35% safety margin."),
 "HCI": dict(name="HCI Group Inc.", price=185.5, shares=0.01256, bv=1.121, roe0=0.21, ni=0.3284, extra=0.0, mos=0.4,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.06), base=dict(g1=0.05,g10=0.03,m=0.15), bull=dict(g1=0.08,g10=0.035,m=0.19)),
              notes="TTM to Sep-2026. Florida homeowners insurance (Homeowners Choice, TypTap, and policies taken from Citizens) plus Exzeo, its insurance software business, now separately listed (NYSE: XZO) with HCI keeping control (outside holders' share shown as noncontrolling interests, $96M). Valued as an insurer on book value and return on equity (Exzeo's market value is not counted separately). ROE -36% in 2022 (Hurricane Ian), then 28-40% in 2023-2025 and ~30% TTM (net income after noncontrolling interests $328M). September quarter: net income after noncontrolling interests $83.5M (+27%), diluted EPS $6.45 vs $4.90, gross written premiums +12% to $353M, gross loss ratio 20.7% (22.0%); lower costs of the new June 2026 reinsurance programme cut ceded premiums. No company guidance; analysts expect EPS of ~$20 next year (ROE ~20-22%). Starting ROE 21%, base 15% over a full storm cycle (6% bear, 19% bull). Book value grows 5% fading to 3%. Book value $1.12B ($90.15 per share vs $63.41 a year earlier); completed an $80M buyback in July. Diluted shares 12.6M (September-quarter weighted average). Risks: a major Florida hurricane, reinsurance costs, Florida politics. Russell 2000 small cap (passes 4 of 5 checks under the Insurance filter): 12% required return (9.5% plus 2.5 points for single-state hurricane exposure), 40% safety margin."),
 "ESNT": dict(name="Essent Group Ltd.", price=65.73, shares=0.0898, bv=5.555, roe0=0.12, ni=0.6799, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.08), base=dict(g1=0.04,g10=0.03,m=0.115), bull=dict(g1=0.06,g10=0.035,m=0.135)),
              notes="TTM to Sep-2026. US private mortgage insurance plus Essent Re (reinsurance for Fannie Mae and Freddie Mac) and a small title-insurance business. Valued as an insurer on book value and return on equity. ROE 19% in 2022, falling to 12% in 2025 and ~12% TTM (11.7% annualised in the September quarter) as capital built up faster than insurance in force. Net income $680M TTM, flat; insurance in force $250.1B (+0.5%), new insurance written $12.1B in the quarter; default rate up to 2.75% from 2.29% a year earlier. Analysts expect EPS of ~$7.60 this year and ~$7.90 next (ROE ~12%), so the starting ROE is 12%, base 11.5% (8% bear: a housing downturn; 13.5% bull). Book value grows 4% fading to 3%. Book value $5.56B ($62.58 a share, up 6% in a year; total book fell 3% because buybacks exceed earnings: 7.7M shares for $474M bought back this year to 31 Oct, a new $500M programme to end-2028, dividend $0.35 a quarter). PMIERs sufficiency 177%. Diluted shares 89.8M (Q3 weighted average, down 9% in a year). Risks: house prices and unemployment (rising defaults), Fannie Mae and Freddie Mac capital rules and their possible privatisation, price competition. Russell 2000 small cap (passes 4 of 5 checks under the Insurance filter): 10% required return, 35% safety margin."),
 "UFCS": dict(name="United Fire Group Inc.", price=47.73, shares=0.026, bv=0.939, roe0=0.12, ni=0.1369, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.0,g10=0.02,m=0.06), base=dict(g1=0.04,g10=0.03,m=0.1), bull=dict(g1=0.06,g10=0.035,m=0.13)),
              notes="TTM to Sep-2026. Commercial property and casualty insurance for small and mid-sized businesses through independent agents (Iowa). Valued as an insurer on book value and return on equity. ROE was weak for years (2% in 2022, -4% in 2023 after reserve charges) and recovered to 8% in 2024 and ~14% in 2025 and TTM under a turnaround plan (re-pricing, exiting weak lines, specialty growth); analysts expect EPS of ~$4.85 next year (ROE ~13%). Starting ROE 12%, base 10%: the turnaround is young (6% bear, 13% bull). Book value grows 4% fading to 3%. Book value $0.94B. Diluted shares ~26M (ESTIMATE). Risks: further reserve charges on older casualty years, catastrophes and convective storms, competition from larger carriers. Russell 2000 small cap (passes 4 of 5 checks under the Insurance filter): 10% required return, 35% safety margin."),
 "SKWD": dict(name="Skyward Specialty Insurance Group Inc.", price=59.8, shares=0.0458, bv=1.276, roe0=0.17, ni=0.1918, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.04,g10=0.025,m=0.11), base=dict(g1=0.12,g10=0.035,m=0.15), bull=dict(g1=0.16,g10=0.04,m=0.18)),
              notes="TTM to Sep-2026. US excess and surplus and specialty insurance (accident and health, captives, programs, agriculture, surety, transactional E&S); bought Apollo's Lloyd's specialty business in early 2026, paid partly in shares (book value up 25% in the March quarter). Valued as an insurer on book value and return on equity. ROE 9% in 2022 rising to 16-19% in 2023-2025; 17.3% for the first nine months of 2026 (15.7% annualised in the September quarter on the larger, share-funded book). Net income $192M TTM; gross written premiums +9.0% and net written premiums +13.7% in the quarter (Apollo included); combined ratio 89.9% (89.2% a year earlier), with 1.8 points of catastrophe losses, mostly convective storms. Analysts expect EPS of ~$5.15 this year and ~$5.70 next (ROE ~18-19% on operating earnings), so the starting ROE is 17%, base 15% (11% bear, 18% bull). Book value grows 12% fading to 3.5%. Book value $1.28B ($28.74 a share, up 15% since December) incl. ~$0.47B goodwill and intangibles. Diluted shares 45.8M (Q3 weighted average). Risks: reserve charges on casualty lines, integrating the Apollo business, softer E&S prices. Russell 2000 small cap (passes 4 of 5 checks under the Insurance filter): 10% required return, 35% safety margin."),
}

def roe_terminal(mo, m, r):
    """ROE earned on book value after the last forecast year, by moat class: wide/short keep m, narrow fades halfway to
    the required return, none to the required return. A ROE at or below the required return is left as it is."""
    if m <= r: return m
    c = mo.get("cls")
    return r if c == "none" else (m + r) / 2 if c == "narrow" else m

def ri_years(mo):
    return max((mo or {}).get("cap_years", 10), 11)       # at least 11, so book growth has reached 2.5% in the last year

def ri_value(bv0, roe0, g1, g10, m, r, extra, shares, gt=GT, ramp=5, detail=False, mo=None, rt=None):
    """Insurer value per share: cash to shareholders (net income - growth in book value) for n years + a value after
    the last year of book value x (terminal ROE - gt) / (r - gt), plus 'extra'. rt overrides the terminal ROE."""
    n = ri_years(mo)
    path = lambda a, t: a + (g10 - a) * (t - 1) / 9 if t <= 10 else g10 + (gt - g10) * (t - 10) / (n - 10)
    bv, pv, rows = bv0, 0.0, []
    for t in range(1, n + 1):
        g = path(g1, t)
        roe = roe0 + (m - roe0) * min(t, ramp) / ramp
        ni = roe * bv
        nb = bv * (1 + g)
        cash = ni - (nb - bv)
        df = 1 / (1 + r) ** t
        pv += cash * df
        rows.append(dict(t=t, g=g, rev=nb, m=roe, fcf=cash, df=df, pv=cash * df, ni=ni))
        bv = nb
    rt = roe_terminal(mo or {}, m, (mo or {}).get("r_req", r)) if rt is None else rt     # fades towards the stock's required return
    tv = bv * (rt - gt) / (r - gt)
    pv_tv = tv * rows[-1]["df"]
    ev = pv + pv_tv
    eq = ev + extra
    ps = eq / shares
    if detail:
        k = (rt - gt) / (rows[-1]["m"] - gt) if abs(rows[-1]["m"] - gt) > 1e-9 else 1.0   # terminal cash flow vs last year's x (1 + gt)
        return dict(rows=rows, pv_fcf=pv, tv=tv, pv_tv=pv_tv, ev=ev, equity=eq, per_share=ps, tv_share=pv_tv / ev if ev else None,
                    tv_factor=k, bv0=bv0, roe_terminal=rt, excess=eq - extra - bv0)
    return ps

def ri_short(s, B, r, n, mo):
    """Base case, but the ROE drops to the required return after year n: later years add nothing, so the business is
    then worth its book value. Value per share."""
    N = ri_years(mo)
    path = lambda a, t: a + (B["g10"] - a) * (t - 1) / 9 if t <= 10 else B["g10"] + (GT - B["g10"]) * min(t - 10, N - 10) / (N - 10)
    bv, pv = s["bv"], 0.0
    for t in range(1, n + 1):
        g = path(B["g1"], t); roe = s["roe0"] + (B["m"] - s["roe0"]) * min(t, 5) / 5
        nb = bv * (1 + g); pv += (roe * bv - (nb - bv)) / (1 + r) ** t; bv = nb
    return (pv + bv / (1 + r) ** n + s["extra"]) / s["shares"]

def ri_cap(price, s, B, r, mo):
    """Years the base-case excess ROE must last for today's price (CAP_MAX + 1 = more than CAP_MAX). None when the base
    ROE is at or below the required return (a longer period would not add value)."""
    if B["m"] <= r: return None
    for n in range(1, CAP_MAX + 1):
        if ri_short(s, B, r, n, mo) >= price: return n
    return CAP_MAX + 1

out = {"as_of": AS_OF, "terminal_growth": GT, "probabilities": PROBS, "assets": {}}

for tk, s in STOCKS.items():
    s["r"] = req_return(tk)                                   # cost of equity (required return)
    mo = dict(moat_of(tk), r_req=s["r"])
    sg = segments_of(tk)
    f = FIN[tk]
    su = stock_setup(tk, s)                                   # cash-flow separation: interest, acquisitions, lenders, tax saving
    D = lambda *x, **kw: dcf(*x, mo=mo, sg=sg, **su["kw"], **kw)   # this stock's DCF (advantage period, terminal returns, segments)
    aint, add, m0 = su["aint"], su["add"], su["m0"]
    W = (lambda re: wacc_of(tk, s, re)) if DCF_METHOD == "fcff_wacc" else (lambda re: re)
    w = W(s["r"])
    nc, S2 = su["nc"], su["S2"]
    res = {}
    for sc, p in S2.items():
        d = D(s["rev"], m0, p["g1"], p["g10"], p["m"], w, nc, s["shares"], detail=True)
        res[sc] = dict(params=p, per_share=d["per_share"], detail=d)
    fv = sum(PROBS[k] * res[k]["per_share"] for k in res)
    base = res["base"]["per_share"]
    # EPV (no-growth floor): normalised SBC-adj FCF / r
    B = S2["base"]
    epv = (s["rev"] * B["m"] / w + nc) / s["shares"]          # no-growth value: base FCFF / WACC - net debt
    # implied return to shareholders at the current price (solve the cost of equity, WACC follows)
    irr = solve(lambda re: D(s["rev"], m0, B["g1"], B["g10"], B["m"], W(re), nc, s["shares"]) - s["price"], 0.035, 0.30)
    # reverse DCF: first-year growth (fading to base g10) needed to justify price at the required return
    rg = solve(lambda g1: D(s["rev"], m0, g1, B["g10"], B["m"], w, nc, s["shares"]) - s["price"], -0.5, 1.5)
    # sensitivity base case: required return (-> WACC) vs terminal growth
    rs = [s["r"] - .02, s["r"] - .01, s["r"], s["r"] + .01, s["r"] + .02]
    gs = [.015, .02, .025, .03, .035]
    sens = [[D(s["rev"], m0, B["g1"], B["g10"], B["m"], W(r), nc, s["shares"], gt=g) for g in gs] for r in rs]
    rates = sorted(set(RATE_GRID + [s["r"]]))
    VS = lambda d: {k: D(s["rev"], m0, S2[k]["g1"], S2[k]["g10"], S2[k]["m"], d, nc, s["shares"]) for k in PROBS}   # bear/base/bull at discount rate d
    def RT(r, d):
        v = VS(d)
        return dict(r=r, wacc=d, fv=sum(PROBS[k] * v[k] for k in PROBS), **v)
    rate_table = [RT(r, W(r)) for r in rates]
    wacc_row = RT(wacc_of(tk, s, s["r"]), wacc_of(tk, s, s["r"]))   # the same cash flows discounted at the blended WACC (Capital and returns card)
    cap = implied_cap(s["price"], s["rev"], m0, B["g1"], B["m"], w, nc, s["shares"], **su["kw"])
    nm = nopat_margin(tk, f["tax"])
    gchk = {k: growth_check(res[k]["detail"], s["rev"], nm, S2[k]["m"], w) for k in res}   # NOPAT and FCFF are both before interest
    E_ = s["price"] * s["shares"]
    out["assets"][tk] = dict(
        implied_cap=cap, nopat_margin=nm, growth_check=gchk, moat=mo["cls"], cap_years=mo["cap_years"], segments=None if not sg else dict(names=sg["names"], share=sg["share"], reported=sg["reported"],
            g1={k: seg_g1s(S2[k]["g1"], sg) for k in S2}, period=SEGS["stocks"][tk]["period"], source=SEGS["stocks"][tk]["source"],
            engines=None if not sg.get("engines") else dict(x=sg["engines"]["x"], moat=[c or mo["cls"] for c in sg["engines"]["moat"]],
                cap_years=[eng_mo(c, mo).get("cap_years", 10) for c in sg["engines"]["moat"]], why=sg["engines"]["why"], source=SEGS["stocks"][tk].get("engines_source", ""))), moat_reason=MOAT["stocks"][tk]["reason"],
        rate_table=rate_table, wacc_row=wacc_row, r_reason=RR["stocks"][tk]["reason"],
        dcf_method=DCF_METHOD, wacc=dict(wacc=wacc_of(tk, s, s["r"]), discount_rate=w, cost_equity=s["r"], equity_weight=E_ / (E_ + f["debt"]), debt_weight=f["debt"] / (E_ + f["debt"]),
                  cost_debt=min(max(f["rd"], 0.02), 0.10), cost_debt_raw=f["rd"], tax=f["tax"], debt=f["debt"], after_tax_interest=aint),
        separation=dict(interest_income_after_tax=su["iinc"], acquisitions_share=su["acq_share"], tax_saving=su["shield"], lender_roe=su["kw"]["roe"]),
        name=s["name"], type="stock", price=s["price"], shares=s["shares"], r=s["r"], mos=s["mos"],
        start_margin=m0, net_cash=nc, rev=s["rev"], notes=s["notes"],
        bear=res["bear"]["per_share"], base=base, bull=res["bull"]["per_share"],
        fair_value=fv, anchor=fv, buy_below=fv * (1 - s["mos"]), epv=epv,
        implied_irr=irr, reverse_g1=rg, tv_share=res["base"]["detail"]["tv_share"],
        sens=dict(r=rs, g=gs, grid=sens), detail={k: res[k]["detail"] for k in res}, scen=s["scen"], fcf=s["fcf"], sbc=s["sbc"],
        scen_source=s["scen_source"], scen_hand=s["scen_hand"], scen_override_reason=(OVERRIDES.get(tk) or {}).get("reason"),
    )

# ----------------------------------------------------------------- insurers (underwriters): excess return on equity
for tk, s in INSURERS.items():
    s["r"] = req_return(tk)
    mo = dict(moat_of(tk), r_req=s["r"])
    V = lambda p, r=s["r"], **kw: ri_value(s["bv"], s["roe0"], p["g1"], p["g10"], p["m"], r, s["extra"], s["shares"], mo=mo, **kw)
    res = {k: V(p, detail=True) for k, p in s["scen"].items()}
    fv = sum(PROBS[k] * res[k]["per_share"] for k in res)
    B = s["scen"]["base"]
    irr = solve(lambda re: V(B, re) - s["price"], 0.035, 0.30) if (V(B, 0.035) - s["price"]) * (V(B, 0.30) - s["price"]) < 0 else None
    roe_need = solve(lambda m: V(dict(B, m=m)) - s["price"], -0.2, 0.9) if (V(dict(B, m=-0.2)) - s["price"]) * (V(dict(B, m=0.9)) - s["price"]) < 0 else None
    rs = [s["r"] - .02, s["r"] - .01, s["r"], s["r"] + .01, s["r"] + .02]
    gs = [.015, .02, .025, .03, .035]
    rates = sorted(set(RATE_GRID + [s["r"]]))
    bvps = s["bv"] / s["shares"]
    out["assets"][tk] = dict(
        method="excess_roe", kind="insurer", implied_cap=ri_cap(s["price"], s, B, s["r"], mo), nopat_margin=None, growth_check=None,
        moat=mo["cls"], cap_years=ri_years(mo), segments=None, moat_reason=MOAT["stocks"][tk]["reason"],
        rate_table=[dict(r=r, fv=sum(PROBS[k] * V(s["scen"][k], r) for k in PROBS), **{k: V(s["scen"][k], r) for k in PROBS}) for r in rates], r_reason=RR["stocks"][tk]["reason"],
        dcf_method="excess_roe", wacc=dict(discount_rate=s["r"], cost_equity=s["r"], after_tax_interest=0.0),
        name=s["name"], type="stock", price=s["price"], shares=s["shares"], r=s["r"], mos=s["mos"],
        start_margin=s["roe0"], net_cash=s["extra"], rev=s["bv"], notes=s["notes"],
        bear=res["bear"]["per_share"], base=res["base"]["per_share"], bull=res["bull"]["per_share"],
        fair_value=fv, anchor=fv, buy_below=fv * (1 - s["mos"]),
        epv=(s["bv"] * B["m"] / s["r"] + s["extra"]) / s["shares"],                 # no growth: base ROE on today's book, all paid out
        implied_irr=irr, reverse_g1=None, tv_share=res["base"]["tv_share"],
        sens=dict(r=rs, g=gs, grid=[[V(B, r, gt=g) for g in gs] for r in rs]), detail=res, scen=s["scen"], fcf=s["ni"], sbc=0.0,
        insurer=dict(bv=s["bv"], bv_ps=bvps, pb=s["price"] / bvps, roe0=s["roe0"], ni=s["ni"], roe_ttm=s["ni"] / s["bv"], roe_needed=roe_need,
                     fv_pb=fv / bvps, roe_terminal={k: res[k]["roe_terminal"] for k in res}, excess_ps={k: res[k]["excess"] / s["shares"] for k in res}),
    )

# ----------------------------------------------------------------- QQQ (look-through earnings model)
q = dict(price=728.95, r=req_return("QQQ"), mos=0.30)
TRAIL_PE, FWD_PE = 27.91, 21.5
e_lo, e_hi = q["price"] / TRAIL_PE, q["price"] / FWD_PE
qs = dict(bear=dict(eps=e_lo, g1=.08, g10=.035, conv=.70),
          base=dict(eps=(e_lo + e_hi) / 2, g1=.12, g10=.05, conv=.80),
          bull=dict(eps=e_hi, g1=.14, g10=.06, conv=.85))
def qqq(eps, g1, g10, conv, r=q["r"], gt=GT, detail=False):
    e, pv, rows = eps, 0.0, []
    for t in range(1, 11):
        g = g1 + (g10 - g1) * (t - 1) / 9
        e *= 1 + g
        f = e * conv
        df = 1 / (1 + r) ** t
        pv += f * df
        rows.append(dict(t=t, g=g, eps=e, fcf=f, df=df, pv=f * df))
    tv = rows[-1]["fcf"] * (1 + gt) / (r - gt)
    pv_tv = tv * rows[-1]["df"]
    v = pv + pv_tv
    return dict(rows=rows, pv_fcf=pv, tv=tv, pv_tv=pv_tv, per_share=v, tv_share=pv_tv / v) if detail else v
qres = {k: qqq(**v, detail=True) for k, v in qs.items()}
qfv = sum(PROBS[k] * qres[k]["per_share"] for k in qres)
qirr = solve(lambda r: qqq(**qs["base"], r=r) - q["price"], 0.035, 0.30)
qrs = [q["r"] - .02, q["r"] - .01, q["r"], q["r"] + .01, q["r"] + .02]
qgs = [.015, .02, .025, .03, .035]
qrates = sorted(set(RATE_GRID + [q["r"]]))
out["assets"]["QQQ"] = dict(
    rate_table=[dict(r=r, fv=sum(PROBS[k] * qqq(**qs[k], r=r) for k in PROBS), base=qqq(**qs["base"], r=r)) for r in qrates], r_reason=RR["stocks"]["QQQ"]["reason"],
    name="Invesco QQQ Trust (Nasdaq-100)", type="etf", price=q["price"], r=q["r"], mos=q["mos"],
    bear=qres["bear"]["per_share"], base=qres["base"]["per_share"], bull=qres["bull"]["per_share"],
    fair_value=qfv, anchor=qfv, buy_below=qfv * (1 - q["mos"]), epv=(qs["base"]["eps"] * qs["base"]["conv"] / q["r"]),
    implied_irr=qirr, tv_share=qres["base"]["tv_share"], scen=qs,
    sens=dict(r=qrs, g=qgs, grid=[[qqq(**qs["base"], r=r, gt=g) for g in qgs] for r in qrs]),
    detail={k: qres[k] for k in qres}, trailing_eps=e_lo, fwd_pe_ref=FWD_PE, trailing_pe=TRAIL_PE,
    notes="Look-through earnings model. Low-medium confidence: EPS inputs blend trailing GAAP (inflated by unrealised investment gains) and forward consensus.")

# ----------------------------------------------------------------- GLD (scenario reference range, NOT intrinsic value)
OZ = 0.0925   # approx. ounces of gold per GLD share (estimate)
g = dict(price=375.99)
gscen = dict(bear=dict(gold=3300, why="Real yields stay >2.5%, USD firm; gold reverts toward the inflation-adjusted 1980 peak (~$3,300-3,500)."),
             base=dict(gold=4100, why="Range-bound near the 2026 trading range as real yields and central-bank buying offset."),
             bull=dict(gold=5000, why="Fed pivots / inflation de-anchors; sell-side targets of $4,900-5,000 are reached."))
gprobs = {"bear": 0.35, "base": 0.45, "bull": 0.20}
gv = {k: v["gold"] * OZ for k, v in gscen.items()}
gfv = sum(gprobs[k] * gv[k] for k in gv)
out["assets"]["GLD"] = dict(
    name="SPDR Gold Shares", type="commodity", price=g["price"], r=None, mos=0.30,
    bear=gv["bear"], base=gv["base"], bull=gv["bull"], fair_value=gfv, anchor=gfv, buy_below=gfv * 0.70,
    epv=None, implied_irr=None, scen=gscen, probs=gprobs, oz_per_share=OZ, implied_gold=g["price"] / OZ,
    notes="No cash flows => no intrinsic value. Scenario REFERENCE range only (low confidence); oz/share is an estimate.")

json.dump(out, open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "results.json"), "w"), indent=1, default=float)

print(f"{'Tkr':6}{'Price':>9}{'Bear':>9}{'Base':>9}{'Bull':>9}{'FV(30/50/20)':>14}{'BuyBelow':>10}{'Diff%':>8}{'EPV':>8}{'IRR':>7}{'revG1':>7}{'TV%':>6}")
for tk, a in out["assets"].items():
    diff = (a["price"] / a["fair_value"] - 1) * 100
    print(f"{tk:6}{a['price']:9.2f}{a['bear']:9.1f}{a['base']:9.1f}{a['bull']:9.1f}{a['fair_value']:14.1f}{a['buy_below']:10.1f}{diff:8.1f}"
          f"{(a['epv'] or 0):8.1f}{(a['implied_irr'] or 0)*100:7.2f}{(a.get('reverse_g1') or 0)*100:7.1f}{(a.get('tv_share') or 0)*100:6.0f}")
print("start margins:", {k: round(v['start_margin'], 4) for k, v in out['assets'].items() if 'start_margin' in v})
