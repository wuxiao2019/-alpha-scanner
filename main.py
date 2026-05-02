import requests
import time
import json
from datetime import datetime
from web3 import Web3
import gspread
from google.oauth2.service_account import Credentials
import config

# ===== 配置 =====
SHEET_ID = "1GYsNqDXZn-VXvJfVE0QRQg4b02zKVWjgPww19O4qHtE"  # ← 替换成你的真实表格ID！

# 币安 Alpha 页面 API（通过抓包发现的内部 API）
BINANCE_ALPHA_API = "https://www.binance.com/bapi/alpha/v1/public/alpha-trade/tokens"

# 请求头（模拟浏览器）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.binance.com/zh-CN/markets/alpha-all",
    "Origin": "https://www.binance.com"
}

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

# ===== 从币安 Alpha 页面抓取数据 =====
def get_binance_alpha_tokens():
    """
    从币安 Alpha 页面 API 抓取代币数据
    """
    all_tokens = []
    
    # 币安 Alpha API 分页抓取
    for page in range(1, 44):  # 43页
        try:
            url = f"{BINANCE_ALPHA_API}?page={page}&size=20"
            print(f"正在抓取第 {page} 页...")
            
            response = requests.get(url, headers=HEADERS, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # 解析数据结构
                if "data" in data and "list" in data["data"]:
                    tokens = data["data"]["list"]
                    print(f"  第 {page} 页获取到 {len(tokens)} 个代币")
                    
                    for token in tokens:
                        try:
                            # 提取关键信息
                            symbol = token.get("symbol", "UNKNOWN")
                            price = float(token.get("price", 0) or 0)
                            market_cap = float(token.get("marketCap", 0) or 0)
                            volume_24h = float(token.get("volume24h", 0) or 0)
                            change_24h = float(token.get("change24h", 0) or 0)
                            contract = token.get("contractAddress", "")
                            chain = token.get("chain", "unknown")
                            
                            # 构建币安 Alpha 页面链接
                            alpha_url = f"https://www.binance.com/zh-CN/alpha/{symbol}"
                            
                            token_info = {
                                "symbol": symbol,
                                "price": price,
                                "market_cap": market_cap,
                                "volume_24h": volume_24h,
                                "change_24h": change_24h,
                                "contract": contract,
                                "chain": chain,
                                "url": alpha_url
                            }
                            
                            all_tokens.append(token_info)
                            
                        except Exception as e:
                            print(f"  解析代币出错: {e}")
                            continue
                else:
                    print(f"  第 {page} 页数据结构异常")
                    
            else:
                print(f"  第 {page} 页请求失败，状态码: {response.status_code}")
                
            # 礼貌等待，避免请求太快被封
            time.sleep(0.5)
            
        except Exception as e:
            print(f"抓取第 {page} 页时出错: {e}")
            continue
    
    print(f"\n总共获取到 {len(all_tokens)} 个代币")
    return all_tokens

# ===== 估算流动性 =====
def estimate_liquidity(market_cap, volume_24h):
    """
    估算流动性（币安不直接提供流动性数据）
    用市值和24h成交量估算
    """
    if volume_24h > 0:
        # 流动性大约是 24h 成交量的 10-30%
        estimated = volume_24h * 0.15
        return estimated
    else:
        # 如果没有成交量数据，用市值的 5% 估算
        return market_cap * 0.05

# ===== 风险检测 =====
def check_risk(market_cap, liquidity, volume_24h):
    """
    风险评估
    """
    risk_score = 0
    reasons = []
    
    # 检查1：市值极低
    if market_cap < 10000:
        risk_score += 40
        reasons.append("市值极低(<$10K)")
    elif market_cap < 50000:
        risk_score += 20
        reasons.append("市值很低(<$50K)")
    
    # 检查2：流动性不足
    if liquidity < 5000:
        risk_score += 30
        reasons.append("流动性极低")
    elif liquidity < 20000:
        risk_score += 15
        reasons.append("流动性较低")
    
    # 检查3：成交量异常
    if volume_24h == 0:
        risk_score += 20
        reasons.append("无成交量")
    elif volume_24h < 1000:
        risk_score += 10
        reasons.append("成交量极低")
    
    # 判断风险等级
    if risk_score >= 50:
        return "HIGH", "; ".join(reasons)
    elif risk_score >= 25:
        return "MEDIUM", "; ".join(reasons)
    else:
        return "LOW", "风险较低"

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
    
    # 筛选市值 < 100万的代币
    filtered_tokens = []
    for token in tokens:
        if 0 < token["market_cap"] < 1_000_000:
            liquidity = estimate_liquidity(token["market_cap"], token["volume_24h"])
            risk, reason = check_risk(token["market_cap"], liquidity, token["volume_24h"])
            
            filtered_tokens.append({
                **token,
                "liquidity": liquidity,
                "risk": risk,
                "risk_reason": reason
            })
    
    print(f"\n符合条件的代币 (市值<$1M): {len(filtered_tokens)} 个")
    
    # 准备表格数据
    results = []
    for token in filtered_tokens:
        results.append([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            token["symbol"],
            f"${token['price']:.8f}" if token['price'] < 0.01 else f"${token['price']:.4f}",
            f"${token['market_cap']:,.0f}",
            f"${token['liquidity']:,.0f}",
            f"${token['volume_24h']:,.0f}",
            f"{token['change_24h']:+.2f}%",
            token["risk"],
            token["risk_reason"],
            token["url"]
        ])
    
    # 写入表格
    print(f"\n正在写入表格...")
    sheet.clear()
    
    # 写入表头
    headers = ["时间", "币种", "价格", "市值", "估算流动性", "24h成交量", "24h涨跌", "风险等级", "风险原因", "币安链接"]
    sheet.append_row(headers)
    
    # 写入数据
    for row in results:
        sheet.append_row(row)
        time.sleep(0.3)
    
    print(f"\n✅ 完成！共写入 {len(results)} 条数据")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
