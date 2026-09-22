"""跌深反彈策略

流程：
1. 篩選 1：從 60 日高點回檔 >= 20%
2. 篩選 2：從 60 日低點反彈，尚未收復跌幅一半
3. 通知 1：跌深警示
4. 通知 2：反彈成功
5. 隔天重新計算（如果又跌深，重新觸發）
"""

from .data import get_price_history


def evaluate_dip(stock_id: str, name: str = "", tracked: dict | None = None) -> dict:
    """評估一檔股票。

    tracked: 若已追蹤，帶入 {'high_60', 'low', 'rebound_done'}
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
        if len(px) < 60:
            result["risk_notes"].append(f"資料不足（僅 {len(px)} 筆）")
            return result

        # 60 日高點（篩選 1）
        high_60 = float(px["high"].iloc[-60:].max())
        # 60 日低點（篩選 2）
        low_60 = float(px["low"].iloc[-60:].min())
        close = float(px["close"].iloc[-1])
        drawdown = (close - high_60) / high_60

        # 60 日跌幅的一半
        drop_60 = high_60 - low_60
        half_rebound_60 = low_60 + drop_60 / 2

        result.update({
            "high_60": round(high_60, 2),
            "low_60": round(low_60, 2),
            "half_rebound_60": round(half_rebound_60, 2),
            "close": round(close, 2),
            "drawdown_pct": round(drawdown * 100, 2),
            "entry_1": round(high_60 * 0.80, 2),
            "entry_2": round(high_60 * 0.75, 2),
            "entry_3": round(high_60 * 0.70, 2),
            "entry_4": round(high_60 * 0.65, 2),
        })

        # ── 情境 A：還沒觸發過 ──
        if not tracked:
            if drawdown > -0.20:
                return result
            if close >= half_rebound_60:
                result["risk_notes"].append(
                    f"已收復跌幅一半（現價 {close:.1f} >= {half_rebound_60:.1f}）"
                )
                return result

            result["action"] = "DIP"
            result["low"] = round(close, 2)
            result["signals"].append(
                f"從 60 日高點 {high_60:.0f} 回檔 {drawdown*100:.1f}%"
            )
            result["signals"].append(
                f"尚未收復跌幅一半（{half_rebound_60:.1f}）"
            )
            return result

        # ── 情境 B：已追蹤 ──
        rebound_done = str(tracked.get("rebound_done", "")).upper() in ("TRUE", "1", "YES")

        # 情境 B1：已通知過反彈成功 → 隔天重新計算
        if rebound_done:
            if drawdown <= -0.20 and close < half_rebound_60:
                result["action"] = "DIP"
                result["low"] = round(close, 2)
                result["signals"].append(
                    f"重新觸發：從 60 日高點 {high_60:.0f} 回檔 {drawdown*100:.1f}%"
                )
                result["signals"].append(
                    f"尚未收復跌幅一半（{half_rebound_60:.1f}）"
                )
                return result
            result["action"] = "DONE"
            return result

        # 情境 B2：追蹤中
        tracked_high = float(tracked.get("high_60", high_60))
        tracked_low = float(tracked.get("low", close))

        new_low = min(tracked_low, close)
        result["low"] = round(new_low, 2)

        drop = tracked_high - new_low
        half_rebound = new_low + drop / 2
        result["half_rebound_price"] = round(half_rebound, 2)

               if close >= half_rebound:
            result["action"] = "REBOUND"
            result["signals"].append("已從最低點反彈收復跌幅一半")
        else:
            result["action"] = "TRACKING"
            result["risk_notes"].append(f"追蹤中（最低 {new_low:.0f}）")
            # 補上完整欄位（已經在 result.update 裡有了）

        return result

    except Exception as e:
        result["action"] = "ERROR"
        result["risk_notes"].append(f"錯誤: {str(e)[:80]}")
        return result
