# Terra's Music Player --- Usage Guide

## Overview

Terra's Music Player is a Python-based desktop music player with: -
**yt-dlp integration** for downloading music from YouTube and other
sites. - **Pygame backend** for playback and UI rendering. - **Custom
widget framework** (UIManager, Buttons, Labels, TextBoxes, Sliders). -
**Discord Rich Presence integration** via `pypresence`. - **Playlist
management** (save/load as JSON). - **Styling support** via JSON
stylesheets. - **Progress bar, drag-and-drop reordering, and context
menu support**.

------------------------------------------------------------------------

## Features

-   Download YouTube audio (mp3 conversion via ffmpeg).
-   Play, pause, resume, skip tracks.
-   Adjust volume with a slider.
-   Save/load playlists as `.json` files.
-   Display Now Playing information.
-   Display status messages in the UI.
-   Rich Presence integration with random flavor messages from
    `config/flavor.json`.
-   Playlist widget supports:
    -   Scrolling through tracks
    -   Drag-and-drop reordering
    -   Right-click to reveal in file explorer or delete (Shift +
        Right-click).

------------------------------------------------------------------------

## Requirements

Install dependencies:

``` bash
pip install yt-dlp pygame mutagen pypresence
```

Additionally, `ffmpeg` must be installed and available in your system
PATH.

------------------------------------------------------------------------

## File Structure

    project/
    │── music/               # Downloaded music files
    │── playlists/           # Saved playlists (.json)
    │── config/
    │    ├── styles.json     # UI styling config
    │    ├── flavor.json     # Random flavor messages
    │── resources/
    │    └── logo.png        # Icon for UI + Discord presence
    │── main.py              # Entry point

------------------------------------------------------------------------

## Configuration

-   **Music directory**: `music/`
-   **Playlist directory**: `playlists/`
-   **Styles file**: `config/styles.json`
-   **Flavor messages**: `config/flavor.json`

Example `flavor.json`:

``` json
{
  "flavors": [
    "God this song slaps",
    "Lost in the vibe",
    "Cranked up to 11",
    "On repeat until the end of time"
  ]
}
```

------------------------------------------------------------------------

## Usage

Run the application:

``` bash
python main.py
```

### UI Controls

-   **TextBox (top-left):** Paste YouTube URLs (one per line).
-   **Download Button:** Downloads and converts audio to mp3.
-   **Play / Pause / Resume / Skip Buttons:** Controls playback.
-   **Volume Slider:** Adjusts playback volume (0--100%).
-   **Playlist Widget:** Displays current playlist.
    -   Left-click: select and drag to reorder.
    -   Right-click: reveal file in Explorer/Finder/Linux file manager.
    -   Shift + Right-click: delete track from playlist.
-   **Save Playlist:** Save current playlist to `playlists/`.
-   **Load Playlist:** Load a saved playlist.
-   **Now Playing Label:** Displays currently playing track.
-   **Status Label:** Displays current status (downloading, error,
    etc.).

------------------------------------------------------------------------

## Rich Presence

-   Updates Discord Rich Presence with:
    -   Random flavor message from `config/flavor.json`.
    -   Current track title.
    -   Playback time tracking.

------------------------------------------------------------------------

## Extending the Player

-   Add new UI widgets via `utils/ui_framework` (UIManager, Button,
    Label, etc.).
-   Extend `MusicPlayer` with new playback features (looping, shuffle,
    etc.).
-   Modify `styles.json` for dark/light themes.
-   Add more metadata handling via `mutagen`.

------------------------------------------------------------------------

## Known Limitations

-   Requires stable internet for downloads.
-   Some YouTube formats may fail if region-locked or restricted.
-   Deletion and file reveal may behave differently across operating
    systems.

------------------------------------------------------------------------

## License

MIT License (assumed --- modify if otherwise).

------------------------------------------------------------------------

## Credits

-   **yt-dlp** for media downloading
-   **pygame** for audio and UI
-   **mutagen** for MP3 metadata
-   **pypresence** for Discord RPC
-   **Terra** --- Project author
