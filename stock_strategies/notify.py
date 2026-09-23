import os
import sys
from datetime import datetime

import numpy as np
import requests

from .config import CONFIG, TELEGRAM_API


def send_telegram(text: str):
    url = TELEGRAM_API.format(token=os.environ["TELEGRAM_BOT_TOKEN"])
    payload = {
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": text,
        "parse_mode": "Markdown",
    }
    r = requests.post(url, json=payload, timeout=10)
    if not r.ok:
        print(f"Telegram 送失敗: {r.text}", file=sys.stderr)


def send_telegram_jg(text: str, max_len: int = 4000):
    """用 JG 專用的 Bot 發送訊息（自動分段，避免超過 Telegram 4096 字元上限）。"""
    import time as _time

    token = os.environ.get("JG_TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("JG_TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("缺少 JG_TELEGRAM_BOT_TOKEN 或 JG_TELEGRAM_CHAT_ID，跳過 JG 推播")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line
    if current:
        chunks.append(current)

    print(f"訊息共 {len(text)} 字元，分成 {len(chunks)} 段發送")

    for i, chunk in enumerate(chunks, 1):
        try:
            resp = requests.post(url, json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
            }, timeout=30)
            if resp.status_code != 200:
                print(f"第 {i} 段發送失敗：{resp.status_code} {resp.text[:200]}")
            else:
                print(f"第 {i} 段發送成功")
        except Exception as e:
            print(f"第 {i} 段發送錯誤: {e}")
        _time.sleep(1)


def _trend_emoji(chg: float) -> str:
    if chg > 3:
        return "🔥"
    elif chg > 0:
        return "📈"
    elif chg > -3:
        return "📉"
    return "💥"


def _format_stock_detail(s: dict, show_trend: bool = True) -> list[str]:
    c = s.get("components", {})
    t = s.get("trend", {})
    lines = []
    wr = f"{c['backtest_winrate']*100:.0f}%" if c.get("backtest_winrate") else "N/A"
    fund = "✅" if c.get("fundamental_pass") else "❌"

    lines.append(f"*{s['stock_id']} {s['name']}*  綜合 {s['signal_score']} 分")
    if show_trend and t:
        ma_status = ""
        if t.get("above_ma20") and t.get("above_ma60"):
            ma_status = "站上月季線"
        elif t.get("above_ma20"):
            ma_status = "站上月線"
        else:
            ma_status = "月線下"
        vol_note = f"量能{'放大' if t.get('vol_ratio', 1) > 1.2 else '縮量' if t.get('vol_ratio', 1) < 0.8 else '持平'}"
        lines.append(
            f"{_trend_emoji(t.get('chg_5d', 0))} 5日{t.get('chg_5d', 0):+.1f}% | 20日{t.get('chg_20d', 0):+.1f}% | "
            f"距高點{t.get('pct_from_high', 0):.0f}% | {ma_status} | {vol_note}"
        )
    lines.append(f"📌 *明日開盤進場* | 參考價 {s['entry_price']}")
    lines.append(
        f"停損 {s['stop_loss_price']} (-{CONFIG['stop_loss']*100:.0f}%) / "
        f"目標 {s['target_price']} (+{CONFIG['target_return']*100:.0f}%)"
    )
    lines.append(f"風報比 1:{s['risk_reward_ratio']} | 建議部位 {s['position_size_pct']}%")
    lines.append(
        f"基本面{fund} | 技術分 {c.get('tech_score', 'N/A')} | 勝率 {wr} ({c.get('backtest_samples', 0)}次)"
    )
    if c.get("tech_signals"):
        lines.append(f"觸發: {', '.join(c['tech_signals'])}")
    if s.get("risk_notes"):
        lines.append(f"⚠️ {' / '.join(s['risk_notes'])}")
    return lines


def _explain_why(s: dict) -> str:
    c = s.get("components", {})
    reasons = []
    if not c.get("fundamental_pass"):
        reasons.append("基本面未達標(EPS>5,ROE>15)")
    if c.get("tech_score", 0) < 50:
        reasons.append(f"技術分僅{c.get('tech_score', 0)}(<50)")
    if s.get("signal_score", 0) < 65:
        reasons.append(f"綜合分{s.get('signal_score', 0)}(<65)")
    if not reasons:
        return "所有條件皆達標"
    return " / ".join(reasons)


