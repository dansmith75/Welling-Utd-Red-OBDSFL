from pathlib import Path
import json
from datetime import datetime, date
import openpyxl

INPUT_FILE = Path('Welling United Red OBDSFL 26-27.xlsx')
OUTPUT_FILE = Path('welling-data.json')

# This script expects to be run from the same folder as the Excel workbook.
# It exports dashboard-safe data only. It deliberately excludes player phone numbers and emails.


def clean_key(value):
    return str(value).strip().lower().replace(' / ', '_').replace(' ', '_').replace('-', '_')


def clean_value(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value == '':
        return None
    return value


def sheet_to_records(ws, header_row=1, max_col=None):
    headers = []
    for cell in ws[header_row][:max_col]:
        if cell.value is None:
            headers.append(None)
        else:
            headers.append(clean_key(cell.value))

    records = []
    for row in ws.iter_rows(min_row=header_row + 1, max_col=max_col, values_only=True):
        record = {}
        has_data = False
        for header, value in zip(headers, row):
            if header is None:
                continue
            value = clean_value(value)
            record[header] = value
            if value not in (None, ''):
                has_data = True
        if has_data:
            records.append(record)
    return records


def player_matrix_to_events(ws, stat_name):
    """Turn a wide sheet like Goals/Assists into a tidy list of events."""
    headers = [cell.value for cell in ws[1]]
    players = headers[2:-1]  # skip Date/Opposition and final count column
    events = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        match_date = clean_value(row[0])
        opposition = row[1]
        if not match_date:
            continue
        for player, value in zip(players, row[2:-1]):
            if player and isinstance(value, (int, float)) and value > 0:
                events.append({
                    'date': match_date,
                    'opposition': opposition,
                    'player': player,
                    stat_name: int(value),
                })
    return events


def export():
    wb = openpyxl.load_workbook(INPUT_FILE, data_only=True)

    fixtures = sheet_to_records(wb['Fixtures'], max_col=9)

    # Public/player dashboard-safe squad fields only
    raw_squad = sheet_to_records(wb['Squad'], max_col=8)
    squad = []
    for p in raw_squad:
        squad.append({
            'name': p.get('name'),
            'short_name': p.get('first_name'),
            'position': p.get('position'),
            'kit_size': p.get('kit_size'),
            'shirt_number': p.get('shirt_number'),
            'likely': p.get('likely'),
        })

    data = {
        'team': 'Welling United Red OBDSFL',
        'season': '2026-27',
        'last_updated': datetime.now().isoformat(timespec='seconds'),
        'fixtures': fixtures,
        'squad': squad,
        'goals': player_matrix_to_events(wb['Goals'], 'goals'),
        'assists': player_matrix_to_events(wb['Assists'], 'assists'),
        'attendance': sheet_to_records(wb['Attendance'], max_col=4),
        'monthly_fees': sheet_to_records(wb['Monthly Fees'], max_col=13),
    }

    OUTPUT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Exported {OUTPUT_FILE}')


if __name__ == '__main__':
    export()
