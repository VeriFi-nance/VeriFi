"""
Kalshi API Explorer
===================
A minimal script to fetch and display active markets from Kalshi's public API.

API Base URL: https://api.elections.kalshi.com/trade-api/v2
NOTE: This uses the "elections" subdomain which provides access to ALL Kalshi markets.

Authentication:
- Public endpoints (markets, events) do NOT require authentication
- Private endpoints (orders, portfolio) require API key + signature

This script uses READ-ONLY public endpoints only.
"""

import requests
import json
from datetime import datetime

# ============================================================================
# API CONFIGURATION
# ============================================================================
# The 'elections' subdomain is the public API gateway for all Kalshi markets
KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"


def fetch_active_markets(limit=5, status="open"):
    """
    Fetch active markets from Kalshi.

    Endpoint: GET /markets
    Parameters:
        - limit: Number of markets to retrieve (1-1000, default 100)
        - status: Filter by market status
          * 'unopened': Market not yet open for trading
          * 'open': Currently trading (ACTIVE)
          * 'closed': Trading ended, awaiting resolution
          * 'settled': Final outcome determined

    NO AUTHENTICATION REQUIRED for this endpoint.
    """
    url = f"{KALSHI_API_BASE}/markets"
    params = {"limit": limit, "status": status}  # Only fetch open/active markets

    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def fetch_market_orderbook(ticker):
    """
    Fetch the order book for a specific market.
    This shows current bid/ask prices.

    Endpoint: GET /markets/{ticker}/orderbook
    """
    url = f"{KALSHI_API_BASE}/markets/{ticker}/orderbook"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def parse_market_data(market):
    """
    Parse a market object and extract key fields.

    Key fields explained:
    - ticker: Unique market identifier (e.g., "KXBTC-25FEB07-B98")
    - title: Short title of the prediction
    - subtitle: Additional context or description
    - event_ticker: Parent event this market belongs to

    PRICE FIELDS (0 to 100 cents):
    - yes_bid / yes_ask: Current best bid/ask for "Yes" contracts
    - no_bid / no_ask: Current best bid/ask for "No" contracts
    - last_price: Last traded price in cents
    - Prices are in CENTS, so 75 = 75% implied probability

    STATUS FIELDS:
    - status: 'open', 'closed', 'settled'
    - close_time: When trading ends (ISO timestamp)

    RESOLUTION FIELDS (after settlement):
    - result: 'yes', 'no', or null if not yet settled
    - settlement_value: Final payout (0 or 100 cents)
    """

    # ========================================================================
    # PROBABILITY INTERPRETATION
    # ========================================================================
    # Kalshi prices are in CENTS (0-100)
    # A 'yes_bid' of 75 means the market implies 75% probability of "Yes"
    # yes_price + no_price should approximately equal 100 (minus spread)

    yes_bid = market.get("yes_bid")
    yes_ask = market.get("yes_ask")
    last_price = market.get("last_price")

    # Calculate implied probability from available price data
    if yes_bid and yes_ask:
        mid_price = (yes_bid + yes_ask) / 2
        implied_prob = f"{mid_price:.1f}%"
    elif last_price:
        implied_prob = f"{last_price}%"
    else:
        implied_prob = "N/A"

    parsed = {
        "ticker": market.get("ticker"),
        "event_ticker": market.get("event_ticker"),
        "title": market.get("title"),
        "subtitle": market.get("subtitle", ""),
        "status": market.get("status", "unknown").upper(),
        # Price fields - THESE REPRESENT PROBABILITIES
        "yes_bid": f"{yes_bid}¢" if yes_bid is not None else "N/A",
        "yes_ask": f"{yes_ask}¢" if yes_ask is not None else "N/A",
        "no_bid": (
            f"{market.get('no_bid')}¢" if market.get("no_bid") is not None else "N/A"
        ),
        "no_ask": (
            f"{market.get('no_ask')}¢" if market.get("no_ask") is not None else "N/A"
        ),
        "last_price": f"{last_price}¢" if last_price is not None else "N/A",
        "implied_probability": implied_prob,
        # Time fields
        "close_time": market.get("close_time"),
        "expiration_time": market.get("expiration_time"),
        # ====================================================================
        # RESOLUTION FIELDS
        # ====================================================================
        # These are populated after market settles
        "result": market.get("result"),  # 'yes', 'no', or None
        "settlement_value": market.get("settlement_value"),  # 0 or 100
    }

    return parsed


