"""跌深反彈策略主程式"""

import os
import sys
import time
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from stock_strategies.sheet import read_watchlist
from stock_strategies.notify import send_telegram
from stock_strategies.dip_strategy import evaluate_dip


REQUIRED_ENV = ["FINMIND_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]


def main():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(f"缺少環境變數: {missing}", file=sys.stderr)
        sys.exit(1)

    # 1. 讀 watchlist
    print(f"[{datetime.now()}] 讀取 watchlist...")
    watchlist = read_watchlist()
    print(f"  -> {len(watchlist)} 檔啟用中")

    # 2. 逐檔評估
    dips = []
    rebounds = []
    for i, row in enumerate(watchlist, 1):
        sid = str(row["stock_id"])
        name = row.get("name", "")
        r = evaluate_dip(sid, name)
        if r["action"] == "DIP":
            dips.append(r)
            print(f"[{i}/{len(watchlist)}] {sid} {name} -> DIP ({r['drawdown_pct']}%)")
        elif r["action"] == "REBOUND":
            rebounds.append(r)
            print(f"[{i}/{len(watchlist)}] {sid} {name} -> REBOUND")
        else:
            reason = " / ".join(r.get("risk_notes", [])) or "未達條件"
            print(f"[{i}/{len(watchlist)}] {sid} {name} -> SKIP: {reason}")
        time.sleep(0.3)

    # 3. 組訊息
    lines = [
        f"📉 *跌深反彈警示* — {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"掃描：{len(watchlist)} 檔 | 跌深：{len(dips)} 檔 | 反彈成功：{len(rebounds)} 檔",
        "",
    ]

    if dips:
        lines.append("*【跌深標的】*")
        for d in dips:
            lines.append(f"*{d['stock_id']} {d['name']}*")
            lines.append(f"  252 日高點：{d['high_252']}")
            lines.append(f"  現價：{d['close']}（{d['drawdown_pct']}%）")
            lines.append(f"  分批進場：")
            lines.append(f"    第 1 批（-20%）：{d['entry_1']}")
            lines.append(f"    第 2 批（-25%）：{d['entry_2']}")
            lines.append(f"    第 3 批（-30%）：{d['entry_3']}")
            lines.append(f"    第 4 批（-35%）：{d['entry_4']}")
            lines.append("")

    if rebounds:
        lines.append("*【反彈成功】*")
        for r in rebounds:
            lines.append(f"*{r['stock_id']} {r['name']}*")
            lines.append(f"  反彈一半價位：{r.get('half_rebound_price', '-')}")
            lines.append("")

    if not dips and not rebounds:
        lines.append("今日無跌深或反彈成功的標的。")

    msg = "\n".join(lines)
    print("發送 Telegram...")
    send_telegram(msg)
    print("完成")


if __name__ == "__main__":
    main()
