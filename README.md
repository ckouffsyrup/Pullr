# Pullr v0.1.3

A small desktop downloader UI built with Python, CustomTkinter, and yt-dlp.

Use this only for videos/audio you own, created yourself, or have permission to download.

## What changed

- Remembers the last download folder you used and restores it on next launch
- Keeps the NexusBar-style black and purple theme
- Keeps the Open Folder button and larger activity area

## Features

- Paste a video link
- Download video as MP4
- Download audio as MP3
- Quality choices: Best, 1080p, 720p, 480p, 360p
- Optional playlist downloads
- Folder picker
- Progress and activity log
- Remembers your last selected folder

## Setup

1. Install Python 3.11+ if needed.
2. Run `install_requirements.bat`.
3. Run `run_app.bat`.

## FFmpeg

MP3 conversion and high-quality MP4 merging need FFmpeg.

Simplest Windows setup:

1. Download FFmpeg.
2. Put `ffmpeg.exe` and `ffprobe.exe` either in your system PATH or in this app folder under:

```text
ffmpeg/bin/ffmpeg.exe
ffmpeg/bin/ffprobe.exe
```

The app checks `./ffmpeg/bin` automatically.

## Build EXE

Run:

```text
build_exe.bat
```

The exe will be in `dist/`.


## v0.1.2
- Added an Open Folder button for the selected download directory.
- Increased the default window height so the Activity area is visible.


## v0.1.3
- Saves the last selected download folder to `pullr_settings.json`.
- Restores that folder automatically the next time Pullr opens.
