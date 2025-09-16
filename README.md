# Terra's Music Player

A lightweight, Python-based music player with YouTube download support,
Discord Rich Presence integration, and a custom Pygame UI.

------------------------------------------------------------------------

## Quick Start

### 1. Install Dependencies

Make sure you have Python 3.9+ installed. Then run:

``` bash
pip install yt-dlp pygame mutagen pypresence
```

You also need **ffmpeg** installed and available in your system PATH.

------------------------------------------------------------------------

### 2. Project Structure

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

### 3. Run the Player

``` bash
python main.py
```

------------------------------------------------------------------------

### 4. Using the UI

-   **Paste a YouTube URL** into the text box at the top.
-   Click **Download** to fetch the track.
-   Use **Play, Pause, Resume, Skip** buttons to control playback.
-   Adjust **Volume** with the slider.
-   **Save** and **Load** playlists from the right-hand panel.
-   The **Playlist Widget** supports drag-and-drop reordering and
    right-click context actions.

------------------------------------------------------------------------

### 5. Discord Rich Presence

-   Shows what you're listening to in Discord.
-   Uses flavor messages from `config/flavor.json`.
-   Updates automatically when tracks change.

------------------------------------------------------------------------

## Example Flavor File

`config/flavor.json`

``` json
{
  "flavors": [
    "God this song slaps",
    "Lost in the vibe",
    "On repeat until the end of time"
  ]
}
```

------------------------------------------------------------------------

## License

MIT License (assumed --- modify if otherwise).
