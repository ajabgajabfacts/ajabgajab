"""
auth_setup.py — Run this ONCE locally for each YouTube channel.
Authenticates your Google account and lets you manually enter each
channel ID (since brand account channels don't appear via the API).

Usage:
    python auth_setup.py

Requirements:
    pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
"""

import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube",           # full access
    "https://www.googleapis.com/auth/youtube.upload",    # upload
    "https://www.googleapis.com/auth/youtube.readonly",  # read stats
    "https://www.googleapis.com/auth/youtube.force-ssl", # required for comments API
    # Retention, average view duration, impressions and CTR live in the YouTube
    # ANALYTICS api, which is a different service with its own scope. Without this
    # the reports endpoint returns a hard 403 and all we can see is a view count —
    # "812 views" with no idea whether people watched or swiped at second four.
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def main():
    print("\n=== YouTube OAuth Setup ===")
    print("Make sure 'client_secret.json' is in this folder.")
    print("A browser window will open — log in to your Google account.\n")

    flow  = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)

    # Try to list channels automatically
    youtube = build("youtube", "v3", credentials=creds)
    response = youtube.channels().list(part="snippet", mine=True, maxResults=50).execute()
    channels = response.get("items", [])

    print("\n=== Channels detected automatically ===")
    if channels:
        for ch in channels:
            print(f"  {ch['snippet']['title']}  ->  {ch['id']}")
    else:
        print("  (none detected automatically)")

    # Auto-use the channel on this account (no typing needed). Falls back to a
    # prompt only if none is detected (e.g. a brand account the API can't see).
    if channels:
        channel_title = channels[0]["snippet"]["title"]
        channel_id    = channels[0]["id"]
        print(f"\nUsing detected channel: {channel_title}  ->  {channel_id}")
    else:
        print("\n=== Manual Channel Entry (no channel auto-detected) ===")
        channel_title = input("Enter the channel NAME: ").strip()
        channel_id    = input("Enter the channel ID (UC...): ").strip()

    if not channel_id.startswith("UC"):
        print("WARNING: Channel ID usually starts with 'UC' -- double check it.")

    credentials_dict = {
        "channel_id":    channel_id,
        "channel_title": channel_title,
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes),
    }

    # The pipeline expects CHANNEL_CONFIG = {niche, accent, keywords, credentials}.
    # Try to inherit niche/accent/keywords from a previous wrapped config for the
    # same channel_id so regeneration is one-shot. Falls back to prompting.
    inherited = {}
    for candidate in sorted(Path(".").glob("CHANNEL*_CONFIG*.json")) + sorted(Path(".").glob("token_*.json")):
        try:
            prev = json.loads(candidate.read_text(encoding="utf-8"))
            prev_creds = prev.get("credentials", prev)
            if isinstance(prev_creds, dict) and prev_creds.get("channel_id") == channel_id:
                inherited = {k: prev[k] for k in ("niche", "accent", "keywords") if k in prev}
                if inherited:
                    print(f"  Inheriting niche/accent/keywords from {candidate.name}")
                    break
        except Exception:
            continue

    # Presets for ajabgajab — no prompts, so the whole run is browser-only.
    inherited.setdefault("niche", "Amazing Facts Hinglish")
    inherited.setdefault("keywords", ["ajab gajab facts", "amazing facts", "facts in hindi",
                                      "hinglish facts", "did you know", "gk facts", "india facts"])
    inherited.setdefault("accent", [124, 58, 237])   # violet, matches the branding

    wrapped = {
        "niche":       inherited["niche"],
        "accent":      inherited["accent"],
        "keywords":    inherited["keywords"],
        "credentials": credentials_dict,
    }

    output = json.dumps(wrapped)

    safe_title = channel_title.replace(" ", "_")[:20]
    print("\n" + "=" * 60)
    print(f"SUCCESS! Copy everything below and save as your GitHub Secret")
    print(f"for {channel_title}:")
    print("=" * 60)
    print(output)
    print("=" * 60 + "\n")

    fname = f"CHANNEL_{safe_title}_CONFIG.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(wrapped, f, indent=2)
    print(f"Wrapped config saved locally to: {fname}  (keep this private!)")
    print("Output is one-line JSON ready to paste into the GitHub secret.\n")


if __name__ == "__main__":
    main()
