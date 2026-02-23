"""
Kalshi Trading API Service
==========================
Fetches market data from Kalshi's public API.
Base URL: https://api.elections.kalshi.com/trade-api/v2
"""

import requests
from typing import Optional


def list_markets(base_url: str, api_key: str = "", limit: int = 50, cursor: Optional[str] = None, **params):
    """
    Fetch markets from Kalshi API.
    """
    url = f"{base_url}/markets"
    query_params = {"limit": limit, **params}
    
    if cursor:
        query_params["cursor"] = cursor
    
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    response = requests.get(url, params=query_params, headers=headers)
    response.raise_for_status()
    return response.json()


def get_market(base_url: str, ticker: str, api_key: str = ""):
    """Fetch a single market by ticker."""
    url = f"{base_url}/markets/{ticker}"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def list_events(base_url: str, api_key: str = "", limit: int = 50, cursor: Optional[str] = None, **params):
    """Fetch events from Kalshi API."""
    url = f"{base_url}/events"
    query_params = {"limit": limit, **params}
    
    if cursor:
        query_params["cursor"] = cursor
    
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = requests.get(url, params=query_params, headers=headers)
    response.raise_for_status()
    return response.json()


def get_orderbook(base_url: str, ticker: str, api_key: str = ""):
    """Fetch the order book for a specific market."""
    url = f"{base_url}/markets/{ticker}/orderbook"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
