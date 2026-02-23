"""
Market API Explorer Views
=========================
Provides HTML page and JSON API endpoints for exploring Polymarket and Kalshi data.
"""

import json
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from .services.polymarket import list_markets as poly_list
from .services.kalshi import list_markets as kalshi_list, list_events as kalshi_events


def parse_polymarket_market(market):
    """Parse a Polymarket market into a unified format."""
    outcome_prices_str = market.get("outcomePrices")
    yes_prob = None
    if outcome_prices_str:
        try:
            prices = json.loads(outcome_prices_str)
            if len(prices) >= 1:
                yes_prob = float(prices[0]) * 100
        except (json.JSONDecodeError, ValueError):
            pass
    
    return {
        "source": "polymarket",
        "id": market.get("id") or market.get("conditionId"),
        "title": market.get("question", ""),
        "image": market.get("image") or market.get("icon"),
        "probability": yes_prob,
        "volume": market.get("volume24hr", 0) or market.get("volumeNum", 0),
        "status": "closed" if market.get("closed") else "open",
        "end_date": market.get("endDate"),
    }


def parse_kalshi_market(market):
    """Parse a Kalshi market into a unified format."""
    yes_bid = market.get("yes_bid")
    yes_ask = market.get("yes_ask")
    last_price = market.get("last_price")
    
    if yes_bid is not None and yes_ask is not None and (yes_bid > 0 or yes_ask > 0):
        prob = (yes_bid + yes_ask) / 2
    elif last_price is not None and last_price > 0:
        prob = last_price
    else:
        prob = None
    
    return {
        "source": "kalshi",
        "id": market.get("ticker"),
        "title": market.get("title", ""),
        "image": market.get("image_url"),
        "probability": prob,
        "volume": market.get("volume", 0),
        "status": market.get("status", "open"),
        "end_date": market.get("close_time"),
    }


class MarketsPage(View):
    """HTML page that displays markets from both Polymarket and Kalshi."""
    
    def get(self, request):
        markets = []
        errors = []
        
        # Fetch from Polymarket
        try:
            poly_data = poly_list(
                settings.POLYMARKET_GAMMA_BASE, 
                limit=50,
                closed="false",
                order="volume24hr",
                ascending="false"
            )
            for m in poly_data if isinstance(poly_data, list) else []:
                parsed = parse_polymarket_market(m)
                if parsed["probability"] is not None:
                    markets.append(parsed)
        except Exception as e:
            errors.append(f"Polymarket: {str(e)}")
        
        # Fetch from Kalshi
        try:
            events_data = kalshi_events(
                settings.KALSHI_BASE,
                api_key=settings.KALSHI_API,
                limit=25,
                status="open"
            )
            events = events_data.get("events", []) if isinstance(events_data, dict) else []
            
            for event in events[:20]:
                event_ticker = event.get("event_ticker")
                if not event_ticker:
                    continue
                    
                kalshi_data = kalshi_list(
                    settings.KALSHI_BASE,
                    api_key=settings.KALSHI_API,
                    limit=5,
                    event_ticker=event_ticker
                )
                kalshi_mkt_list = kalshi_data.get("markets", []) if isinstance(kalshi_data, dict) else []
                
                for m in kalshi_mkt_list:
                    parsed = parse_kalshi_market(m)
                    if parsed["probability"] is not None:
                        markets.append(parsed)
        except Exception as e:
            errors.append(f"Kalshi: {str(e)}")
        
        # Sort by probability extremity
        markets.sort(key=lambda x: abs(50 - (x["probability"] or 50)), reverse=True)
        
        context = {
            "markets": markets,
            "errors": errors,
        }
        return render(request, "markets/markets.html", context)


def markets_api(request):
    """JSON API endpoint for fetching markets from either source."""
    source = request.GET.get("source", "polymarket")
    limit = int(request.GET.get("limit", 50))
    
    try:
        if source == "kalshi":
            data = kalshi_list(
                settings.KALSHI_BASE,
                api_key=settings.KALSHI_API,
                limit=limit, 
                cursor=request.GET.get("cursor"),
                status="open"
            )
        else:
            data = poly_list(
                settings.POLYMARKET_GAMMA_BASE, 
                limit=limit,
                closed="false"
            )
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
