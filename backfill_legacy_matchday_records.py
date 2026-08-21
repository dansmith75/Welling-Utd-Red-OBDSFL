#!/usr/bin/env python3
"""Backfill pre-Matchday-app goals/assists/events into MatchdayRecords.

The first friendlies were recorded directly in the workbook before Matchday
was live. This script mirrors those legacy summary-sheet stats into
MatchdayRecords while leaving real Matchday App rows untouched.

Rules:
- Only matches without an existing non-legacy MatchdayRecords session are backfilled.
- Legacy rows are rebuilt on every run, so edits to Goals/Assists/Events remain in sync.
- Player goals/assists are stored as aggregate Value counts.
- Known guest-player goals can be represented in MatchdayRecords without adding the
  guest to the Squad or normal player-stat areas of the Dashboard.
- Any remaining Goals For gap after credited and known guest goals is recorded as
  an uncredited own goal.
- No starters/substitutions/minutes are invented for historical matches.
"""

from __future__ import annotations

import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

MATCHDAY_SHEET = "MatchdayRecords"
MATCHDAY_TABLE = "MatchdayRecords"
SOURCE = "Legacy Excel backfill"
HEADERS = [
    "ImportKey", "SessionId", "MatchId", "MatchDate", "Opposition", "Competition",
    "RecordType", "PlayerId", "DisplayName", "RelatedPlayerId", "RelatedDisplayName",
    "Minute", "Detail", "Value", "SubmittedBy", "StartedAt", "FinishedAt", "Source",
]

# Historical scorers who were not members of the tracked squad. These entries are
# deliberately MatchdayRecords-only, so they can appear in a match timeline without
# being added to player selectors, charts or season player totals.
LEGACY_GUEST_GOALS: dict[tuple[str, str], list[tuple[str, int]]] = {
    ("2026-08-09", "charity tournament"): [("Daniel", 1)],
}


def iso_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)):
        try:
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).date().isoformat()
        except Exception:
            pass
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            pass
    return text[:10]


