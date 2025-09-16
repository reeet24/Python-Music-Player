import os
import sys
import json
import threading
import queue
import time
import traceback
import yt_dlp
import pygame
from utils.ui_framework import UIManager, Button, Label, TextBox, Slider, StyleManager
import pypresence
import random
from mutagen.mp3 import MP3
import subprocess, platform

rpc = pypresence.Presence("1417624017883500596")
RPCdata = None

rpc.connect()

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

rpc.update(**RPCdata)

# ---- Configuration ----
MUSIC_DIR = "music"
PLAYLIST_DIR = "playlists"
STYLES_FILE = "config/styles.json"

os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(PLAYLIST_DIR, exist_ok=True)

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

# ---- Music backend ----
class MusicPlayer:
    def __init__(self, ui_queue):
        self.playlist = []           # list of file paths
        self.index = 0
        self.ui_queue = ui_queue     # queue to send events to UI thread
        self.current_title = ""
        self.volume = 0.8
        pygame.mixer.music.set_volume(self.volume)

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
            "quiet": True,
            "noplaylist": True,
            "nopart": True,
            "geo_bypass": True,  # optional: bypass some region restrictions
            "cookies": "cookies.json",
            "rm-cache-dir": True
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
                    self.playlist.append(entry)
                    self.ui_queue.put(("download_complete", entry))
                else:
                    self.ui_queue.put(("download_failed", url, "file-not-found-after-download"))
        except Exception as e:
            tb = traceback.format_exc()
            self.ui_queue.put(("download_failed", url, str(e), tb))

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
            RPCdata = {
                "details": get_random_flavor_message(),
                "state": "Listening to " + self.current_title,
                "start": int(time.time()),
                "large_image": "resources/logo.png",
                "large_text": "Terra's Music Player",
                "small_image": "resources/logo.png",
                "small_text": "Terra's Music Player"
            }
        except Exception as e:
            self.ui_queue.put(("play_error", str(e)))

    def pause(self):
        pygame.mixer.music.pause()
        self.ui_queue.put(("paused", None))

    def resume(self):
        pygame.mixer.music.unpause()
        self.ui_queue.put(("resumed", None))

    def stop(self):
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

