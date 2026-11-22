"""youtube_login.py - One-time login that lets the pipeline upload to YOUR YouTube channel.

Run once on your laptop:   python scripts/youtube_login.py
A browser opens. Sign in with the Google account that owns the channel, pick the
channel, and allow access. The result is saved to youtube_token.json (git ignores it).
Copy its 3 values into .env and later into GitHub Secrets. Never share or commit them.
"""
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parents[1]
CLIENT_FILE = ROOT / "client_secret.json"   # the file you downloaded from Google Cloud
OUTPUT_FILE = ROOT / "youtube_token.json"   # the result (ignored by git)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]  # permission to upload only


def main() -> None:
    if not CLIENT_FILE.exists():
        raise SystemExit(f"Put your downloaded OAuth file here first: {CLIENT_FILE}")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    # access_type=offline + prompt=consent make Google give us a long-lived refresh token
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        raise SystemExit(
            "Google did not return a refresh token. Remove this app at "
            "myaccount.google.com/permissions, then run the script again."
        )

    OUTPUT_FILE.write_text(
        json.dumps(
            {
                "YOUTUBE_CLIENT_ID": creds.client_id,
                "YOUTUBE_CLIENT_SECRET": creds.client_secret,
                "YOUTUBE_REFRESH_TOKEN": creds.refresh_token,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Done. Saved to {OUTPUT_FILE.name}. Copy the values into .env. Do not share or commit them.")


if __name__ == "__main__":
    main()