# 1. Using Kalshi / Polymarket

Kalshi and Polymarket are existing prediction markets where prices represent probabilities of real-world events. They already define:
- **Clear questions** (markets)
- **Crowd-based probabilities**
- **Objective resolution rules** and outcomes

*Note: We use them only as data sources, not for trading.*

### How we use them
- Users select an existing market from Kalshi or Polymarket.
- Users post their own probability for that event.
- At the time of posting, we store:
  - The user’s probability
  - The market probability (snapshot)
  - The timestamp
- When the market resolves, we fetch the final outcome and compute scores.

### Why this approach
- **Efficiency**: Avoids building our own prediction markets.
- **Simplicity**: Avoids oracle, dispute, and moderation complexity.
- **Objectivity**: Provides objective ground truth.
- **Compliance**: Keeps the system simple and legally safer.
- **Focus**: Allows us to focus on scoring, transparency, and social features.

### Cost / Access
- **Data**: Market data APIs are free to read (subject to rate limits).
- **Trading**: Trading costs money, but our app does not involve trading.
- **Onboarding**: Users never need to connect wallets or place bets.

# 2. Use Cases
- **Calibration**: Users track how accurate and well-calibrated their predictions are over time.
- **Verifiable Track Record**: Finance and crypto influencers build a transparent, verifiable history.
- **Skill Discovery**: Followers can distinguish skill from hype.
- **Market Comparison**: People compare their beliefs against market consensus.
- **Leaderboards**: Highlight consistently accurate forecasters by topic.
- **AI Benchmarking**: Human predictions can be compared against AI-generated forecasts.
- **Education**: Forecasting tournaments without real money stakes.
- **Probabilistic Thinking**: Encourages probabilistic thinking instead of absolute claims.