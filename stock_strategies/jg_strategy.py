"""JG 反市場策略（支援自訂目標價）

依《反市場：JG股市操作原理》設計：
1. 大盤在月線之上（多頭濾鏡）
2. 個股在 20MA 之上
3. 逆 KD：K < D（向下交叉）但未跌破前波低點
4. 逆布林：股價接近布林下軌（距離 < 3%）
5. 風報比 >= 1:3（若使用者有指定 target_price，以使用者為準）
"""

import pandas as pd

from .data import get_price_history
from .indicators import add_indicators


def get_market_ok() -> tuple[bool, str]:
    """判斷大盤是否在月線之上。回傳 (是否多頭, 說明文字)。"""
    try:
        df = get_price_history("TAIEX", years=1)
        if len(df) < 25:
            return True, "大盤資料不足，預設為多頭"
        df = add_indicators(df)
        latest = df.iloc[-1]
        close = float(latest["close"])
        ma20 = latest["ma20"]
        if pd.isna(ma20):
            return True, "大盤月線資料不足，預設為多頭"
        if close > ma20:
            return True, f"大盤 {close:.0f} 在月線 {ma20:.0f} 之上（多頭）"
        else:
            return False, f"大盤 {close:.0f} 跌破月線 {ma20:.0f}（空頭）"
    except Exception as e:
        return True, f"大盤判斷失敗（{str(e)[:40]}），預設為多頭"


def find_swing_low(df: pd.DataFrame, lookback: int = 20) -> float:
    """找最近 N 根 K 的最低點，當停損參考。"""
    recent = df.tail(lookback)
    return float(recent["low"].min())


def evaluate_jg(
    stock_id: str,
    name: str = "",
    market_ok: bool = True,
    target_price: float | None = None,
) -> dict:
    """評估一檔股票是否符合 JG 進場條件。

    target_price: 若提供，會用此目標價算風報比（需 >= 停損距離的 3 倍）。
    """
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

        close = float(latest["close"])
        ma20 = latest["ma20"]
        bb_lower = latest["bb_lower"]
        bb_mid = latest["bb_mid"]
        k = latest["k"]
        d = latest["d"]

        if pd.isna(ma20) or pd.isna(bb_lower) or pd.isna(k) or pd.isna(d):
            result["risk_notes"].append("指標資料不足")
            return result

        # 條件 1：大盤多頭
        if not market_ok:
            result["risk_notes"].append("大盤跌破月線，不做多")
            return result

        # 條件 2：個股在 20MA 之上
        if close < ma20:
            result["risk_notes"].append("股價在 20MA 之下，非多頭")
            return result

        # 條件 3：逆 KD（K < D）
        if not (k < d):
            result["risk_notes"].append("KD 未向下交叉，非逆 KD 買點")
            return result

        # 條件 4：逆布林（接近下軌）
        dist_to_lower = (close - bb_lower) / bb_lower
        near_lower = 0 < dist_to_lower < 0.03
        below_mid = close < bb_mid
        if not (near_lower or below_mid):
            result["risk_notes"].append("股價未接近布林下軌")
            return result

        # 條件 5：風報比
        swing_low = find_swing_low(px, lookback=20)
        stop_price = max(swing_low * 0.99, close * 0.92)
        stop_distance = close - stop_price
        if stop_distance <= 0:
            result["risk_notes"].append("停損距離異常")
            return result

        # 若有自訂目標價，用它；否則用停損距離的 3 倍
        if target_price and target_price > close:
            target = float(target_price)
            rr = (target - close) / stop_distance
            rr_source = "自訂目標價"
        else:
            target = close + stop_distance * 3
            rr = 3.0
            rr_source = "系統預設 1:3"

        # 若自訂目標價的風報比 < 3，就不算 BUY（JG 要求至少 1:3）
        if target_price and rr < 3.0:
            result["risk_notes"].append(
                f"自訂目標價 {target:.0f} 的風報比只有 1:{rr:.1f}，未達 1:3"
            )
            return result

        result.update({
            "action": "BUY",
            "entry_price": round(close, 2),
            "stop_loss_price": round(stop_price, 2),
            "target_price": round(target, 2),
            "risk_reward_ratio": round(rr, 2),
            "rr_source": rr_source,
            "signals": [
                "個股在 20MA 之上",
                f"KD 向下交叉（K={k:.1f}, D={d:.1f}）",
                "股價接近布林下軌" if near_lower else "股價在布林中線之下",
                f"風報比 1:{rr:.1f}（{rr_source}）",
            ],
        })
        return result

    except Exception as e:
        result["action"] = "ERROR"
        result["risk_notes"].append(f"錯誤: {str(e)[:80]}")
        return result
