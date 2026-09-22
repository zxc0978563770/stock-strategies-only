"""跌深反彈主程式"""

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
from stock_strategies.dip_tracker import read_tracker, upsert_tracker


REQUIRED_ENV = ["FINMIND_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]


def main():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(f"缺少環境變數: {missing}", file=sys.stderr)
        sys.exit(1)

    print(f"[{datetime.now()}] 讀取 watchlist...")
    watchlist = read_watchlist()
    print(f"  -> {len(watchlist)} 檔啟用中")

    print("讀取 DipTracker...")
    tracker = read_tracker()
    print(f"  -> 追蹤中：{len(tracker)} 檔")

    new_dips = []
    rebounds = []
    today = datetime.now().strftime("%Y-%m-%d")

    for i, row in enumerate(watchlist, 1):
        sid = str(row["stock_id"])
        name = row.get("name", "")
        tracked = tracker.get(sid)

        r = evaluate_dip(sid, name, tracked=tracked)

        if r["action"] == "DIP":
            new_dips.append(r)
            tracker[sid] = {
                "name": name,
                "high_252": r["high_252"],
                "low": r["low"],
                "rebound_done": "FALSE",
                "first_seen": today,
            }
            print(f"[{i}/{len(watchlist)}] {sid} {name} -> DIP ({r['drawdown_pct']}%)")
        elif r["action"] == "REBOUND":
            rebounds.append(r)
            tracker[sid]["low"] = r["low"]
            tracker[sid]["rebound_done"] = "TRUE"
            print(f"[{i}/{len(watchlist)}] {sid} {name} -> REBOUND")
        elif r["action"] == "TRACKING":
            tracker[sid]["low"] = r["low"]
            print(f"[{i}/{len(watchlist)}] {sid} {name} -> TRACKING（最低 {r['low']}）")
        else:
            reason = " / ".join(r.get("risk_notes", [])) or r["action"]
            print(f"[{i}/{len(watchlist)}] {sid} {name} -> {reason}")
        time.sleep(0.3)

    print("寫回 DipTracker...")
    upsert_tracker(tracker)

    lines = [
        f"📉 *跌深反彈警示* — {today}",
        "",
        f"掃描：{len(watchlist)} 檔 | 新跌深：{len(new_dips)} 檔 | 反彈成功：{len(rebounds)} 檔",
        "",
    ]

    if new_dips:
        lines.append("*【新跌深標的】*")
        for d in new_dips:
            lines.append(f"*{d['stock_id']} {d['name']}*")
            lines.append(f"  252 日高點：{d['high_252']}")
            lines.append(f"  現價：{d['close']}（{d['drawdown_pct']}%）")
            lines.append(f"  從 60 日低點反彈：{d.get('rebound_pct', 0)}%")
            lines.append(f"  參考分批進場：")
            lines.append(f"    第 1 批（-20%）：{d['entry_1']}")
            lines.append(f"    第 2 批（-25%）：{d['entry_2']}")
            lines.append(f"    第 3 批（-30%）：{d['entry_3']}")
            lines.append(f"    第 4 批（-35%）：{d['entry_4']}")
            lines.append("")

    if rebounds:
        lines.append("*【反彈成功】*")
        for r in rebounds:
            lines.append(f"*{r['stock_id']} {r['name']}*")
            lines.append(f"  最低點：{r['low']}")
            lines.append(f"  反彈一半價位：{r.get('half_rebound_price', '-')}")
            lines.append(f"  現價：{r['close']}")
            lines.append("")

    if not new_dips and not rebounds:
        lines.append("今日無新跌深或反彈成功的標的。")

    msg = "\n".join(lines)
    print("發送 Telegram...")
    send_telegram(msg)
    print("完成")


if __name__ == "__main__":
    main()