def _sector_summary(signals: list[dict], watchlist: list[dict]) -> list[str]:
    cat_map = {str(w["stock_id"]): w.get("category", "其他") for w in watchlist}
    sectors = {}
    for s in signals:
        cat = cat_map.get(s["stock_id"], "其他")
        if cat not in sectors:
            sectors[cat] = {"stocks": [], "chg_5d": [], "buy": 0, "watch": 0}
        sectors[cat]["stocks"].append(s)
        t = s.get("trend", {})
        if t.get("chg_5d") is not None:
            sectors[cat]["chg_5d"].append(t["chg_5d"])
        if s.get("action") == "BUY":
            sectors[cat]["buy"] += 1
        elif s.get("action") == "WATCH":
            sectors[cat]["watch"] += 1

    ranked = sorted(
        sectors.items(),
        key=lambda x: np.mean(x[1]["chg_5d"]) if x[1]["chg_5d"] else 0,
        reverse=True,
    )

    lines = []
    for cat, d in ranked:
        avg = np.mean(d["chg_5d"]) if d["chg_5d"] else 0
        emoji = _trend_emoji(avg)
        total = len(d["stocks"])
        lines.append(
            f"{emoji} *{cat}* ({total}檔) 5日均漲{avg:+.1f}% | "
            f"BUY {d['buy']} WATCH {d['watch']}"
        )
    return lines


def _market_sentiment(signals: list[dict]) -> str:
    valid = [s for s in signals if s.get("trend")]
    if not valid:
        return "無法判斷"
    up = sum(1 for s in valid if s["trend"].get("chg_5d", 0) > 0)
    above_ma20 = sum(1 for s in valid if s["trend"].get("above_ma20"))
    pct_up = up / len(valid) * 100
    pct_ma20 = above_ma20 / len(valid) * 100

    if pct_up > 70 and pct_ma20 > 60:
        return "🟢 偏多 — 多數標的上漲且站穩月線，可積極佈局"
    elif pct_up > 50:
        return "🟡 中性偏多 — 漲多跌少但力道分歧，選股不選市"
    elif pct_up > 30:
        return "🟠 中性偏空 — 多數標的走弱，保守觀望為主"
    else:
        return "🔴 偏空 — 普遍下跌，建議空手等待"


