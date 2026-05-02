import requests

def get_marketcap(symbol):
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/search?query={symbol}",
            timeout=10
        ).json()

        coins = r.get("coins", [])
        if not coins:
            return 0

        coin_id = coins[0]["id"]

        r2 = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}",
            timeout=10
        ).json()

        return r2.get("market_data", {}).get("market_cap", {}).get("usd", 0)

    except:
        return 0
