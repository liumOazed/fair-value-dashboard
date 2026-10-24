"""
Fair-value model (modern Graham framework) – shared by the Google Sheet and the dashboard.
All $ figures in billions unless noted. Inputs sourced from Q2-2026 filings / price history as of 2026-10-14 close.
"""
import json, math

AS_OF = "2026-10-24"   # method change: FCF before interest at the required return, minus net debt
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
 "MSFT": dict(name="Microsoft Corp.", price=533.69, shares=7.43, rev=331.3, fcf=66.987, sbc=12.405,
              net_cash=20.0, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=.12,g10=.035,m=.18), base=dict(g1=.17,g10=.05,m=.25), bull=dict(g1=.20,g10=.06,m=.29)),
              notes="FY26 (Jun-2026). Capex $116B cash (+finance leases) crushes current FCF; margin recovers as build-out matures."),
 "GOOGL": dict(name="Alphabet Inc. (Class A)", price=347.64, shares=12.23, rev=445.8, fcf=53.273, sbc=24.5,
              net_cash=129.7, extra=65.7, mos=0.30,
              scen=dict(bear=dict(g1=.14,g10=.035,m=.13), base=dict(g1=.20,g10=.05,m=.19), bull=dict(g1=.24,g10=.06,m=.24)),
              notes="TTM to Jun-2026. SBC and TTM revenue are estimates. 'extra' = $131.5B private equity stakes at a 50% haircut."),
 "AMZN": dict(name="Amazon.com Inc.", price=254.08, shares=10.786, rev=775.7, fcf=-7.604, sbc=22.0,
              net_cash=-100.2, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.09,g10=.035,m=.05), base=dict(g1=.13,g10=.05,m=.085), bull=dict(g1=.16,g10=.06,m=.12)),
              notes="TTM to Jun-2026. FCF negative on $169B capex. SBC estimated. Anthropic stake NOT valued (upside not counted)."),
 "NVDA": dict(name="NVIDIA Corp.", price=217.23, shares=24.147, rev=302.97, fcf=127.01, sbc=7.0,
              net_cash=23.61, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.08,g10=.03,m=.32), base=dict(g1=.22,g10=.04,m=.42), bull=dict(g1=.35,g10=.06,m=.50)),
              notes="TTM to Jul-2026 (FY27 Q2). SBC is an ESTIMATE (about 2.3% of revenue). Data-centre demand is highly cyclical and concentrated: lower confidence. Base case is deliberately below consensus growth. Base case is deliberately below consensus growth."),
 "AVGO": dict(name="Broadcom Inc.", price=344.33, shares=4.774, rev=89.10, fcf=39.40, sbc=8.9,
              net_cash=-35.44, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.12,g10=.03,m=.30), base=dict(g1=.25,g10=.05,m=.38), bull=dict(g1=.35,g10=.06,m=.43)),
              notes="TTM to Aug-2026 (FY26 Q3). SBC is an ESTIMATE (about 10% of revenue). Net debt from acquisitions. AI custom-chip demand drives growth."),
 "LLY": dict(name="Eli Lilly and Co.", price=1251.61, shares=0.8915, rev=79.67, fcf=18.19, sbc=2.2,
              net_cash=-45.16, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=.08,g10=.03,m=.26), base=dict(g1=.20,g10=.04,m=.32), bull=dict(g1=.28,g10=.05,m=.38)),
              notes="TTM to Jun-2026. SBC is an ESTIMATE. FCF is depressed by $9.9B capex on new plants; margin rises as the build-out matures. Growth rests on obesity drugs; pricing and patent risk."),
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
              scen=dict(bear=dict(g1=.05,g10=.03,m=.33), base=dict(g1=.10,g10=.04,m=.38), bull=dict(g1=.14,g10=.05,m=.43)),
              notes="TTM to Jun-2026. SBC is an ESTIMATE (about 8% of revenue). Net debt of $5.4B from buybacks. Pricing power in credit scores faces regulatory scrutiny."),
 "APA": dict(name="APA Corporation", price=49.15, shares=0.34015, rev=8.57, fcf=2.10, sbc=0.15,
              net_cash=-3.44, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-.08,g10=.00,m=.10), base=dict(g1=-.04,g10=.02,m=.15), bull=dict(g1=.02,g10=.025,m=.20)),
              notes="TTM to Jun-2026, earned at about $98/bbl realised oil: a cycle high, so every case assumes revenue falls and the cash margin shrinks from today's ~23% (after SBC) toward 10-20%. SBC from filings (~$0.15B/yr). Net debt $3.4B. Oil-price dependent: lower confidence, 10% required return and 35% safety margin."),
 "DECK": dict(name="Deckers Outdoor Corp.", price=85.71, shares=0.13618, rev=5.53, fcf=1.12, sbc=0.07,
              net_cash=1.13, extra=0.0, mos=0.30,
              scen=dict(bear=dict(g1=.00,g10=.02,m=.15), base=dict(g1=.06,g10=.03,m=.18), bull=dict(g1=.10,g10=.04,m=.20)),
              notes="TTM to Jun-2026. FY27 guidance: revenue $5.86-5.91B (high single digit growth), HOKA low-double-digit, UGG mid-single-digit, operating margin ~21.5% after ~150bp tariff drag. SBC is an ESTIMATE (~1% of revenue). $1.1B net cash, heavy buybacks. Fashion/brand risk: the bear case assumes HOKA growth stalls."),
 "INCY": dict(name="Incyte Corp.", price=113.07, shares=0.2027, rev=5.57, fcf=1.92, sbc=0.26,
              net_cash=3.23, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=-.02,g10=.02,m=.18), base=dict(g1=.03,g10=.03,m=.24), bull=dict(g1=.08,g10=.04,m=.30)),
              notes="TTM to Jun-2026, revenue cut by the one-off $246M Opzelura settlement benefit. Net cash $4.5B less ~$1.27B Vega (latarcibart) upfront due in Q3-2026. SBC from filings (~$0.26B/yr). Jakafi is ~60% of sales and faces loss of exclusivity later this decade, so the bear case has shrinking sales and lower margins; 35% safety margin."),
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
 "ALLE": dict(name="Allegion plc", price=178.98, shares=0.08504, rev=4.288, fcf=0.671, sbc=0.03,
              net_cash=-1.71, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.01,g10=0.02,m=0.13), base=dict(g1=0.06,g10=0.035,m=0.155), bull=dict(g1=0.08,g10=0.045,m=0.17)),
              notes="TTM to Jun-2026. Locks and access control; steady FCF growth 2022-2025. SBC from filings (~$30M; not in the TTM data). Net debt $1.7B. Analysts expect ~6% growth. Risk: non-residential construction cycle."),
 "FTNT": dict(name="Fortinet Inc.", price=179.99, shares=0.73371, rev=7.527, fcf=2.7, sbc=0.296,
              net_cash=3.573, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.06,g10=0.03,m=0.26), base=dict(g1=0.11,g10=0.05,m=0.3), bull=dict(g1=0.15,g10=0.06,m=0.33)),
              notes="TTM to Jun-2026. FCF NORMALISED to $2.7B: TTM $3.1B includes a jump in prepaid service contracts; FY25 was $2.2B. Firewall refresh cycle lifted growth to ~20%; analysts expect ~11% next year as it fades. $3.6B net cash. Risk: hardware cycle and competition (Palo Alto, cloud security)."),
 "RMD": dict(name="ResMed Inc.", price=252.86, shares=0.14064, rev=5.653, fcf=1.629, sbc=0.104,
              net_cash=0.643, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.02,g10=0.02,m=0.22), base=dict(g1=0.06,g10=0.035,m=0.26), bull=dict(g1=0.09,g10=0.045,m=0.28)),
              notes="FY to Jun-2026. Sleep-apnoea devices and masks; SBC-adjusted cash margin ~27%, small net cash. Analysts expect ~6% growth. Risk: GLP-1 weight-loss drugs shrinking the apnoea patient pool (so far demand has held up); bear case 2% growth."),
 "V": dict(name="Visa Inc.", price=407.92, shares=1.70411, rev=44.488, fcf=21.013, sbc=0.919,
              net_cash=-10.07, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.07,g10=0.04,m=0.41), base=dict(g1=0.105,g10=0.05,m=0.45), bull=dict(g1=0.13,g10=0.06,m=0.47)),
              notes="TTM to Jun-2026. Network with ~45% SBC-adjusted cash margin; FCF grew almost every year. Analysts expect ~11% revenue growth. Net debt $10B. Risks: US interchange regulation (Credit Card Competition Act), real-time payments and stablecoins; bear case 7% growth and margin 41%."),
 "FIX": dict(name="Comfort Systems USA Inc.", price=1160.86, shares=0.03519, rev=11.228, fcf=1.35, sbc=0.038,
              net_cash=1.527, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0,g10=0.02,m=0.07), base=dict(g1=0.18,g10=0.04,m=0.1), bull=dict(g1=0.25,g10=0.05,m=0.12)),
              notes="TTM to Jun-2026. Mechanical and electrical contractor riding the AI data-centre build-out: revenue +50%. FCF NORMALISED to $1.35B (~12% of sales): TTM $2.16B is inflated by customer advance payments; FY25 was $1.0B. Analysts expect ~19-22% growth next year. Highly cyclical: the bear case has data-centre spending stalling (flat sales, 7% margin). 11% required return and 35% safety margin."),
 "MA": dict(name="Mastercard Inc.", price=623.6, shares=0.86946, rev=35.083, fcf=15.975, sbc=0.615,
              net_cash=-13.03, extra=0.0, mos=0.25,
              scen=dict(bear=dict(g1=0.08,g10=0.04,m=0.4), base=dict(g1=0.12,g10=0.055,m=0.44), bull=dict(g1=0.14,g10=0.065,m=0.46)),
              notes="TTM to Jun-2026. Network with ~44% SBC-adjusted cash margin; slightly faster growth than Visa (more cross-border and value-added services). Analysts expect ~13% revenue growth. Net debt $13B. Same regulatory and new-payment-rail risks as Visa."),
 "CTAS": dict(name="Cintas Corp.", price=224.1, shares=0.39708, rev=11.561, fcf=1.881, sbc=0.128,
              net_cash=-2.417, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.14), base=dict(g1=0.075,g10=0.045,m=0.16), bull=dict(g1=0.09,g10=0.055,m=0.17)),
              notes="Revenue TTM to Aug-2026; cash flow FY to May-2026. Uniform rental and facility services: very steady (FCF up every year). Analysts expect ~7.5% growth. Net debt $2.4B. Expensive on earnings (P/E ~44); the risk is valuation and a jobs slowdown, not the business."),
 "DXCM": dict(name="DexCom Inc.", price=77.94, shares=0.37736, rev=4.969, fcf=1.25, sbc=0.162,
              net_cash=0.549, extra=0.0, mos=0.35,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.16), base=dict(g1=0.11,g10=0.05,m=0.21), bull=dict(g1=0.14,g10=0.06,m=0.25)),
              notes="TTM to Jun-2026. Continuous glucose monitors. FCF NORMALISED to $1.25B: TTM $1.4B vs FY25 $1.1B. Analysts expect ~11% growth (2026 guidance was raised). Risks: Abbott competition, pricing in type-2 / over-the-counter CGM, and the 2025 product-quality issues. 35% safety margin."),
 "IDXX": dict(name="IDEXX Laboratories Inc.", price=560.38, shares=0.07888, rev=4.553, fcf=1.237, sbc=0.063,
              net_cash=-0.899, extra=0.0, mos=0.3,
              scen=dict(bear=dict(g1=0.04,g10=0.03,m=0.22), base=dict(g1=0.085,g10=0.045,m=0.25), bull=dict(g1=0.11,g10=0.055,m=0.27)),
              notes="TTM to Jun-2026. Veterinary diagnostics with recurring test revenue; SBC-adjusted cash margin ~26%. Analysts expect ~9% growth. Risk: fewer US vet visits; bear case 4% growth."),
}