def main():
    print("=" * 80)
    print("KALSHI API EXPLORER")
    print("=" * 80)

    # ========================================================================
    # STEP 1: Fetch raw JSON response
    # ========================================================================
    print("\n[1] Fetching active markets from Kalshi...")
    print("-" * 40)

    try:
        raw_response = fetch_active_markets(limit=5, status="open")

        print("\n📋 RAW JSON RESPONSE (first 2 markets):")
        print("-" * 40)
        # The response has a 'markets' key containing the list
        markets_list = raw_response.get("markets", [])
        sample = markets_list[:2]
        print(json.dumps(sample, indent=2))

        # ====================================================================
        # STEP 2: Parse and display cleaned data
        # ====================================================================
        print("\n\n✅ PARSED MARKET DATA:")
        print("=" * 80)

        for i, market in enumerate(markets_list, 1):
            parsed = parse_market_data(market)

            print(f"\n📊 Market #{i}")
            print(f"   Ticker:          {parsed['ticker']}")  # Market ID
            print(f"   Event:           {parsed['event_ticker']}")  # Parent event
            print(f"   Title:           {parsed['title']}")  # Question
            print(
                f"   Subtitle:        {parsed['subtitle'][:60]}..."
                if len(parsed["subtitle"]) > 60
                else f"   Subtitle:        {parsed['subtitle']}"
            )
            print(f"   Status:          {parsed['status']}")
            print(f"   ---")
            print(
                f"   Yes Bid/Ask:     {parsed['yes_bid']} / {parsed['yes_ask']}"
            )  # <-- PRICE/PROBABILITY
            print(
                f"   No Bid/Ask:      {parsed['no_bid']} / {parsed['no_ask']}"
            )  # <-- PRICE/PROBABILITY
            print(
                f"   Last Price:      {parsed['last_price']}"
            )  # <-- PRICE/PROBABILITY
            print(
                f"   Implied Prob:    {parsed['implied_probability']}"
            )  # <-- PROBABILITY
            print(f"   ---")
            print(f"   Close Time:      {parsed['close_time']}")  # When trading ends
            print(
                f"   Result:          {parsed['result'] or 'Not yet settled'}"
            )  # <-- RESOLUTION
            print("-" * 40)

        # ====================================================================
        # STEP 3: Key fields summary
        # ====================================================================
        print("\n\n📚 KEY FIELDS REFERENCE:")
        print("=" * 80)
        print(
            """
PROBABILITY/PRICE FIELDS:
  - Prices are in CENTS (0-100) = percentage probability
  - 'yes_bid': Best bid price for Yes contracts
  - 'yes_ask': Best ask price for Yes contracts  
  - 'no_bid': Best bid price for No contracts
  - 'no_ask': Best ask price for No contracts
  - 'last_price': Most recent trade price
  
  Example: yes_bid=72, yes_ask=75 means ~73.5% implied probability

STATUS VALUES:
  - 'unopened': Not yet trading
  - 'open': Currently active and tradeable
  - 'closed': Trading ended, awaiting settlement
  - 'settled': Final outcome determined

RESOLUTION FIELDS (after settlement):
  - 'result': Final outcome ('yes' or 'no')
  - 'settlement_value': Payout (100 for winners, 0 for losers)
  - After settlement, holding 1 Yes contract pays $1.00 if 'yes' wins
        """
        )

        # ====================================================================
        # AUTHENTICATION NOTE
        # ====================================================================
        print("\n\n🔐 AUTHENTICATION (for private endpoints):")
        print("=" * 80)
        print(
            """
The above endpoints are PUBLIC and require NO authentication.

For PRIVATE endpoints (orders, portfolio, trading), you need:

1. Generate API keys at: https://kalshi.com → Account & Security → API Keys

2. Each authenticated request requires these headers:
   - KALSHI-ACCESS-KEY: Your API Key ID
   - KALSHI-ACCESS-TIMESTAMP: Request timestamp in milliseconds
   - KALSHI-ACCESS-SIGNATURE: HMAC signature of the request

3. Example header construction:

   import time
   import hmac
   import hashlib
   import base64
   
   def sign_request(method, path, private_key):
       timestamp = str(int(time.time() * 1000))
       message = f"{timestamp}{method.upper()}{path}"
       signature = hmac.new(
           private_key.encode(),
           message.encode(),
           hashlib.sha256
       ).digest()
       return {
           "KALSHI-ACCESS-KEY": "YOUR_API_KEY_ID",
           "KALSHI-ACCESS-TIMESTAMP": timestamp,
           "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode()
       }

NOTE: Authentication tokens expire every 30 minutes.
        """
        )

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
