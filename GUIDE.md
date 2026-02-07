# Touch Bet Strategy Guide

## How to Trade "No Touch"

When the scanner signals **[BUY NO (Overpriced)]**, it means the market (Polymarket) thinks a touch event is **more likely** than the options market (Deribit) implies.

**Signal:**
- **Poly Implied Prob:** 40% (Price of Yes is 40c).
- **Deribit Fair Value:** 25%.
- **Edge:** 15%.

**Execution:**
1.  **Polymarket (The Alpha):**
    -   Go to the market link.
    -   **Buy "NO"** shares.
    -   You are betting the price will **NOT** touch the strike.
    -   *Risk:* You lose if price touches.
    -   *Reward:* You win if price never touches.

2.  **Deribit Hedge (Optional Risk-Free):**
    -   We need to cover the risk of the price touching.
    -   **Instrument:** Vertical Credit Spread (Bear Call Spread for Upside, Bull Put Spread for Downside).
    -   **Setup (Upside Example):** "Will BTC hit \$75k?"
        -   Sell Call @ \$75,000 (Short).
        -   Buy Call @ \$76,000 (Long Protection).
    -   **Mechanism:**
        -   You receive a **Premium** upfront.
        -   If BTC never touches \$75k, options expire worthless. You keep Premium.
        -   If BTC hits \$75k, the spread value rises. You close it at a loss.
    -   **Why Hedge?** If you buy Poly "NO", you lose on a touch. The Deribit spread acts as a buffer (though imperfect).
    -   **Recommendation:** For small size, just trade the Poly "NO" directionally. The edge is statistical.

## Website Automation
This repository includes a GitHub Actions workflow that runs the scanner every hour and updates a static website.

**To Enable:**
1.  Go to Repo Settings > Pages.
2.  Select Source: `gh-pages` branch (created automatically after first run).
3.  Your scanner will be live at `https://yourusername.github.io/touch-bet-replicator`.
