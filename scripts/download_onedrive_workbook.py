#!/usr/bin/env python3
"""Download the private Welling workbook from OneDrive using Microsoft Graph.

Required environment variables:
- MS_CLIENT_ID
- MS_REFRESH_TOKEN
- ONEDRIVE_FILE_PATH

The Azure/Microsoft app should use delegated Microsoft Graph Files.Read access
and offline_access. The workbook is downloaded only into the workflow runner;
it is never committed to the repository.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def post_form(url: str, data: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def download_file(url: str, token: str, output: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        output.write_bytes(response.read())


def main() -> None:
    client_id = required_env("MS_CLIENT_ID")
    refresh_token = required_env("MS_REFRESH_TOKEN")
    one_drive_path = required_env("ONEDRIVE_FILE_PATH").lstrip("/")

    output = Path(
        os.environ.get(
            "WORKBOOK_OUTPUT",
            "Welling United Red OBDSFL 26-27.xlsx",
        )
    )

    token_response = post_form(
        TOKEN_URL,
        {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "offline_access Files.Read",
        },
    )

    access_token = token_response.get("access_token")
    if not access_token:
        raise RuntimeError("Microsoft token refresh did not return an access token.")

    encoded_path = urllib.parse.quote(one_drive_path, safe="/")
    content_url = f"{GRAPH_ROOT}/me/drive/root:/{encoded_path}:/content"

    print(f"Downloading OneDrive workbook: /{one_drive_path}")
    download_file(content_url, access_token, output)

    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("Workbook download produced an empty file.")

    print(f"Workbook downloaded to {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