def slugify(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def table_headers(table) -> list[str]:
    values = table.range.rows[0].value
    if not isinstance(values, list):
        values = [values]
    return [str(v or "").strip() for v in values]


def table_rows(table) -> list[dict[str, Any]]:
    values = table.range.value
    if not values:
        return []
    if not isinstance(values[0], list):
        values = [values]
    headers = [str(v or "").strip() for v in values[0]]
    output = []
    for raw in values[1:]:
        if not raw or all(v in (None, "") for v in raw):
            continue
        output.append({headers[i]: raw[i] if i < len(raw) else "" for i in range(len(headers))})
    return output


def get_table(book, sheet_name: str, table_name: str):
    if sheet_name not in [s.name for s in book.sheets]:
        return None, None
    sheet = book.sheets[sheet_name]
    try:
        return sheet, sheet.tables[table_name]
    except Exception:
        return sheet, None


def ensure_matchday_table(book):
    names = [s.name for s in book.sheets]
    if MATCHDAY_SHEET in names:
        sheet = book.sheets[MATCHDAY_SHEET]
    else:
        sheet = book.sheets.add(MATCHDAY_SHEET, after=book.sheets[-1])

    try:
        table = sheet.tables[MATCHDAY_TABLE]
    except Exception:
        sheet.range("A1").value = [HEADERS]
        table = sheet.tables.add(sheet.range((1, 1), (2, len(HEADERS))), name=MATCHDAY_TABLE)
        sheet.range((2, 1), (2, len(HEADERS))).clear_contents()
    return sheet, table


def squad_name_map(book) -> dict[str, tuple[str, str]]:
    _, table = get_table(book, "Squad", "Squad")
    if table is None:
        return {}
    result: dict[str, tuple[str, str]] = {}
    for row in table_rows(table):
        pid = str(row.get("ID") or "").strip()
        display = str(row.get("Display Name") or row.get("Name") or "").strip()
        if not pid or not display:
            continue
        # Legacy wide sheets may now use either the permanent ID or the display name
        # as the player-column heading. Resolve both to the same friendly display name.
        result[pid.lower()] = (pid, display)
        result[display.lower()] = (pid, display)
    return result


def fixture_map(book) -> dict[tuple[str, str], dict[str, Any]]:
    _, table = get_table(book, "Fixtures", "Fixtures")
    if table is None:
        return {}
    result = {}
    for row in table_rows(table):
        d = iso_date(row.get("Date"))
        opp = str(row.get("Opposition") or "").strip()
        if not d or not opp:
            continue
        result[(d, opp.lower())] = row
    return result


def wide_rows(book, sheet_name: str) -> list[dict[str, Any]]:
    _, table = get_table(book, sheet_name, sheet_name)
    return table_rows(table) if table is not None else []


def numeric_count(value: Any) -> int:
    if value in (None, "", False):
        return 0
    try:
        number = int(round(float(value)))
        return max(0, number)
    except Exception:
        return 0


def build_legacy_rows(book, real_matches: set[tuple[str, str]]) -> list[dict[str, Any]]:
    names = squad_name_map(book)
    fixtures = fixture_map(book)
    goals_rows = wide_rows(book, "Goals")
    assists_rows = wide_rows(book, "Assists")
    events_rows = wide_rows(book, "Events")

    assists_by_match = {(iso_date(r.get("Date")), str(r.get("Opposition") or "").strip().lower()): r for r in assists_rows}
    events_by_match = {(iso_date(r.get("Date")), str(r.get("Opposition") or "").strip().lower()): r for r in events_rows}

    output: list[dict[str, Any]] = []
    ignored = {"Date", "Opposition", "count", "Count", "COUNT", ""}

    def add(match_key, competition, record_type, suffix, player_id="", display_name="", detail="", value=""):
        d, opp_lower = match_key
        fixture = fixtures.get(match_key, {})
        opposition = str(fixture.get("Opposition") or opp_lower).strip()
        match_id = slugify(f"{d}-{opposition}")
        session_id = f"legacy-{match_id}"
        output.append({
            "ImportKey": f"{session_id}|{suffix}",
            "SessionId": session_id,
            "MatchId": match_id,
            "MatchDate": d,
            "Opposition": opposition,
            "Competition": competition,
            "RecordType": record_type,
            "PlayerId": player_id,
            "DisplayName": display_name,
            "RelatedPlayerId": "",
            "RelatedDisplayName": "",
            "Minute": "",
            "Detail": detail,
            "Value": value,
            "SubmittedBy": "Legacy workbook",
            "StartedAt": "",
            "FinishedAt": "",
            "Source": SOURCE,
        })

    for goal_row in goals_rows:
        d = iso_date(goal_row.get("Date"))
        opposition = str(goal_row.get("Opposition") or "").strip()
        if not d or not opposition:
            continue
        key = (d, opposition.lower())
        if key in real_matches:
            continue

        fixture = fixtures.get(key, {})
        competition = str(fixture.get("Competition") or "").strip()
        assist_row = assists_by_match.get(key, {})
        event_row = events_by_match.get(key, {})

        credited_goals = 0
        has_data = False
        goal_items = []
        assist_items = []
        event_items = []

        for header, value in goal_row.items():
            if header in ignored:
                continue
            count = numeric_count(value)
            if not count:
                continue
            has_data = True
            credited_goals += count
            pid, display = names.get(str(header).strip().lower(), (slugify(header), str(header).strip()))
            goal_items.append((pid, display, count))

        for header, value in assist_row.items():
            if header in ignored:
                continue
            count = numeric_count(value)
            if not count:
                continue
            has_data = True
            pid, display = names.get(str(header).strip().lower(), (slugify(header), str(header).strip()))
            assist_items.append((pid, display, count))

        for header, value in event_row.items():
            if header in ignored or value in (None, "", 0, False):
                continue
            has_data = True
            pid, display = names.get(str(header).strip().lower(), (slugify(header), str(header).strip()))
            if isinstance(value, (int, float)):
                detail = "Legacy event"
                event_value = numeric_count(value) or 1
            else:
                detail = str(value).strip()
                event_value = 1
            event_items.append((pid, display, detail, event_value))

        guest_goals = LEGACY_GUEST_GOALS.get(key, [])
        guest_goal_total = sum(count for _, count in guest_goals)
        if guest_goal_total:
            has_data = True

        goals_for = numeric_count(fixture.get("Goals For"))
        own_goals = max(0, goals_for - credited_goals - guest_goal_total) if goals_for else 0
        if own_goals:
            has_data = True

        if not has_data:
            continue

        add(key, competition, "Session", "session", detail=f"{opposition} · {competition}")
        for i, (pid, display, count) in enumerate(goal_items):
            add(key, competition, "Goal", f"goal-{i}-{pid}", pid, display, "Legacy player goal(s)", count)
        for i, (guest_name, count) in enumerate(guest_goals):
            # PlayerId intentionally blank: Daniel can appear in this match timeline without
            # becoming a squad player or leaking into Dashboard player totals/charts.
            add(key, competition, "Goal", f"guest-goal-{i}", "", guest_name, "Guest player goal(s)", count)
        if own_goals:
            add(key, competition, "Own Goal", "own-goal", detail="Uncredited own goal(s)", value=own_goals)
        for i, (pid, display, count) in enumerate(assist_items):
            add(key, competition, "Assist", f"assist-{i}-{pid}", pid, display, "Legacy assist(s)", count)
        for i, (pid, display, detail, event_value) in enumerate(event_items):
            add(key, competition, "Event", f"event-{i}-{pid}", pid, display, detail, event_value)

    return output


def rewrite_table(sheet, table, rows: list[dict[str, Any]]) -> None:
    headers = table_headers(table)
    start_row = table.range.row
    start_col = table.range.column
    old_last_row = start_row + max(1, table.range.rows.count) - 1
    end_col = start_col + len(headers) - 1
    if old_last_row > start_row:
        sheet.range((start_row + 1, start_col), (old_last_row, end_col)).clear_contents()

    if rows:
        matrix = [[row.get(header, "") for header in headers] for row in rows]
        new_last_row = start_row + len(matrix)
        sheet.range((start_row + 1, start_col), (new_last_row, end_col)).value = matrix
        table.resize(sheet.range((start_row, start_col), (new_last_row, end_col)))
    else:
        seed = start_row + 1
        sheet.range((seed, start_col), (seed, end_col)).clear_contents()
        table.resize(sheet.range((start_row, start_col), (seed, end_col)))


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python backfill_legacy_matchday_records.py /path/to/workbook.xlsx")
    workbook_path = Path(sys.argv[1]).expanduser().resolve()
    if not workbook_path.exists():
        raise FileNotFoundError(workbook_path)

    import xlwings as xw
    app = None
    book = None
    try:
        app = xw.App(visible=False, add_book=False)
        app.display_alerts = False
        app.screen_updating = False
        book = app.books.open(str(workbook_path), update_links=False, read_only=False)
        sheet, table = ensure_matchday_table(book)
        existing = table_rows(table)

        real_rows = [r for r in existing if str(r.get("Source") or "").strip() != SOURCE]
        real_matches = {
            (iso_date(r.get("MatchDate")), str(r.get("Opposition") or "").strip().lower())
            for r in real_rows
            if iso_date(r.get("MatchDate")) and str(r.get("Opposition") or "").strip()
        }
        legacy_rows = build_legacy_rows(book, real_matches)
        rewrite_table(sheet, table, real_rows + legacy_rows)
        book.save()

        sessions = sum(1 for r in legacy_rows if r.get("RecordType") == "Session")
        goals = sum(numeric_count(r.get("Value")) for r in legacy_rows if r.get("RecordType") == "Goal")
        own_goals = sum(numeric_count(r.get("Value")) for r in legacy_rows if r.get("RecordType") == "Own Goal")
        assists = sum(numeric_count(r.get("Value")) for r in legacy_rows if r.get("RecordType") == "Assist")
        events = sum(1 for r in legacy_rows if r.get("RecordType") == "Event")
        print(f"Legacy MatchdayRecords refreshed: {sessions} matches, {goals} player/guest goals, {own_goals} own goals, {assists} assists, {events} events")
    finally:
        if book is not None:
            try: book.close()
            except Exception: pass
        if app is not None:
            try: app.quit()
            except Exception: pass


if __name__ == "__main__":
    main()
