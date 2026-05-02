def risk_score(mcap, liq, vol, listed):

    score = 0
    reasons = []

    if mcap < 5_000_000:
        score += 40
        reasons.append("低市值")

    if liq < 50_000:
        score += 30
        reasons.append("低流动性")

    if vol < 20_000:
        score += 20
        reasons.append("低交易量")

    if not listed:
        score += 10
        reasons.append("未上币安现货")

    if score >= 70:
        return "HIGH", reasons
    elif score >= 40:
        return "MEDIUM", reasons
    else:
        return "WATCHLIST", reasons
