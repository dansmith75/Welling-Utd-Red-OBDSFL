# One-click Welling data update

Excel remains the football-data source of truth. GitHub is the publishing layer.

## Windows

1. Save and close `Welling United Red OBDSFL 26-27.xlsx`.
2. Pull the repo once after this file is added.
3. Double-click `UPDATE-WELLING.bat`.
4. Review the update summary.
5. Enter `Y` to publish.

The updater automatically finds the workbook in the normal personal OneDrive location on Dan's Windows PC.

## Mac

The same Python updater supports OneDrive under macOS CloudStorage.

First-time setup in Terminal from the repo folder:

```bash
chmod +x UPDATE-WELLING.command
```

Then double-click `UPDATE-WELLING.command` in Finder.

Python 3, Git and `openpyxl` must be available locally.

## What it does

1. `git pull --ff-only`
2. Finds the master `.xlsx` workbook in OneDrive
3. Runs `export_welling_json.py`
4. Validates all six JSON exports
5. Shows player, fixture/result and other-data changes
6. Asks for confirmation
7. Commits only `data/*`
8. Pushes to GitHub

Dashboard and Attendance/Matchday then consume the shared published squad/fixture data.
