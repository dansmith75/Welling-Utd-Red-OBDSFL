#!/usr/bin/env python3
"""Remove orphaned legacy stat rows after a fixture is deleted from Excel.

The wide Goals / Assists / Events sheets historically contain formula-linked
Date/Opposition cells. Deleting a row from Fixtures can leave #REF! rows behind.
This cleanup is deliberately conservative: it removes explicit #REF! rows and
fully identified rows whose fixture no longer exists, while preserving blank
placeholder/template rows.
"""

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
    text = str(value).strip()
    if "#REF" in text.upper():
        return ""
    return text[:10]


def clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if "#REF" in text.upper() else text


def table_matrix(table) -> list[list[Any]]:
    values = table.range.value
    if not values:
        return []
    if not isinstance(values[0], list):
        values = [values]
    return values


def fixture_keys(book) -> set[tuple[str, str]]:
    table = book.sheets["Fixtures"].tables["Fixtures"]
    matrix = table_matrix(table)
    if not matrix:
        return set()
    headers = [str(value or "").strip() for value in matrix[0]]
    try:
        date_idx = headers.index("Date")
        opp_idx = headers.index("Opposition")
    except ValueError:
        raise RuntimeError("Fixtures table must contain Date and Opposition columns")

    keys: set[tuple[str, str]] = set()
    for row in matrix[1:]:
        if not row:
            continue
        date_key = iso_date(row[date_idx] if date_idx < len(row) else None)
        opposition = clean_text(row[opp_idx] if opp_idx < len(row) else None).lower()
        if date_key and opposition:
            keys.add((date_key, opposition))
    return keys


def prune_table(book, sheet_name: str, table_name: str, valid_keys: set[tuple[str, str]]) -> int:
    if sheet_name not in [sheet.name for sheet in book.sheets]:
        return 0
    sheet = book.sheets[sheet_name]
    try:
        table = sheet.tables[table_name]
    except Exception:
        return 0

    matrix = table_matrix(table)
    if len(matrix) <= 1:
        return 0

    headers = [str(value or "").strip() for value in matrix[0]]
    try:
        date_idx = headers.index("Date")
        opp_idx = headers.index("Opposition")
    except ValueError:
        return 0

    delete_indexes: list[int] = []
    for list_row_index, row in enumerate(matrix[1:], start=1):
        date_value = row[date_idx] if date_idx < len(row) else None
        opp_value = row[opp_idx] if opp_idx < len(row) else None
        raw_date = str(date_value or "").strip()
        raw_opp = str(opp_value or "").strip()

        # Explicit broken formula references are always safe to remove.
        if "#REF" in raw_date.upper() or "#REF" in raw_opp.upper():
            delete_indexes.append(list_row_index)
            continue

        date_key = iso_date(date_value)
        opposition = clean_text(opp_value).lower()

        # Keep blank/template rows. Only remove a fully identified data row when
        # its Date + Opposition no longer exists in Fixtures.
        if date_key and opposition and (date_key, opposition) not in valid_keys:
            delete_indexes.append(list_row_index)

    for list_row_index in reversed(delete_indexes):
        table.api.ListRows(list_row_index).Delete()

    return len(delete_indexes)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python prune_deleted_fixture_rows.py /path/to/workbook.xlsx")

    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    import xlwings as xw

    app = None
    book = None
    try:
        app = xw.App(visible=False, add_book=False)
        app.display_alerts = False
        app.screen_updating = False
        book = app.books.open(str(path), update_links=False, read_only=False)

        valid_keys = fixture_keys(book)
        removed = 0
        removed += prune_table(book, "Goals", "Goals", valid_keys)
        removed += prune_table(book, "Assists", "Assists", valid_keys)
        removed += prune_table(book, "Events", "Events", valid_keys)

        book.save()
        print(f"Deleted-fixture cleanup: removed {removed} orphan Goals/Assists/Events rows")
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
    main()
