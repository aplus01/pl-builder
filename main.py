#!/usr/bin/env python3
"""
YouTube Playlist Builder CLI
Search for videos and add them to your YouTube playlists.
"""

import os
import json
import argparse
import sys
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# --- Config ---
SCOPES = ["https://www.googleapis.com/auth/youtube"]
TOKEN_FILE = Path("token.json")
SECRETS_FILE = Path("client_secrets.json")


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

def authenticate() -> object:
    """Authenticate and return a YouTube API service object."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not SECRETS_FILE.exists():
                print(f"[error] '{SECRETS_FILE}' not found.")
                print("Download OAuth 2.0 credentials from Google Cloud Console and save as client_secrets.json")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())
        print(f"[auth] Credentials saved to {TOKEN_FILE}")

    return build("youtube", "v3", credentials=creds)


# ──────────────────────────────────────────────
# API helpers
# ──────────────────────────────────────────────

def search_videos(youtube, query: str, max_results: int = 10) -> list[dict]:
    """Search YouTube and return a list of video dicts."""
    response = youtube.search().list(
        part="snippet",
        q=query,
        type="video",
        maxResults=max_results,
        safeSearch="none",
    ).execute()

    return [
        {
            "index": i + 1,
            "videoId": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "url": f"https://youtu.be/{item['id']['videoId']}",
        }
        for i, item in enumerate(response.get("items", []))
    ]


def list_playlists(youtube) -> list[dict]:
    """Return all playlists owned by the authenticated user."""
    playlists = []
    request = youtube.playlists().list(
        part="snippet,contentDetails",
        mine=True,
        maxResults=50,
    )
    while request:
        response = request.execute()
        for item in response.get("items", []):
            playlists.append({
                "playlistId": item["id"],
                "title": item["snippet"]["title"],
                "count": item["contentDetails"]["itemCount"],
            })
        request = youtube.playlists().list_next(request, response)
    return playlists


def create_playlist(youtube, title: str, description: str = "", privacy: str = "private") -> dict:
    """Create a new playlist and return its metadata."""
    response = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": privacy},
        },
    ).execute()
    return {"playlistId": response["id"], "title": response["snippet"]["title"]}


def add_video_to_playlist(youtube, playlist_id: str, video_id: str) -> bool:
    """Add a video to a playlist. Returns True on success."""
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()
        return True
    except HttpError as e:
        error = json.loads(e.content).get("error", {})
        print(f"  [error] {error.get('message', str(e))}")
        return False


# ──────────────────────────────────────────────
# Interactive helpers
# ──────────────────────────────────────────────

def print_videos(videos: list[dict]) -> None:
    print()
    for v in videos:
        print(f"  {v['index']:>2}. {v['title'][:70]}")
        print(f"      {v['channel']}  |  {v['url']}")
    print()


def print_playlists(playlists: list[dict]) -> None:
    print()
    for i, p in enumerate(playlists, 1):
        print(f"  {i:>2}. {p['title']}  ({p['count']} videos)  [{p['playlistId']}]")
    print()


def pick_from_list(items: list, label: str) -> list:
    """
    Prompt the user to select items by number.
    Supports ranges (1-3), comma-separated (1,3,5), or 'all'.
    Returns selected items.
    """
    raw = input(f"Select {label} (e.g. 1,3 or 1-5 or all): ").strip()
    if raw.lower() == "all":
        return items

    selected = []
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            for idx in range(int(start), int(end) + 1):
                if 1 <= idx <= len(items):
                    selected.append(items[idx - 1])
        else:
            idx = int(part)
            if 1 <= idx <= len(items):
                selected.append(items[idx - 1])
    return selected


# ──────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────

def cmd_search_and_add(youtube, args) -> None:
    """Interactive: search → pick videos → pick/create playlist → add."""
    query = args.query or input("Search query: ").strip()
    max_results = args.max_results

    print(f"\n[search] Searching for '{query}'...")
    videos = search_videos(youtube, query, max_results)
    if not videos:
        print("[error] No results found.")
        return

    print_videos(videos)
    selected_videos = pick_from_list(videos, "videos to add")
    if not selected_videos:
        print("[info] No videos selected.")
        return

    # Pick or create playlist
    print("\n[playlists] Fetching your playlists...")
    playlists = list_playlists(youtube)
    print_playlists(playlists)
    print(f"  {len(playlists) + 1:>2}. + Create new playlist")
    print()

    raw = input("Select playlist number: ").strip()
    idx = int(raw)

    if idx == len(playlists) + 1:
        title = input("New playlist title: ").strip()
        privacy = input("Privacy (public/unlisted/private) [private]: ").strip() or "private"
        playlist = create_playlist(youtube, title, privacy=privacy)
        print(f"[created] '{playlist['title']}' ({playlist['playlistId']})")
    elif 1 <= idx <= len(playlists):
        playlist = playlists[idx - 1]
    else:
        print("[error] Invalid selection.")
        return

    # Add videos
    print(f"\n[adding] Adding {len(selected_videos)} video(s) to '{playlist['title']}'...")
    for v in selected_videos:
        success = add_video_to_playlist(youtube, playlist["playlistId"], v["videoId"])
        status = "✓" if success else "✗"
        print(f"  {status} {v['title'][:70]}")

    print("\nDone.")


def cmd_list_playlists(youtube, args) -> None:
    """Print all playlists for the authenticated account."""
    print("\n[playlists] Your playlists:")
    playlists = list_playlists(youtube)
    if not playlists:
        print("  No playlists found.")
        return
    print_playlists(playlists)


def cmd_add_by_url(youtube, args) -> None:
    """Add a specific video URL/ID to a playlist."""
    video_input = args.video or input("Video URL or ID: ").strip()
    # Extract ID from URL if needed
    if "v=" in video_input:
        video_id = video_input.split("v=")[1].split("&")[0]
    elif "youtu.be/" in video_input:
        video_id = video_input.split("youtu.be/")[1].split("?")[0]
    else:
        video_id = video_input.strip()

    print("\n[playlists] Fetching your playlists...")
    playlists = list_playlists(youtube)
    print_playlists(playlists)

    raw = input("Select playlist number: ").strip()
    idx = int(raw)
    if not (1 <= idx <= len(playlists)):
        print("[error] Invalid selection.")
        return

    playlist = playlists[idx - 1]
    print(f"\n[adding] Adding {video_id} to '{playlist['title']}'...")
    success = add_video_to_playlist(youtube, playlist["playlistId"], video_id)
    print("✓ Done." if success else "✗ Failed.")


# ──────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-playlist",
        description="YouTube Playlist Builder — search and add videos from the terminal.",
    )
    sub = parser.add_subparsers(dest="command")

    # search-and-add
    p_search = sub.add_parser("search", help="Search for videos and add them to a playlist")
    p_search.add_argument("query", nargs="?", default=None, help="Search query")
    p_search.add_argument("-n", "--max-results", type=int, default=10, help="Number of results (default: 10)")

    # list playlists
    sub.add_parser("playlists", help="List your playlists")

    # add by URL
    p_add = sub.add_parser("add", help="Add a specific video by URL or ID")
    p_add.add_argument("video", nargs="?", default=None, help="YouTube video URL or ID")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    youtube = authenticate()

    try:
        if args.command == "search":
            cmd_search_and_add(youtube, args)
        elif args.command == "playlists":
            cmd_list_playlists(youtube, args)
        elif args.command == "add":
            cmd_add_by_url(youtube, args)
    except HttpError as e:
        print(f"[api error] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[cancelled]")


if __name__ == "__main__":
    main()
