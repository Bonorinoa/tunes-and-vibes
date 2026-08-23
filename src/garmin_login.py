"""One-time Garmin Connect login. Prompts for password + MFA, caches tokens under auth/."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
TOKEN_STORE = str(ROOT / "auth" / "garmin")


def main() -> None:
    load_dotenv(ROOT / ".env")
    email = os.getenv("GARMIN_EMAIL")
    if not email:
        sys.exit("set GARMIN_EMAIL in .env first")
    from getpass import getpass

    from garminconnect import Garmin

    password = getpass("Garmin password: ")
    client = Garmin(email=email, password=password, prompt_mfa=lambda: input("MFA code: "))
    try:
        client.login(TOKEN_STORE)
    except TypeError:
        client.login()  # older signature
    print("login ok · tokens cached in", TOKEN_STORE)

    # Smoke test: yesterday's sleep + today's stats. Tolerant of method drift.
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    for label, fn in (
        ("sleep(yesterday)", lambda: client.get_sleep_data(yesterday)),
        ("stats(today)", lambda: client.get_stats(date.today().isoformat())),
        ("heart-rates(today)", lambda: client.get_heart_rates(date.today().isoformat())),
    ):
        try:
            data = fn()
            if isinstance(data, dict):
                print(f"{label}: ok · top-level keys: {sorted(data.keys())[:12]}")
            else:
                print(f"{label}: ok · {type(data).__name__}")
        except Exception as exc:  # noqa: BLE001 - diagnostic sweep, not control flow
            print(f"{label}: unavailable ({type(exc).__name__}: {exc})")


if __name__ == "__main__":
    main()
