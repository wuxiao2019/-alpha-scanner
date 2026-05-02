import requests
import time
import base64
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials

from config import *

session = requests.Session()

# ===== 初始化凭证 =====
def init_credentials():
    creds_base64 = os.getenv("GOOGLE_CREDS")
    if creds_base64:
        with open("credentials.json", "wb") as f:
            f.write(base64.b64decode(creds_base64))


# ===== 北京时间 =====
def get_beijing_time():
    return datetime.now(ZoneInfo("Asia/Shanghai"))


# ===== 连接 Sheet =====
def connect_sheet():
    creds = Credentials.from_service_account_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1


# ===== Binance Alpha =====
def fetch_alpha(page):
    url = f"https://www.binance.com/bapi/defi/v1/public/alpha/tokens?page={page}&size=20"
    try:
        return session.get(url, timeout=10).json()
    except:
        return None


def get_alpha_tokens():
    tokens = []
    seen = set()

    for page in range(1, 100):
        data = fetch_alpha(page)
        if not data:
            break

        lst = data.get("data", {}).get("list", [])
        if not lst:
            break

        for t in lst:
            symbol = (
                t.get("baseAsset") or
                t.get("tokenSymbol") or
                t.get("symbol") or
                t.get("name")
            )

            if not symbol:
                continue

            symbol = symbol.upper()

            # 清洗
            if len(symbol) > 12 or " " in symbol:
                continue

            if symbol in seen:
                continue

            seen.add(symbol)

            try:
                tokens.append({
                    "symbol": symbol,
                    "market_cap": float(t.get("marketCap", 0))
                })
            except:
                continue

        if len(lst) < 20:
            break

        time.sleep(0.2)

    return tokens


# ===== Binance Spot =====
def get_spot_symbols():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    data = session.get(url).json()
    return {s["baseAsset"] for s in data["symbols"]}


# ===== Dexscreener =====
def get_dex(symbol):
    url = f"https://api.dexscreener.com/latest/dex/search?q={symbol}"

    try:
        data = session.get(url, timeout=10).json()
        pairs = data.get("pairs", [])

        if not pairs:
            return None

        best = max(pairs, key=lambda x: x.get("liquidity", {}).get("usd", 0))

        return {
            "price": float(best.get("priceUsd", 0)),
            "liquidity": float(best.get("liquidity", {}).get("usd", 0)),
            "volume": float(best.get("volume", {}).get("h24", 0)),
            "url": best.get("url")
        }
    except:
        return None


# ===== 风险 =====
def risk(mcap, liq, vol, listed):
    score = 0
    reasons = []

    if mcap < LOW_MARKET_CAP:
        score += 30
        reasons.append("低市值")

    if liq < LOW_LIQUIDITY:
        score += 25
        reasons.append("低流动性")

    if vol < LOW_VOLUME:
        score += 15
        reasons.append("低交易量")

    if not listed:
        score += 10
        reasons.append("未上币安")

    if score >= 50:
        return "HIGH", ",".join(reasons)
    elif score >= 25:
        return "MEDIUM", ",".join(reasons)
    return "LOW", "正常"


# ===== 主流程 =====
def main():
    print("启动:", get_beijing_time())

    init_credentials()
    sheet = connect_sheet()

    alpha = get_alpha_tokens()
    spot = get_spot_symbols()

    rows = []
    now = get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")

    for t in alpha:
        symbol = t["symbol"]
        mcap = t["market_cap"]

        if not mcap or mcap > MAX_MARKET_CAP:
            continue

        dex = get_dex(symbol)
        if not dex:
            continue

        if dex["liquidity"] < MIN_LIQUIDITY:
            continue

        listed = symbol in spot

        r, reason = risk(mcap, dex["liquidity"], dex["volume"], listed)

        rows.append([
            now,
            symbol,
            dex["price"],
            mcap,
            dex["liquidity"],
            dex["volume"],
            "是" if listed else "否",
            r,
            reason,
            dex["url"]
        ])

        time.sleep(0.2)

    if rows:
        sheet.append_rows(rows, value_input_option="RAW")

    print("完成:", len(rows))


if __name__ == "__main__":
    main()
