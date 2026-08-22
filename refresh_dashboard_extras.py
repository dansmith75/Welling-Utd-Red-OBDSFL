#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

LINK_HEADERS = ["Category", "Name", "URL", "Description", "Active", "Sort Order"]
LEAGUE_HEADERS = ["Position", "Team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]
FA_LEAGUE_TABLE_URL = "https://fulltime.thefa.com/table.html?league=3117271&selectedSeason=964418083&selectedDivision=387107891&selectedCompetition=0&selectedFixtureGroupKey=1_822238577"
FULLTIME_API_URL = "https://faapi.jwhsolutions.co.uk/api/League/387107891/season/964418083"


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.table_depth = 0
        self.current_table: list[list[str]] | None = None
        self.current_row: list[str] | None = None
        self.current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag == "table":
            self.table_depth += 1
            if self.table_depth == 1:
                self.current_table = []
        elif self.table_depth == 1 and tag == "tr":
            self.current_row = []
        elif self.table_depth == 1 and tag in {"th", "td"}:
            self.current_cell = []
        elif self.table_depth == 1 and tag == "br" and self.current_cell is not None:
            self.current_cell.append(" ")

    def handle_data(self, data: str):
        if self.table_depth == 1 and self.current_cell is not None:
            self.current_cell.append(data)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if self.table_depth == 1 and tag in {"th", "td"} and self.current_cell is not None:
            text = " ".join("".join(self.current_cell).split())
            if self.current_row is not None:
                self.current_row.append(html.unescape(text))
            self.current_cell = None
        elif self.table_depth == 1 and tag == "tr" and self.current_row is not None:
            if any(cell.strip() for cell in self.current_row):
                assert self.current_table is not None
                self.current_table.append(self.current_row)
            self.current_row = None
        elif tag == "table" and self.table_depth:
            if self.table_depth == 1 and self.current_table:
                self.tables.append(self.current_table)
                self.current_table = None
            self.table_depth -= 1


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


def rewrite_table(sheet, table, headers: list[str], rows: list[dict[str, Any]]):
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


def ensure_table(book, sheet_name: str, table_name: str, headers: list[str]):
    names = [sheet.name for sheet in book.sheets]
    sheet = book.sheets[sheet_name] if sheet_name in names else book.sheets.add(sheet_name, after=book.sheets[-1])
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
    existing_headers = [str(v or "").strip() for v in table.range.rows[0].value]
    if existing_headers != headers:
        rewrite_table(sheet, table, headers, table_rows(table))
    return sheet, table


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() not in {"no", "n", "false", "0", "inactive", "off"}


def number(value: Any):
    if value in (None, ""):
        return None
    try:
        f = float(str(value).strip())
        return int(f) if f.is_integer() else f
    except Exception:
        return value


def clean_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def header_index(headers: list[str], aliases: set[str]) -> int | None:
    for i, value in enumerate(headers):
        if clean_header(value) in aliases:
            return i
    return None


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Welling-Dashboard/1.0",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def pick(mapping: dict[str, Any], aliases: set[str], default=None):
    by_clean = {clean_header(k): v for k, v in mapping.items()}
    for alias in aliases:
        if alias in by_clean:
            return by_clean[alias]
    return default


def find_dict_lists(value: Any):
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            yield value
        for item in value:
            yield from find_dict_lists(item)
    elif isinstance(value, dict):
        for child in value.values():
            yield from find_dict_lists(child)


def normalise_api_league(payload: Any) -> list[dict[str, Any]]:
    aliases = {
        "Position": {"position", "pos", "place", "rank", "ranking"},
        "Team": {"team", "teamname", "club", "clubname", "name"},
        "P": {"p", "pl", "played", "gamesplayed"},
        "W": {"w", "won", "wins"},
        "D": {"d", "drawn", "draws"},
        "L": {"l", "lost", "losses"},
        "GF": {"gf", "goalsfor", "for"},
        "GA": {"ga", "goalsagainst", "against"},
        "GD": {"gd", "goaldifference", "difference", "diff"},
        "Pts": {"pts", "points", "point"},
    }
    for items in find_dict_lists(payload):
        rows = []
        for item in items:
            team = str(pick(item, aliases["Team"], "") or "").strip()
            played = pick(item, aliases["P"], None)
            points = pick(item, aliases["Pts"], None)
            if not team or played is None or points is None:
                continue
            rows.append({
                "Position": number(pick(item, aliases["Position"], len(rows) + 1)) or len(rows) + 1,
                "Team": team,
                "P": number(played) or 0,
                "W": number(pick(item, aliases["W"], 0)) or 0,
                "D": number(pick(item, aliases["D"], 0)) or 0,
                "L": number(pick(item, aliases["L"], 0)) or 0,
                "GF": number(pick(item, aliases["GF"], 0)) or 0,
                "GA": number(pick(item, aliases["GA"], 0)) or 0,
                "GD": number(pick(item, aliases["GD"], 0)) or 0,
                "Pts": number(points) or 0,
            })
        if len(rows) >= 2:
            return rows
    raise RuntimeError("FullTime API returned data, but no league table could be identified")


def fetch_fulltime_api_league() -> list[dict[str, Any]]:
    return normalise_api_league(fetch_json(FULLTIME_API_URL))


def fetch_fa_html_league() -> list[dict[str, Any]]:
    req = urllib.request.Request(FA_LEAGUE_TABLE_URL, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        markup = response.read().decode("utf-8", errors="replace")

    parser = TableParser()
    parser.feed(markup)
    alias_map = {
        "Position": {"pos", "position", "place"},
        "Team": {"team", "club"},
        "P": {"p", "pl", "played"},
        "W": {"w", "won"},
        "D": {"d", "drawn"},
        "L": {"l", "lost"},
        "GF": {"gf", "goalsfor", "for"},
        "GA": {"ga", "goalsagainst", "against"},
        "GD": {"gd", "goaldifference", "diff"},
        "Pts": {"pts", "points"},
    }
    for table in parser.tables:
        for header_row_index, raw_headers in enumerate(table[:5]):
            indices = {key: header_index(raw_headers, vals) for key, vals in alias_map.items()}
            if any(indices[k] is None for k in ["Team", "P", "W", "D", "L", "Pts"]):
                continue
            rows = []
            for raw in table[header_row_index + 1:]:
                team_idx = indices["Team"]
                if team_idx is None or team_idx >= len(raw):
                    continue
                team = " ".join(str(raw[team_idx] or "").split()).strip()
                if not team:
                    continue
                def cell(key: str, default=""):
                    idx = indices[key]
                    return raw[idx] if idx is not None and idx < len(raw) else default
                rows.append({
                    "Position": number(cell("Position")) or len(rows) + 1,
                    "Team": team,
                    "P": number(cell("P")) or 0,
                    "W": number(cell("W")) or 0,
                    "D": number(cell("D")) or 0,
                    "L": number(cell("L")) or 0,
                    "GF": number(cell("GF")) or 0,
                    "GA": number(cell("GA")) or 0,
                    "GD": number(cell("GD")) or 0,
                    "Pts": number(cell("Pts")) or 0,
                })
            if len(rows) >= 2:
                return rows
    raise RuntimeError("Could not identify the league table in the FA Full-Time page")


def league_json(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    league = []
    for row in rows:
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
    return league


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
        try:
            links_sheet.range("A:F").column_width = 18
            links_sheet.range("C:C").column_width = 42
            links_sheet.range("D:D").column_width = 34
            league_sheet.range("A:J").column_width = 10
            league_sheet.range("B:B").column_width = 28
        except Exception:
            pass

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

        live_rows = None
        league_source = "cached Excel table"
        try:
            live_rows = fetch_fulltime_api_league()
            league_source = "FullTime API"
            print(f"League table refreshed via FullTime API: {len(live_rows)} teams")
        except Exception as api_exc:
            print(f"WARNING: FullTime API refresh failed: {api_exc}")
            try:
                live_rows = fetch_fa_html_league()
                league_source = "FA Full-Time page"
                print(f"League table refreshed directly from FA Full-Time: {len(live_rows)} teams")
            except Exception as fa_exc:
                print(f"WARNING: Direct FA Full-Time refresh failed: {fa_exc}")
                print("Using the current League Table sheet as a fallback.")
                live_rows = table_rows(league_table)

        rewrite_table(league_sheet, league_table, LEAGUE_HEADERS, live_rows)
        book.save()
        league = league_json(live_rows)

        data_dir = Path(__file__).resolve().parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "links.json").write_text(json.dumps(links, indent=2, ensure_ascii=False), encoding="utf-8")
        (data_dir / "league-table.json").write_text(json.dumps(league, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"Dashboard extras refreshed: {len(links)} web links, {len(league)} league rows ({league_source})")
        print("Web Links remains Excel-driven; League Table refresh is automatic.")
    finally:
        if book is not None:
            try: book.close()
            except Exception: pass
        try: app.quit()
        except Exception: pass


if __name__ == "__main__":
    main()
