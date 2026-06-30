from pathlib import Path
import json
from datetime import datetime, date
import openpyxl

INPUT_FILE = Path("Welling United Red OBDSFL 26-27.xlsx")
OUTPUT_DIR = Path("data")


def clean_value(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value in ("", None):
        return None
    return value


def safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def attendance_value(value):
    if value is True:
        return "Y"
    if value is False or value is None:
        return ""
    return str(value).strip()


def get_players(wb):
    ws = wb["Squad"]
    players = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        first_name = row[1]
        likely = row[7]

        if first_name and str(likely).upper() in ("Y", "Q", "N"):
            players.append(str(first_name).strip())

    return players


def export_matches(wb):
    ws = wb["Fixtures"]
    rows = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        match_date = clean_value(row[0])
        opposition = row[2]

        if not match_date:
            continue

        rows.append({
            "date": match_date,
            "opposition": "" if opposition in (None, 0) else opposition,
            "competition": "" if row[3] in (None, 0) else row[3],
            "homeAway": "" if row[4] in (None, 0) else row[4],
            "postponed": bool(row[5]),
            "goalsFor": safe_int(row[6]),
            "goalsAgainst": safe_int(row[7]),
            "result": "" if row[8] in (None, 0) else row[8],
        })

    return rows


def export_player_stat_sheet(wb, sheet_name, key_name):
    ws = wb[sheet_name]
    headers = [cell.value for cell in ws[1]]
    players = headers[2:-1]
    rows = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        match_date = clean_value(row[0])
        opposition = row[1]

        if not match_date:
            continue

        player_values = {}

        for player, value in zip(players, row[2:-1]):
            if player:
                player_values[str(player).strip()] = safe_int(value)

        rows.append({
            "date": match_date,
            "opposition": "" if opposition in (None, 0) else opposition,
            key_name: player_values
        })

    return rows


def export_events(wb):
    ws = wb["Events"]
    headers = [cell.value for cell in ws[1]]
    players = headers[2:]
    rows = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        event_date = clean_value(row[0])
        opposition = row[1]

        if not event_date:
            continue

        events = {}

        for player, value in zip(players, row[2:]):
            if player:
                events[str(player).strip()] = "" if value in (None, 0) else str(value).strip()

        rows.append({
            "date": event_date,
            "opposition": "" if opposition in (None, 0) else opposition,
            "events": events
        })

    return rows


def export_attendance_sheet(wb, sheet_name, opposition_column=True):
    ws = wb[sheet_name]
    headers = [cell.value for cell in ws[1]]

    player_start_col = 3
    player_end_col = len(headers) - 1

    players = headers[player_start_col:player_end_col]
    rows = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        session_date = clean_value(row[0])

        if not session_date:
            continue

        attendance = {}

        for player, value in zip(players, row[player_start_col:player_end_col]):
            if player:
                attendance[str(player).strip()] = attendance_value(value)

        record = {
            "date": session_date,
            "attendance": attendance,
            "count": safe_int(row[player_end_col])
        }

        if opposition_column:
            record["opposition"] = "" if row[2] in (None, 0) else row[2]
        else:
            record["session"] = "" if row[2] in (None, 0) else row[2]

        rows.append(record)

    return rows


def write_json(filename, data):
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported {path}")


def export():
    wb = openpyxl.load_workbook(INPUT_FILE, data_only=True)

    write_json("players.json", get_players(wb))
    write_json("matches.json", export_matches(wb))
    write_json("goals.json", export_player_stat_sheet(wb, "Goals", "goals"))
    write_json("assists.json", export_player_stat_sheet(wb, "Assists", "assists"))
    write_json("events.json", export_events(wb))
    write_json("match-attendance.json", export_attendance_sheet(wb, "Match Attendance", True))
    write_json("training-attendance.json", export_attendance_sheet(wb, "Training Attendance", False))

    print("Export complete.")


if __name__ == "__main__":
    export()