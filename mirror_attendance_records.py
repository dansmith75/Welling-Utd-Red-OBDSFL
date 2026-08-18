#!/usr/bin/env python3
"""Mirror Supabase attendance into the Excel AttendanceRecords table.

This deliberately treats Supabase as the source of truth for app-submitted
attendance. Rows deleted or changed in Supabase are therefore removed/updated
in Excel on the next UPDATE-WELLING run.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SUPABASE_URL = "https://dszgeoimkilzeeqapish.supabase.co"
SUPABASE_KEY = "sb_publishable_uTJVDSSD7jPePv1BdODmSg_qO6U8get"
SHEET_NAME = "AttendanceRecords"
TABLE_NAME = "AttendanceRecords"


def api_get(table: str, select: str, order: str | None = None) -> list[dict[str, Any]]:
    params = {"select": select}
    if order:
        params["order"] = order
    url = f"{SUPABASE_URL}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def make_session_key(session: dict[str, Any]) -> str:
    date_part = session.get("session_date") or "unknown-date"
    type_part = str(session.get("session_type") or "session").lower()
    venue_part = str(session.get("venue") or "na").lower()
    return f"{date_part}-{type_part}-{venue_part}-{str(session.get('id'))[:8]}"


def table_headers(table) -> list[str]:
    values = table.range.rows[0].value
    if not isinstance(values, list):
        values = [values]
    return [str(v or "").strip() for v in values]


def mirror(workbook_path: Path) -> int:
    sessions = api_get(
        "attendance_sessions",
        "id,session_date,session_type,venue,submitted_by,submitted_at",
        "submitted_at.asc",
    )
    records = api_get(
        "attendance_records",
        "session_id,player_id,display_name,status",
    )
    sessions_by_id = {str(s["id"]): s for s in sessions}

    desired: list[dict[str, Any]] = []
    for record in records:
        session = sessions_by_id.get(str(record.get("session_id")))
        if not session:
            continue
        session_key = make_session_key(session)
        desired.append({
            "RecordKey": f"{session_key}-{record.get('player_id')}",
            "SessionKey": session_key,
            "SessionId": session.get("id"),
            "SessionDate": session.get("session_date"),
            "SessionType": session.get("session_type"),
            "Venue": session.get("venue") or "",
            "PlayerId": record.get("player_id"),
            "DisplayName": record.get("display_name"),
            "Status": record.get("status"),
            "FeePaid": "",
            "PaymentStatus": "",
            "LatePayment": "",
            "SubmittedBy": session.get("submitted_by") or "",
            "SubmittedAt": session.get("submitted_at") or "",
            "Source": "App",
        })

    import xlwings as xw

    app = None
    book = None
    try:
        app = xw.App(visible=False, add_book=False)
        app.display_alerts = False
        app.screen_updating = False
        book = app.books.open(str(workbook_path), update_links=False, read_only=False)
        sheet = book.sheets[SHEET_NAME]
        table = sheet.tables[TABLE_NAME]
        headers = table_headers(table)

        start_row = table.range.row
        start_col = table.range.column
        old_rows = table.range.rows.count
        old_last_row = start_row + old_rows - 1
        end_col = start_col + len(headers) - 1

        if old_rows > 1:
            sheet.range((start_row + 1, start_col), (old_last_row, end_col)).clear_contents()

        if desired:
            matrix = [[row.get(header, "") for header in headers] for row in desired]
            new_last_row = start_row + len(matrix)
            sheet.range((start_row + 1, start_col), (new_last_row, end_col)).value = matrix
            table.resize(sheet.range((start_row, start_col), (new_last_row, end_col)))
        else:
            # Excel tables need a seed data row; keep it blank.
            seed_row = start_row + 1
            sheet.range((seed_row, start_col), (seed_row, end_col)).clear_contents()
            table.resize(sheet.range((start_row, start_col), (seed_row, end_col)))

        book.save()
        return len(desired)
    finally:
        if book is not None:
            try:
                book.close()
            except Exception:
                pass
        if app is not None:
            try:
                app.quit()
            except Exception:
                pass


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python mirror_attendance_records.py /path/to/workbook.xlsx")
    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    count = mirror(path)
    print(f"AttendanceRecords mirrored from Supabase: {count} rows")


if __name__ == "__main__":
    main()
