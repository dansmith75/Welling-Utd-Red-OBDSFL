#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ALIASES = [
    ("Match ID", "MatchId"),
    ("Match Date", "MatchDate"),
    ("Record Type", "RecordType"),
]


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python ensure_matchday_export_columns.py /path/to/workbook.xlsx")
    workbook = Path(sys.argv[1]).expanduser().resolve()

    import xlwings as xw
    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    app.screen_updating = False
    book = None
    try:
        book = app.books.open(str(workbook), update_links=False, read_only=False)
        if "MatchdayRecords" not in [s.name for s in book.sheets]:
            print("MatchdayRecords not present; no export aliases needed")
            return
        sheet = book.sheets["MatchdayRecords"]
        table = sheet.tables["MatchdayRecords"]
        headers = [str(v or "").strip() for v in table.range.rows[0].value]

        for alias, source in ALIASES:
            if alias in headers:
                continue
            new_col = table.range.last_cell.column + 1
            new_end = table.range.last_cell.row
            sheet.range((table.range.row, new_col)).value = alias
            table.resize(sheet.range((table.range.row, table.range.column), (new_end, new_col)))
            headers.append(alias)

        headers = [str(v or "").strip() for v in table.range.rows[0].value]
        first_data_row = table.range.row + 1
        last_data_row = table.range.last_cell.row
        for alias, source in ALIASES:
            if alias not in headers or source not in headers or last_data_row < first_data_row:
                continue
            alias_col = table.range.column + headers.index(alias)
            source_col = table.range.column + headers.index(source)
            values = sheet.range((first_data_row, source_col), (last_data_row, source_col)).value
            sheet.range((first_data_row, alias_col), (last_data_row, alias_col)).value = values

        book.save()
        print("Matchday export aliases refreshed: Match ID, Match Date, Record Type")
    finally:
        if book is not None:
            try: book.close()
            except Exception: pass
        try: app.quit()
        except Exception: pass


if __name__ == "__main__":
    main()
