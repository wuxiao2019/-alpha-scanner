import requests
from config import *

DEX_CACHE = {}

def get_dex(symbol):
    if symbol in DEX_CACHE:
        return DEX_CACHE[symbol]

    url = f"https://api.dexscreener.com/latest/dex/search?q={symbol}"

    try:
        data = requests.get(url, timeout=10).json()
        pairs = data.get("pairs", [])

        if not pairs:
            return None

        best = max(pairs, key=lambda x: x.get("liquidity", {}).get("usd", 0))

        result = {
            "price": float(best.get("priceUsd") or 0),
            "liquidity": float(best.get("liquidity", {}).get("usd") or 0),
            "volume": float(best.get("volume", {}).get("h24") or 0),
            "url": best.get("url")
        }

        DEX_CACHE[symbol] = result
        return result

    except:
        return None
