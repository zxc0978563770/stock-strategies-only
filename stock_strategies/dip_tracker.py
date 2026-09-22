"""DipTracker 分頁讀寫"""

from .sheet import get_gsheet


HEADERS = ["stock_id", "name", "high_252", "low", "rebound_done", "first_seen"]


def read_tracker() -> dict:
    """讀取所有追蹤記錄，回傳 {stock_id: {...}}"""
    sh = get_gsheet()
    try:
        ws = sh.worksheet("DipTracker")
    except Exception:
        return {}
    rows = ws.get_all_records()
    return {str(r["stock_id"]): r for r in rows if r.get("stock_id")}


def upsert_tracker(records: dict):
    """整張 DipTracker 清空重寫。"""
    sh = get_gsheet()
    try:
        ws = sh.worksheet("DipTracker")
        ws.clear()
    except Exception:
        ws = sh.add_worksheet(title="DipTracker", rows=1000, cols=len(HEADERS))

    ws.append_row(HEADERS)
    if not records:
        return

    rows = []
    for sid, r in records.items():
        rows.append([
            sid,
            r.get("name", ""),
            r.get("high_252", ""),
            r.get("low", ""),
            r.get("rebound_done", ""),
            r.get("first_seen", ""),
        ])
    ws.append_rows(rows)
