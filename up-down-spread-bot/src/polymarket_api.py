"""
Polymarket API integration for market outcome verification
"""

import requests
import json
from typing import Optional, Dict

GAMMA_API = "https://gamma-api.polymarket.com"

def get_market_outcome(slug: str, timeout: int = 10) -> Dict:
    """
    Get market outcome from Polymarket API
    
    Returns:
        {
            "success": bool,
            "winner": "UP" | "DOWN" | None,
            "resolved": bool,
            "closed": bool,
            "error": str (if success=False)
        }
    """
    try:
        url = f"{GAMMA_API}/events?slug={slug}"
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        
        events = resp.json()
        if not events or len(events) == 0:
            return {
                "success": False,
                "error": f"Market not found in API: {slug}"
            }
        
        event = events[0]
        markets = event.get("markets", [])
        
        if not markets:
            return {
                "success": False,
                "error": f"No markets in event: {slug}"
            }
        
        market = markets[0]
        
        # Parse outcomes and prices
        outcomes = market.get("outcomes", [])
        prices = market.get("outcomePrices", [])
        
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        if isinstance(prices, str):
            prices = json.loads(prices)
        
        # Get status
        closed = market.get("closed", False)
        resolved = market.get("resolved", False)
        
        # Determine winner by prices (winner has price = $1.00)
        winner = None
        if prices and len(prices) >= 2:
            price_up = float(prices[0])
            price_down = float(prices[1])
            
            if price_up > 0.99:
                winner = "UP"
            elif price_down > 0.99:
                winner = "DOWN"
        
        return {
            "success": True,
            "winner": winner,
            "resolved": resolved,
            "closed": closed,
            "outcomes": outcomes,
            "prices": prices
        }
        
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": f"API timeout for {slug}"
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"API request failed: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

