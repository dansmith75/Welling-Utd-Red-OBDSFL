# Welling OneDrive → GitHub cloud sync

Once configured, the normal workflow is:

1. Edit `Welling United Red OBDSFL 26-27.xlsx` in Excel on Windows or Mac.
2. Save it to OneDrive.
3. GitHub checks OneDrive every 15 minutes.
4. If the exported JSON changes, GitHub commits `data/*.json`.
5. GitHub Pages updates the Dashboard; Attendance/Matchday consume the same shared player/fixture feeds.

The Excel workbook itself is **not** committed to this repository.

## One-time Microsoft setup

Create an app registration for the Microsoft account that owns the workbook.

Use a supported account type that includes **personal Microsoft accounts**.

Under **Authentication**, enable **Allow public client flows** so the one-time device-code helper can authenticate.

Under **API permissions**, add Microsoft Graph delegated permission:

- `Files.Read`

The helper also requests `offline_access` at sign-in so Microsoft can issue a refresh token.

Copy the app's **Application (client) ID**.

## Get the refresh token

Pull the repo locally, then run:

```powershell
py scripts/get_onedrive_refresh_token.py YOUR_CLIENT_ID
```

Follow the Microsoft sign-in instructions shown in the terminal. Sign in with the account that owns the Welling workbook.

The helper prints a refresh token. Treat this value as a password.

## GitHub repository secrets

In the repository:

**Settings → Secrets and variables → Actions → New repository secret**

Create:

- `MS_CLIENT_ID` — the Application (client) ID
- `MS_REFRESH_TOKEN` — the refresh token printed by the helper

The workbook path is already configured in the workflow as:

`Documents/Dan/Football/Welling United Red OBDSFL 26-27.xlsx`

## Test

Go to:

**Actions → Sync Welling workbook data → Run workflow**

A successful run will:

- privately download the workbook from OneDrive
- run `export_welling_json.py`
- validate all JSON outputs
- commit only changed `data/*.json`

After that, the scheduled workflow checks every 15 minutes.
