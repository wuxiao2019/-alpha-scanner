import requests
import time
import base64
import os
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from config import SHEET_ID

session = requests.Session()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}

API = "https://www.binance.com/bapi/defi/v1/public/alpha/tokens"


def get_beijing_time():
    return datetime.utcnow() + timedelta(hours=8)


def init_credentials():
    creds_base64 = os.getenv("GOOGLE_CREDS")
    if creds_base64:
        with open("credentials.json", "wb") as f:
            f.write(base64.b64decode(creds_base64))


def connect_sheet():
    creds = Credentials.from_service_account_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1


def fetch(page):
    url = f"{API}?page={page}&size=20"
    try:
        res = session.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            return res.json()
    except:
        return None


def get_tokens():
    tokens_all = []
    seen = set()

    for page in range(1, 100):
        data = fetch(page)
        if not data:
            break

        tokens = data.get("data", {}).get("list", [])
        if not tokens:
            break

        for t in tokens:
            symbol = t.get("symbol")
            if not symbol or symbol in seen:
                continue

            seen.add(symbol)

            try:
                tokens_all.append({
                    "symbol": symbol,
                    "price": float(t.get("price", 0)),
                    "market_cap": float(t.get("marketCap", 0)),
                    "volume": float(t.get("volume24h", 0)),
                    "change": float(t.get("priceChangePercent", 0)),
                    "url": f"https://www.binance.com/zh-CN/alpha/{symbol}"
                })
            except:
                continue

        if len(tokens) < 20:
            break

        time.sleep(0.2)

    return tokens_all


def risk_check(mcap, vol, change):
    score = 0
    if mcap < 50000:
        score += 20
    if vol < 1000:
        score += 20
    if abs(change) > 50:
        score += 20

    if score >= 40:
        return "HIGH"
    elif score >= 20:
        return "MEDIUM"
    return "LOW"


def main():
    print("启动:", get_beijing_time())

    init_credentials()
    sheet = connect_sheet()

    tokens = get_tokens()

    now = get_beijing_time().strftime("%Y-%m-%d %H:%M")

    rows = []
    for t in tokens:
        if t["market_cap"] and t["market_cap"] < 1_000_000:
            risk = risk_check(t["market_cap"], t["volume"], t["change"])

            rows.append([
                now,
                t["symbol"],
                t["price"],
                t["market_cap"],
                t["volume"],
                t["change"],
                risk,
                t["url"]
            ])

    if rows:
        sheet.append_rows(rows, value_input_option="RAW")

    print("完成，数量:", len(rows))


if __name__ == "__main__":
    main()
