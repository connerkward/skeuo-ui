---
name: media-download
description: Download torrents/YouTube to Desky via PIA VPN, organize into media library (Emby). Use when user provides a magnet link, .torrent URL, or YouTube URL for download.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Media Download (Desky)

Download media via torrent or YouTube to Desky, organize into media library. Emby (port 8096) is the sole media server. All downloads go through PIA VPN.

## Prerequisites (one-time setup on Desky)

1. **PIA VPN:** Install from privateinternetaccess.com, login via GUI once, verify: `piactl get connectionstate`
2. **Tools to `C:\tools` on PATH:** yt-dlp.exe, ffmpeg.exe (direct downloads, no installer)
3. **Emby Server:** `http://desky:8096` (installed at `C:\Emby-Server\`). Also via Tailscale Funnel: `https://desky.tilapia-micro.ts.net`
4. **Media directories:** Run `Get-PSDrive -PSProvider FileSystem` to pick drive with most free space, then create:

```
E:\Media\Movies
E:\Media\TV
E:\Media\Music
E:\Media\Other
E:\Media\Downloads
```


## Emby Library Paths

Emby indexes **both `C:\Media` and `E:\Media`** — they are parallel roots with identical subfolder layouts (Movies / TV / Music / Other / Downloads). Before searching for or placing a file, always check both. New downloads go to `E:\Media` (more free space); existing content may live in either.

| Type | Path | Naming |
|------|------|--------|
| Movie | `{C,E}:\Media\Movies` | `Movie Name (Year)\Movie Name (Year).ext` |
| TV | `{C,E}:\Media\TV` | `Show Name\Season 01\Show Name - S01E01.ext` |
| Music | `{C,E}:\Media\Music` | `Artist\Album (Year)\01 - Track.ext` |
| Other | `{C,E}:\Media\Other` | Flat |

Staging (new downloads): `E:\Media\Downloads`

## Workflow

### 1. Classify

Determine type from URL/name patterns:
- `S\d{2}E\d{2}` or season/episode keywords → **TV**
- Year + codec keywords (x264, BluRay, 1080p) → **Movie**
- FLAC, MP3, album, discography → **Music**
- Otherwise → **Other** (or ask user if ambiguous)

### 2. Verify VPN

```
ssh desky 'powershell -Command "piactl get connectionstate"'
```

Must return `Connected`. If not:

```
ssh desky 'powershell -Command "piactl connect"'
```

Poll every 5s for up to 30s. **Never download without VPN confirmed.**

### 3. Download

**Torrent:** Use Deluge WebUI at `http://desky:8112` or CLI:
```
ssh desky 'powershell -Command "deluge-console add \"<magnet-or-url>\""'
```

**YouTube video:**
```
ssh desky 'powershell -Command "yt-dlp -f \"bestvideo[height<=1080]+bestaudio/best\" --merge-output-format mkv -o \"E:\Media\Downloads\%(title)s.%(ext)s\" \"<url>\""'
```

**YouTube music:**
```
ssh desky 'powershell -Command "yt-dlp --extract-audio --audio-format mp3 -o \"E:\Media\Downloads\%(title)s.%(ext)s\" \"<url>\""'
```

### 4. Organize (automated)

`media_sorter.py` runs every 10 min (scheduled task `MediaSorter`). It auto-classifies, renames, and moves completed downloads to the correct Emby library folder. No manual step needed.

- Movies: `E:\Media\Movies\Title (Year)\Title (Year).ext`
- TV: `E:\Media\TV\Show\Season XX\Show - S01E01.ext`
- Music: `E:\Media\Music\` (flat)
- Skips incomplete downloads (`.aria2` files present)
- Skips junk (`.torrent`, `.nfo`, `.txt`, etc.)

### 5. Report

Confirm to user: download started, Emby will pick it up automatically.

## Remote Execution

- SSH: `ssh desky 'powershell -Command "..."'`
- Quoting: single quotes outer (bash), double quotes inner (PowerShell), backslash-escape inner doubles
- Long downloads: wrap in `Start-Job` so SSH disconnect doesn't kill the process, then poll job status

## Edge Cases

- **VPN drop:** Deluge and yt-dlp both support resume; re-verify VPN before retrying. PIA watchdog auto-kills Deluge if VPN drops.
- **Disk space:** Check before starting: `Get-PSDrive <letter> | Select-Object Free`
- **Seeding:** Deluge configured with `stop_seed_ratio: 0.0` — stops seeding immediately
- **Sorting:** Handled automatically by `media_sorter.py` every 10 min
- **move_completed MUST be disabled in Deluge** (`core.set_config {"move_completed": false}`). If enabled, Deluge races with the sorter: files get moved to Movies before the sorter sees them. Verify via Deluge WebUI → Preferences → Downloads → "Move completed" unchecked.
- **Torrents stuck in Queued at 100% / files missing from E:\Media\Downloads:** Deluge silently falls back to `C:\Users\conner\Downloads` when E: is unavailable or the torrent was configured with a different save path. Check there first. To relocate: use `core.move_storage` API (not robocopy — files are locked by Deluge). Example: `curl ... core.move_storage [["<tid>"], "E:\\Media\\Downloads"]`.