# ---------------------------------------------------------------- capital structure (for WACC)
# Gross debt and after-tax cost of debt make the DCF consistent: free cash flow BEFORE interest (FCFF) is discounted at
# WACC, then net debt is subtracted. Source: yfinance annual statements via the screener run of 2026-10-23.
# debt = total debt incl. leases ($B); rd = interest expense / average debt (clipped to 2-10% when used); tax = effective rate.
FIN = {
 "AAPL": dict(debt=84.34, interest=3.933, rd=0.0383, tax=0.156), "MSFT": dict(debt=128.81, interest=3.051, rd=0.0520, tax=0.194),
 "GOOGL": dict(debt=120.79, interest=0.736, rd=0.0180, tax=0.168), "AMZN": dict(debt=251.64, interest=2.274, rd=0.0160, tax=0.196),
 "NVDA": dict(debt=38.86, interest=0.259, rd=0.0246, tax=0.151), "AVGO": dict(debt=59.42, interest=3.210, rd=0.0484, tax=0.256),
 "LLY": dict(debt=54.91, interest=0.781, rd=0.0205, tax=0.198), "ADBE": dict(debt=6.79, interest=0.263, rd=0.0414, tax=0.180),
 "APP": dict(debt=3.52, interest=0.207, rd=0.0583, tax=0.132), "FICO": dict(debt=5.60, interest=0.134, rd=0.0504, tax=0.188),
 "APA": dict(debt=3.88, interest=0.278, rd=0.0517, tax=0.350), "DECK": dict(debt=0.47, interest=0.003, rd=0.0078, tax=0.228),
 "INCY": dict(debt=0.04, interest=0.002, rd=0.0578, tax=0.227), "MKC": dict(debt=5.02, interest=0.196, rd=0.0452, tax=0.214),
 "EXPE": dict(debt=5.685, interest=0.355, rd=0.0624, tax=0.18),
 "BKNG": dict(debt=20.694, interest=1.103, rd=0.0533, tax=0.21),
 "INTU": dict(debt=8.421, interest=0.256, rd=0.0304, tax=0.24),
 "ADSK": dict(debt=3.705, interest=0.13, rd=0.0351, tax=0.22),
 "TPR": dict(debt=3.953, interest=0.055, rd=0.0139, tax=0.18),
 "VEEV": dict(debt=0.152, interest=0.0, rd=0.0500, tax=0.23),
 "MNST": dict(debt=0.093, interest=0.0, rd=0.0500, tax=0.23),
 "ALLE": dict(debt=2.031, interest=0.101, rd=0.0497, tax=0.16),
 "FTNT": dict(debt=0.497, interest=0.018, rd=0.0362, tax=0.19),
 "RMD": dict(debt=0.826, interest=0.03, rd=0.0363, tax=0.2),
 "V": dict(debt=23.858, interest=0.776, rd=0.0325, tax=0.17),
 "FIX": dict(debt=0.328, interest=0.007, rd=0.0213, tax=0.22),
 "MA": dict(debt=24.643, interest=0.748, rd=0.0304, tax=0.19),
 "CTAS": dict(debt=2.706, interest=0.106, rd=0.0392, tax=0.2),
 "DXCM": dict(debt=1.398, interest=0.015, rd=0.0107, tax=0.22),
 "IDXX": dict(debt=1.096, interest=0.038, rd=0.0347, tax=0.2),
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
