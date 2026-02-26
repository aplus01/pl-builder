# YouTube Playlist Builder

A terminal app to search YouTube and add videos to your playlists.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get OAuth credentials
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **YouTube Data API v3**
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth Client ID**
4. Choose **Desktop App**, download the JSON file
5. Rename it to `client_secrets.json` and place it in this directory
6. Go to **OAuth consent screen → Test users** and add your Google account

### 3. First run (one-time browser login)
```bash
python main.py search "lo-fi music"
```
A browser window will open to authorize the app. After that, credentials are saved to `token.json` and future runs are headless.

---

## Usage

### Search for videos and add to a playlist
```bash
python main.py search "lo-fi beats"
python main.py search "python tutorials" -n 20   # up to 20 results
```
You'll be shown results, then prompted to pick videos (supports ranges like `1-5` or `1,3,7` or `all`), then pick or create a playlist.

### Add a specific video by URL or ID
```bash
python main.py add https://www.youtube.com/watch?v=dQw4w9WgXcQ
python main.py add dQw4w9WgXcQ
```

### List your playlists
```bash
python main.py playlists
```

---

## Quota
The free YouTube Data API gives you **10,000 units/day**.
- Search: 100 units per call
- Add video: 50 units per call

That's plenty for personal use (~60 searches or ~200 video additions per day).

## Notes
- `token.json` stores your OAuth token — keep it private, don't commit it to git
- Add `token.json` and `client_secrets.json` to your `.gitignore`
