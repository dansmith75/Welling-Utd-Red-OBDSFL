#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SUPABASE_URL = "https://dszgeoimkilzeeqapish.supabase.co"
SUPABASE_KEY = "sb_publishable_uTJVDSSD7jPePv1BdODmSg_qO6U8get"

MATCHDAY_HEADERS = [
    "ImportKey", "SessionId", "MatchId", "MatchDate", "Opposition", "Competition",
    "RecordType", "PlayerId", "DisplayName", "RelatedPlayerId", "RelatedDisplayName",
    "Minute", "Detail", "Value", "SubmittedBy", "StartedAt", "FinishedAt", "Source",
]


def api_get() -> list[dict[str, Any]]:
    params = {
        "select": "id,match_id,match_date,opposition,competition,submitted_by,started_at,finished_at,match_seconds,payload,created_at",
        "order": "created_at.asc",
    }
    url = f"{SUPABASE_URL}/rest/v1/matchday_sessions?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def logical_key(session: dict[str, Any]) -> tuple[str, str]:
    payload = session.get("payload") or {}
    return (
        str(payload.get("matchId") or session.get("match_id") or "").strip(),
        str(payload.get("startedAt") or session.get("started_at") or "").strip(),
    )


def canonical_sessions(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    output = []
    for session in sessions:
        key = logical_key(session)
        if key in seen:
            continue
        seen.add(key)
        output.append(session)
    return output


def names_for(payload: dict[str, Any]) -> dict[str, str]:
    names = {}
    for p in payload.get("squad") or []:
        pid = str(p.get("playerId") or "")
        if pid:
            names[pid] = str(p.get("displayName") or pid)
    for p in payload.get("playerStats") or []:
        pid = str(p.get("playerId") or "")
        if pid:
            names[pid] = str(p.get("displayName") or names.get(pid) or pid)
    return names


def audit_rows(session: dict[str, Any]) -> list[dict[str, Any]]:
    payload = session.get("payload") or {}
    fixture = payload.get("fixture") or {}
    sid = str(session.get("id") or "")
    match_id = payload.get("matchId") or session.get("match_id") or ""
    match_date = fixture.get("date") or session.get("match_date") or ""
    opposition = fixture.get("opposition") or session.get("opposition") or ""
    competition = fixture.get("competition") or session.get("competition") or ""
    started = payload.get("startedAt") or session.get("started_at") or ""
    finished = payload.get("finishedAt") or session.get("finished_at") or ""
    submitted = payload.get("submittedBy") or session.get("submitted_by") or ""
    names = names_for(payload)
    rows: list[dict[str, Any]] = []

    def add(kind: str, suffix: str, player_id="", related_id="", minute="", detail="", value=""):
        rows.append({
            "ImportKey": f"{sid}|{suffix}", "SessionId": sid, "MatchId": match_id,
            "MatchDate": match_date, "Opposition": opposition, "Competition": competition,
            "RecordType": kind, "PlayerId": player_id, "DisplayName": names.get(str(player_id), str(player_id) if player_id else ""),
            "RelatedPlayerId": related_id, "RelatedDisplayName": names.get(str(related_id), str(related_id) if related_id else ""),
            "Minute": minute, "Detail": detail, "Value": value, "SubmittedBy": submitted,
            "StartedAt": started, "FinishedAt": finished, "Source": "Matchday App",
        })

    add("Session", "session", detail=f"{opposition} · {competition}")
    for i, pid in enumerate(payload.get("starters") or []):
        add("Starter", f"starter-{i}-{pid}", player_id=pid, value=1)
    for i, sub in enumerate(payload.get("substitutions") or []):
        add("Substitution", f"sub-{i}", player_id=sub.get("off") or "", related_id=sub.get("on") or "",
            minute=sub.get("minute", ""), detail="OFF → ON")
    for i, event in enumerate(payload.get("events") or []):
        etype = str(event.get("type") or "Event")
        if etype == "Goal":
            add("Goal", f"event-{i}", player_id=event.get("playerId") or "", related_id=event.get("assistPlayerId") or "",
                minute=event.get("minute", ""), detail=event.get("goalType") or "Goal", value=1)
            if event.get("assistPlayerId"):
                add("Assist", f"assist-{i}", player_id=event.get("assistPlayerId") or "", related_id=event.get("playerId") or "",
                    minute=event.get("minute", ""), detail="Assist", value=1)
        elif etype == "Card":
            add("Card", f"event-{i}", player_id=event.get("playerId") or "", minute=event.get("minute", ""),
                detail=event.get("cardType") or "Card", value=1)
        elif etype == "Note":
            add("Note", f"event-{i}", player_id=event.get("playerId") or "", minute=event.get("minute", ""), detail=event.get("text") or "")
        else:
            add(etype, f"event-{i}", player_id=event.get("playerId") or "", minute=event.get("minute", ""), detail=json.dumps(event, ensure_ascii=False))
    for i, stat in enumerate(payload.get("playerStats") or []):
        pid = stat.get("playerId") or ""
        add("Minutes", f"minutes-{i}-{pid}", player_id=pid,
            detail="Starter" if stat.get("starter") else "Squad", value=stat.get("minutesPlayed", 0))
    return rows


def table_rows(table) -> list[dict[str, Any]]:
    values = table.range.value
    if not values:
        return []
    if not isinstance(values[0], list):
        values = [values]
    headers = [str(v or "").strip() for v in values[0]]
    return [dict(zip(headers, row)) for row in values[1:] if row and any(v not in (None, "") for v in row)]


def rewrite_table(sheet, table, headers: list[str], rows: list[dict[str, Any]]):
    start_row = table.range.row
    start_col = table.range.column
    old_end_row = table.range.last_cell.row
    old_end_col = table.range.last_cell.column
    sheet.range((start_row, start_col), (old_end_row, old_end_col)).clear_contents()
    matrix = [headers] + [[row.get(h, "") for h in headers] for row in rows]
    end_row = start_row + max(len(matrix), 2) - 1
    end_col = start_col + len(headers) - 1
    sheet.range((start_row, start_col), (start_row + len(matrix) - 1, end_col)).value = matrix
    table.resize(sheet.range((start_row, start_col), (end_row, end_col)))
    if len(matrix) == 1:
        sheet.range((start_row + 1, start_col), (start_row + 1, end_col)).clear_contents()


def ensure_summary_row(book, sheet_name: str, match_date: str, opposition: str):
    if sheet_name not in [s.name for s in book.sheets]:
        return None, None, []
    sheet = book.sheets[sheet_name]
    try:
        table = sheet.tables[sheet_name]
    except Exception:
        return sheet, None, []
    headers = [str(v or "").strip() for v in table.range.rows[0].value]
    date_col = headers.index("Date") + table.range.column if "Date" in headers else None
    opp_col = headers.index("Opposition") + table.range.column if "Opposition" in headers else None
    if date_col is None or opp_col is None:
        return sheet, None, headers
    for row_num in range(table.range.row + 1, table.range.last_cell.row + 1):
        d = sheet.range((row_num, date_col)).value
        o = str(sheet.range((row_num, opp_col)).value or "").strip()
        d_text = getattr(d, "date", lambda: d)()
        if str(d_text)[:10] == str(match_date)[:10] and o == str(opposition).strip():
            return sheet, row_num, headers
    new_row = table.range.last_cell.row + 1
    sheet.range((new_row, table.range.column), (new_row, table.range.column + len(headers) - 1)).value = [["" for _ in headers]]
    table.resize(sheet.range((table.range.row, table.range.column), (new_row, table.range.column + len(headers) - 1)))
    sheet.range((new_row, date_col)).value = match_date
    sheet.range((new_row, opp_col)).value = opposition
    return sheet, new_row, headers


def sync_summary_sheets(book, sessions: list[dict[str, Any]]) -> list[str]:
    warnings = []
    for session in sessions:
        payload = session.get("payload") or {}
        fixture = payload.get("fixture") or {}
        match_date = str(fixture.get("date") or session.get("match_date") or "")
        opposition = str(fixture.get("opposition") or session.get("opposition") or "")
        names = names_for(payload)
        goal_counts: dict[str, int] = {}
        assist_counts: dict[str, int] = {}
        event_text: dict[str, list[str]] = {}
        our_goals = 0
        opp_goals = 0
        for event in payload.get("events") or []:
            etype = str(event.get("type") or "")
            pid = str(event.get("playerId") or "")
            minute = event.get("minute", "")
            if etype == "Goal":
                our_goals += 1
                if pid:
                    goal_counts[pid] = goal_counts.get(pid, 0) + 1
                aid = str(event.get("assistPlayerId") or "")
                if aid:
                    assist_counts[aid] = assist_counts.get(aid, 0) + 1
            elif etype == "Own Goal":
                our_goals += 1
            elif etype == "Opponent Goal":
                opp_goals += 1
            elif etype in ("Card", "Note") and pid:
                detail = event.get("cardType") if etype == "Card" else event.get("text")
                prefix = f"{minute}' " if minute not in (None, "") else ""
                event_text.setdefault(pid, []).append(f"{prefix}{detail or etype}")

        for sheet_name, values in (("Goals", goal_counts), ("Assists", assist_counts)):
            sheet, row_num, headers = ensure_summary_row(book, sheet_name, match_date, opposition)
            if not sheet or not row_num:
                warnings.append(f"Could not prepare {sheet_name} row for {match_date} v {opposition}")
                continue
            for pid, count in values.items():
                name = names.get(pid, pid)
                if name in headers:
                    col = sheet.tables[sheet_name].range.column + headers.index(name)
                    sheet.range((row_num, col)).value = count
                else:
                    warnings.append(f"Missing {sheet_name} player column: {name}")

        sheet, row_num, headers = ensure_summary_row(book, "Events", match_date, opposition)
        if sheet and row_num:
            for pid, texts in event_text.items():
                name = names.get(pid, pid)
                if name in headers:
                    col = sheet.tables["Events"].range.column + headers.index(name)
                    sheet.range((row_num, col)).value = " | ".join(texts)
                else:
                    warnings.append(f"Missing Events player column: {name}")

        if "Fixtures" in [s.name for s in book.sheets]:
            sheet = book.sheets["Fixtures"]
            try:
                table = sheet.tables["Fixtures"]
                headers = [str(v or "").strip() for v in table.range.rows[0].value]
                aliases = {
                    "GF": ["GF", "Goals For"],
                    "GA": ["GA", "Goals Against"],
                    "Result": ["Result"],
                }
                date_idx = headers.index("Date") if "Date" in headers else None
                opp_idx = headers.index("Opposition") if "Opposition" in headers else None
                target = None
                if date_idx is not None and opp_idx is not None:
                    for r in range(table.range.row + 1, table.range.last_cell.row + 1):
                        d = sheet.range((r, table.range.column + date_idx)).value
                        o = str(sheet.range((r, table.range.column + opp_idx)).value or "").strip()
                        d_text = getattr(d, "date", lambda: d)()
                        if str(d_text)[:10] == match_date[:10] and o == opposition:
                            target = r
                            break
                if target:
                    for key, names_list in aliases.items():
                        header = next((h for h in names_list if h in headers), None)
                        if not header:
                            continue
                        col = table.range.column + headers.index(header)
                        if key == "GF": value = our_goals
                        elif key == "GA": value = opp_goals
                        else: value = "Win" if our_goals > opp_goals else "Loss" if our_goals < opp_goals else "Draw"
                        sheet.range((target, col)).value = value
            except Exception:
                pass
    return warnings


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python reconcile_matchday_records.py /path/to/workbook.xlsx")
    workbook = Path(sys.argv[1]).expanduser().resolve()
    sessions = canonical_sessions(api_get())

    import xlwings as xw
    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    app.screen_updating = False
    book = None
    try:
        book = app.books.open(str(workbook), update_links=False, read_only=False)
        if "MatchdayRecords" not in [s.name for s in book.sheets]:
            sheet = book.sheets.add("MatchdayRecords", after=book.sheets[-1])
            sheet.range("A1").value = [MATCHDAY_HEADERS]
            table = sheet.tables.add(sheet.range((1, 1), (2, len(MATCHDAY_HEADERS))), name="MatchdayRecords")
            sheet.range((2, 1), (2, len(MATCHDAY_HEADERS))).clear_contents()
        else:
            sheet = book.sheets["MatchdayRecords"]
            table = sheet.tables["MatchdayRecords"]

        existing = table_rows(table)
        legacy = [r for r in existing if str(r.get("Source") or "").strip().lower() != "matchday app"]
        app_rows = [row for session in sessions for row in audit_rows(session)]
        rewrite_table(sheet, table, MATCHDAY_HEADERS, legacy + app_rows)
        warnings = sync_summary_sheets(book, sessions)
        book.save()
        print(f"MatchdayRecords reconciled: {len(sessions)} completed matches, {len(app_rows)} app audit rows")
        for warning in warnings:
            print(f"WARNING: {warning}")
    finally:
        if book is not None:
            try: book.close()
            except Exception: pass
        try: app.quit()
        except Exception: pass


if __name__ == "__main__":
    main()
