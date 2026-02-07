import pandas as pd
import numpy as np
from datetime import datetime
from deribit_connector import DeribitConnector
from polymarket_touch_scanner import PolymarketTouchScanner
from bs_models import BlackScholesModels

class TouchReplicator:
    """
    Replicates Polymarket 'Touch' bets using Deribit Option Chains.
    Implements methodologies from Dimitris Andreou (Spread Replication)
    and Black-Scholes (Analytical).
    """
    
    def __init__(self):
        self.poly_scanner = PolymarketTouchScanner()
        self.deribit = DeribitConnector("BTC")
        self.option_chain = pd.DataFrame()
        self.risk_free_rate = 0.04 # Estimating 4% risk free rate

    def get_time_to_expiry(self, expiry_str):
        """Calculate years to expiry"""
        try:
            exp_date = datetime.strptime(expiry_str, "%Y-%m-%d")
            delta = exp_date - datetime.now()
            return max(0.001, delta.days / 365.0)
        except:
            return 0.0

    def calculate_deribit_metrics(self, strike, expiry, poly_type="Up"):
        """
        Calculate implied probabilities using Deribit data.
        Returns: { 'bs_prob': float, 'spread_prob': float, 'details': dict }
        """
        if self.option_chain.empty: return None

        # Filter for relevant expiry
        relevant_opts = self.option_chain[self.option_chain["expiry"] >= expiry].sort_values("expiry")
        if relevant_opts.empty: return None
        
        target_expiry = relevant_opts.iloc[0]["expiry"]
        chain = relevant_opts[relevant_opts["expiry"] == target_expiry]
        
        # Get Spot Price (Index)
        spot = chain.iloc[0]["underlying_price"]
        if not spot: return None
        
        # 1. Analytical Black-Scholes Probability
        # Need Implied Volatility at the Strike
        # Find option closest to strike
        
        # If Target > Spot (Call side)
        target_opt = chain.iloc[(chain['strike'] - strike).abs().argsort()[:1]]
        if target_opt.empty: return None
        
        iv = target_opt.iloc[0]["mark_iv"] / 100.0 # Convert to decimal
        T = self.get_time_to_expiry(target_expiry)
        
        bs_prob = BlackScholesModels.one_touch_probability(
            S=spot, K=strike, T=T, sigma=iv, r=self.risk_free_rate
        )
        
        # 2. Spread Replication (Andreou Method)
        # Construct Vertical Credit Spread centered around K (or just above/below)
        # Andreou: "Vertical Spread Value at Touch ~ 50% of Width"
        # Strategy: Sell Spread (Credit).
        # Implied Prob = 2 * Credit / Width
        
        # Find strikes for spread: [K-1000, K+1000] if possible, or closest
        calls = chain[chain["type"] == "call"].sort_values("strike")
        
        # Find strike just below and just above K
        lower_candidates = calls[calls["strike"] <= strike]
        upper_candidates = calls[calls["strike"] > strike]
        
        if lower_candidates.empty or upper_candidates.empty:
            return {"bs_prob": bs_prob, "spread_prob": None, "details": {"iv": iv, "T": T}}
            
        short_leg = lower_candidates.iloc[-1] # Sell (Bid)
        long_leg = upper_candidates.iloc[0]   # Buy (Ask)
        
        k_short = short_leg["strike"]
        k_long = long_leg["strike"]
        
        # Check liquidity
        if pd.isna(short_leg["bid"]) or pd.isna(long_leg["ask"]):
             return {"bs_prob": bs_prob, "spread_prob": None, "details": {"iv": iv, "T": T}}

        # Credit Calculation (BTC -> USD)
        credit_btc = short_leg["bid"] - long_leg["ask"]
        credit_usd = credit_btc * spot
        width = k_long - k_short
        
        spread_prob = 0.0
        if width > 0 and credit_usd > 0:
            # Formula: P = 2 * Credit / Width
            spread_prob = (2 * credit_usd) / width
            
        return {
            "bs_prob": bs_prob,
            "spread_prob": spread_prob,
            "details": {
                "iv": iv, 
                "T": T, 
                "spread": f"{k_short}-{k_long}",
                "credit": credit_usd,
                "spot": spot
            }
        }

    def scan(self, html_output=False):
        print("=== Touch Bet Replicator (v2.0) ===")
        print("Fetching Deribit Data...")
        self.option_chain = self.deribit.get_option_chain_summary()
        
        print("Fetching Polymarket Data...")
        poly_markets = self.poly_scanner.fetch_polymarket_touch_markets()
        
        opportunities = []
        scan_results = []
        
        print(f"\nScanning {len(poly_markets)} Markets...\n")
        
        for m in poly_markets:
            details = self.poly_scanner.parse_market_details(m)
            if not details: continue
            
            strike = details["strike"]
            poly_prob = details["poly_price"]
            
            if details["expiry"] < datetime.now().strftime("%Y-%m-%d"): continue

            metrics = self.calculate_deribit_metrics(strike, details["expiry"])
            if not metrics: continue
            
            bs_prob = metrics["bs_prob"]
            spread_prob = metrics["spread_prob"]
            
            ref_prob = spread_prob if spread_prob else bs_prob
            diff = poly_prob - ref_prob
            
            result_item = {
                "market": details["question"],
                "expiry": details["expiry"],
                "strike": strike,
                "poly_prob": poly_prob,
                "bs_prob": bs_prob,
                "spread_prob": spread_prob,
                "iv": metrics['details']['iv'],
                "edge": diff,
                "url": details["url"],
                "spread_details": metrics['details']['spread'] if spread_prob else "N/A"
            }
            scan_results.append(result_item)
            
            print(f"Market: {details['question']}")
            print(f"  Expiry: {details['expiry']} | Strike: {strike}")
            print(f"  Polymarket: {poly_prob:.1%}")
            print(f"  Deribit BS: {bs_prob:.1%} (IV: {metrics['details']['iv']:.1%})")
            if spread_prob:
                print(f"  Deribit Spread: {spread_prob:.1%} (Spread: {metrics['details']['spread']})")
            print(f"  Edge: {diff*100:.1f}%")
            
            if diff > 0.10:
                print("  >>> SIGNAL: BUY NO (Overpriced)")
                opportunities.append(result_item)
            
            print("-" * 30)
            
        if html_output:
            self.generate_html(scan_results)

    def generate_html(self, results):
        """Generate a simple dashboard HTML file"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Touch Bet Arbitrage Scanner</title>
            <style>
                body { font-family: sans-serif; padding: 20px; background: #f0f2f5; }
                h1 { color: #333; }
                .disclaimer { background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; margin-bottom: 20px; border-radius: 5px; color: #856404; }
                .card { background: white; padding: 15px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .signal { color: green; font-weight: bold; }
                .metric { margin: 5px 0; }
                .btn { display: inline-block; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; margin-top: 10px; }
                .instructions { margin-top: 15px; padding: 10px; background-color: #f9f9f9; border-left: 3px solid #ccc; }
                .instructions h4 { margin-top: 0; color: #444; }
                .risk-warning { color: red; font-weight: bold; margin-top: 10px; }
                ol { padding-left: 20px; }
                li { margin-bottom: 8px; }
            </style>
        </head>
        <body>
            <h1>Touch Bet Arbitrage Scanner</h1>
            <div class="disclaimer">
                <strong>DISCLAIMER:</strong> This tool provides information only, not investment advice. Cryptocurrency and derivatives trading involve substantial risk. Past performance does not guarantee future results. Do not invest more than you can afford to lose. Consult a qualified financial advisor before making investment decisions. No representation is made regarding the profitability of any strategy. <em>This is Haram.</em>
            </div>
            <p>Last Updated: """ + datetime.now().strftime("%Y-%m-%d %H:%M UTC") + """</p>
            <p><em>Signals appear when Polymarket 'Yes' probability significantly exceeds Deribit's implied 'Touch' probability (via spread replication).</em></p>
        """
        
        # Sort by edge descending
        results.sort(key=lambda x: x["edge"], reverse=True)
        
        for r in results:
            if r["edge"] < 0.05: continue # Filter noise
            
            signal_color = "green" if r["edge"] > 0.1 else "orange"
            
            # Generate specific instructions for this market
            # Assume it's an "Up" bet for now (e.g., "Will BTC hit $X?")
            # Extract strike and expiry for instructions
            strike_str = f"${r['strike']:,.0f}"
            expiry_str = r['expiry']
            
            # Determine hedge spread legs based on the output format
            spread_detail = r['spread_details']
            hedge_legs = "N/A"
            leg1 = "N/A"
            leg2 = "N/A"
            if spread_detail != "N/A":
                # Parse the spread detail string (e.g., "70000.0-71000.0") to get hedge strikes
                try:
                    legs = spread_detail.split('-')
                    if len(legs) == 2:
                        leg1 = f"${float(legs[0]):,.0f}"
                        leg2 = f"${float(legs[1]):,.0f}"
                        hedge_legs = f"Sell Call @{leg1}, Buy Call @{leg2}"
                except:
                    pass # If parsing fails, leave as N/A
            
            html += f"""
            <div class="card" style="border-left: 5px solid {signal_color}">
                <h3>{r['market']}</h3>
                <div class="metric"><b>Edge:</b> <span style="color:{signal_color}">{r['edge']*100:.1f}%</span></div>
                <div class="metric">Polymarket (Yes): {r['poly_prob']:.1%} | Deribit (Implied): {r['spread_prob'] if r['spread_prob'] else r['bs_prob']:.1%}</div>
                <div class="metric">Strike: {strike_str} | Expiry: {expiry_str}</div>
                <div class="metric">Reference Spread: {r['spread_details']}</div>
                
                <div class="instructions">
                    <h4>How to Execute:</h4>
                    <strong>1. Polymarket (Go Short 'Touch'):</strong>
                    <ol>
                        <li>Navigate to the market: <a href="{r['url']}" target="_blank">View on Polymarket</a>.</li>
                        <li>Confirm the event details match: <em>{r['market']}</em> (Strike: {strike_str}, Expiry: {expiry_str}).</li>
                        <li>Connect your wallet and ensure you have sufficient USDC.</li>
                        <li>Find the <strong>'NO'</strong> outcome.</li>
                        <li>Place an order to <strong>Buy 'NO' shares</strong>. The price reflects the {r['poly_prob']:.1%} probability.</li>
                    </ol>
                    
                    <strong>2. Deribit Hedge (Cover Touch Risk):</strong>
                    <ol>
                        <li>Log in to Deribit.</li>
                        <li>Go to the BTC Options chain expiring on or before {expiry_str}.</li>
                        <li>Identify the hedge spread: <strong>{hedge_legs}</strong>. This replicates the 'No Touch' payoff.</li>
                        <li>Place a <strong>Sell Order for the {leg1} Call</strong>.</li>
                        <li>Place a <strong>Buy Order for the {leg2} Call</strong> (same number of contracts).</li>
                        <li><em>(Preferred):</em> Use a 'Vertical Spread' order type if available, selecting the {leg1} (short) and {leg2} (long) legs. This ensures simultaneous execution.</li>
                        <li>Ensure adequate BTC collateral for the short call option.</li>
                    </ol>
                </div>
                
                <div class="risk-warning">
                    <strong>RISK WARNING:</strong> Options trading and crypto markets are highly risky. This is not financial advice. Trade at your own risk.
                </div>
                
                <a href="{r['url']}" class="btn" target="_blank">View Market</a>
            </div>
            """
            
        html += "</body></html>"
        
        with open("index.html", "w") as f:
            f.write(html)
        print("Generated index.html")

if __name__ == "__main__":
    import sys
    scanner = TouchReplicator()
    html_mode = "--html" in sys.argv
    scanner.scan(html_output=html_mode)

