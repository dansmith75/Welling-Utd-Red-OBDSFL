#!/usr/bin/env python3
"""Regenerate wide attendance sheets; use completed Matchday squad as match fallback."""
from __future__ import annotations
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


def iso_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def excel_date(value: Any) -> datetime | str:
    text = iso_date(value)
    if not text:
        return ""
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return text


def table_rows(table) -> list[dict[str, Any]]:
    values = table.range.value
    if not values:
        return []
    if not isinstance(values[0], list):
        values = [values]
    headers = [str(v or "").strip() for v in values[0]]
    rows = []
    for raw in values[1:]:
        if not raw or all(v in (None, "") for v in raw):
            continue
        rows.append({headers[i]: raw[i] if i < len(raw) else "" for i in range(len(headers))})
    return rows


def truthy(value: Any) -> bool:
    if isinstance(value, bool): return value
    if isinstance(value, (int, float)): return value != 0
    return str(value or "").strip().lower() in {"true", "yes", "y", "1"}


def active_player_ids(book) -> list[str]:
    rows = table_rows(book.sheets["Squad"].tables["Squad"])
    ids = [str(r.get("ID") or "").strip() for r in rows if str(r.get("ID") or "").strip() and truthy(r.get("Active"))]
    # Attendance columns must be stable and independent of however the Squad table
    # happens to be sorted in Excel. Player ID is the canonical ordering key.
    return sorted(ids, key=lambda value: value.casefold())


def attendance_sessions(book, session_type: str) -> list[dict[str, Any]]:
    rows = table_rows(book.sheets["AttendanceRecords"].tables["AttendanceRecords"])
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if str(row.get("SessionType") or "").strip().lower() != session_type.lower():
            continue
        key = str(row.get("SessionKey") or "").strip()
        if not key:
            continue
        submitted = str(row.get("SubmittedAt") or "")
        session = grouped.setdefault(key, {"Date": row.get("SessionDate"), "SubmittedAt": submitted, "Players": {}})
        if submitted > str(session.get("SubmittedAt") or ""):
            session["SubmittedAt"] = submitted
        pid = str(row.get("PlayerId") or "").strip()
        if pid:
            session["Players"][pid] = str(row.get("Status") or "").strip()
    latest: dict[str, dict[str, Any]] = {}
    for session in grouped.values():
        d = iso_date(session.get("Date"))
        if not d:
            continue
        current = latest.get(d)
        if current is None or str(session.get("SubmittedAt") or "") >= str(current.get("SubmittedAt") or ""):
            latest[d] = session
    return list(latest.values())


def completed_matchday_squads(book) -> dict[str, set[str]]:
    if "MatchdayRecords" not in [s.name for s in book.sheets]:
        return {}
    try:
        rows = table_rows(book.sheets["MatchdayRecords"].tables["MatchdayRecords"])
    except Exception:
        return {}
    squads: dict[str, set[str]] = {}
    for row in rows:
        record_type = str(row.get("RecordType") or row.get("Record Type") or "").strip().lower()
        if record_type != "minutes":
            continue
        d = iso_date(row.get("MatchDate") or row.get("Match Date"))
        pid = str(row.get("PlayerId") or "").strip()
        if d and pid:
            squads.setdefault(d, set()).add(pid)
    return squads


def write_table(sheet, table_name: str, headers: list[str], rows: list[list[Any]]) -> None:
    matrix = [headers, *rows]
    old_last_row = max(sheet.used_range.last_cell.row, 2)
    old_last_col = max(sheet.used_range.last_cell.column, len(headers))
    sheet.range((1,1),(old_last_row,old_last_col)).clear_contents()
    sheet.range((1,1),(len(matrix),len(headers))).value = matrix
    end_row = max(len(matrix), 2)
    try:
        table = sheet.tables[table_name]
        table.resize(sheet.range((1,1),(end_row,len(headers))))
    except Exception:
        table = sheet.tables.add(sheet.range((1,1),(end_row,len(headers))), name=table_name)
    if len(matrix) == 1:
        sheet.range((2,1),(2,len(headers))).clear_contents()


def refresh_match(book, players: list[str]) -> int:
    fixtures = table_rows(book.sheets["Fixtures"].tables["Fixtures"])
    by_date = {iso_date(s.get("Date")): s for s in attendance_sessions(book, "Match")}
    matchday = completed_matchday_squads(book)
    rows = []
    for fixture in fixtures:
        d = iso_date(fixture.get("Date"))
        opposition = str(fixture.get("Opposition") or "").strip()
        if not d or not opposition:
            continue
        session = by_date.get(d)
        if session:
            statuses = session.get("Players") or {}
            present = [str(statuses.get(pid) or "").lower() in {"present", "late"} for pid in players]
        else:
            squad = matchday.get(d, set())
            present = [pid in squad for pid in players]
        rows.append([excel_date(d), excel_date(d), opposition, *present, sum(present)])
    sheet = book.sheets["Match Attendance"]
    write_table(sheet, "Match_Attendance", ["Date", "Day", "Opposition", *players, "COUNT"], rows)
    sheet.range("A:A").number_format = "dd-mm-yy"
    sheet.range("B:B").number_format = "dddd"
    return len(rows)


def refresh_training(book, players: list[str]) -> int:
    rows = []
    for session in attendance_sessions(book, "Training"):
        statuses = session.get("Players") or {}
        present = [str(statuses.get(pid) or "").lower() in {"present", "late"} for pid in players]
        d = iso_date(session.get("Date"))
        rows.append([excel_date(d), excel_date(d), "Training", *present, sum(present)])
    sheet = book.sheets["Training Attendance"]
    write_table(sheet, "Training_Attendance", ["Date", "Day", "Session", *players, "Count"], rows)
    sheet.range("A:A").number_format = "dd-mm-yy"
    sheet.range("B:B").number_format = "dddd"
    return len(rows)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python refresh_attendance_views_v2.py /path/to/workbook.xlsx")
    path = Path(sys.argv[1]).expanduser().resolve()
    import xlwings as xw
    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    app.screen_updating = False
    book = None
    try:
        book = app.books.open(str(path), update_links=False, read_only=False)
        players = active_player_ids(book)
        match_rows = refresh_match(book, players)
        training_rows = refresh_training(book, players)
        book.save()
        print(f"Attendance views refreshed: {len(players)} active players, {match_rows} fixtures, {training_rows} training sessions; player columns sorted by ID; completed Matchday squad used when match attendance was not separately submitted")
    finally:
        if book is not None:
            try: book.close()
            except Exception: pass
        try: app.quit()
        except Exception: pass

if __name__ == "__main__":
    main()
