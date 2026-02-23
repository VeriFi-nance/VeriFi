"""
Polymarket Gamma API Service
============================
Fetches market data from Polymarket's Gamma API.
Base URL: https://gamma-api.polymarket.com

Key endpoints:
- GET /markets - List markets (paginated)
- GET /events - List events (which contain markets)

No authentication required for read-only access.
"""

import requests


def list_markets(base_url: str, limit: int = 50, **params):
    """
    Fetch markets from Polymarket Gamma API.
    
    Args:
        base_url: API base URL
        limit: Number of markets to fetch
        **params: Additional query parameters (e.g., closed=false, order=id)
    
    Returns:
        List of market objects
    
    Key response fields:
        - id: Market identifier
        - question: The prediction question
        - outcomePrices: JSON array of probabilities [yes_prob, no_prob]
        - closed: Boolean, True if market has resolved
        - active: Boolean, True if trading is enabled
        - endDate: ISO timestamp when market closes
    """
    url = f"{base_url}/markets"
    query_params = {"limit": limit, **params}
    
    response = requests.get(url, params=query_params)
    response.raise_for_status()
    return response.json()


def get_market(base_url: str, condition_id: str):
    """
    Fetch a single market by condition ID.
    
    Args:
        base_url: API base URL
        condition_id: The market's condition ID
    
    Returns:
        Market object
    """
    url = f"{base_url}/markets/{condition_id}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def list_events(base_url: str, limit: int = 50, **params):
    """
    Fetch events from Polymarket Gamma API.
    Events are containers for related markets.
    
    Args:
        base_url: API base URL
        limit: Number of events to fetch
        **params: Additional query parameters
    
    Returns:
        List of event objects (each containing markets)
    """
    url = f"{base_url}/events"
    query_params = {"limit": limit, **params}
    
    response = requests.get(url, params=query_params)
    response.raise_for_status()
    return response.json()
