"""
Fair-value model (modern Graham framework) – shared by the Google Sheet and the dashboard.
All $ figures in billions unless noted. Inputs sourced from Q2-2026 filings / price history as of 2026-10-14 close.
"""
import json, math

AS_OF = "2026-11-03"   # valuation date of the latest update (method: FCF before interest at the required return, minus net debt)
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
 "AAPL": dict(name="Apple Inc.", price=342.96, shares=14.594, rev=466.8, fcf=136.683, sbc=13.706,
              net_cash=64.2, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=.06,g10=.03,m=.225), base=dict(g1=.09,g10=.04,m=.245), bull=dict(g1=.12,g10=.05,m=.265)),
              notes="TTM to Jun-2026. FCF margin is flattered by low cash taxes; normalised SBC-adjusted margin 24.5% base."),
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
 "APP": dict(name="AppLovin Corp.", price=279.29, shares=0.3347, rev=6.83, fcf=4.53, sbc=0.4,
              net_cash=-0.46, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=.10,g10=.03,m=.45), base=dict(g1=.25,g10=.05,m=.55), bull=dict(g1=.40,g10=.06,m=.62)),
              notes="TTM to Jun-2026. SBC is an ESTIMATE. Very high margins and heavy reliance on terminal value: lower confidence. Higher required return (11%) and 35% safety margin."),
 "FICO": dict(name="Fair Isaac Corp.", price=769.93, shares=0.0216, rev=2.39, fcf=1.00, sbc=0.2,
              net_cash=-5.35, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.01,g10=.025,m=.30), base=dict(g1=.07,g10=.035,m=.38), bull=dict(g1=.11,g10=.045,m=.42)),
              notes="TTM to Jun-2026. SBC is an ESTIMATE (about 8% of revenue). Net debt of $5.4B from buybacks. Scenarios CUT after the Oct-2026 price-drop review (lasting cause): the FHFA put VantageScore on the same Fannie/Freddie pricing grid (Sep 2026), Rocket made VantageScore its preferred score and FICO froze its $10 mortgage score price, ending the price rises behind its margin gains (mortgage ~62% of scores revenue). Base growth 7% (was 10%, consensus ~8%) with the cash margin (after SBC, before interest) held at today's ~38% instead of expanding; bear: mortgage share loss and price cuts, ~1% growth and a 30% margin (was 5% / 33%); bull 11% / 42% (was 14% / 43%). FY Q4 results due 4 Nov 2026."),
 "APA": dict(name="APA Corporation", price=49.15, shares=0.34015, rev=8.57, fcf=2.10, sbc=0.15,
              net_cash=-3.44, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-.08,g10=.00,m=.10), base=dict(g1=-.04,g10=.02,m=.15), bull=dict(g1=.02,g10=.025,m=.20)),
              notes="TTM to Jun-2026, earned at about $98/bbl realised oil: a cycle high, so every case assumes revenue falls and the cash margin shrinks from today's ~23% (after SBC) toward 10-20%. SBC from filings (~$0.15B/yr). Net debt $3.4B. Oil-price dependent: lower confidence, 10% required return and 35% safety margin."),
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
 "EXPE": dict(name="Expedia Group Inc.", price=289.01, shares=0.1145, rev=15.7, fcf=3.6, sbc=0.412,
              net_cash=1.442, extra=-1.442, mos=0.35,
              scen=dict(bear=dict(g1=0,g10=0.01,m=0.12), base=dict(g1=0.06,g10=0.03,m=0.17), bull=dict(g1=0.09,g10=0.04,m=0.2)),
              notes="TTM to Jun-2026. FCF NORMALISED to $3.6B: the reported $4.46B TTM is swollen by customer prepayments (merchant bookings) at the seasonal peak; FY25 was $3.1B. Cash ($7.1B) is mostly customers' money, so net cash is set to zero. Analysts expect ~7% sales growth next year. Main risk: AI agents (e.g. Meta's Muse) booking directly with hotels and airlines and bypassing aggregators; the bear case has flat sales and margins squeezed to 12%. 35% safety margin."),
 "BKNG": dict(name="Booking Holdings Inc.", price=155.83, shares=0.77488, rev=28.241, fcf=9.539, sbc=0.601,
              net_cash=-3.48, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.03,g10=0.02,m=0.26), base=dict(g1=0.08,g10=0.04,m=0.3), bull=dict(g1=0.11,g10=0.05,m=0.32)),
              notes="TTM to Jun-2026 (prices after the 2026 stock split). Very consistent: FCF grew every year 2022-2025 and the SBC-adjusted cash margin is ~32%. Analysts expect ~9% sales growth. Net debt $3.5B (gross debt $20.7B). Main risk: AI agents bypassing online travel agencies; Booking's direct traffic and hotel supply make it less exposed than Expedia, so the bear case still grows slowly with margins down to 26%."),
 "INTU": dict(name="Intuit Inc.", price=343.39, shares=0.26724, rev=21.448, fcf=7.3, sbc=2.056,
              net_cash=-1.221, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.05,g10=0.03,m=0.21), base=dict(g1=0.095,g10=0.045,m=0.26), bull=dict(g1=0.12,g10=0.055,m=0.3)),
              notes="FY to Jul-2026. FCF NORMALISED to $7.3B: FY26 reported $8.6B vs $6.1B in FY25 (timing). Stock pay is large (~10% of revenue), so the SBC-adjusted margin is ~24%. FY27 guidance: revenue +9-10% ($23.3-23.5B), GAAP EPS $20.12-20.36. Shares are down sharply in 2026 on fears that AI tax and bookkeeping agents erode TurboTax and QuickBooks; the bear case halves growth and trims margins."),
 "ADSK": dict(name="Autodesk Inc.", price=252.2, shares=0.209, rev=7.79, fcf=2.804, sbc=0.706,
              net_cash=0.45, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.06,g10=0.03,m=0.22), base=dict(g1=0.11,g10=0.05,m=0.27), bull=dict(g1=0.14,g10=0.06,m=0.31)),
              notes="TTM to Jul-2026. Revenue growing ~15% (helped by the shift to annual billing and the new transaction model); analysts expect ~11% next year. SBC is heavy (~9% of revenue). FY26 SBC-adjusted margin was 22%, TTM 27%; base target 27%. Small net cash. Risk: AI-native design tools and a construction slowdown."),
 "TPR": dict(name="Tapestry Inc.", price=110.37, shares=0.19844, rev=8.004, fcf=1.8125, sbc=0.1045,
              net_cash=-2.8, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.02,g10=0.01,m=0.13), base=dict(g1=0.05,g10=0.03,m=0.17), bull=dict(g1=0.08,g10=0.035,m=0.2)),
              notes="FY to Jun-2026. Coach brand strong: revenue +14% in FY26 and SBC-adjusted cash margin a record ~21% (history ~15%), so the base target is 17%, not today's peak. Analysts expect ~5% growth. Net debt $2.8B includes $1.6B of store leases. Fashion and tariff risk: the bear case has sales falling and margins back to 13%. 35% safety margin."),
 "VEEV": dict(name="Veeva Systems Inc.", price=323.04, shares=0.16191, rev=3.458, fcf=1.665, sbc=0.495,
              net_cash=7.091, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.07,g10=0.04,m=0.28), base=dict(g1=0.12,g10=0.055,m=0.33), bull=dict(g1=0.15,g10=0.065,m=0.36)),
              notes="TTM to Jul-2026. Life-sciences cloud software; $7.1B net cash (~14% of market value). Stock pay ~14% of revenue, so the SBC-adjusted margin is ~34%. Analysts expect ~12% growth. Risks: customers moving CRM back to Salesforce and pharma budget cuts; bear case 7% growth."),
 "MNST": dict(name="Monster Beverage Corp.", price=46.19, shares=1.95905, rev=9.219, fcf=2.081, sbc=0.136,
              net_cash=3.326, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.18), base=dict(g1=0.09,g10=0.045,m=0.21), bull=dict(g1=0.12,g10=0.055,m=0.23)),
              notes="TTM to Jun-2026 (prices after the stock split). Energy drinks; revenue +20% TTM; analysts expect ~10% next year. No debt, $3.3B cash. SBC-adjusted cash margin ~21%. Risk: competition (Celsius, Red Bull) and aluminium/tariff costs; bear case 4% growth."),
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
 "IDXX": dict(name="IDEXX Laboratories Inc.", price=560.38, shares=0.07888, rev=4.553, fcf=1.237, sbc=0.063,
              net_cash=-0.899, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.22), base=dict(g1=0.085,g10=0.045,m=0.25), bull=dict(g1=0.11,g10=0.055,m=0.27)),
              notes="TTM to Jun-2026. Veterinary diagnostics with recurring test revenue; SBC-adjusted cash margin ~26%. Analysts expect ~9% growth. Risk: fewer US vet visits; bear case 4% growth."),
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
 "CBOE": dict(name="Cboe Global Markets Inc.", price=344.28, shares=0.10425, rev=5.278, fcf=2.53, sbc=0.055,
              net_cash=1.152, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.04,g10=0.025,m=0.3), base=dict(g1=0.04,g10=0.04,m=0.34), bull=dict(g1=0.08,g10=0.05,m=0.37)),
              notes="TTM to Sep-2026 (gross revenue; margins on the same basis). Options exchanges (SPX, VIX): 2026 trading volumes were exceptionally high, so the bear case has revenue falling 4% as volatility normalises and analysts expect only ~3% growth next year. Small net cash. [Numbers auto-updated 04 Nov 2026 from Yahoo quarterly data (TTM roll-forward); text review pending.]"),
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
 "AME": dict(name="AMETEK Inc.", price=240.03, shares=0.2292, rev=7.864, fcf=1.825, sbc=0.049,
              net_cash=-1.541, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.03,m=0.19), base=dict(g1=0.1,g10=0.045,m=0.22), bull=dict(g1=0.14,g10=0.055,m=0.24)),
              notes="TTM to Jun-2026. Electronic instruments and electromechanical devices; grows by steady bolt-on acquisitions (analysts' ~16% includes deals). SBC-adjusted cash margin ~23%. Net debt $1.5B. Risk: industrial slowdown (bear case 2% growth)."),
 "AXP": dict(name="American Express Co.", price=319.63, shares=0.671, rev=72.85, fcf=11.445, sbc=0.0,
              net_cash=0.0, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.13), base=dict(g1=0.09,g10=0.045,m=0.155), bull=dict(g1=0.11,g10=0.05,m=0.17)),
              notes="TTM to Sep-2026. Card issuer AND network that lends to card members, so it is valued like a lender: cash flow = NET INCOME ($11.4B, stock pay already deducted), revenue = total revenues net of interest expense ($72.9B), and debt/interest are treated as part of the business (net cash set to zero, no interest add-back). Analysts expect ~9% revenue growth. Risks: consumer credit losses in a downturn and competition for premium cardholders."),
 "SHOP": dict(name="Shopify Inc.", price=155.38, shares=1.209, rev=13.269, fcf=2.352, sbc=0.482,
              net_cash=4.769, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.15,g10=0.04,m=0.14), base=dict(g1=0.24,g10=0.06,m=0.19), bull=dict(g1=0.3,g10=0.07,m=0.22)),
              notes="TTM to Jun-2026. E-commerce platform with integrated payments (Shopify Payments). Revenue +30% TTM; analysts expect ~26% next year. SBC-adjusted FCF margin ~14% today; the base case assumes it rises to 19% with scale. Very high expectations in the price (forward P/E ~63, beta ~2.6): 11% required return and 35% safety margin. $4.8B net cash."),
 "PYPL": dict(name="PayPal Holdings Inc.", price=57.36, shares=0.831, rev=34.295, fcf=6.299, sbc=0.977,
              net_cash=-3.192, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.04,g10=0.01,m=0.11), base=dict(g1=0.04,g10=0.03,m=0.155), bull=dict(g1=0.07,g10=0.04,m=0.18)),
              notes="TTM to Sep-2026. Digital wallet and online checkout (PayPal, Venmo, Braintree). Slow growth (~4% expected) but cheap (forward P/E ~10) with heavy buybacks. SBC-adjusted cash margin ~16%. Net debt $3.2B (customer balances excluded). Risks: losing branded-checkout share to Apple Pay and others; the bear case has sales shrinking 4% and margins down to 11% (the price implies roughly that)."),
 "XYZ": dict(name="Block Inc.", price=75.86, shares=0.541, rev=11.5, fcf=3.882, sbc=1.201,
              net_cash=5.097, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.06,g10=0.03,m=0.18), base=dict(g1=0.15,g10=0.05,m=0.24), bull=dict(g1=0.2,g10=0.06,m=0.28)),
              notes="TTM to Jun-2026. Valued on GROSS PROFIT (~$11.5B TTM, ESTIMATE from 2025 GP and 2026 guidance), not revenue: ~$9-10B of reported revenue is low-margin bitcoin sales passed through Cash App. 2026 guidance raised: gross profit $12.51B (+21%), adjusted operating income $3.47B (28% margin). Cash App GP +31%, Square GP +13% in Q2. Stock pay is heavy (~10% of gross profit). Net cash $5.1B. High beta (~2.5): 11% required return, 35% safety margin."),
 "ADYEY": dict(name="Adyen N.V. (ADR)", price=9.14, shares=3.157, rev=3.19, fcf=1.15, sbc=0.046,
              net_cash=0.0, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.1,g10=0.04,m=0.3), base=dict(g1=0.2,g10=0.06,m=0.36), bull=dict(g1=0.25,g10=0.07,m=0.4)),
              notes="Per US ADR (ADYEY; 100 ADRs = 1 Amsterdam share; shares = ADR equivalents). Reports in EUR, converted at 1.117 USD/EUR (27 Oct 2026). TTM to Jun-2026 net revenue ~EUR 2.86B (2025 EUR 2.65B + H1-26 EUR 1.30B, +19%); EBITDA margin 49%; capex ~7% of revenue in 2026. FCF is an ESTIMATE (~36% of net revenue: net income + depreciation - capex), because reported cash flow swings with merchant settlement funds. Its large cash balance is mostly merchants' money, so net cash is set to zero (conservative). 2026 guidance (Q3 update, Oct 2026): net revenue +21-23% (constant currency) but EBITDA margin cut to ~50% (2025: 53%) and the >55% medium-term margin target withdrawn to invest faster; new 2027 targets in Feb 2027. The base FCF margin (36%) already equals today's, so no expansion is assumed. FX moves the USD value."),
 "FISV": dict(name="Fiserv Inc.", price=50.39, shares=0.532, rev=20.866, fcf=3.926, sbc=0.377,
              net_cash=-27.789, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.02,g10=0.015,m=0.13), base=dict(g1=0.02,g10=0.025,m=0.16), bull=dict(g1=0.04,g10=0.035,m=0.18)),
              notes="TTM to Jun-2026 (ticker FISV since the Nasdaq move). Banking technology and merchant acquiring (Clover). Guidance was reset in 2025; 2026 guidance: organic revenue +1-3%, adjusted EPS $8.00-8.30; 2027-29 FCF ~90% of adjusted net income. Very cheap (P/E ~6) but carries $27.8B net debt, so equity value is very sensitive to the business value: 35% safety margin."),
 "CRCL": dict(name="Circle Internet Group", price=71.61, shares=0.235, rev=2.905, fcf=0.71, sbc=0.224,
              net_cash=1.731, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.1,g10=0.02,m=0.1), base=dict(g1=0.12,g10=0.05,m=0.17), bull=dict(g1=0.3,g10=0.07,m=0.25)),
              notes="TTM to Jun-2026. Issuer of the USDC stablecoin: earns interest on the reserves backing USDC (Q2-26 reserve income $668M, +5%) and pays ~59% of revenue to distributors (mainly Coinbase). USDC circulation $73.3B (Q2-26, +19% YoY but down from $77B in Q1). Income falls when interest rates fall; growth depends on stablecoin adoption and regulation. Corporate net cash $1.7B (USDC reserves are customers' money, excluded). Short public history: 12% required return, 35% safety margin."),
 "SPG": dict(name="Simon Property Group", price=217.75, shares=0.3796, rev=6.94, fcf=3.22, sbc=0.04,
              net_cash=-28.41, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0,g10=0.015,m=0.38), base=dict(g1=0.04,g10=0.025,m=0.44), bull=dict(g1=0.06,g10=0.03,m=0.47)),
              notes="TTM to Jun-2026. Largest US mall REIT (premium malls and outlets). Cash flow = operating cash flow minus capital spending ($3.2B; development included); stock pay is an ESTIMATE (~$40M). REIT: almost no income tax, so the tax rate is ~0. Revenue +19% recently partly from consolidating acquired stakes; analysts expect ~4% next year. Shares include operating-partnership units (380M). Net debt $28.4B (mortgages and notes): equity value is very sensitive to rents and interest rates; the bear case has flat sales and lower margins."),
 "META": dict(name="Meta Platforms Inc.", price=614.99, shares=2.5568, rev=241.6, fcf=28.65, sbc=26.94,
              net_cash=-32.39, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.12,g10=0.035,m=0.12), base=dict(g1=0.2,g10=0.05,m=0.2), bull=dict(g1=0.25,g10=0.06,m=0.26)),
              notes="TTM to Sep-2026. Facebook, Instagram, WhatsApp ads plus Reality Labs. Revenue +26% in Q3 (analysts ~22% next year). FCF fell to $28.7B (Q3 negative) on record AI capex, so after $26.9B of stock pay the starting cash margin is ~1%: the value rests on margins recovering toward the 2024 level (~23%) as the build-out matures (base 20%, bear 12%). Net debt $32B incl. leases after large bond issues. Shares = all classes (2.56B). Risks: capex overshoot, regulation, Reality Labs losses."),
 "TT": dict(name="Trane Technologies plc", price=410.0, shares=0.2189, rev=23.2, fcf=3.82, sbc=0.1,
              net_cash=-2.99, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.03,g10=0.03,m=0.12), base=dict(g1=0.1,g10=0.045,m=0.15), bull=dict(g1=0.14,g10=0.055,m=0.17)),
              notes="TTM to Sep-2026. HVAC and climate systems; data-centre cooling demand lifted Q3 revenue +18%. Analysts expect ~10% next year. SBC-adjusted cash margin ~16%. Net debt $3.0B. Cyclical (commercial construction, residential HVAC): bear case 3% growth and 12% margin."),
 "RL": dict(name="Ralph Lauren Corp.", price=392.87, shares=0.0596, rev=8.36, fcf=1.0, sbc=0.12,
              net_cash=-1.06, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0,g10=0.02,m=0.08), base=dict(g1=0.05,g10=0.03,m=0.11), bull=dict(g1=0.08,g10=0.04,m=0.13)),
              notes="TTM to Jun-2026 (FY27 Q1). Premium apparel brand repositioning upmarket: revenue +14% recently, analysts expect ~5% next year. FCF is seasonal and lumpy (TTM $1.0B; FY26 $0.7B). Net debt $1.1B incl. leases. Shares = all classes (59.6M). Fashion and tariff risk: bear case flat sales, 8% margin."),
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
 "STE": dict(name="STERIS plc", price=227.12, shares=0.0975, rev=6.04, fcf=0.93, sbc=0.06,
              net_cash=-1.56, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.03,g10=0.03,m=0.12), base=dict(g1=0.07,g10=0.04,m=0.15), bull=dict(g1=0.09,g10=0.05,m=0.17)),
              notes="TTM to Jun-2026 (FY27 Q1). Sterilisation equipment, consumables and outsourced sterilisation services for hospitals and medical-device makers: highly recurring (~70% consumables and services). Analysts expect ~7% growth. SBC-adjusted cash margin ~14%. Net debt $1.6B after selling the dental business."),
 "WDAY": dict(name="Workday Inc.", price=197.82, shares=0.241, rev=10.15, fcf=2.84, sbc=1.65,
              net_cash=-0.37, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.05,g10=0.03,m=0.12), base=dict(g1=0.1,g10=0.04,m=0.17), bull=dict(g1=0.13,g10=0.05,m=0.22)),
              notes="TTM to Jul-2026 (FY27 Q2). HR and finance cloud software for large enterprises; subscription revenue ~13%. Stock pay is very heavy ($1.65B, 16% of revenue), so the SBC-adjusted cash margin is only ~12%: the base case assumes it rises to 17% as stock pay falls. Cheap vs history (forward P/E ~15) on fears that AI agents reduce seat counts: bear case 5% growth, 12% margin. Shares = all classes (241M)."),
 "BR": dict(name="Broadridge Financial Solutions", price=178.82, shares=0.1129, rev=7.48, fcf=1.23, sbc=0.09,
              net_cash=-3.12, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.02,g10=0.025,m=0.13), base=dict(g1=0.05,g10=0.035,m=0.16), bull=dict(g1=0.07,g10=0.045,m=0.18)),
              notes="FY to Jun-2026. Investor communications (proxy and shareholder mail) and trading/post-trade technology: ~75% recurring revenue under multi-year contracts. Analysts expect ~5% growth. SBC-adjusted cash margin ~15%. Net debt $3.1B. Event-driven revenue (mutual fund proxies) swings year to year."),
 "MSI": dict(name="Motorola Solutions Inc.", price=491.53, shares=0.1655, rev=12.23, fcf=2.67, sbc=0.35,
              net_cash=-8.91, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.17), base=dict(g1=0.08,g10=0.045,m=0.2), bull=dict(g1=0.1,g10=0.055,m=0.22)),
              notes="TTM to Jun-2026 (sum of 4 quarters). Mission-critical radios, command-centre software and video security for police and public safety: sticky government customers and a large backlog. Analysts expect ~9% growth. SBC-adjusted cash margin ~19%. Net debt $8.9B after acquisitions (Silvus)."),
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
              scen=dict(bear=dict(g1=-0.04,g10=0.02,m=0.1), base=dict(g1=0.01,g10=0.035,m=0.13), bull=dict(g1=0.05,g10=0.045,m=0.16)),
              notes="TTM to Jul-2026 (FY26 Q2). Premium athletic apparel. US sales are shrinking under competition (Alo, Vuori) and tariffs while international grows; analysts expect revenue to fall ~1% next year. SBC-adjusted cash margin ~12% (FY24-25 ~15%). Cheap (forward P/E ~12) because the brand may be fading: bear case -4% and a 10% margin. Net cash after store leases ~-$0.75B (cash $1.4B, leases $2.1B). Shares = all classes."),
 "RDDT": dict(name="Reddit Inc.", price=90.97, shares=0.2019, rev=3.089, fcf=1.198, sbc=0.386,
              net_cash=3.0, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.06,g10=0.03,m=0.18), base=dict(g1=0.24,g10=0.05,m=0.28), bull=dict(g1=0.36,g10=0.06,m=0.34)),
              notes="TTM to Sep-2026. Online communities monetised through ads and data licensing to AI companies. Q3 revenue +53%, adjusted EBITDA margin 45%; Q4 guide revenue $1.00-1.03B (+38-42%). But search referral traffic (Google AI answers) fell sharply: US daily uniques -2% (logged-out -4%), >1M fewer referrals a week in October, and management warned daily users may fall by a low double-digit percent in Q4. Growth assumptions CUT after the Nov 2026 price-drop review (lasting cause): base 24% (was 28%), bear 6% (was 10%), bull 36% (was 40%). SBC-adjusted cash margin ~26%. Net cash $3.0B (cash + marketable securities, no debt). Shares = all classes (diluted). 11.5% required return, 35% safety margin."),
 "CF": dict(name="CF Industries Holdings", price=123.3, shares=0.1513, rev=7.74, fcf=1.65, sbc=0.04,
              net_cash=-1.13, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.15,g10=0.015,m=0.13), base=dict(g1=-0.08,g10=0.02,m=0.2), bull=dict(g1=0,g10=0.03,m=0.25)),
              notes="TTM to Jun-2026. Largest North American nitrogen fertiliser producer (ammonia, urea, UAN) with cheap US natural gas as its edge. Prices are cyclical: analysts expect revenue to fall ~11% next year as nitrogen prices normalise. FCF $1.9B less ~$0.25B paid to CHS for its stake in CF Nitrogen (ESTIMATE) = $1.65B. Capex will rise for the Blue Point low-carbon ammonia JV. Net debt $1.1B. Commodity cycle: 35% safety margin, bear case -15% and a 13% margin."),
 "EME": dict(name="EMCOR Group Inc.", price=679.55, shares=0.0438, rev=19.84, fcf=1.48, sbc=0.02,
              net_cash=0.21, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0,g10=0.03,m=0.05), base=dict(g1=0.12,g10=0.045,m=0.07), bull=dict(g1=0.16,g10=0.055,m=0.08)),
              notes="TTM to Sep-2026. Electrical and mechanical contractor (data centres, healthcare, manufacturing). Q3 revenue +29% with record backlog; analysts expect ~13% next year. SBC-adjusted cash margin ~7.4% (normal for contractors). Small net cash. Like FIX, near a cyclical peak in data-centre construction: 10.5% required return, 35% safety margin, bear case flat sales and a 5% margin."),
 "HST": dict(name="Host Hotels & Resorts", price=25.3, shares=0.6947, rev=6.22, fcf=1.02, sbc=0.03,
              net_cash=-3.69, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=-0.03,g10=0.015,m=0.11), base=dict(g1=0.02,g10=0.025,m=0.155), bull=dict(g1=0.04,g10=0.03,m=0.18)),
              notes="TTM to Jun-2026. Largest US lodging REIT (upscale hotels run by Marriott, Hyatt, Hilton). Cash flow = operating cash flow minus hotel capex. Revenue roughly flat next year. REIT: almost no income tax. Net debt $3.7B. Hotel demand is cyclical (business and group travel): bear case -3% and an 11% margin."),
 "LII": dict(name="Lennox International", price=344.08, shares=0.0342, rev=5.45, fcf=0.84, sbc=0.02,
              net_cash=-2.03, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0,g10=0.03,m=0.12), base=dict(g1=0.055,g10=0.04,m=0.15), bull=dict(g1=0.08,g10=0.05,m=0.17)),
              notes="TTM to Sep-2026. Residential and light-commercial HVAC (US). SBC-adjusted cash margin ~15%. Analysts expect ~5% growth after a weak 2025 (refrigerant transition, housing slowdown). Net debt $2.0B. Cyclical: bear case flat sales."),
 "NEM": dict(name="Newmont Corp.", price=106.61, shares=1.0392, rev=26.61, fcf=10.07, sbc=0.1,
              net_cash=3.25, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-0.15,g10=0.01,m=0.15), base=dict(g1=0,g10=0.02,m=0.25), bull=dict(g1=0.05,g10=0.025,m=0.33)),
              notes="TTM to Sep-2026. World's largest gold miner. Record FCF ($10.1B, ~38% of revenue) is earned at a gold price near $3,900/oz: like APA's oil, the base case assumes the cash margin falls to 25% (a more normal gold price) and the bear case to 15% with revenue down 15%. SBC is an ESTIMATE. Net cash $3.3B. The value moves with gold: 35% safety margin."),
 "REGN": dict(name="Regeneron Pharmaceuticals", price=973.36, shares=0.10368, rev=16.892, fcf=3.633, sbc=1.006,
              net_cash=6.586, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0,g10=0.02,m=0.14), base=dict(g1=0.1,g10=0.04,m=0.2), bull=dict(g1=0.14,g10=0.05,m=0.25)),
              notes="TTM to Sep-2026 (Yahoo's Sep quarter not filled yet). Biotech: Dupixent (with Sanofi), EYLEA/EYLEA HD (eye), Libtayo and a broad pipeline. EYLEA faces biosimilars while Dupixent keeps growing; analysts expect ~13% growth next year. Stock pay is heavy (~$1B), so the SBC-adjusted cash margin is ~17%. Net cash $5.3B counts only cash and short-term investments (long-term securities of roughly $10B NOT counted: upside). Low beta, but pipeline and pricing risk. [Numbers auto-updated 04 Nov 2026 from Yahoo quarterly data (TTM roll-forward); text review pending.]"),
 "ZTS": dict(name="Zoetis Inc.", price=79.72, shares=0.4132, rev=9.52, fcf=2.32, sbc=0.1,
              net_cash=-7.57, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=-0.02,g10=0.025,m=0.19), base=dict(g1=0.03,g10=0.04,m=0.23), bull=dict(g1=0.06,g10=0.05,m=0.26)),
              notes="TTM to Jun-2026. World's largest animal-health company (pet and livestock medicines, vaccines, diagnostics). Growth has stalled (analysts ~1% next year) as its pet pain drug Librela faced safety questions and competition hit the Simparica franchise: cheap vs history (forward P/E ~12). SBC-adjusted cash margin ~23%. Net debt $7.6B after debt-funded buybacks."),
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
 "NRG": dict(name="NRG Energy Inc.", price=96.06, shares=0.2102, rev=33.12, fcf=1.8, sbc=0.14,
              net_cash=-23.31, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0,g10=0.02,m=0.035), base=dict(g1=0.08,g10=0.03,m=0.055), bull=dict(g1=0.12,g10=0.04,m=0.07)),
              notes="TTM to Jun-2026. Power generation plus retail electricity and home services (Reliant, Direct Energy, Vivint). FCF NORMALISED to $1.8B (ESTIMATE): reported TTM FCF is only $0.3B after working-capital swings and acquisition-related spending, vs $1.8B in 2024. The LS Power plants acquisition (2026) adds generation and debt: net debt $23.3B. Data-centre power demand is the bull case. LOW CONFIDENCE (thin margins, heavy debt, commodity-linked cash flow): 10% required return, 35% safety margin."),
 "FIS": dict(name="Fidelity National Information Services", price=38.55, shares=0.5157, rev=12.2, fcf=1.92, sbc=0.19,
              net_cash=-20.52, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.02,g10=0.02,m=0.12), base=dict(g1=0.1,g10=0.03,m=0.17), bull=dict(g1=0.13,g10=0.04,m=0.2)),
              notes="TTM to Jun-2026. Banking and capital-markets software after swapping its Worldpay stake for Global Payments' card-issuer business (early 2026): revenue run-rate ~$13.5B, so base growth of 10% next year includes the acquisition's full year. Debt rose to $21.3B. SBC-adjusted cash margin ~14% (FIS targets ~20%+ FCF conversion). Flagged 'check first' on the Monthly Top 5 (forward P/E ~6 looks too cheap to trust): LOW CONFIDENCE until integration results are clearer."),
}

