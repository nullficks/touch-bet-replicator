# Touch Bet Replicator (Arbitrage & Hedging)

## Overview
This tool scans Polymarket for "Touch" markets (e.g., "Will Bitcoin hit $100k?") and compares their implied probability against Deribit Option Chains.

## Strategy
A "No Touch" bet on Polymarket (betting NO) can be replicated/hedged using a **Vertical Credit Spread** on Deribit.
- **Polymarket:** Buy "NO". Payout = $1 if Spot never touches Strike.
- **Deribit:** Sell Call ($K$) / Buy Call ($K+\epsilon$). Receive Premium $P$.
    - If Spot touches $K$, the spread value rises to $\approx Width/2$. We stop out (Loss).
    - If Spot never touches, spread expires worthless. We keep $P$.

## Usage
1.  Run `python3 touch_replicator.py`
2.  The script fetches Polymarket active markets and Deribit option chains.
3.  It calculates the "Fair Value" of the Touch probability using Deribit spreads.
4.  It flags opportunities where Polymarket Price > Deribit Price (Buy NO).

## Files
- `touch_replicator.py`: Main scanner.
- `deribit_connector.py`: Fetches Deribit option data.
- `polymarket_touch_scanner.py`: Fetches Polymarket data.
- `STRATEGY_TOUCH.md`: Detailed mathematical explanation.
-  Haram
