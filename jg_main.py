"""JG 反市場策略主程式

每日掃描 Watchlist，套用 JG 進場條件，推播 Telegram。
"""

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
from stock_strategies.jg_strategy import evaluate_jg, get_market_ok


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

    # 2. 大盤濾鏡
    print("判斷大盤多空...")
    market_ok, market_note = get_market_ok()
    print(f"  -> {market_note}")

    if not market_ok:
        print("大盤空頭，JG 策略不做多，結束。")
        send_telegram(f"📉 *JG 反市場策略*\n\n{market_note}\n\n大盤空頭，今日不做多。")
        return

    # 3. 逐檔評估
    buys = []
    for i, row in enumerate(watchlist, 1):
        sid = str(row["stock_id"])
        name = row.get("name", "")
        print(f"[{i}/{len(watchlist)}] {sid} {name}")
        r = evaluate_jg(sid, name, market_ok=True)
        if r["action"] == "BUY":
            buys.append(r)
        time.sleep(0.3)

    # 4. 組訊息
    lines = [
        f"🎯 *JG 反市場策略* — {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"大盤：{market_note}",
        f"掃描：{len(watchlist)} 檔 | 符合：{len(buys)} 檔",
        "",
    ]

    if not buys:
        lines.append("今日無符合 JG 條件的標的。")
    else:
        for b in buys:
            lines.append(f"*{b['stock_id']} {b['name']}*")
            lines.append(f"  進場：{b['entry_price']}")
            lines.append(f"  停損：{b['stop_loss_price']}（風報比 1:{b['risk_reward_ratio']}）")
            lines.append(f"  停利：{b['target_price']}")
            for s in b["signals"]:
                lines.append(f"  ✓ {s}")
            lines.append("")

    msg = "\n".join(lines)
    print("發送 Telegram...")
    send_telegram(msg)
    print("完成")


if __name__ == "__main__":
    main()