def format_messages(
    signals: list[dict],
    watchlist: list[dict] = None,
    market: dict = None,
    night_note: str = None,
) -> list[str]:
    buys = [s for s in signals if s.get("action") == "BUY"]
    watches = [s for s in signals if s.get("action") == "WATCH"]
    skips = [s for s in signals if s.get("action") in ("SKIP", "ERROR")]
    today = datetime.now().strftime("%Y/%m/%d")
    total = len(signals)
    messages = []

    msg1 = []
    msg1.append(f"📊 *V3.0 每日選股報告* {today}")
    msg1.append(f"掃描 {total} 檔 | BUY {len(buys)} | WATCH {len(watches)} | SKIP {len(skips)}")
    msg1.append("")

    if market and market.get("note"):
        msg1.append("🎯 *大盤濾鏡*")
        msg1.append(market["note"])
        msg1.append("")

    if night_note:
        msg1.append("🌙 *夜盤濾鏡*")
        msg1.append(night_note)
        msg1.append("")

    msg1.append("🌡️ *市場氛圍*")
    msg1.append(_market_sentiment(signals))
    valid = [s for s in signals if s.get("trend")]
    if valid:
        avg_5d = np.mean([s["trend"]["chg_5d"] for s in valid])
        up_count = sum(1 for s in valid if s["trend"]["chg_5d"] > 0)
        above_ma20 = sum(1 for s in valid if s["trend"]["above_ma20"])
        msg1.append(
            f"池內均漲 {avg_5d:+.1f}% | {up_count}/{len(valid)} 檔上漲 | "
            f"{above_ma20}/{len(valid)} 檔站上月線"
        )
    msg1.append("")

    if watchlist:
        msg1.append("📡 *類股強弱排名*")
        msg1.extend(_sector_summary(signals, watchlist))
        msg1.append("")

    msg1.append("📋 *策略規則*")
    msg1.append(
        "基本面(EPS>5,ROE>15) + 技術面(均線/布林/KD/MACD) + 3年回測\n"
        f"綜合 = 基本面30% + 技術30% + 回測40%\n"
        f"BUY≥65(三關全過) | WATCH≥50\n"
        f"停損{CONFIG['stop_loss']*100:.0f}% / 停利{CONFIG['target_return']*100:.0f}% / 持有{CONFIG['hold_days']}日"
    )
    messages.append("\n".join(msg1))

    msg2 = []
    if buys:
        msg2.append(f"🟢 *BUY — 建議進場 ({len(buys)})*")
        msg2.append("")
        for s in buys:
            msg2.extend(_format_stock_detail(s))
            msg2.append(f"💡 為何買: {_explain_why(s)}")
            msg2.append("")
    else:
        msg2.append("🟢 *BUY: 今日無符合全部條件的標的*")
        msg2.append("（需基本面+技術面+回測三關全過）")
        msg2.append("")

    if watches:
        top_watches = watches[:8]
        rest_watches = watches[8:]
        msg2.append(f"🟡 *WATCH — 接近訊號 TOP {len(top_watches)}*")
        msg2.append("")
        for s in top_watches:
            msg2.extend(_format_stock_detail(s))
            msg2.append(f"❓ 差在: {_explain_why(s)}")
            msg2.append("")

        if rest_watches:
            msg2.append(f"📎 *其他觀察 ({len(rest_watches)})*")
            rest_line = ", ".join(
                [f"{s['stock_id']}{s['name']}({s['signal_score']})" for s in rest_watches]
            )
            msg2.append(rest_line)
            msg2.append("")
    messages.append("\n".join(msg2))

    msg3 = []
    msg3.append("🧠 *今日操作建議*")
    msg3.append("")

    focus = (buys + watches)[:3]
    if focus:
        msg3.append("🔑 *最值得關注*")
        for s in focus:
            c = s.get("components", {})
            t = s.get("trend", {})
            reason_parts = []
            if c.get("tech_signals"):
                reason_parts.append(f"技術面出現{'/'.join(c['tech_signals'])}")
            if t.get("chg_5d", 0) > 0 and t.get("vol_ratio", 1) > 1.2:
                reason_parts.append("帶量上攻")
            if t.get("above_ma20") and t.get("above_ma60"):
                reason_parts.append("多頭排列")
            if c.get("backtest_winrate", 0) >= 0.6:
                reason_parts.append(f"歷史勝率{c['backtest_winrate']*100:.0f}%")
            reason = "，".join(reason_parts) if reason_parts else "綜合分數領先"
            msg3.append(
                f"• *{s['stock_id']} {s['name']}* ({s['action']}, {s['signal_score']}分)"
            )
            msg3.append(f"  {reason}")
            msg3.append(
                f"  明日開盤進場（參考 {s['entry_price']}）→ "
                f"損 {s['stop_loss_price']} / 標 {s['target_price']}"
            )
            msg3.append("")

    msg3.append("📌 *操作方向*")
    sentiment = _market_sentiment(signals)
    if "偏多" in sentiment and "中性" not in sentiment:
        msg3.append("• 市場偏多，可挑選技術面強勢股分批進場")
        msg3.append("• 優先選回測勝率>60%、站穩月線的標的")
    elif "偏多" in sentiment:
        msg3.append("• 市場中性偏多，選股不選市")
        msg3.append("• 等拉回月線支撐再找買點，不追高")
    elif "偏空" in sentiment and "中性" not in sentiment:
        msg3.append("• 市場偏空，建議空手觀望")
        msg3.append("• 等止跌訊號出現再考慮進場")
    else:
        msg3.append("• 市場中性偏空，控制總部位在半倉以下")
        msg3.append("• 只做高勝率、風報比好的機會")
    msg3.append("")
    msg3.append("_以上為系統自動分析，僅供參考，投資決策請自行判斷_")
    messages.append("\n".join(msg3))

    msg4 = _format_deep_analysis(signals, today)
    messages.append(msg4)

    return messages


