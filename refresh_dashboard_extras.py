#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

LINK_HEADERS = ["Category", "Name", "URL", "Description", "Active", "Sort Order"]
LEAGUE_HEADERS = ["Position", "Team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]


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


def ensure_table(book, sheet_name: str, table_name: str, headers: list[str]):
    names = [sheet.name for sheet in book.sheets]
    if sheet_name in names:
        sheet = book.sheets[sheet_name]
    else:
        sheet = book.sheets.add(sheet_name, after=book.sheets[-1])

    try:
        table = sheet.tables[table_name]
    except Exception:
        sheet.range("A1").value = [headers]
        sheet.range((2, 1), (2, len(headers))).clear_contents()
        table = sheet.tables.add(sheet.range((1, 1), (2, len(headers))), name=table_name)
        try:
            table.table_style = "TableStyleMedium2"
        except Exception:
            pass
        sheet.autofit("c")

    existing_headers = [str(v or "").strip() for v in table.range.rows[0].value]
    if existing_headers != headers:
        # Preserve rows by header name while normalising the table schema.
        rows = table_rows(table)
        start_row = table.range.row
        start_col = table.range.column
        end_col = start_col + len(headers) - 1
        end_row = start_row + max(1, len(rows))
        table.resize(sheet.range((start_row, start_col), (end_row, end_col)))
        sheet.range((start_row, start_col), (start_row, end_col)).value = [headers]
        if rows:
            matrix = [[row.get(header, "") for header in headers] for row in rows]
            sheet.range((start_row + 1, start_col), (start_row + len(matrix), end_col)).value = matrix
        else:
            sheet.range((start_row + 1, start_col), (start_row + 1, end_col)).clear_contents()
    return sheet, table


def truthy(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text not in {"no", "n", "false", "0", "inactive", "off"}


def number(value: Any):
    if value in (None, ""):
        return None
    try:
        f = float(value)
        return int(f) if f.is_integer() else f
    except Exception:
        return value


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python refresh_dashboard_extras.py /path/to/workbook.xlsx")

    workbook = Path(sys.argv[1]).expanduser().resolve()
    if not workbook.exists():
        raise FileNotFoundError(workbook)

    import xlwings as xw

    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    app.screen_updating = False
    book = None
    try:
        book = app.books.open(str(workbook), update_links=False, read_only=False)
        links_sheet, links_table = ensure_table(book, "Web Links", "WebLinks", LINK_HEADERS)
        league_sheet, league_table = ensure_table(book, "League Table", "LeagueTable", LEAGUE_HEADERS)

        # Light usability formatting for the two manually maintained tables.
        try:
            links_sheet.range("A:F").column_width = 18
            links_sheet.range("C:C").column_width = 42
            links_sheet.range("D:D").column_width = 34
            league_sheet.range("A:J").column_width = 10
            league_sheet.range("B:B").column_width = 28
        except Exception:
            pass

        book.save()

        links = []
        for row in table_rows(links_table):
            url = str(row.get("URL") or "").strip()
            name = str(row.get("Name") or "").strip()
            if not url or not name or not truthy(row.get("Active")):
                continue
            links.append({
                "category": str(row.get("Category") or "Useful Links").strip() or "Useful Links",
                "name": name,
                "url": url,
                "description": str(row.get("Description") or "").strip(),
                "sortOrder": number(row.get("Sort Order")) or 999,
            })
        links.sort(key=lambda row: (str(row["category"]).lower(), row["sortOrder"], str(row["name"]).lower()))

        league = []
        for row in table_rows(league_table):
            team = str(row.get("Team") or "").strip()
            if not team:
                continue
            league.append({
                "position": number(row.get("Position")),
                "team": team,
                "played": number(row.get("P")) or 0,
                "won": number(row.get("W")) or 0,
                "drawn": number(row.get("D")) or 0,
                "lost": number(row.get("L")) or 0,
                "goalsFor": number(row.get("GF")) or 0,
                "goalsAgainst": number(row.get("GA")) or 0,
                "goalDifference": number(row.get("GD")) or 0,
                "points": number(row.get("Pts")) or 0,
            })
        league.sort(key=lambda row: (row["position"] if isinstance(row["position"], (int, float)) else 999, str(row["team"]).lower()))

        data_dir = Path(__file__).resolve().parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "links.json").write_text(json.dumps(links, indent=2, ensure_ascii=False), encoding="utf-8")
        (data_dir / "league-table.json").write_text(json.dumps(league, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"Dashboard extras refreshed: {len(links)} web links, {len(league)} league rows")
        print("Excel tables ready: Web Links!WebLinks and League Table!LeagueTable")
    finally:
        if book is not None:
            try: book.close()
            except Exception: pass
        try: app.quit()
        except Exception: pass


if __name__ == "__main__":
    main()
