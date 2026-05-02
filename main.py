import requests
import time
import json
from datetime import datetime
from web3 import Web3
import gspread
from google.oauth2.service_account import Credentials
import config

# ===== 第一部分：连接 Google 表格 =====
def connect_sheet():
    """
    这个函数就像机器人的"钥匙"，用来打开你的 Google 表格
    """
    try:
        # 读取凭证文件
        creds = Credentials.from_service_account_file(
            "credentials.json",
            scopes=["https://www.googleapis.com/auth/spreadsheets",
                   "https://www.googleapis.com/auth/drive"]
        )
        # 授权并打开表格
        client = gspread.authorize(creds)
        sheet = client.open(config.SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        print(f"连接表格失败: {e}")
        return None

# ===== 第二部分：获取区块链数据 =====
def get_token_info(contract_address, chain="bsc"):
    """
    这个函数去区块链上查币的真实信息
    就像去银行查账户余额一样
    """
    # 根据链选择不同的网络地址
    if chain == "bsc":
        rpc_url = config.BSC_RPC
    else:
        rpc_url = config.ETH_RPC
    
    try:
        # 连接到区块链网络
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # 检查连接是否成功
        if not w3.is_connected():
            return None
        
        # ERC20 代币标准接口（就像通用的"查询语言"）
        erc20_abi = [
            {
                "constant": True,
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]
        
        # 创建合约对象
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=erc20_abi
        )
        
        # 查询总供应量
        supply = contract.functions.totalSupply().call()
        # 查询小数位数（比如 18 表示要除以 10^18）
        decimals = contract.functions.decimals().call()
        
        # 计算真实供应量
        real_supply = supply / (10 ** decimals)
        
        return {
            "supply": real_supply,
            "decimals": decimals
        }
        
    except Exception as e:
        print(f"查询区块链失败 {contract_address}: {e}")
        return None

# ===== 第三部分：风险检测 =====
def check_risk(liquidity, supply, holders=None):
    """
    这个函数判断一个币是不是骗子项目
    就像银行的风控系统
    """
    risk_score = 0
    reasons = []
    
    # 检查1：流动性太低（容易跑路）
    if liquidity < 20000:
        risk_score += 40
        reasons.append("流动性极低")
    elif liquidity < 50000:
        risk_score += 20
        reasons.append("流动性较低")
    
    # 检查2：供应量异常
    if supply > 1e15:  # 超过 1 千万亿
        risk_score += 30
        reasons.append("供应量异常巨大")
    
    # 检查3：持仓集中度（如果有数据）
    if holders and holders.get("top10_percent", 0) > 80:
        risk_score += 30
        reasons.append("持仓高度集中")
    
    # 判断风险等级
    if risk_score >= 60:
        return "HIGH", "; ".join(reasons)
    elif risk_score >= 30:
        return "MEDIUM", "; ".join(reasons)
    else:
        return "LOW", "风险较低"

# ===== 第四部分：从 Binance Alpha 获取数据 =====
def get_alpha_tokens():
    """
    这个函数去 Binance Alpha 页面"抓"数据
    就像用望远镜观察远处的船只
    """
    tokens = []
    
    # 注意：这里使用 DexScreener API 作为替代方案
    # 因为 Binance Alpha 没有公开的免费 API
    try:
        # 尝试从 DexScreener 获取热门新币
        response = requests.get(
            "https://api.dexscreener.com/latest/dex/search?q=binance%20alpha",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            pairs = data.get("pairs", [])
            
            for pair in pairs[:50]:  # 只取前50个
                token = {
                    "symbol": pair.get("baseToken", {}).get("symbol", "UNKNOWN"),
                    "name": pair.get("baseToken", {}).get("name", "Unknown"),
                    "price": float(pair.get("priceUsd", 0)),
                    "liquidity": float(pair.get("liquidity", {}).get("usd", 0)),
                    "contract": pair.get("baseToken", {}).get("address"),
                    "chain": pair.get("chainId", "bsc"),
                    "url": pair.get("url", "")
                }
                tokens.append(token)
                
    except Exception as e:
        print(f"获取数据失败: {e}")
    
    return tokens

# ===== 第五部分：主程序 =====
def main():
    """
    这是机器人的"大脑"，协调所有工作
    """
    print(f"开始扫描... {datetime.now()}")
    
    # 1. 连接表格
    sheet = connect_sheet()
    if not sheet:
        print("无法连接表格，程序结束")
        return
    
    # 2. 获取代币列表
    tokens = get_alpha_tokens()
    print(f"获取到 {len(tokens)} 个代币")
    
    # 3. 处理每个代币
    results = []
    
    for token in tokens:
        try:
            symbol = token["symbol"]
            price = token["price"]
            contract = token["contract"]
            liquidity = token["liquidity"]
            chain = token["chain"]
            
            # 跳过没有合约地址的
            if not contract:
                continue
            
            # 查询链上数据
            chain_info = get_token_info(contract, chain)
            
            if chain_info:
                supply = chain_info["supply"]
                market_cap = price * supply
                
                # 筛选：市值小于 100万
                if market_cap > config.MAX_MARKET_CAP:
                    continue
                
                # 风险检测
                risk, reason = check_risk(liquidity, supply)
                
                # 记录结果
                results.append([
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    symbol,
                    f"${price:.6f}",
                    f"${market_cap:,.0f}",
                    f"${liquidity:,.0f}",
                    risk,
                    reason,
                    token.get("url", "")
                ])
                
                print(f"✓ {symbol}: 市值 ${market_cap:,.0f}, 风险: {risk}")
            
            # 礼貌地等待一下，不要请求太快
            time.sleep(1)
            
        except Exception as e:
            print(f"处理 {symbol} 时出错: {e}")
            continue
    
    # 4. 更新表格
    if results:
        # 清空旧数据
        sheet.clear()
        
        # 写入表头
        headers = ["时间", "币种", "价格", "市值", "流动性", "风险等级", "风险原因", "链接"]
        sheet.append_row(headers)
        
        # 写入数据
        for row in results:
            sheet.append_row(row)
        
        print(f"完成！共更新 {len(results)} 条数据")
    else:
        print("没有符合条件的数据")

# 程序入口
if __name__ == "__main__":
    main()
