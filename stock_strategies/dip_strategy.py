"""跌深反彈策略

邏輯：
1. 從 252 日高點回檔 >= 20% → 通知
2. 列出分批進場價：-20%、-25%、-30%、-35%
3. 從最低點反彈，收復跌幅一半 → 通知「反彈成功」
"""

import pandas as pd

from .data import get_price_history


def evaluate_dip(stock_id: str, name: str = "") -> dict:
    """評估一檔股票是否符合跌深反彈條件。"""
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
            result["risk_notes"].append(f"資料不足（僅 {len(px)} 筆，需 252 筆）")
            return result

        # 252 日高點（不含最近 5 日，避免高點就是最近）
        high_252 = float(px["high"].iloc[-252:].max())
        close = float(px["close"].iloc[-1])

        # 回檔幅度
        drawdown = (close - high_252) / high_252

        # 分批進場價
        entry_1 = round(high_252 * 0.80, 2)  # -20%
        entry_2 = round(high_252 * 0.75, 2)  # -25%
        entry_3 = round(high_252 * 0.70, 2)  # -30%
        entry_4 = round(high_252 * 0.65, 2)  # -35%

        result.update({
            "high_252": round(high_252, 2),
            "close": round(close, 2),
            "drawdown_pct": round(drawdown * 100, 2),
            "entry_1": entry_1,
            "entry_2": entry_2,
            "entry_3": entry_3,
            "entry_4": entry_4,
        })

        # 條件 1：回檔 >= 20%
        if drawdown <= -0.20:
            result["action"] = "DIP"
            result["signals"].append(
                f"從 252 日高點 {high_252:.0f} 回檔 {drawdown*100:.1f}%"
            )

        # 條件 2：反彈成功（從最低點反彈，收復跌幅一半）
        # 找進場後的最低點
        recent = px.iloc[-60:]  # 最近 60 日
        low_60 = float(recent["low"].min())

        if drawdown <= -0.20:
            # 跌幅
            drop = high_252 - low_60
            # 反彈一半價位
            half_rebound = low_60 + drop / 2

            if close >= half_rebound:
                result["action"] = "REBOUND"
                result["half_rebound_price"] = round(half_rebound, 2)
                result["signals"].append(
                    f"已從最低 {low_60:.0f} 反彈收復跌幅一半（{half_rebound:.0f}）"
                )

        return result

    except Exception as e:
        result["action"] = "ERROR"
        result["risk_notes"].append(f"錯誤: {str(e)[:80]}")
        return result