# ---------------------------------------------------------------- capital structure (for WACC)
# Gross debt and after-tax cost of debt make the DCF consistent: free cash flow BEFORE interest (FCFF) is discounted at
# WACC, then net debt is subtracted. Source: yfinance annual statements via the screener run of 2026-10-23.
# debt = total debt incl. leases ($B); rd = interest expense / average debt (clipped to 2-10% when used); tax = effective rate.
FIN = {
 "AAPL": dict(debt=84.34, interest=3.933, rd=0.0383, tax=0.156), "MSFT": dict(debt=133.1, interest=3.223, rd=0.0242, tax=0.197),
 "GOOGL": dict(debt=141.917, interest=3.868, rd=0.0273, tax=0.181), "AMZN": dict(debt=300.35, interest=6.764, rd=0.0225, tax=0.223),
 "NVDA": dict(debt=38.86, interest=0.259, rd=0.0246, tax=0.151), "AVGO": dict(debt=59.42, interest=3.210, rd=0.0484, tax=0.256),
 "LLY": dict(debt=49.503, interest=1.3, rd=0.0263, tax=0.207), "ADBE": dict(debt=6.79, interest=0.263, rd=0.0414, tax=0.180),
 "APP": dict(debt=3.52, interest=0.207, rd=0.0583, tax=0.132), "FICO": dict(debt=5.60, interest=0.134, rd=0.0504, tax=0.188),
 "APA": dict(debt=3.88, interest=0.278, rd=0.0517, tax=0.350), "DECK": dict(debt=0.54, interest=0.0047, rd=0.0087, tax=0.228),
 "INCY": dict(debt=0.032, interest=0.0024, rd=0.0757, tax=0.21), "MKC": dict(debt=5.02, interest=0.196, rd=0.0452, tax=0.214),
 "EXPE": dict(debt=5.685, interest=0.355, rd=0.0624, tax=0.18),
 "BKNG": dict(debt=20.694, interest=1.103, rd=0.0533, tax=0.21),
 "INTU": dict(debt=8.421, interest=0.256, rd=0.0304, tax=0.24),
 "ADSK": dict(debt=3.705, interest=0.13, rd=0.0351, tax=0.22),
 "TPR": dict(debt=3.953, interest=0.055, rd=0.0139, tax=0.18),
 "VEEV": dict(debt=0.152, interest=0.0, rd=0.0500, tax=0.23),
 "MNST": dict(debt=0.093, interest=0.0, rd=0.0500, tax=0.23),
 "ALLE": dict(debt=2.224, interest=0.098, rd=0.0441, tax=0.188),
 "FTNT": dict(debt=0.497, interest=0.015, rd=0.0298, tax=0.18),
 "RMD": dict(debt=0.611, interest=0.022, rd=0.036, tax=0.21),
 "V": dict(debt=22.071, interest=0.758, rd=0.0343, tax=0.163),
 "FIX": dict(debt=0.374, interest=0.0059, rd=0.0157, tax=0.224),
 "MA": dict(debt=23.938, interest=1.0, rd=0.0418, tax=0.196),
 "CTAS": dict(debt=2.706, interest=0.106, rd=0.0392, tax=0.2),
 "DXCM": dict(debt=1.393, interest=0.013, rd=0.0093, tax=0.215),
 "IDXX": dict(debt=1.096, interest=0.038, rd=0.0347, tax=0.2),
 "VRSN": dict(debt=1.792, interest=0.078, rd=0.0435, tax=0.236),
 "NDAQ": dict(debt=9.216, interest=0.335, rd=0.0363, tax=0.2),
 "MCO": dict(debt=7.492, interest=0.258, rd=0.0344, tax=0.22),
 "SPGI": dict(debt=13.465, interest=0.322, rd=0.0239, tax=0.227),
 "NFLX": dict(debt=15.132, interest=0.857, rd=0.0566, tax=0.166),
 "CBOE": dict(debt=1.552, interest=0.0528, rd=0.034, tax=0.285),
 "GRMN": dict(debt=0.173, interest=0.0, rd=0.05, tax=0.166),
 "FDS": dict(debt=1.542, interest=0.055, rd=0.0357, tax=0.179),
 "CRM": dict(debt=41.743, interest=1.5, rd=0.0359, tax=0.222),
 "HWM": dict(debt=4.606, interest=0.192, rd=0.0417, tax=0.19),
 "ADP": dict(debt=5.472, interest=0.472, rd=0.0863, tax=0.23),
 "AME": dict(debt=2.036, interest=0.096, rd=0.0472, tax=0.174),
 "AXP": dict(debt=0.0, interest=0.0, rd=0.0500, tax=0.225),
 "SHOP": dict(debt=0.178, interest=0.0, rd=0.0500, tax=0.18),
 "PYPL": dict(debt=13.472, interest=0.486, rd=0.0361, tax=0.17),
 "XYZ": dict(debt=7.171, interest=0.12, rd=0.0167, tax=0.21),
 "ADYEY": dict(debt=0.409, interest=0.0, rd=0.0500, tax=0.23),
 "FISV": dict(debt=28.034, interest=1.553, rd=0.0554, tax=0.17),
 "CRCL": dict(debt=0.0, interest=0.0, rd=0.0500, tax=0.21),
 "SPG": dict(debt=29.43, interest=1.07, rd=0.0364, tax=0.02),
 "META": dict(debt=114.84, interest=2.78, rd=0.0242, tax=0.15),
 "TT": dict(debt=4.22, interest=0.22, rd=0.0521, tax=0.18),
 "RL": dict(debt=3.0, interest=0.06, rd=0.0200, tax=0.21),
 "ROST": dict(debt=4.74, interest=0.03, rd=0.0063, tax=0.24),
 "GDDY": dict(debt=3.88, interest=0.15, rd=0.0387, tax=0.22),
 "FAST": dict(debt=0.45, interest=0.005, rd=0.0111, tax=0.24),
 "SYK": dict(debt=14.93, interest=0.586, rd=0.0393, tax=0.2),
 "CMG": dict(debt=5.6, interest=0.0, rd=0.0500, tax=0.25),
 "KLAC": dict(debt=5.99, interest=0.28, rd=0.0467, tax=0.14),
 "CME": dict(debt=3.42, interest=0.17, rd=0.0497, tax=0.235),
 "STE": dict(debt=2.04, interest=0.06, rd=0.0294, tax=0.22),
 "WDAY": dict(debt=3.77, interest=0.11, rd=0.0292, tax=0.2),
 "BR": dict(debt=3.52, interest=0.11, rd=0.0312, tax=0.22),
 "MSI": dict(debt=9.62, interest=0.44, rd=0.0457, tax=0.21),
 "BKR": dict(debt=18.26, interest=0.39, rd=0.0214, tax=0.25),
 "RSG": dict(debt=14.27, interest=0.605, rd=0.0424, tax=0.24),
 "WAB": dict(debt=6.38, interest=0.3, rd=0.0470, tax=0.25),
 "MRVL": dict(debt=5.29, interest=0.44, rd=0.0832, tax=0.14),
 "LULU": dict(debt=2.14, interest=0.0, rd=0.0500, tax=0.29),
 "RDDT": dict(debt=0.03, interest=0.0, rd=0.0500, tax=0.15),
 "CF": dict(debt=3.61, interest=0.16, rd=0.0443, tax=0.2),
 "EME": dict(debt=0.56, interest=0.01, rd=0.0179, tax=0.26),
 "HST": dict(debt=5.64, interest=0.24, rd=0.0426, tax=0.05),
 "LII": dict(debt=2.08, interest=0.07, rd=0.0337, tax=0.21),
 "NEM": dict(debt=5.58, interest=0.14, rd=0.0251, tax=0.35),
 "REGN": dict(debt=2.71, interest=0.0513, rd=0.0189, tax=0.16),
 "ZTS": dict(debt=9.24, interest=0.24, rd=0.0260, tax=0.2),
 "MO": dict(debt=24.06, interest=1.19, rd=0.0495, tax=0.24),
 "HAS": dict(debt=3.55, interest=0.17, rd=0.0479, tax=0.21),
 "BMY": dict(debt=44.81, interest=1.65, rd=0.0368, tax=0.18),
 "NRG": dict(debt=23.47, interest=1.02, rd=0.0435, tax=0.24),
 "FIS": dict(debt=21.26, interest=0.6, rd=0.0282, tax=0.22),
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

def dcf(rev0, m0, g1, g10, m_target, r, net_cash_plus, shares, gt=GT, ramp=5, detail=False):
    rev, pv, rows = rev0, 0.0, []
    for t in range(1, 11):
        g = g1 + (g10 - g1) * (t - 1) / 9
        rev *= 1 + g
        m = m0 + (m_target - m0) * min(t, ramp) / ramp
        fcf = rev * m
        df = 1 / (1 + r) ** t
        pv += fcf * df
        rows.append(dict(t=t, g=g, rev=rev, m=m, fcf=fcf, df=df, pv=fcf * df))
    tv = rows[-1]["fcf"] * (1 + gt) / (r - gt)
    pv_tv = tv * rows[-1]["df"]
    ev = pv + pv_tv
    eq = ev + net_cash_plus
    ps = eq / shares
    if detail:
        return dict(rows=rows, pv_fcf=pv, tv=tv, pv_tv=pv_tv, ev=ev, equity=eq, per_share=ps, tv_share=pv_tv / ev)
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

out = {"as_of": AS_OF, "terminal_growth": GT, "probabilities": PROBS, "assets": {}}

for tk, s in STOCKS.items():
    s["r"] = req_return(tk)                                   # cost of equity (required return)
    f = FIN[tk]
    aint = 0.0 if DCF_METHOD == "equity" else f["interest"] * (1 - f["tax"])   # after-tax interest added back: FCF -> FCFF
    add = aint / s["rev"]                                     # kept as a constant share of revenue in every year
    m0 = (s["fcf"] - s["sbc"] + aint) / s["rev"]              # starting FCFF margin (after SBC)
    W = (lambda re: wacc_of(tk, s, re)) if DCF_METHOD == "fcff_wacc" else (lambda re: re)
    w = W(s["r"])
    nc = s["net_cash"] + s["extra"]
    S2 = {k: dict(v, m=v["m"] + add) for k, v in s["scen"].items()}   # scenario margins stated to equity, + interest share
    res = {}
    for sc, p in S2.items():
        d = dcf(s["rev"], m0, p["g1"], p["g10"], p["m"], w, nc, s["shares"], detail=True)
        res[sc] = dict(params=p, per_share=d["per_share"], detail=d)
    fv = sum(PROBS[k] * res[k]["per_share"] for k in res)
    base = res["base"]["per_share"]
    # EPV (no-growth floor): normalised SBC-adj FCF / r
    B = S2["base"]
    epv = (s["rev"] * B["m"] / w + nc) / s["shares"]          # no-growth value: base FCFF / WACC - net debt
    # implied return to shareholders at the current price (solve the cost of equity, WACC follows)
    irr = solve(lambda re: dcf(s["rev"], m0, B["g1"], B["g10"], B["m"], W(re), nc, s["shares"]) - s["price"], 0.035, 0.30)
    # reverse DCF: first-year growth (fading to base g10) needed to justify price at the required return
    rg = solve(lambda g1: dcf(s["rev"], m0, g1, B["g10"], B["m"], w, nc, s["shares"]) - s["price"], -0.5, 1.5)
    # sensitivity base case: required return (-> WACC) vs terminal growth
    rs = [s["r"] - .02, s["r"] - .01, s["r"], s["r"] + .01, s["r"] + .02]
    gs = [.015, .02, .025, .03, .035]
    sens = [[dcf(s["rev"], m0, B["g1"], B["g10"], B["m"], W(r), nc, s["shares"], gt=g) for g in gs] for r in rs]
    rates = sorted(set(RATE_GRID + [s["r"]]))
    rate_table = [dict(r=r, wacc=W(r), fv=sum(PROBS[k] * dcf(s["rev"], m0, S2[k]["g1"], S2[k]["g10"], S2[k]["m"], W(r), nc, s["shares"]) for k in PROBS),
                       base=dcf(s["rev"], m0, B["g1"], B["g10"], B["m"], W(r), nc, s["shares"])) for r in rates]
    E_ = s["price"] * s["shares"]
    out["assets"][tk] = dict(
        rate_table=rate_table, r_reason=RR["stocks"][tk]["reason"],
        dcf_method=DCF_METHOD, wacc=dict(wacc=wacc_of(tk, s, s["r"]), discount_rate=w, cost_equity=s["r"], equity_weight=E_ / (E_ + f["debt"]), debt_weight=f["debt"] / (E_ + f["debt"]),
                  cost_debt=min(max(f["rd"], 0.02), 0.10), cost_debt_raw=f["rd"], tax=f["tax"], debt=f["debt"], after_tax_interest=aint),
        name=s["name"], type="stock", price=s["price"], shares=s["shares"], r=s["r"], mos=s["mos"],
        start_margin=m0, net_cash=nc, rev=s["rev"], notes=s["notes"],
        bear=res["bear"]["per_share"], base=base, bull=res["bull"]["per_share"],
        fair_value=fv, anchor=fv, buy_below=fv * (1 - s["mos"]), epv=epv,
        implied_irr=irr, reverse_g1=rg, tv_share=res["base"]["detail"]["tv_share"],
        sens=dict(r=rs, g=gs, grid=sens), detail={k: res[k]["detail"] for k in res}, scen=s["scen"], fcf=s["fcf"], sbc=s["sbc"],
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