def _format_deep_analysis(signals: list[dict], today: str) -> str:
    lines = [f"🔬 *量價深度解析* {today}", ""]

    buys = [s for s in signals if s.get("action") == "BUY"]
    watches = [s for s in signals if s.get("action") == "WATCH"]

    has_patterns = lambda s: bool(s.get("components", {}).get("volume_patterns"))
    has_danger = lambda s: "放量滯漲" in s.get("components", {}).get("volume_patterns", [])

    danger_stocks = [s for s in signals if has_danger(s)]

    if buys:
        lines.append("🟢 *BUY 深度解析*")
        lines.append("")
        for s in buys:
            lines.extend(_format_volume_block(s))
            lines.append("")

    interesting_watches = [s for s in watches if has_patterns(s)]
    if interesting_watches:
        lines.append(f"🟡 *WATCH 量價解讀 ({len(interesting_watches)})*")
        lines.append("")
        for s in interesting_watches[:8]:
            lines.extend(_format_volume_block(s))
            lines.append("")

    if danger_stocks:
        lines.append("⚠️ *風險警示 — 放量滯漲*")
        lines.append("")
        for s in danger_stocks:
            if s.get("action") in ("BUY", "WATCH") and has_patterns(s):
                continue
            lines.append(
                f"• *{s['stock_id']} {s['name']}* ({s.get('action', '—')})"
            )
            c = s.get("components", {})
            details = c.get("volume_details", {})
            if "放量滯漲" in details:
                lines.append(f"  ↳ {details['放量滯漲']}")
            lines.append(f"  {c.get('volume_verdict', '')}")
            lines.append("")

    if not buys and not interesting_watches and not danger_stocks:
        lines.append("_今日無顯著量價訊號_")
        lines.append("")

    lines.append("📖 *V3.1 量價字典速查*")
    lines.append("• 倍量柱 = 今日量 ≥ 昨日 2x（主力點火）")
    lines.append("• 梯量柱 = 連續 3 日量能遞增（健康上攻）")
    lines.append("• 縮量柱 = 下跌時量能遞減（洗盤，主力未退）")
    lines.append("• 低量柱 = 極限窒息量（拋壓耗盡）")
    lines.append("• 放量滯漲 = 高檔爆量但 K 收黑（主力倒貨）")

    return "\n".join(lines)


def _format_volume_block(s: dict) -> list[str]:
    c = s.get("components", {})
    patterns = c.get("volume_patterns", [])
    details = c.get("volume_details", {})
    verdict = c.get("volume_verdict", "")

    lines = [f"• *{s['stock_id']} {s['name']}* ({s.get('action')}, {s['signal_score']}分)"]

    if patterns:
        lines.append(f"  量能陣列: {' + '.join(patterns)}")
        for p in patterns:
            if p in details:
                lines.append(f"  ↳ {details[p]}")
    else:
        lines.append("  量能陣列: 無特殊型態")

    if verdict:
        lines.append(f"  結論: {verdict}")
    return lines


def format_premarket(night: dict | None, signals: list[dict]) -> str:
    from .night_session import tailwind_tag, bias_guidance

    today = datetime.now()
    wd = "一二三四五六日"[today.weekday()]
    lines = [f"🌙 *夜盤盤前快報* {today.strftime('%Y/%m/%d')} (週{wd})", ""]

    if night:
        lines.append(
            f"{night['emoji']} *台指期夜盤 {night['pct']:+.2f}% "
            f"({night['spread']:+.0f} 點)*"
        )
        lines.append(f"近月收 {night['close']:.0f} | 量 {night['volume']:,}")
        if night["date"] != today.strftime("%Y-%m-%d"):
            lines.append(f"_（資料時間：{night['date']} 夜盤）_")
        lines.append(f"📈 開盤方向預判：*{night['label']}* → {night['direction']}")
    else:
        lines.append("⚠️ 夜盤資料暫時取不到，今日盤前以個股訊號為主")
    lines.append("")

    bias = night["bias"] if night else "flat"
    tag = tailwind_tag(bias)
    actionable = [
        s for s in signals
        if str(s.get("action", "")).upper() in ("BUY", "WATCH")
    ]
    if actionable:
        latest_day = actionable[0].get("date", "")
        batch = [s for s in actionable if s.get("date", "") == latest_day]
        buys = [s for s in batch if str(s["action"]).upper() == "BUY"]
        watches = [s for s in batch if str(s["action"]).upper() == "WATCH"]
        lines.append(f"📋 *昨日訊號 × 夜盤對照* ({latest_day})")
        for s in (buys + watches)[:12]:
            act = str(s["action"]).upper()
            dot = "🟢" if act == "BUY" else "🟡"
            lines.append(
                f"{dot} {act} {s.get('stock_id', '')} {s.get('name', '')} "
                f"{s.get('signal_score', '')}分 · {tag}"
            )
        lines.append(f"↳ _{bias_guidance(bias)}_")
    else:
        lines.append("📋 昨日無 BUY/WATCH 訊號（或尚未跑過選股）")
    lines.append("")

    lines.append("💡 _夜盤僅領先參考，開盤後仍以實際量價為準_")
    return "\n".join(lines)


def format_message(signals: list[dict]) -> str:
    return format_messages(signals)[0]
