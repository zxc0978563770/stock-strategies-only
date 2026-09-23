"""DipTracker 分頁讀寫"""

from .sheet import get_gsheet


HEADERS = ["stock_id", "name", "high_60", "low", "rebound_done", "first_seen"]


def read_tracker() -> dict:
    sh = get_gsheet()
    try:
        ws = sh.worksheet("DipTracker")
    except Exception:
        return {}
    rows = ws.get_all_records()
    return {str(r["stock_id"]): r for r in rows if r.get("stock_id")}


def upsert_tracker(records: dict):
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
            r.get("name") or "",
            r.get("high_60") or "",
            r.get("low") or "",
            r.get("rebound_done") or "FALSE",
            r.get("first_seen") or "",
        ])
    ws.append_rows(rows)
