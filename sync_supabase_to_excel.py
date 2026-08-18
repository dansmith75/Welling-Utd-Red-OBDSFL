#!/usr/bin/env python3
"""Pull centrally submitted Attendance/Matchday data from Supabase into Excel.

Excel remains the football-data source of truth. This script uses xlwings so
Excel itself opens/saves the workbook rather than rewriting the XLSX package.
That keeps the existing workbook structure, tables and formulas under Excel's
control on Windows and macOS.

The Supabase key below is the app's public publishable/anon key, not a secret.
The database must allow anon SELECT on attendance_sessions,
attendance_records and matchday_sessions.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

SUPABASE_URL = "https://dszgeoimkilzeeqapish.supabase.co"
SUPABASE_KEY = "sb_publishable_uTJVDSSD7jPePv1BdODmSg_qO6U8get"

ATTENDANCE_SHEET = "AttendanceRecords"
ATTENDANCE_TABLE = "AttendanceRecords"
MATCHDAY_SHEET = "MatchdayRecords"
MATCHDAY_TABLE = "MatchdayRecords"

MATCHDAY_HEADERS = [
    "ImportKey",
    "SessionId",
    "MatchId",
    "MatchDate",
    "Opposition",
    "Competition",
    "RecordType",
    "PlayerId",
    "DisplayName",
    "RelatedPlayerId",
    "RelatedDisplayName",
    "Minute",
    "Detail",
    "Value",
    "SubmittedBy",
    "StartedAt",
    "FinishedAt",
    "Source",
]


def api_get(table: str, select: str, order: str | None = None) -> list[dict[str, Any]]:
    params = {"select": select}
    if order:
        params["order"] = order
    url = f"{SUPABASE_URL}/rest/v1/{table}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Could not read Supabase table '{table}'. "
            "Check internet access and the anon SELECT policy."
        ) from exc


def iso_date(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    return text[:10]


def excel_date(value: Any) -> datetime | str:
    text = iso_date(value)
    if not text:
        return ""
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return text


def table_headers(table) -> list[str]:
    values = table.range.rows[0].value
    if not isinstance(values, list):
        values = [values]
    return [str(v or "").strip() for v in values]


def table_existing_column_values(table, header: str) -> set[str]:
    headers = table_headers(table)
    if header not in headers:
        return set()
    idx = headers.index(header) + 1
    values = table.range.columns[idx - 1].value
    if not isinstance(values, list):
        values = [values]
    # first item is header
    return {str(v) for v in values[1:] if v not in (None, "")}


def table_dict_rows(table) -> list[dict[str, Any]]:
    values = table.range.value
    if not values:
        return []
    if not isinstance(values[0], list):
        values = [values]
    headers = [str(v or "").strip() for v in values[0]]
    rows: list[dict[str, Any]] = []
    for raw in values[1:]:
        if not raw or all(v in (None, "") for v in raw):
            continue
        rows.append({headers[i]: raw[i] if i < len(raw) else "" for i in range(len(headers))})
    return rows


def append_table_rows(sheet, table, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    headers = table_headers(table)
    start_row = table.range.row
    start_col = table.range.column
    current_rows = table.range.rows.count
    next_row = start_row + current_rows
    matrix = [[row.get(header, "") for header in headers] for row in rows]
    end_row = next_row + len(matrix) - 1
    end_col = start_col + len(headers) - 1
    sheet.range((next_row, start_col), (end_row, end_col)).value = matrix
    table.resize(sheet.range((start_row, start_col), (end_row, end_col)))
    return len(matrix)


def make_session_key(session: dict[str, Any]) -> str:
    date_part = session.get("session_date") or "unknown-date"
    type_part = str(session.get("session_type") or "session").lower()
    venue_part = str(session.get("venue") or "na").lower()
    return f"{date_part}-{type_part}-{venue_part}-{str(session.get('id'))[:8]}"


def import_attendance(book) -> int:
    sessions = api_get(
        "attendance_sessions",
        "id,session_date,session_type,venue,submitted_by,submitted_at",
        "submitted_at.asc",
    )
    records = api_get(
        "attendance_records",
        "session_id,player_id,display_name,status",
    )

    if ATTENDANCE_SHEET not in [s.name for s in book.sheets]:
        raise RuntimeError(f"Workbook sheet '{ATTENDANCE_SHEET}' was not found.")
    sheet = book.sheets[ATTENDANCE_SHEET]
    try:
        table = sheet.tables[ATTENDANCE_TABLE]
    except Exception as exc:
        raise RuntimeError(f"Excel table '{ATTENDANCE_TABLE}' was not found.") from exc

    existing = table_existing_column_values(table, "RecordKey")
    sessions_by_id = {str(s["id"]): s for s in sessions}
    new_rows: list[dict[str, Any]] = []

    for record in records:
        session = sessions_by_id.get(str(record.get("session_id")))
        if not session:
            continue
        session_key = make_session_key(session)
        record_key = f"{session_key}-{record.get('player_id')}"
        if record_key in existing:
            continue
        new_rows.append(
            {
                "RecordKey": record_key,
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
            }
        )
        existing.add(record_key)

    return append_table_rows(sheet, table, new_rows)


def active_player_ids(book) -> list[str]:
    if "Squad" not in [s.name for s in book.sheets]:
        return []
    sheet = book.sheets["Squad"]
    try:
        table = sheet.tables["Squad"]
    except Exception:
        return []
    players: list[str] = []
    for row in table_dict_rows(table):
        pid = str(row.get("ID") or "").strip()
        active = row.get("Active")
        if pid and active in (True, 1, "TRUE", "True", "true", "Yes", "YES", "yes"):
            players.append(pid)
    return players


def fixture_lookup(book) -> dict[tuple[str, str], str]:
    lookup: dict[tuple[str, str], str] = {}
    if "Fixtures" not in [s.name for s in book.sheets]:
        return lookup
    sheet = book.sheets["Fixtures"]
    try:
        table = sheet.tables["Fixtures"]
    except Exception:
        return lookup
    for row in table_dict_rows(table):
        match_date = iso_date(row.get("Date"))
        opposition = str(row.get("Opposition") or "").strip()
        home_away = str(row.get("Home / Away") or "").strip().lower()
        if not match_date or not opposition:
            continue
        lookup[(match_date, home_away)] = opposition
        lookup.setdefault((match_date, ""), opposition)
    return lookup


def latest_attendance_sessions(book, session_type: str) -> list[dict[str, Any]]:
    sheet = book.sheets[ATTENDANCE_SHEET]
    table = sheet.tables[ATTENDANCE_TABLE]
    rows = table_dict_rows(table)

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if str(row.get("SessionType") or "").strip().lower() != session_type.lower():
            continue
        session_key = str(row.get("SessionKey") or "").strip()
        if not session_key:
            continue
        submitted_at = str(row.get("SubmittedAt") or "")
        session = grouped.setdefault(
            session_key,
            {
                "SessionKey": session_key,
                "SessionDate": row.get("SessionDate"),
                "Venue": str(row.get("Venue") or "").strip(),
                "SubmittedAt": submitted_at,
                "Players": {},
            },
        )
        if submitted_at > str(session.get("SubmittedAt") or ""):
            session["SubmittedAt"] = submitted_at
        pid = str(row.get("PlayerId") or "").strip()
        if pid:
            session["Players"][pid] = str(row.get("Status") or "").strip()

    # A re-submission creates a new SessionKey. For the legacy wide sheets we
    # want one row per actual date/venue, using the latest submission.
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for session in grouped.values():
        key = (iso_date(session.get("SessionDate")), str(session.get("Venue") or "").lower())
        current = latest.get(key)
        if current is None or str(session.get("SubmittedAt") or "") >= str(current.get("SubmittedAt") or ""):
            latest[key] = session

    return sorted(latest.values(), key=lambda s: (iso_date(s.get("SessionDate")), str(s.get("Venue") or "")))


def refresh_wide_attendance_sheet(book, sheet_name: str, table_name: str, session_type: str) -> int:
    if sheet_name not in [s.name for s in book.sheets]:
        return 0
    sheet = book.sheets[sheet_name]
    players = active_player_ids(book)
    sessions = latest_attendance_sessions(book, session_type)
    fixtures = fixture_lookup(book) if session_type.lower() == "match" else {}

    third_header = "Opposition" if session_type.lower() == "match" else "Session"
    count_header = "COUNT" if session_type.lower() == "match" else "Count"
    headers = ["Date", "Day", third_header, *players, count_header]
    matrix: list[list[Any]] = [headers]

    for session in sessions:
        session_date = session.get("SessionDate")
        date_key = iso_date(session_date)
        venue = str(session.get("Venue") or "").strip()
        if session_type.lower() == "match":
            label = fixtures.get((date_key, venue.lower())) or fixtures.get((date_key, "")) or venue or "Match"
        else:
            label = "Training"

        statuses = session.get("Players") or {}
        present = [str(statuses.get(pid) or "").lower() in ("present", "late") for pid in players]
        matrix.append([excel_date(session_date), excel_date(session_date), label, *present, sum(1 for value in present if value)])

    # Keep the existing look/formatting but replace the old hand-maintained data.
    old_last_row = max(sheet.used_range.last_cell.row, 2)
    old_last_col = max(sheet.used_range.last_cell.column, len(headers))
    sheet.range((1, 1), (old_last_row, old_last_col)).clear_contents()
    sheet.range((1, 1), (len(matrix), len(headers))).value = matrix

    # Reuse the existing Excel table so filters/style remain intact.
    try:
        table = sheet.tables[table_name]
        end_row = max(len(matrix), 2)
        table.resize(sheet.range((1, 1), (end_row, len(headers))))
        if len(matrix) == 1:
            sheet.range((2, 1), (2, len(headers))).clear_contents()
    except Exception:
        end_row = max(len(matrix), 2)
        table = sheet.tables.add(sheet.range((1, 1), (end_row, len(headers))), name=table_name)
        if len(matrix) == 1:
            sheet.range((2, 1), (2, len(headers))).clear_contents()

    sheet.range("A:B").number_format = "ddd dd-mmm-yy"
    return len(sessions)


def refresh_wide_attendance_sheets(book) -> dict[str, int]:
    return {
        "matchRows": refresh_wide_attendance_sheet(book, "Match Attendance", "Match_Attendance", "Match"),
        "trainingRows": refresh_wide_attendance_sheet(book, "Training Attendance", "Training_Attendance", "Training"),
    }


def ensure_matchday_table(book):
    names = [s.name for s in book.sheets]
    if MATCHDAY_SHEET in names:
        sheet = book.sheets[MATCHDAY_SHEET]
    else:
        sheet = book.sheets.add(MATCHDAY_SHEET, after=book.sheets[-1])

    try:
        table = sheet.tables[MATCHDAY_TABLE]
        return sheet, table
    except Exception:
        sheet.range("A1").value = [MATCHDAY_HEADERS]
        table = sheet.tables.add(sheet.range((1, 1), (2, len(MATCHDAY_HEADERS))), name=MATCHDAY_TABLE)
        # Leave row 2 empty as a table seed; imports will overwrite it if needed.
        sheet.range((2, 1), (2, len(MATCHDAY_HEADERS))).clear_contents()
        return sheet, table


def player_lookup(payload: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for p in payload.get("squad") or []:
        if p.get("playerId"):
            lookup[str(p["playerId"])] = str(p.get("displayName") or p["playerId"])
    return lookup


def matchday_rows(session: dict[str, Any]) -> list[dict[str, Any]]:
    payload = session.get("payload") or {}
    fixture = payload.get("fixture") or {}
    sid = str(session.get("id"))
    match_id = payload.get("matchId") or session.get("match_id") or ""
    match_date = fixture.get("date") or session.get("match_date") or ""
    opposition = fixture.get("opposition") or session.get("opposition") or ""
    competition = fixture.get("competition") or session.get("competition") or ""
    submitted_by = payload.get("submittedBy") or session.get("submitted_by") or ""
    started_at = payload.get("startedAt") or session.get("started_at") or ""
    finished_at = payload.get("finishedAt") or session.get("finished_at") or ""
    names = player_lookup(payload)
    rows: list[dict[str, Any]] = []

    def add(kind, suffix, player_id="", related_id="", minute="", detail="", value=""):
        rows.append(
            {
                "ImportKey": f"{sid}|{suffix}",
                "SessionId": sid,
                "MatchId": match_id,
                "MatchDate": match_date,
                "Opposition": opposition,
                "Competition": competition,
                "RecordType": kind,
                "PlayerId": player_id,
                "DisplayName": names.get(str(player_id), str(player_id) if player_id else ""),
                "RelatedPlayerId": related_id,
                "RelatedDisplayName": names.get(str(related_id), str(related_id) if related_id else ""),
                "Minute": minute,
                "Detail": detail,
                "Value": value,
                "SubmittedBy": submitted_by,
                "StartedAt": started_at,
                "FinishedAt": finished_at,
                "Source": "Matchday App",
            }
        )

    add("Session", "session", detail=f"{opposition} · {competition}")

    for index, pid in enumerate(payload.get("starters") or []):
        add("Starter", f"starter-{index}-{pid}", player_id=pid, value=1)

    for index, sub in enumerate(payload.get("substitutions") or []):
        add(
            "Substitution",
            f"sub-{index}",
            player_id=sub.get("off") or "",
            related_id=sub.get("on") or "",
            minute=sub.get("minute", ""),
            detail="OFF → ON",
        )

    for index, event in enumerate(payload.get("events") or []):
        etype = event.get("type") or "Event"
        if etype == "Goal":
            detail = event.get("goalType") or "Goal"
            add(
                "Goal",
                f"event-{index}",
                player_id=event.get("playerId") or "",
                related_id=event.get("assistPlayerId") or "",
                minute=event.get("minute", ""),
                detail=detail,
                value=1,
            )
            if event.get("assistPlayerId"):
                add(
                    "Assist",
                    f"assist-{index}",
                    player_id=event.get("assistPlayerId"),
                    related_id=event.get("playerId") or "",
                    minute=event.get("minute", ""),
                    detail=f"Assist for {names.get(str(event.get('playerId')), event.get('playerId'))}",
                    value=1,
                )
        elif etype == "Card":
            add(
                "Card",
                f"event-{index}",
                player_id=event.get("playerId") or "",
                minute=event.get("minute", ""),
                detail=event.get("cardType") or "Card",
                value=1,
            )
        elif etype == "Note":
            add(
                "Note",
                f"event-{index}",
                player_id=event.get("playerId") or "",
                minute=event.get("minute", ""),
                detail=event.get("text") or "",
            )
        else:
            add(
                str(etype),
                f"event-{index}",
                player_id=event.get("playerId") or "",
                minute=event.get("minute", ""),
                detail=json.dumps(event, ensure_ascii=False),
            )

    for index, stat in enumerate(payload.get("playerStats") or []):
        pid = stat.get("playerId") or ""
        if pid and stat.get("displayName"):
            names[str(pid)] = str(stat["displayName"])
        add(
            "Minutes",
            f"minutes-{index}-{pid}",
            player_id=pid,
            detail="Starter" if stat.get("starter") else "Squad",
            value=stat.get("minutesPlayed", 0),
        )

    # Refresh display names that may have arrived through playerStats.
    for row in rows:
        if row["PlayerId"]:
            row["DisplayName"] = names.get(str(row["PlayerId"]), row["DisplayName"])
        if row["RelatedPlayerId"]:
            row["RelatedDisplayName"] = names.get(str(row["RelatedPlayerId"]), row["RelatedDisplayName"])
    return rows


def excel_row_for_match(sheet, match_date: str, opposition: str) -> int | None:
    used = sheet.used_range.value
    if not used:
        return None
    if not isinstance(used[0], list):
        used = [used]
    for idx, row in enumerate(used[1:], start=2):
        if len(row) < 2:
            continue
        if iso_date(row[0]) == iso_date(match_date) and str(row[1] or "").strip() == str(opposition or "").strip():
            return idx
    return None


def player_column(sheet, display_name: str) -> int | None:
    headers = sheet.range((1, 1), (1, sheet.used_range.last_cell.column)).value
    if not isinstance(headers, list):
        headers = [headers]
    for idx, header in enumerate(headers, start=1):
        if str(header or "").strip() == str(display_name or "").strip():
            return idx
    return None


def increment_stat(sheet, row: int, col: int, amount: int = 1):
    cell = sheet.range((row, col))
    current = cell.value
    try:
        value = int(current or 0)
    except Exception:
        value = 0
    cell.value = value + amount


def append_event_text(sheet, row: int, col: int, text: str):
    cell = sheet.range((row, col))
    current = str(cell.value or "").strip()
    cell.value = f"{current} | {text}" if current else text


def apply_matchday_to_summary_sheets(book, session: dict[str, Any]) -> list[str]:
    payload = session.get("payload") or {}
    fixture = payload.get("fixture") or {}
    match_date = fixture.get("date") or session.get("match_date") or ""
    opposition = fixture.get("opposition") or session.get("opposition") or ""
    names = player_lookup(payload)
    for stat in payload.get("playerStats") or []:
        if stat.get("playerId") and stat.get("displayName"):
            names[str(stat["playerId"])] = str(stat["displayName"])

    warnings: list[str] = []
    sheet_cache = {}
    for sheet_name in ("Goals", "Assists", "Events"):
        if sheet_name not in [s.name for s in book.sheets]:
            warnings.append(f"Missing sheet: {sheet_name}")
            continue
        sheet = book.sheets[sheet_name]
        row = excel_row_for_match(sheet, match_date, opposition)
        if row is None:
            warnings.append(f"No {sheet_name} row for {match_date} v {opposition}")
        sheet_cache[sheet_name] = (sheet, row)

    for event in payload.get("events") or []:
        etype = event.get("type")
        pid = str(event.get("playerId") or "")
        display = names.get(pid, pid)
        minute = event.get("minute", "")

        if etype == "Goal":
            sheet, row = sheet_cache.get("Goals", (None, None))
            col = player_column(sheet, display) if sheet is not None else None
            if row and col:
                increment_stat(sheet, row, col, 1)
            else:
                warnings.append(f"Could not place goal: {display} v {opposition}")

            assist_id = str(event.get("assistPlayerId") or "")
            if assist_id:
                assist_name = names.get(assist_id, assist_id)
                sheet, row = sheet_cache.get("Assists", (None, None))
                col = player_column(sheet, assist_name) if sheet is not None else None
                if row and col:
                    increment_stat(sheet, row, col, 1)
                else:
                    warnings.append(f"Could not place assist: {assist_name} v {opposition}")

        elif etype in ("Card", "Note"):
            sheet, row = sheet_cache.get("Events", (None, None))
            col = player_column(sheet, display) if sheet is not None else None
            if etype == "Card":
                detail = event.get("cardType") or "Card"
            else:
                detail = event.get("text") or "Event"
            prefix = f"{minute}' " if minute not in (None, "") else ""
            if row and col:
                append_event_text(sheet, row, col, f"{prefix}{detail}")
            else:
                warnings.append(f"Could not place event: {display} v {opposition}")

    return warnings


def import_matchday(book) -> tuple[int, int, list[str]]:
    sessions = api_get(
        "matchday_sessions",
        "id,match_id,match_date,opposition,competition,submitted_by,started_at,finished_at,match_seconds,payload",
        "finished_at.asc",
    )
    sheet, table = ensure_matchday_table(book)
    existing_session_ids = table_existing_column_values(table, "SessionId")
    new_rows: list[dict[str, Any]] = []
    new_sessions = 0
    warnings: list[str] = []

    for session in sessions:
        sid = str(session.get("id"))
        if not sid or sid in existing_session_ids:
            continue
        rows = matchday_rows(session)
        new_rows.extend(rows)
        warnings.extend(apply_matchday_to_summary_sheets(book, session))
        existing_session_ids.add(sid)
        new_sessions += 1

    added = append_table_rows(sheet, table, new_rows)
    return new_sessions, added, warnings


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python sync_supabase_to_excel.py /path/to/workbook.xlsx")
    workbook_path = Path(sys.argv[1]).expanduser().resolve()
    if not workbook_path.exists():
        raise FileNotFoundError(workbook_path)

    try:
        import xlwings as xw
    except ImportError as exc:
        raise RuntimeError("xlwings is not installed. Run: python -m pip install xlwings") from exc

    app = None
    book = None
    try:
        app = xw.App(visible=False, add_book=False)
        app.display_alerts = False
        app.screen_updating = False
        book = app.books.open(str(workbook_path), update_links=False, read_only=False)

        attendance_rows = import_attendance(book)
        attendance_views = refresh_wide_attendance_sheets(book)
        matchday_sessions, matchday_rows_added, warnings = import_matchday(book)

        # The wide attendance sheets are regenerated every run, so save even if
        # there were no new Supabase rows this time.
        book.save()

        print("SUPABASE_SYNC_SUMMARY=" + json.dumps({
            "attendanceRows": attendance_rows,
            "matchAttendanceRows": attendance_views.get("matchRows", 0),
            "trainingAttendanceRows": attendance_views.get("trainingRows", 0),
            "matchdaySessions": matchday_sessions,
            "matchdayRows": matchday_rows_added,
            "warnings": warnings,
        }, ensure_ascii=False))
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


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SUPABASE SYNC FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
