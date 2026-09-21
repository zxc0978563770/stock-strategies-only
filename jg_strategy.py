"""JG 反市場策略

依《反市場：JG股市操作原理》設計：
1. 大盤在月線之上（多頭濾鏡）
2. 個股在 20MA 之上
3. 逆 KD：K < D（向下交叉）但未跌破前波低點
4. 逆布林：股價接近布林下軌（距離 < 3%）
5. 風報比 ≥ 1:3
"""

import pandas as pd

from .data import get_price_history
from .indicators import add_indicators


def find_swing_low(df: pd.DataFrame, lookback: int = 20) -> float:
    """找最近 N 根 K 的最低點，當停損參考。"""
    recent = df.tail(lookback)
    return float(recent["low"].min())


def evaluate_jg(stock_id: str, name: str = "", market_ok: bool = True) -> dict:
    """評估一檔股票是否符合 JG 進場條件。"""
    result = {
        "stock_id": stock_id,
        "name": name,
        "action": "SKIP",
        "signals": [],
        "risk_notes": [],
    }

    try:
        px = get_price_history(stock_id, years=1)
        if len(px) < 60:
            result["risk_notes"].append("資料不足")
            return result

        px = add_indicators(px)
        latest = px.iloc[-1]
        prev = px.iloc[-2]

        close = float(latest["close"])
        ma20 = latest["ma20"]
        bb_lower = latest["bb_lower"]
        bb_mid = latest["bb_mid"]
        k = latest["k"]
        d = latest["d"]

        if pd.isna(ma20) or pd.isna(bb_lower) or pd.isna(k) or pd.isna(d):
            result["risk_notes"].append("指標資料不足")
            return result

        # ── 條件 1：大盤多頭 ──
        if not market_ok:
            result["risk_notes"].append("大盤跌破月線，不做多")
            return result

        # ── 條件 2：個股在 20MA 之上 ──
        if close < ma20:
            result["risk_notes"].append("股價在 20MA 之下，非多頭")
            return result

        # ── 條件 3：逆 KD（K < D，向下交叉）──
        kd_bearish_cross = k < d
        if not kd_bearish_cross:
            result["risk_notes"].append("KD 未向下交叉，非逆 KD 買點")
            return result

        # ── 條件 4：逆布林（接近下軌）──
        dist_to_lower = (close - bb_lower) / bb_lower
        near_lower = 0 < dist_to_lower < 0.03
        below_mid = close < bb_mid
        if not (near_lower or below_mid):
            result["risk_notes"].append("股價未接近布林下軌")
            return result

        # ── 條件 5：風報比 ──
        swing_low = find_swing_low(px, lookback=20)
        stop_price = max(swing_low * 0.99, close * 0.92)  # 前低再低 1%，或 -8% 取較高者
        stop_distance = close - stop_price
        if stop_distance <= 0:
            result["risk_notes"].append("停損距離異常")
            return result

        target_price = close + stop_distance * 3  # 風報比 1:3
        rr = 3.0

        # ── 符合條件 ──
        result.update({
            "action": "BUY",
            "entry_price": round(close, 2),
            "stop_loss_price": round(stop_price, 2),
            "target_price": round(target_price, 2),
            "risk_reward_ratio": rr,
            "signals": [
                "個股在 20MA 之上",
                f"KD 向下交叉（K={k:.1f}, D={d:.1f}）",
                "股價接近布林下軌" if near_lower else "股價在布林中線之下",
            ],
        })
        return result

    except Exception as e:
        result["action"] = "ERROR"
        result["risk_notes"].append(f"錯誤: {str(e)[:80]}")
        return result
