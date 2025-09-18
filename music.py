import os
import sys
import json
import threading
import queue
import time
import traceback
from typing import Any, Optional
import yt_dlp
import pygame
from utils.ui_framework import UIManager, Button, Label, TextBox, Slider, StyleManager, Widget, Container, GlobalEventRegistry, JSONUILoader, Event
import pypresence
import random
from mutagen.mp3 import MP3
import subprocess, platform
import requests
import utils.updater as updater

GlobalEventRegistry = GlobalEventRegistry

settings = json.load(open("config/settings.json", "r"))

if settings["auto_update_on_start"]:
    local_ver = updater.get_local_version()
    remote_ver = updater.get_remote_version()
    print(f"Local version: {local_ver} | Remote version: {remote_ver}")
    if local_ver != remote_ver:
        updater.Update()

class RPCWraper(pypresence.Presence):
    def __init__(self):
        super().__init__("1417624017883500596")
        self.Connected = False
    
    def _connect(self):
        self.Connected = True
        self.connect()
    
    def _close(self):
        self.Connected = False
        self.close()

rpc = RPCWraper()

RPCDefault = {
    "details": "Terra's Music Player",
    "state": "Idle",
    "start": int(time.time()),
    "large_image": "resources/logo.png",
    "large_text": "Terra's Music Player",
    "small_image": "resources/logo.png",
    "small_text": "Terra's Music Player"
}

RPCdata = RPCDefault

# ---- Configuration ----
MUSIC_DIR = settings["music_dir"] or "music"
METADATA_DIR = f"{MUSIC_DIR}/metadata"
PLAYLIST_DIR = settings["playlist_dir"] or "playlists"
STYLES_FILE = settings["styles_file"] or "config/styles.json"
UI_DIR = settings["ui_dir"] or "config/UIs"

UI_Loader = JSONUILoader(UI_DIR, STYLES_FILE)

