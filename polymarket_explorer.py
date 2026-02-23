"""
Polymarket API Explorer
========================
A minimal script to fetch and display active markets from Polymarket's Gamma API.

API Base URL: https://gamma-api.polymarket.com
No authentication required for read-only access.

Key Concepts:
- Polymarket uses a CLOB (Central Limit Order Book) model
- Prices are between 0 and 1, representing implied probability
- outcomePrices field contains the probability for each outcome
- Markets can be binary (Yes/No) or multi-outcome
"""

import requests
import json
from datetime import datetime

# ============================================================================
# API CONFIGURATION
# ============================================================================
GAMMA_API_BASE = "https://gamma-api.polymarket.com"


def fetch_active_markets(limit=5):
    """
    Fetch active (non-closed) markets from Polymarket.

    Endpoint: GET /markets
    Parameters:
        - closed=false: Only fetch active markets
        - limit: Number of markets to retrieve
        - order: Order by field
        - ascending: Sort direction
    """
    url = f"{GAMMA_API_BASE}/markets"
    params = {
        "closed": "false",  # Only active markets
        "limit": limit,
        "order": "id",
        "ascending": "false",  # Newest first
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def fetch_single_market(condition_id):
    """Fetch details for a specific market by condition ID."""
    url = f"{GAMMA_API_BASE}/markets/{condition_id}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def parse_market_data(market):
    """
    Parse a market object and extract key fields.

    Key fields explained:
    - id / conditionId: Unique market identifier
    - question: The prediction question being asked
    - outcomePrices: JSON string containing outcome probabilities
      * For binary markets: [yes_price, no_price]
      * Prices sum to 1.0 (or close to it)
      * Example: "[0.75, 0.25]" means 75% Yes, 25% No
    - closed: Whether the market is still active
    - active: Whether trading is currently enabled

    Resolution fields (after market closes):
    - resolutionSource: Where the result will be determined
    - endDate: When the market closes for trading
    """
    parsed = {
        "market_id": market.get("id") or market.get("conditionId"),
        "question": market.get("question"),
        "description": (
            market.get("description", "")[:100] + "..."
            if market.get("description") and len(market.get("description", "")) > 100
            else market.get("description", "")
        ),
        "status": (
            "CLOSED"
            if market.get("closed")
            else ("ACTIVE" if market.get("active") else "INACTIVE")
        ),
    }

    # ========================================================================
    # PROBABILITY PARSING
    # ========================================================================
    # outcomePrices is a JSON string like "[0.75, 0.25]"
    # The values represent implied probabilities for each outcome
    # Index 0 = "Yes" probability, Index 1 = "No" probability
    outcome_prices_str = market.get("outcomePrices")
    if outcome_prices_str:
        try:
            prices = json.loads(outcome_prices_str)
            if len(prices) >= 2:
                parsed["yes_probability"] = f"{float(prices[0]) * 100:.1f}%"
                parsed["no_probability"] = f"{float(prices[1]) * 100:.1f}%"
            elif len(prices) == 1:
                parsed["yes_probability"] = f"{float(prices[0]) * 100:.1f}%"
                parsed["no_probability"] = "N/A"
        except (json.JSONDecodeError, ValueError):
            parsed["yes_probability"] = "N/A"
            parsed["no_probability"] = "N/A"
    else:
        parsed["yes_probability"] = "N/A"
        parsed["no_probability"] = "N/A"

    # ========================================================================
    # RESOLUTION FIELDS
    # ========================================================================
    # These fields contain information about how/when the market resolves
    parsed["end_date"] = market.get("endDate")
    parsed["resolution_source"] = market.get("resolutionSource", "N/A")

    # After resolution, the market's 'closed' will be True
    # and outcomePrices will reflect the final outcome (1.0 for winner, 0.0 for loser)

    return parsed


def main():
    print("=" * 80)
    print("POLYMARKET API EXPLORER")
    print("=" * 80)

    # ========================================================================
    # STEP 1: Fetch raw JSON response
    # ========================================================================
    print("\n[1] Fetching active markets from Polymarket...")
    print("-" * 40)

    try:
        raw_response = fetch_active_markets(limit=5)

        print("\n📋 RAW JSON RESPONSE (first 2 markets):")
        print("-" * 40)
        # Print first 2 markets as raw JSON for structure inspection
        sample = raw_response[:2] if isinstance(raw_response, list) else [raw_response]
        print(json.dumps(sample, indent=2))

        # ====================================================================
        # STEP 2: Parse and display cleaned data
        # ====================================================================
        print("\n\n✅ PARSED MARKET DATA:")
        print("=" * 80)

        markets = raw_response if isinstance(raw_response, list) else [raw_response]

        for i, market in enumerate(markets, 1):
            parsed = parse_market_data(market)

            print(f"\n📊 Market #{i}")
            print(f"   ID:              {parsed['market_id']}")
            print(f"   Question:        {parsed['question']}")
            print(f"   Status:          {parsed['status']}")
            print(
                f"   Yes Probability: {parsed['yes_probability']}"
            )  # <-- PROBABILITY FIELD
            print(
                f"   No Probability:  {parsed['no_probability']}"
            )  # <-- PROBABILITY FIELD
            print(f"   End Date:        {parsed['end_date']}")
            print(
                f"   Resolution Src:  {parsed['resolution_source']}"
            )  # <-- RESOLUTION SOURCE
            print("-" * 40)

        # ====================================================================
        # STEP 3: Key fields summary
        # ====================================================================
        print("\n\n📚 KEY FIELDS REFERENCE:")
        print("=" * 80)
        print(
            """
PROBABILITY FIELDS:
  - 'outcomePrices': JSON array of probabilities (0.0 to 1.0)
    * For binary markets: [yes_prob, no_prob]
    * Values sum to approximately 1.0
    * Derived from order book / last trade prices
  
RESOLUTION FIELDS:
  - 'closed': Boolean, True when market has ended
  - 'active': Boolean, True when trading is enabled
  - 'resolutionSource': Where outcome is determined
  - 'endDate': ISO timestamp when market closes
  
AFTER RESOLUTION:
  - 'outcomePrices' will show [1.0, 0.0] or [0.0, 1.0]
    depending on which outcome won
  - 'closed' will be True
        """
        )

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
