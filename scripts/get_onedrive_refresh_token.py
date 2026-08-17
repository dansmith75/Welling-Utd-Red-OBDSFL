#!/usr/bin/env python3
"""One-time helper to obtain a Microsoft refresh token for the Welling sync.

Usage:
    python scripts/get_onedrive_refresh_token.py YOUR_CLIENT_ID

The script uses Microsoft's OAuth device-code flow. It will print a URL and
short code. Sign in with the Microsoft account that owns the Welling workbook.
At the end it prints the refresh token to copy into the GitHub repository
secret named MS_REFRESH_TOKEN.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

AUTH_ROOT = "https://login.microsoftonline.com/common/oauth2/v2.0"
SCOPES = "offline_access Files.Read"


def post_form(url: str, data: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(payload)
        except Exception:
            raise RuntimeError(payload) from exc


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/get_onedrive_refresh_token.py YOUR_CLIENT_ID")

    client_id = sys.argv[1].strip()

    device = post_form(
        f"{AUTH_ROOT}/devicecode",
        {"client_id": client_id, "scope": SCOPES},
    )

    if "device_code" not in device:
        raise RuntimeError(f"Device-code request failed: {device}")

    print()
    print(device.get("message", "Open the Microsoft sign-in page and enter the displayed code."))
    print()

    interval = int(device.get("interval", 5))
    expires_at = time.time() + int(device.get("expires_in", 900))

    while time.time() < expires_at:
        token = post_form(
            f"{AUTH_ROOT}/token",
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": client_id,
                "device_code": device["device_code"],
            },
        )

        if "refresh_token" in token:
            print("Authorisation complete.\n")
            print("COPY THIS VALUE INTO GITHUB SECRET: MS_REFRESH_TOKEN\n")
            print(token["refresh_token"])
            print()
            return

        error = token.get("error")
        if error == "authorization_pending":
            time.sleep(interval)
            continue
        if error == "slow_down":
            interval += 5
            time.sleep(interval)
            continue

        raise RuntimeError(f"Microsoft authorisation failed: {token}")

    raise RuntimeError("Microsoft authorisation timed out. Run the helper again.")


if __name__ == "__main__":
    main()
