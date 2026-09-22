"""跌深反彈策略

流程：
1. 篩選 1：從 252 日高點回檔 >= 20%
2. 篩選 2：從近 60 日最低點反彈 < 10%
3. 通知 1：跌深警示（含分批進場價）
4. 通知 2：從最低點反彈收復跌幅一半 → 「反彈成功」+ 反彈一半價位
5. 不出場，繼續持有
"""

from .data import get_price_history


def evaluate_dip(stock_id: str, name: str = "", tracked: dict | None = None) -> dict:
    """評估一檔股票。

    tracked: 若已追蹤，帶入 {'high_252': 高點, 'low': 最低點, 'rebound_done': bool}
    """
    result = {
        "stock_id": stock_id,
        "name": name,
        "action": "SKIP",
        "signals": [],
        "risk_notes": [],
    }

    try:
        px = get_price_history(stock_id, years=2)
        if len(px) < 252:
            result["risk_notes"].append(f"資料不足（僅 {len(px)} 筆）")
            return result

        high_252 = float(px["high"].iloc[-252:].max())
        close = float(px["close"].iloc[-1])
        drawdown = (close - high_252) / high_252

        result.update({
            "high_252": round(high_252, 2),
            "close": round(close, 2),
            "drawdown_pct": round(drawdown * 100, 2),
            "entry_1": round(high_252 * 0.80, 2),
            "entry_2": round(high_252 * 0.75, 2),
            "entry_3": round(high_252 * 0.70, 2),
            "entry_4": round(high_252 * 0.65, 2),
        })

        # 情境 A：還沒觸發過
        if not tracked:
            if drawdown > -0.20:
                return result

            recent = px.iloc[-60:]
            low_60 = float(recent["low"].min())
            rebound_pct = (close - low_60) / low_60 if low_60 > 0 else 0

            result["low"] = round(low_60, 2)
            result["rebound_pct"] = round(rebound_pct * 100, 2)

            if rebound_pct >= 0.10:
                result["risk_notes"].append(
                    f"已從 60 日低點反彈 {rebound_pct*100:.1f}%（>= 10%），不觸發"
                )
                return result

            result["action"] = "DIP"
            result["signals"].append(
                f"從 252 日高點 {high_252:.0f} 回檔 {drawdown*100:.1f}%"
            )
            result["signals"].append(
                f"從 60 日低點 {low_60:.0f} 反彈 {rebound_pct*100:.1f}%（< 10%）"
            )
            return result

        # 情境 B：已追蹤，檢查反彈
        tracked_high = float(tracked.get("high_252", high_252))
        tracked_low = float(tracked.get("low", close))
        rebound_done = str(tracked.get("rebound_done", "")).upper() in ("TRUE", "1", "YES")

        new_low = min(tracked_low, close)
        result["low"] = round(new_low, 2)

        drop = tracked_high - new_low
        half_rebound = new_low + drop / 2
        result["half_rebound_price"] = round(half_rebound, 2)

        if rebound_done:
            result["action"] = "DONE"
            return result

        if close >= half_rebound:
            result["action"] = "REBOUND"
            result["signals"].append("已從最低點反彈收復跌幅一半")
        else:
            result["action"] = "TRACKING"
            result["risk_notes"].append(f"追蹤中（最低 {new_low:.0f}）")

        return result

    except Exception as e:
        result["action"] = "ERROR"
        result["risk_notes"].append(f"錯誤: {str(e)[:80]}")
        return result