# ---- Minimal playlist widget that fits your framework interface ----
# The UIManager expects objects with `handle_event(event)` and `draw(surface)` methods.
class PlaylistWidget:
    def __init__(self, rect, style, font, player):
        self.rect = pygame.Rect(rect)
        self.style = style or {}
        self.font = font
        self.player = player
        self.item_height = max(20, self.font.get_linesize() + 4)
        self.selected = 0
        self.scroll = 0  # number of items scrolled down
        self.dragging = None
        self.shift_down = False
        self.debounce = False

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
        for i in range(self.scroll, min(len(self.player.playlist), self.scroll + visible)):
            entry = self.player.playlist[i]
            title = entry["title"]
            dur = entry.get("duration", 0)
            mins, secs = divmod(dur, 60)
            text = f"{i+1}. {title} [{mins}:{secs:02d}]"

            item_rect = pygame.Rect(self.rect.x, y, self.rect.w, self.item_height)
            if i == self.player.index:
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
                if 0 <= idx < len(self.player.playlist):
                    self.dragging = idx
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging is not None:
            local_y = event.pos[1] - self.rect.y
            new_idx = self.scroll + (local_y // self.item_height)
            if 0 <= new_idx < len(self.player.playlist):
                item = self.player.playlist.pop(self.dragging)
                self.player.playlist.insert(new_idx, item)
            self.dragging = None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.rect.collidepoint(event.pos):
                local_y = event.pos[1] - self.rect.y
                idx = self.scroll + (local_y // self.item_height)
                if 0 <= idx < len(self.player.playlist):
                    # Right-click context: delete or reveal
                    entry = self.player.playlist[idx]

                    if self.debounce:
                        return
                    
                    self.debounce = True

                    if self.shift_down:
                        self.player.playlist.pop(idx)
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

# ---- Main UI assembly ----
def main():
    screen = pygame.display.set_mode((800, 480))
    pygame.display.set_caption("Pygame yt_dlp Music — Widget UI")
    clock = pygame.time.Clock()

    # Load styles (optional)
    try:
        style_mgr = StyleManager(STYLES_FILE)
    except Exception:
        style_mgr = None

    ui = UIManager()
    ui_queue = queue.Queue()
    player = MusicPlayer(ui_queue)

    # font
    font = pygame.font.SysFont("Arial", 18)

    # Widgets
    url_box = TextBox(rect=(12, 12, 520, 32), style=safe_style_get(style_mgr, "TextBox", {"bg_color":[255,255,255]}))
    ui.add(url_box)

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

    btn_download = Button(rect=(548, 12, 120, 32), style=safe_style_get(style_mgr, "Button"), text="Download", callback=on_download)
    ui.add(btn_download)

    btn_play = Button(rect=(12, 60, 90, 32), style=safe_style_get(style_mgr, "Button"), text="Play", callback=lambda: player.play())
    ui.add(btn_play)
    btn_pause = Button(rect=(112, 60, 90, 32), style=safe_style_get(style_mgr, "Button"), text="Pause", callback=player.pause)
    ui.add(btn_pause)
    btn_resume = Button(rect=(212, 60, 90, 32), style=safe_style_get(style_mgr, "Button"), text="Resume", callback=player.resume)
    ui.add(btn_resume)
    btn_skip = Button(rect=(312, 60, 90, 32), style=safe_style_get(style_mgr, "Button"), text="Skip", callback=player.skip)
    ui.add(btn_skip)

    # Volume slider (0..100)
    def volume_cb(val):
        # slider expected to send 0..100
        player.set_volume(val / 100.0)

    slider = Slider(rect=(420, 60, 200, 28), style=safe_style_get(style_mgr, "Slider"), min_val=0, max_val=100, start_val=int(player.volume * 100), callback=volume_cb)
    ui.add(slider)

    # Playlist widget (left)
    playlist_style = safe_style_get(style_mgr, "ListBox", {"bg_color":[30,30,30], "fg_color":[230,230,230], "selected_bg":[80,80,120]})
    playlist = PlaylistWidget(rect=(12, 110, 520, 340), style=playlist_style, font=font, player=player)
    ui.add(playlist)

    # Right column controls: playlist save/load
    name_box = TextBox(rect=(548, 110, 240, 32), style=safe_style_get(style_mgr, "TextBox"))
    ui.add(name_box)

    def do_save():
        name = getattr(name_box, "text", "").strip()
        if name:
            player.save_playlist(name)

    def do_load():
        name = getattr(name_box, "text", "").strip()
        if name:
            player.load_playlist(name)

    btn_save = Button(rect=(548, 152, 110, 36), style=safe_style_get(style_mgr, "Button"), text="Save Playlist", callback=do_save)
    ui.add(btn_save)
    btn_load = Button(rect=(678, 152, 110, 36), style=safe_style_get(style_mgr, "Button"), text="Load Playlist", callback=do_load)
    ui.add(btn_load)

    # Now playing label
    now_label_style = safe_style_get(style_mgr, "Label")
    now_label = Label(rect=(548, 210, 320, 28), style=now_label_style, text="Now: (stopped)")
    ui.add(now_label)

    # Small status area
    status_label = Label(rect=(12, 460 - 28, 780, 28), style=safe_style_get(style_mgr, "Label"), text="Status: idle")
    ui.add(status_label)

    # Filter box
    filter_box = TextBox(rect=(12, 90, 520, 20), style=safe_style_get(style_mgr, "TextBox"))
    ui.add(filter_box)


    running = True
    # UI loop
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
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
                    _, path, title = msg
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
                elapsed = pygame.mixer.music.get_pos() // 1000
                ratio = min(1.0, elapsed / dur)
                bar_rect = pygame.Rect(14, 460-40, 516, 10)
                pygame.draw.rect(screen, (80,80,80), bar_rect)
                fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, int(bar_rect.w * ratio), bar_rect.h)
                pygame.draw.rect(screen, (120,200,120), fill_rect)
        pygame.display.flip()
        clock.tick(60)

        if RPCdata:
            rpc.update(**RPCdata)
        else:
            rpc.clear()

    pygame.quit()

if __name__ == "__main__":
    main()
