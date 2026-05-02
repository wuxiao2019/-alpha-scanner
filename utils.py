from datetime import datetime
from zoneinfo import ZoneInfo

def now_beijing():
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
