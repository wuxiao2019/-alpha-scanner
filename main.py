import requests
import time

from utils import now_beijing
from dex import get_dex
from coingecko import get_marketcap
from risk_engine import risk_score
from sheets import connect_sheet, write_row
from config import *

session = requests.Session()

# ===== Binance Alpha =====
def fetch_alpha(page):
    url = f"https://www.binance.com/bapi/defi/v1/public/alpha/tokens?page={page}&size=20"
    try:
        return session.get(url, timeout=10).json()
    except:
        return None


def get_tokens():
    tokens = []
    seen = set()

    for page in range(1, 30):  # 控制请求量
        data = fetch_alpha(page)
        if not data:
            break

        lst = data.get("data", {}).get("list", [])
        if not lst:
            break

        for t in lst:
            symbol = (t.get("baseAsset") or "").upper()

            if not symbol or symbol in seen:
                continue

            seen.add(symbol)

            mcap = float(t.get("marketCap") or 0)

            tokens.append({
                "symbol": symbol,
                "market_cap": mcap
            })

        if len(lst) < 20:
            break

        time.sleep(0.1)

    return tokens


# ===== 主程序 =====
def main():

    print("启动时间:", now_beijing())

    sheet = connect_sheet()

    tokens = get_tokens()

    for t in tokens:

        symbol = t["symbol"]

        dex = get_dex(symbol)
        if not dex:
            continue

        mcap = t["market_cap"]
        if not mcap:
            mcap = get_marketcap(symbol)

        level, reason = risk_score(
            mcap,
            dex["liquidity"],
            dex["volume"],
            False
        )

        if level == "WATCHLIST":
            continue

        row = [
            now_beijing(),
            symbol,
            mcap,
            dex["price"],
            dex["liquidity"],
            dex["volume"],
            level,
            ",".join(reason),
            dex["url"]
        ]

        write_row(sheet, level, row)

        time.sleep(0.2)


if __name__ == "__main__":
    main()
