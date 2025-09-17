import json
import os
from mutagen.mp3 import MP3

def update_playlist_durations(path):
    """
    Load a playlist JSON (new format), compute durations for each track using mutagen,
    and write the file back with updated duration values.
    """
    with open(path, "r", encoding="utf-8") as f:
        playlist = json.load(f)

    updated = False
    for entry in playlist:
        file_path = entry.get("path")
        if not file_path or not os.path.exists(file_path):
            continue
        try:
            audio = MP3(file_path)
            duration = int(audio.info.length)
            if entry.get("duration") != duration:
                entry["duration"] = duration
                updated = True
        except Exception as e:
            print(f"Could not read {file_path}: {e}")

    if updated:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(playlist, f, indent=2)
        print(f"Updated durations written to {path}")
    else:
        print(f"No changes needed for {path}")

# Example usage:
# update_playlist_durations("playlists/my_playlist.json")

if __name__ == "__main__":
    for playlist in os.listdir("playlists"):
        if playlist.endswith(".json"):
            update_playlist_durations(os.path.join("playlists", playlist))