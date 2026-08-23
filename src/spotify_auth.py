"""One-time Spotify OAuth. Opens a browser, catches the localhost redirect, caches tokens."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

ROOT = Path(__file__).resolve().parents[1]
AUTH_DIR = ROOT / "auth"
CACHE = AUTH_DIR / "spotify_token.json"
ENV_PATH = ROOT / ".env"

SCOPES = " ".join(
    [
        "user-read-private",
        "user-read-email",
        "user-read-recently-played",
        "user-read-currently-playing",
        "user-top-read",
        "user-library-read",
        "playlist-read-private",
        "playlist-read-collaborative",
    ]
)


def _load_env() -> None:
    load_dotenv(ENV_PATH)
    missing = [k for k in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET") if not os.getenv(k)]
    if missing:
        sys.exit(f"missing {missing} in {ENV_PATH}")


def _oauth() -> SpotifyOAuth:
    AUTH_DIR.mkdir(exist_ok=True)
    return SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        scope=SCOPES,
        cache_path=str(CACHE),
        open_browser=True,
    )


def _write_refresh_token(token: str) -> None:
    """Keep refresh token in .env without rewriting other values."""
    text = ENV_PATH.read_text() if ENV_PATH.exists() else ""
    lines = text.splitlines()
    key = "SPOTIFY_REFRESH_TOKEN="
    written = False
    out = []
    for line in lines:
        if line.startswith(key) or line.startswith("# " + key):
            out.append(key + token)
            written = True
        else:
            out.append(line)
    if not written:
        if out and out[-1] != "":
            out.append("")
        out.append(key + token)
    ENV_PATH.write_text("\n".join(out) + "\n")


def main() -> None:
    _load_env()
    oauth = _oauth()
    print("If a browser does not open, visit:")
    print(oauth.get_authorize_url())
    print("Waiting on http://127.0.0.1:8888/callback ...")
    token_info = oauth.get_access_token(as_dict=True, check_cache=False)
    refresh = token_info.get("refresh_token")
    if not refresh:
        cached = oauth.get_cached_token() or {}
        refresh = cached.get("refresh_token")
    if refresh:
        _write_refresh_token(refresh)
        print("refresh token written to .env")
    else:
        print("warning: no refresh token in response (check scopes / consent screen)")

    sp = Spotify(auth_manager=oauth)
    me = sp.current_user()
    recent = sp.current_user_recently_played(limit=5)
    items = recent.get("items") or []
    print(f"user: {me.get('id')}  product: {me.get('product')}  display: {me.get('display_name')}")
    print(f"recently-played sample: {len(items)} items")
    for item in items:
        track = item.get("track") or {}
        artists = ", ".join(a.get("name", "?") for a in (track.get("artists") or []))
        print(f"  {item.get('played_at')}  {artists} — {track.get('name')}")


if __name__ == "__main__":
    main()
