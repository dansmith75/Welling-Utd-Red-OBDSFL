#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

SEASON_ID = 964418083
GROUP_ID = "1_822238577"
LEAGUE_HEADERS = ["Position", "Team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]


def ensure_package() -> None:
    if importlib.util.find_spec("full_time_api") is not None:
        return
    print("Installing one-time helper: full-time-api...")
    subprocess.run([sys.executable, "-m", "pip", "install", "full-time-api"], check=True)


def clean_team(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def build_table(teams: list[str], raw_results: list[list[str]]) -> list[dict]:
    stats = {}
    order = []
    for name in teams:
        team = clean_team(name)
        if not team or team.lower() in {"all", "select team"}:
            continue
        if team not in stats:
            order.append(team)
            stats[team] = {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0, "Pts": 0}

    for row in raw_results:
        if len(row) < 4:
            continue
        home = clean_team(row[1])
        score = clean_team(row[2])
        away = clean_team(row[3])
        match = re.search(r"(\d+)\s*-\s*(\d+)", score)
        if not home or not away or not match:
            continue
        if home not in stats or away not in stats:
            # Ignore cup/cross-division rows if Full-Time includes any.
            continue
        hg, ag = int(match.group(1)), int(match.group(2))
        hs, aas = stats[home], stats[away]
        hs["P"] += 1; aas["P"] += 1
        hs["GF"] += hg; hs["GA"] += ag
        aas["GF"] += ag; aas["GA"] += hg
        if hg > ag:
            hs["W"] += 1; hs["Pts"] += 3; aas["L"] += 1
        elif hg < ag:
            aas["W"] += 1; aas["Pts"] += 3; hs["L"] += 1
        else:
            hs["D"] += 1; aas["D"] += 1; hs["Pts"] += 1; aas["Pts"] += 1

    rows = []
    for team in order:
        s = stats[team]
        s["GD"] = s["GF"] - s["GA"]
        rows.append({"Team": team, **s})

    # Normal league ordering. At 0 games retain Full-Time team-list order.
    if any(row["P"] for row in rows):
        rows.sort(key=lambda r: (-r["Pts"], -r["GD"], -r["GF"], r["Team"].lower()))
    for i, row in enumerate(rows, 1):
        row["Position"] = i
    return rows


def rewrite_excel(workbook: Path, rows: list[dict]) -> None:
    import xlwings as xw
    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    app.screen_updating = False
    book = None
    try:
        book = app.books.open(str(workbook), update_links=False, read_only=False)
        names = [sheet.name for sheet in book.sheets]
        sheet = book.sheets["League Table"] if "League Table" in names else book.sheets.add("League Table", after=book.sheets[-1])
        try:
            table = sheet.tables["LeagueTable"]
        except Exception:
            sheet.range("A1").value = [LEAGUE_HEADERS]
            sheet.range((2, 1), (2, len(LEAGUE_HEADERS))).clear_contents()
            table = sheet.tables.add(sheet.range((1, 1), (2, len(LEAGUE_HEADERS))), name="LeagueTable")

        start_row, start_col = table.range.row, table.range.column
        end_row = start_row + max(1, len(rows))
        end_col = start_col + len(LEAGUE_HEADERS) - 1
        table.resize(sheet.range((start_row, start_col), (end_row, end_col)))
        sheet.range((start_row, start_col), (start_row, end_col)).value = [LEAGUE_HEADERS]
        if rows:
            matrix = [[row.get(h, "") for h in LEAGUE_HEADERS] for row in rows]
            sheet.range((start_row + 1, start_col), (start_row + len(rows), end_col)).value = matrix
        else:
            sheet.range((start_row + 1, start_col), (start_row + 1, end_col)).clear_contents()
        try:
            sheet.range("A:J").column_width = 10
            sheet.range("B:B").column_width = 32
        except Exception:
            pass
        book.save()
    finally:
        if book is not None:
            try: book.close()
            except Exception: pass
        try: app.quit()
        except Exception: pass


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python refresh_league_from_results.py /path/to/workbook.xlsx")
    workbook = Path(sys.argv[1]).expanduser().resolve()
    ensure_package()
    from full_time_api import Division

    division = Division()
    teams = division.get_teams(SEASON_ID, GROUP_ID)
    results = division.get_results(SEASON_ID, GROUP_ID)
    rows = build_table(teams, results)
    if len(rows) < 2:
        raise RuntimeError(f"Full-Time returned only {len(rows)} league teams")
    rewrite_excel(workbook, rows)
    played = sum(row["P"] for row in rows) // 2
    print(f"FA Full-Time standings rebuilt from teams/results: {len(rows)} teams, {played} league games")


if __name__ == "__main__":
    main()
