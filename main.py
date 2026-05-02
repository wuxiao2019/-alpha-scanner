import requests
import time
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ===== 配置 =====
SHEET_ID = "1GYsNqDXZn-VXvJfVE0QRQg4b02zKVWjgPww19O4qHtE"  # ← 替换成你的真实表格ID！

# 币安官方 Alpha API（基于 SDK 文档）
BINANCE_ALPHA_APIS = [
    "https://www.binance.com/bapi/defi/v1/public/alpha/tokens",
    "https://www.binance.com/bapi/alpha/v1/public/alpha-trade/tokens",
    "https://www.binance.com/bapi/defi/v1/public/alpha/all-coins",
]

# 请求头（模拟浏览器）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.binance.com/zh-CN/markets/alpha-all",
    "Origin": "https://www.binance.com"
}

# ===== 带重试的请求函数 =====
def fetch_with_retry(url, headers=None, max_retries=3, timeout=15):
    for i in range(max_retries):
        try:
            print(f"  第 {i+1} 次请求: {url[:70]}...")
            response = requests.get(url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                print(f"  ✅ 请求成功")
                return response
            elif response.status_code == 429:
                wait_time = 5 * (i + 1)
                print(f"  ⏳ 请求太频繁，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"  ❌ 状态码: {response.status_code}")
                if i < max_retries - 1:
                    time.sleep(2 ** i)
        except Exception as e:
            print(f"  💥 异常: {e}")
            if i < max_retries - 1:
                time.sleep(2 ** i)
    
    return None

# ===== 连接 Google 表格 =====
def connect_sheet():
    try:
        creds = Credentials.from_service_account_file(
            "credentials.json",
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        print("✅ 成功连接 Google 表格")
        return sheet
    except Exception as e:
        print(f"❌ 连接表格失败: {e}")
        return None

# ===== 从币安 Alpha API 获取数据 =====
def get_binance_alpha_tokens():
    """
    尝试多个币安 Alpha API 端点，直到找到可用的
    """
    all_tokens = []
    
    # 尝试每个 API 端点
    for api_url in BINANCE_ALPHA_APIS:
        print(f"\n{'='*60}")
        print(f"尝试 API: {api_url}")
        print(f"{'='*60}")
        
        # 分页抓取（币安 Alpha 有43页）
        for page in range(1, 44):  # 1-43页
            try:
                # 构建分页 URL
                if "?" in api_url:
                    url = f"{api_url}&page={page}&size=20"
                else:
                    url = f"{api_url}?page={page}&size=20"
                
                print(f"\n抓取第 {page}/43 页...")
                response = fetch_with_retry(url, headers=HEADERS, max_retries=2)
                
                if not response:
                    print(f"第 {page} 页失败，跳过")
                    continue
                
                data = response.json()
                print(f"响应结构: {list(data.keys()) if isinstance(data, dict) else '非字典'}")
                
                # 解析不同可能的数据结构
                tokens = []
                if isinstance(data, dict):
                    if "data" in data and isinstance(data["data"], dict):
                        if "list" in data["data"]:
                            tokens = data["data"]["list"]
                        elif "tokens" in data["data"]:
                            tokens = data["data"]["tokens"]
                        elif "coins" in data["data"]:
                            tokens = data["data"]["coins"]
                    elif "list" in data:
                        tokens = data["list"]
                    elif "tokens" in data:
                        tokens = data["tokens"]
                
                print(f"第 {page} 页获取到 {len(tokens)} 个代币")
                
                if len(tokens) == 0:
                    print("本页无数据，可能已到达末尾")
                    break
                
                for token in tokens:
                    try:
                        # 提取关键字段（适配不同字段名）
                        symbol = token.get("symbol") or token.get("assetCode") or token.get("name", "UNKNOWN")
                        price = float(token.get("price") or token.get("lastPrice") or token.get("currentPrice") or 0)
                        market_cap = float(token.get("marketCap") or token.get("marketCapitalization") or token.get("cap") or 0)
                        volume_24h = float(token.get("volume24h") or token.get("volume") or token.get("totalVolume") or 0)
                        change_24h = float(token.get("change24h") or token.get("priceChangePercent") or token.get("change") or 0)
                        
                        # 币安 Alpha 页面链接（必须是币安链接！）
                        alpha_url = f"https://www.binance.com/zh-CN/alpha/{symbol}"
                        
                        token_info = {
                            "symbol": symbol,
                            "price": price,
                            "market_cap": market_cap,
                            "volume_24h": volume_24h,
                            "change_24h": change_24h,
                            "url": alpha_url  # ← 币安官方链接！
                        }
                        
                        all_tokens.append(token_info)
                        
                    except Exception as e:
                        print(f"  解析代币出错: {e}")
                        continue
                
                # 礼貌等待
                time.sleep(0.3)
                
            except Exception as e:
                print(f"第 {page} 页异常: {e}")
                continue
        
        # 如果获取到数据，就不再尝试其他 API
        if len(all_tokens) > 0:
            print(f"\n✅ API 成功！共获取 {len(all_tokens)} 个代币")
            break
        else:
            print(f"\n❌ 此 API 无数据，尝试下一个...")
    
    return all_tokens

# ===== 风险检测 =====
def check_risk(market_cap, volume_24h):
    risk_score = 0
    reasons = []
    
    if market_cap < 10000:
        risk_score += 40
        reasons.append("市值极低(<$10K)")
    elif market_cap < 50000:
        risk_score += 20
        reasons.append("市值很低(<$50K)")
    
    if volume_24h == 0:
        risk_score += 30
        reasons.append("无成交量")
    elif volume_24h < 1000:
        risk_score += 15
        reasons.append("成交量极低")
    
    if risk_score >= 50:
        return "HIGH", "; ".join(reasons)
    elif risk_score >= 25:
        return "MEDIUM", "; ".join(reasons)
    else:
        return "LOW", "风险较低"

# ===== 增量更新表格 =====
def update_sheet_incremental(sheet, new_results):
    headers = ["时间", "币种", "价格", "市值", "24h成交量", "24h涨跌", "风险等级", "风险原因", "币安Alpha链接"]
    
    # 获取现有数据
    try:
        existing_data = sheet.get_all_records()
    except:
        sheet.clear()
        sheet.append_row(headers)
        existing_data = []
    
    # 已存在的币种
    existing_symbols = {row.get("币种", "") for row in existing_data}
    
    # 筛选新币种
    to_add = []
    for row in new_results:
        symbol = row[1]
        if symbol not in existing_symbols:
            to_add.append(row)
            existing_symbols.add(symbol)
    
    # 批量追加
    if to_add:
        sheet.append_rows(to_add)
        print(f"✅ 新增 {len(to_add)} 条数据")
    
    return len(existing_data) + len(to_add)

# ===== 主程序 =====
def main():
    print(f"\n{'='*60}")
    print(f"🤖 币安 Alpha Scanner 启动")
    print(f"⏰ 时间: {datetime.now()}")
    print(f"{'='*60}\n")
    
    # 连接表格
    sheet = connect_sheet()
    if not sheet:
        print("无法连接表格，退出")
        return
    
    # 获取币安 Alpha 代币
    tokens = get_binance_alpha_tokens()
    print(f"\n总共获取到 {len(tokens)} 个代币")
    
    # 筛选市值 < 100万
    filtered = []
    for token in tokens:
        if 0 < token["market_cap"] < 1_000_000:
            risk, reason = check_risk(token["market_cap"], token["volume_24h"])
            filtered.append({
                **token,
                "risk": risk,
                "risk_reason": reason
            })
    
    print(f"符合条件的代币 (市值<$1M): {len(filtered)} 个")
    
    # 准备表格数据
    results = []
    for token in filtered:
        results.append([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            token["symbol"],
            f"${token['price']:.8f}" if token['price'] < 0.01 else f"${token['price']:.4f}",
            f"${token['market_cap']:,.0f}",
            f"${token['volume_24h']:,.0f}",
            f"{token['change_24h']:+.2f}%",
            token["risk"],
            token["risk_reason"],
            token["url"]  # ← 币安链接！
        ])
    
    # 增量更新
    total = update_sheet_incremental(sheet, results)
    print(f"表格总数据: {total} 条")
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    main()