os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(PLAYLIST_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

pygame.init()
pygame.mixer.init()
# event posted when a track ends
TRACK_END_EVENT = pygame.USEREVENT + 1
pygame.mixer.music.set_endevent(TRACK_END_EVENT)

# ---- Utilities ----
def safe_style_get(sm, key, default=None):
    try:
        return sm.get_style(key)
    except Exception:
        return default or {}

def sanitize_filename_for_display(path):
    return os.path.basename(path)

def get_random_flavor_message():
    flavorFile = "config/flavor.json"
    with open(flavorFile, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["flavors"][random.randint(0, len(data["flavors"]) - 1)]

def get_playlists() -> dict[str, Any]:
    playlists = {}
    for playlist in os.listdir(PLAYLIST_DIR):
        with open(os.path.join(PLAYLIST_DIR, playlist), "r", encoding="utf-8") as f:
            playlists[playlist[:-5]] = json.load(f)
    return playlists

def save_song_metadata(metadata):
    with open(f'{METADATA_DIR}/{metadata["title"]}.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
def load_song_metadata(title):
    with open(f'{METADATA_DIR}/{title}.json', 'r', encoding='utf-8') as f:
        return json.load(f)
    
def _get_song_metadata(song_path, youtube_id=None):
    title = os.path.basename(song_path)
    duration = None

    try:
        audio = MP3(song_path)
        duration = int(audio.info.length)
    except Exception as e:
        print(f"Could not read {song_path}: {e}")

    return {
        "title": title,
        "duration": duration,
        "path": song_path,
        "youtube_id": youtube_id
    }

def get_songs():
    songs = {}
    for metadata in os.listdir(METADATA_DIR):
        with open(f'{METADATA_DIR}/{metadata}', 'r', encoding='utf-8') as f:
            songs[metadata[:-5]] = json.load(f)
    return songs

# ---- Music backend ----
class MusicPlayer:
    def __init__(self, ui_queue):
        self.playlist = []           # list of file paths
        self.index = 0
        self.ui_queue = ui_queue     # queue to send events to UI thread
        self.current_title = ""
        self.volume = 0.8
        pygame.mixer.music.set_volume(self.volume)
        self.is_online = True
        self.is_playing = False
        self.is_stopped = True

    # Blocking download routine — run in a background thread
    def _download_worker(self, url):
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": os.path.join(MUSIC_DIR, "%(title).200s-%(id)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": False,
            "noplaylist": True,
            "nopart": True,
            "geo_bypass": True,  # optional: bypass some region restrictions
            "cookies-from-browser": "chrome",
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: # type: ignore
                info = ydl.extract_info(url, download=True)
                # prepare_filename gives the file name used by outtmpl (before postprocessing ext change)
                filename = ydl.prepare_filename(info)
                mp3_path = os.path.splitext(filename)[0] + ".mp3"
                if not os.path.exists(mp3_path):
                    # postprocessor might have created a different name in rare setups; try to infer
                    mp3_path = None
                    for ext in (".mp3", ".m4a", ".aac"):
                        candidate = os.path.splitext(filename)[0] + ext
                        if os.path.exists(candidate):
                            mp3_path = candidate
                            break
                if mp3_path:
                    # collect metadata
                    title = info.get("title") or sanitize_filename_for_display(mp3_path) # type: ignore
                    youtube_id = info.get("id") # type: ignore
                    duration = None
                    try:
                        duration = int(MP3(mp3_path).info.length)
                    except Exception:
                        duration = 0

                    entry = {
                        "title": title,
                        "youtube_id": youtube_id,
                        "path": mp3_path,
                        "duration": duration
                    }
                    save_song_metadata(entry)
                    self.playlist.append(entry)
                    self.ui_queue.put(("download_complete", entry))
                else:
                    self.ui_queue.put(("download_failed", url, "file-not-found-after-download"))
        except Exception as e:
            tb = traceback.format_exc()
            self.ui_queue.put(("download_failed", url, str(e), tb))

    def check_music_dir_for_new_songs(self):
        for song in os.listdir(MUSIC_DIR):
            song_path = os.path.join(MUSIC_DIR, song)
            if not os.path.exists(f'{METADATA_DIR}/{song}.json'):
                metadata = _get_song_metadata(song_path)
                save_song_metadata(metadata)
                print(f"Found new song: {metadata['title']}")

    def load_song(self, title):
        metadata = load_song_metadata(title)
        save_song_metadata(metadata)
        self.playlist.append(metadata)
        self.ui_queue.put(("song_added", metadata))

    def download_async(self, url):
        threading.Thread(target=self._download_worker, args=(url,), daemon=True).start()

    def play(self, index=None):
        global RPCdata
        if index is not None:
            if 0 <= index < len(self.playlist):
                self.index = index
            else:
                return
        if not self.playlist:
            return
        track = self.playlist[self.index]
        try:
            pygame.mixer.music.load(track["path"])
            pygame.mixer.music.play()
            self.current_title = track["title"]
            self.ui_queue.put(("play_started", self.index, self.current_title))
            if self.is_online:
                RPCdata = {
                    "details": get_random_flavor_message(),
                    "state": "Listening to " + self.current_title,
                    "start": int(time.time()),
                    "large_image": "resources/logo.png",
                    "large_text": "Terra's Music Player",
                    "small_image": "resources/logo.png",
                    "small_text": "Terra's Music Player"
                }
            self.is_playing = True
            self.is_stopped = False
        except Exception as e:
            self.ui_queue.put(("play_error", str(e)))

    def pause(self):
        if self.is_playing:
            self.is_playing = False
            pygame.mixer.music.pause()
            self.ui_queue.put(("paused", None))

    def resume(self):
        if not self.is_playing and not self.is_stopped:
            self.is_playing = True
            pygame.mixer.music.unpause()
            self.ui_queue.put(("resumed", None))

    def stop(self):
        global RPCdata
        if not self.is_stopped:
            self.is_playing = False
            self.is_stopped = True
            pygame.mixer.music.stop()
            RPCdata = RPCDefault
            self.ui_queue.put(("stopped", None))

    def skip(self):
        if not self.playlist:
            return
        self.index += 1
        if self.index >= len(self.playlist):
            self.index = 0
        self.play(self.index)

    def set_volume(self, v):  # v in 0..1
        self.volume = max(0.0, min(1.0, v))
        pygame.mixer.music.set_volume(self.volume)
        self.ui_queue.put(("volume", self.volume))

    def save_playlist(self, name):
        if not name:
            self.ui_queue.put(("save_failed", "empty-name"))
            return
        path = os.path.join(PLAYLIST_DIR, f"{name}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.playlist, f, indent=2)
            self.ui_queue.put(("save_ok", name))
        except Exception as e:
            self.ui_queue.put(("save_failed", str(e)))

    def load_playlist(self, name):
        if not name:
            self.ui_queue.put(("load_failed", "empty-name"))
            return
        path = os.path.join(PLAYLIST_DIR, f"{name}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # keep only files that exist
            self.playlist = [d for d in data if os.path.exists(d["path"])]
            self.index = 0
            self.ui_queue.put(("load_ok", name, len(self.playlist)))
        except Exception as e:
            self.ui_queue.put(("load_failed", str(e)))


class PlaylistWidget(Widget):
    def __init__(self, rect, style, font, font_size, player: Optional[MusicPlayer] = None, name = ""):
        self.name = name
        self.rect = pygame.Rect(rect)
        self.style = style or {}
        self.font = pygame.font.SysFont(font or None, font_size)
        self.player = player
        self.item_height = max(20, self.font.get_linesize() + 4)
        self.selected = 0
        self.scroll = 0  # number of items scrolled down
        self.dragging = None
        self.shift_down = False
        self.debounce = False

    def set_player(self, player: MusicPlayer):
        self.player = player

    def draw(self, surf):
        bg = tuple(self.style.get("bg_color", (30, 30, 30)))
        fg = tuple(self.style.get("fg_color", (230, 230, 230)))
        sel_bg = tuple(self.style.get("selected_bg", (80, 80, 120)))
        pygame.draw.rect(surf, bg, self.rect)
        # clip drawing to widget rect
        clip = surf.get_clip()
        surf.set_clip(self.rect)
        x, y = self.rect.x + 4, self.rect.y + 4
        visible = self.rect.h // self.item_height
        for i in range(self.scroll, min(len(self.player.playlist), self.scroll + visible)): # type: ignore
            entry = self.player.playlist[i] # type: ignore
            title = entry["title"]
            dur = entry.get("duration", 0)
            mins, secs = divmod(dur, 60)
            text = f"{i+1}. {title} [{mins}:{secs:02d}]"

            item_rect = pygame.Rect(self.rect.x, y, self.rect.w, self.item_height)
            if i == self.player.index: # type: ignore
                pygame.draw.rect(surf, sel_bg, item_rect)

            txtsurf = self.font.render(text, True, fg)
            surf.blit(txtsurf, (x, y))
            y += self.item_height
        surf.set_clip(clip)
        # border
        pygame.draw.rect(surf, (0,0,0), self.rect, 2)

    def handle_event(self, event):

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
                self.shift_down = True
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
                self.shift_down = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                local_y = event.pos[1] - self.rect.y
                idx = self.scroll + (local_y // self.item_height)
                if 0 <= idx < len(self.player.playlist): # type: ignore
                    self.dragging = idx
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging is not None:
            local_y = event.pos[1] - self.rect.y
            new_idx = self.scroll + (local_y // self.item_height)
            if 0 <= new_idx < len(self.player.playlist): # type: ignore
                item = self.player.playlist.pop(self.dragging) # type: ignore
                self.player.playlist.insert(new_idx, item) # type: ignore
            self.dragging = None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.rect.collidepoint(event.pos):
                local_y = event.pos[1] - self.rect.y
                idx = self.scroll + (local_y // self.item_height)
                if 0 <= idx < len(self.player.playlist): # type: ignore
                    # Right-click context: delete or reveal
                    entry = self.player.playlist[idx] # type: ignore

                    if self.debounce:
                        return
                    
                    self.debounce = True

                    if self.shift_down:
                        self.player.playlist.pop(idx) # type: ignore
                        return
                    
                    if platform.system() == "Windows":
                        subprocess.Popen(f'explorer /select,"{entry["path"]}"')
                    else:
                        subprocess.Popen(["xdg-open", os.path.dirname(entry["path"])])
                    
                    # Spawn a thread to avoid blocking
                    def delayed():
                        time.sleep(0.5)
                        self.debounce = False
                    threading.Thread(target=delayed).start()
        elif event.type == pygame.MOUSEWHEEL:
            if event.y > 0:
                self.scroll = max(0, self.scroll - 1)
            elif event.y < 0:
                self.scroll = min(len(self.player.playlist) - self.rect.h // self.item_height, self.scroll + 1) # type: ignore

class SearchBoxWidget(Widget):
    def __init__(self, rect, style, font, font_size, item_height: int, items: dict[str, Any] = {}, name = "", search_event = ""):
        super().__init__(rect, style, name)
        self.font = pygame.font.SysFont(font or None, font_size)
        self.items = items
        self.visible_items = {}
        self.query = ""
        self.selected = -1
        self.item_height = item_height
        self.active = False
        self.search_rect = pygame.Rect(self.rect.x + 4, self.rect.y + 4, self.rect.w, item_height)
        self.search_event = search_event
        self.mod = {
            "backspace": False
        }

    def set_items(self, items: dict[str, Any]):
        self.items = items

    def draw(self, surf):
        self.visible_items = {}
        # Draw first item as search box, then draw all other items
        bg = tuple(self.style.get("bg_color", (30, 30, 30)))
        fg = tuple(self.style.get("fg_color", (230, 230, 230)))
        sel_bg = tuple(self.style.get("selected_bg", (80, 80, 120)))
        pygame.draw.rect(surf, bg, self.rect)
        # clip drawing to widget rect
        clip = surf.get_clip()
        surf.set_clip(self.rect)
        x, y = self.rect.x + 4, self.rect.y + 4

        # search box
        pygame.draw.rect(surf, tuple(self.style.get("search_box_color", (50, 50, 50))), self.search_rect)
        txtsurf = self.font.render(self.query or "Search", True, fg)
        surf.blit(txtsurf, (x, y))
        y += self.item_height

        for i, (text, item) in enumerate(self.items.items()):

            if not text.lower().startswith(self.query.lower()):
                continue
            
            self.visible_items[text] = item

            item_rect = pygame.Rect(self.rect.x, y, self.rect.w, self.item_height)
            if i == self.selected:
                pygame.draw.rect(surf, sel_bg, item_rect)

            txtsurf = self.font.render(text, True, fg)
            surf.blit(txtsurf, (x, y))
            y += self.item_height
        surf.set_clip(clip)
        # border
        pygame.draw.rect(surf, (0,0,0), self.rect, 2)

    def _backspace_helper(self):
        def backspace():
            i = 0
            length = len(self.query)
            while length > 0 and self.mod["backspace"]:
                length = len(self.query)
                self.query = self.query[:-1]
                i += 1
                time.sleep((0.5 / i))
        
        threading.Thread(target=backspace).start()

    def handle_event(self, event):

        if event.type == pygame.KEYDOWN:

            if not self.active:
                return

            if event.key == pygame.K_BACKSPACE:
                self.mod["backspace"] = True
                self._backspace_helper()
            elif event.key == pygame.K_RETURN:
                if self.selected >= 0:
                    self.active = False
                    self.query = list(self.items.keys())[self.selected]
                    self.selected = -1
                    GlobalEventRegistry.dispatch(Event(self.search_event, {"query": self.query, "state": self.state}))
                    return
            elif event.key == pygame.K_ESCAPE:
                self.active = False
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.items)
            elif event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.items)
            else:
                self.query += event.unicode
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_BACKSPACE:
                self.mod["backspace"] = False
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            #First check if we clicked on the text box and set active accordingly
            if self.search_rect.collidepoint(event.pos):
                self.active = True
                return
            else:
                self.active = False

            local_y = event.pos[1] - self.rect.y
            idx = self.selected + (local_y // self.item_height)
            if 0 <= idx < len(self.visible_items) and self.rect.collidepoint(event.pos):
                self.query = list(self.visible_items)[idx]
                GlobalEventRegistry.dispatch(Event(self.search_event, {"query": self.query, "state": self.state}))

class ProgressBar(Widget):
    def __init__(self, rect, style, name = ""):
        super().__init__(rect, style, name)
        self.progress = 0.0 # 0-100
        self.enabled = True
    
    def draw(self, surf):
        if not self.enabled:
            return
        bg = tuple(self.style.get("bg_color", (30, 30, 30)))
        fg = tuple(self.style.get("fg_color", (230, 230, 230)))
        progress = self.progress / 100
        pygame.draw.rect(surf, bg, self.rect)
        pygame.draw.rect(surf, fg, (self.rect.x, self.rect.y, self.rect.w * progress, self.rect.h))
    
        # border
        pygame.draw.rect(surf, (0,0,0), self.rect, 2)

# A class to manage online actions and allow for offline use.
class OnlineManager:
    def __init__(self):
        self.online = True
        self.running = True

    def _connection_loop(self):
        while self.running:
            self.check_status()
            if not self.is_online():
                if rpc.Connected:
                    rpc._close()
                continue

            if not rpc.Connected:
                rpc._connect()

            if RPCdata:
                rpc.update(**RPCdata)
            else:
                rpc.clear()
            time.sleep(1)

    def init_connection_loop(self):
        threading.Thread(target=self._connection_loop).start()

    def check_status(self):
        try:
            requests.get("https://www.google.com", timeout=1)
            if not self.online:
                print("Online")
            self.online = True
        except Exception:
            if self.online:
                print("Offline")
            self.online = False
    
    def is_online(self):
        return self.online
    
# Register custom widgets
UI_Loader.register_widget_type("SearchBox", SearchBoxWidget)
UI_Loader.register_widget_type("ProgressBar", ProgressBar)
UI_Loader.register_widget_type("PlaylistWidget", PlaylistWidget)

# ---- Main UI assembly ----
def main():
    running = True
    screen = pygame.display.set_mode((800, 480))
    pygame.display.set_caption("Pygame yt_dlp Music — Widget UI")
    clock = pygame.time.Clock()

    # Load styles (optional)
    try:
        style_mgr = StyleManager(STYLES_FILE)
    except Exception:
        style_mgr = None

    ui = UI_Loader.load_scene("main")
    ui_queue = queue.Queue()
    player = MusicPlayer(ui_queue)
    player.check_music_dir_for_new_songs()
    online_manager = OnlineManager()
    online_manager.init_connection_loop()
    playlists = get_playlists()

    # Assigning important widgets to variables
    for w in ui.widgets:
        try:
            if w.name == "status_label":
                status_label = w
            elif w.name == "now_playing_label":
                now_label = w
            elif w.name == "name_box":
                name_box = w
                name_box.set_items(playlists)
            elif w.name == "playlist":
                playlist = w
                playlist.set_player(player)
            elif w.name == "url_box":
                url_box = w
            elif w.name == "progress_bar":
                progress_bar = w
        except AttributeError:
            continue

    # Helper functions for UI events
    def on_download():
        urls_text = getattr(url_box, "text", "").strip()
        if not urls_text:
            return
        # split by newline to allow pasting multiple links at once
        urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
        for url in urls:
            player.download_async(url)
        ui_queue.put(("download_started", urls_text))
        # clear input
        url_box.text = ""

    def name_box_state_change(state: bool = True):
        if state:
            name_box.state = "default"
            name_box.set_items(get_playlists())
        else:
            name_box.state = "song"
            name_box.set_items(get_songs())
    
    def on_search(query: str, state: str):
        if state == "default":
            player.load_playlist(query)
        elif state == "song":
            player.load_song(query)

    GlobalEventRegistry.register("playlist_selected", callback=on_search)

    GlobalEventRegistry.register("download_button_pressed", on_download)
    GlobalEventRegistry.register("play_button_pressed", callback=(lambda: player.play()))
    GlobalEventRegistry.register("pause_button_pressed", callback=(lambda: player.pause()))
    GlobalEventRegistry.register("resume_button_pressed", callback=(lambda: player.resume()))
    GlobalEventRegistry.register("skip_button_pressed", callback=(lambda: player.skip()))
    GlobalEventRegistry.register("playlist_button_pressed", callback=(lambda: name_box_state_change()))
    GlobalEventRegistry.register("song_button_pressed", callback=(lambda: name_box_state_change(False)))

    GlobalEventRegistry.register("volume_slider_changed", callback=(lambda value: player.set_volume(value/100)))
    
    # UI loop
    
    pygame.scrap.init()
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                online_manager.running = False
            elif event.type == TRACK_END_EVENT:
                # automatic skip when track ends
                player.skip()
            else:
                # forward to UI manager and playlist widget
                ui.handle_event(event)
                playlist.handle_event(event)

        # Process messages from background threads
        try:
            while True:
                msg = ui_queue.get_nowait()
                if not msg:
                    continue
                tag = msg[0]
                if tag == "download_complete":
                    _, down_entry = msg
                    title = down_entry["title"]
                    status_text = f"Downloaded: {title}"
                    # refresh playlist widget (it uses player.playlist directly)
                    if hasattr(now_label, "set_text"):
                        now_label.set_text(f"Now: {player.current_title or '(stopped)'}")
                    else:
                        now_label.text = f"Now: {player.current_title or '(stopped)'}"
                    status_label.set_text(status_text) if hasattr(status_label, "set_text") else setattr(status_label, "text", status_text)
                elif tag == "download_failed":
                    _, url, error, *rest = msg
                    status_label.set_text(f"Download failed: {error}") if hasattr(status_label, "set_text") else setattr(status_label, "text", f"Download failed: {error}")
                elif tag == "download_started":
                    _, url = msg
                    status_label.set_text(f"Downloading...") if hasattr(status_label, "set_text") else setattr(status_label, "text", "Downloading...")
                elif tag == "play_started":
                    _, idx, title = msg
                    if hasattr(now_label, "set_text"):
                        now_label.set_text(f"Now: {title}")
                    else:
                        now_label.text = f"Now: {title}"
                    status_label.set_text("Playing") if hasattr(status_label, "set_text") else setattr(status_label, "text", "Playing")
                elif tag == "play_error":
                    _, err = msg
                    status_label.set_text(f"Play error: {err}") if hasattr(status_label, "set_text") else setattr(status_label, "text", f"Play error: {err}")
                elif tag == "paused":
                    status_label.set_text("Paused") if hasattr(status_label, "set_text") else setattr(status_label, "text", "Paused")
                elif tag == "resumed":
                    status_label.set_text("Resumed") if hasattr(status_label, "set_text") else setattr(status_label, "text", "Resumed")
                elif tag == "save_ok":
                    _, name = msg
                    status_label.set_text(f"Saved playlist: {name}") if hasattr(status_label, "set_text") else setattr(status_label, "text", f"Saved playlist: {name}")
                elif tag == "save_failed":
                    _, reason = msg
                    status_label.set_text(f"Save failed: {reason}") if hasattr(status_label, "set_text") else setattr(status_label, "text", f"Save failed: {reason}")
                elif tag == "load_ok":
                    _, name, count = msg
                    status_label.set_text(f"Loaded {count} entries from {name}") if hasattr(status_label, "set_text") else setattr(status_label, "text", f"Loaded {count} entries from {name}")
                elif tag == "load_failed":
                    _, reason = msg
                    status_label.set_text(f"Load failed: {reason}") if hasattr(status_label, "set_text") else setattr(status_label, "text", f"Load failed: {reason}")
                elif tag == "volume":
                    _, vol = msg
                    status_label.set_text(f"Volume: {int(vol*100)}%") if hasattr(status_label, "set_text") else setattr(status_label, "text", f"Volume: {int(vol*100)}%")
                else:
                    # unknown message
                    pass
        except queue.Empty:
            pass

        # draw
        screen.fill((40, 40, 40))
        ui.draw(screen)
        playlist.draw(screen)

        # Draw progress bar
        if player.playlist and player.index < len(player.playlist):
            entry = player.playlist[player.index]
            dur = entry.get("duration", 0)
            if dur > 0:
                progress_bar.enabled = True
                elapsed = pygame.mixer.music.get_pos() // 1000
                ratio = min(1.0, elapsed / dur) * 100
                progress_bar.progress = ratio
            else:
                progress_bar.enabled = False
                
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    

if __name__ == "__main__":
    main()