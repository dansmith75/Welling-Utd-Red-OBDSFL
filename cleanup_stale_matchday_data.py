#!/usr/bin/env python3
"""Remove workbook data left behind by Matchday sessions deleted from Supabase.

This keeps real historical/manual data intact. It only cleans matches that previously
had rows sourced from "Matchday App" in MatchdayRecords but no longer have a
completed Matchday session in Supabase.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

SUPABASE_URL = "https://dszgeoimkilzeeqapish.supabase.co"
SUPABASE_KEY = "sb_publishable_uTJVDSSD7jPePv1BdODmSg_qO6U8get"


def normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def iso_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text[:10]


def current_completed_matches() -> set[tuple[str, str]]:
    params = {
        "select": "match_date,opposition",
        "order": "match_date.asc",
    }
    url = f"{SUPABASE_URL}/rest/v1/matchday_sessions?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as response:
        rows = json.loads(response.read().decode("utf-8"))
    return {
        (iso_date(row.get("match_date")), str(row.get("opposition") or "").strip().lower())
        for row in rows
        if row.get("match_date") and row.get("opposition")
    }


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


def stale_app_matches(book, current: set[tuple[str, str]]) -> set[tuple[str, str]]:
    if "MatchdayRecords" not in [s.name for s in book.sheets]:
        return set()
    sheet = book.sheets["MatchdayRecords"]
    try:
        table = sheet.tables["MatchdayRecords"]
    except Exception:
        return set()

    seen = set()
    for row in table_rows(table):
        if str(row.get("Source") or "").strip().lower() != "matchday app":
            continue
        d = iso_date(row.get("MatchDate") or row.get("Match Date"))
        opp = str(row.get("Opposition") or "").strip().lower()
        if d and opp:
            seen.add((d, opp))
    return seen - current


def find_header(headers: list[str], *names: str) -> int | None:
    wanted = {normal(name) for name in names}
    for i, header in enumerate(headers):
        if normal(header) in wanted:
            return i
    return None


def clear_summary_match(book, sheet_name: str, match_key: tuple[str, str]) -> bool:
    if sheet_name not in [s.name for s in book.sheets]:
        return False
    sheet = book.sheets[sheet_name]
    try:
        table = sheet.tables[sheet_name]
    except Exception:
        return False

    headers = [str(v or "").strip() for v in table.range.rows[0].value]
    date_idx = find_header(headers, "Date")
    opp_idx = find_header(headers, "Opposition")
    if date_idx is None or opp_idx is None:
        return False

    start_col = table.range.column
    for row_num in range(table.range.row + 1, table.range.last_cell.row + 1):
        d = iso_date(sheet.range((row_num, start_col + date_idx)).value)
        opp = str(sheet.range((row_num, start_col + opp_idx)).value or "").strip().lower()
        if (d, opp) != match_key:
            continue
        for idx, header in enumerate(headers):
            if idx in (date_idx, opp_idx) or normal(header) == "count":
                continue
            sheet.range((row_num, start_col + idx)).clear_contents()
        return True
    return False


def clear_fixture_result(book, match_key: tuple[str, str]) -> bool:
    if "Fixtures" not in [s.name for s in book.sheets]:
        return False
    sheet = book.sheets["Fixtures"]
    try:
        table = sheet.tables["Fixtures"]
    except Exception:
        return False

    headers = [str(v or "").strip() for v in table.range.rows[0].value]
    date_idx = find_header(headers, "Date")
    opp_idx = find_header(headers, "Opposition")
    if date_idx is None or opp_idx is None:
        return False

    clear_indices = [
        idx for idx, header in enumerate(headers)
        if normal(header) in {"gf", "goalsfor", "ga", "goalsagainst", "result"}
    ]
    start_col = table.range.column
    for row_num in range(table.range.row + 1, table.range.last_cell.row + 1):
        d = iso_date(sheet.range((row_num, start_col + date_idx)).value)
        opp = str(sheet.range((row_num, start_col + opp_idx)).value or "").strip().lower()
        if (d, opp) != match_key:
            continue
        for idx in clear_indices:
            sheet.range((row_num, start_col + idx)).clear_contents()
        return True
    return False


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python cleanup_stale_matchday_data.py /path/to/workbook.xlsx")
    workbook = Path(sys.argv[1]).expanduser().resolve()
    if not workbook.exists():
        raise FileNotFoundError(workbook)

    current = current_completed_matches()

    import xlwings as xw
    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    app.screen_updating = False
    book = None
    try:
        book = app.books.open(str(workbook), update_links=False, read_only=False)
        stale = stale_app_matches(book, current)
        if not stale:
            print("Stale Matchday cleanup: nothing to remove")
            return

        summary_cells = 0
        fixture_rows = 0
        for match_key in sorted(stale):
            for sheet_name in ("Goals", "Assists", "Events"):
                if clear_summary_match(book, sheet_name, match_key):
                    summary_cells += 1
            if clear_fixture_result(book, match_key):
                fixture_rows += 1

        book.save()
        labels = ", ".join(f"{d} v {opp}" for d, opp in sorted(stale))
        print(f"Stale Matchday cleanup: cleared {len(stale)} removed session match(es): {labels}")
        print(f"  Summary rows cleaned: {summary_cells}; fixture result rows reset: {fixture_rows}")
    finally:
        if book is not None:
            try:
                book.close()
            except Exception:
                pass
        try:
            app.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
