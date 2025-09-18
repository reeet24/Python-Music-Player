# ui_framework.py
import math
from typing import Any, Callable, Optional
import pygame
import json
import re
import time
import threading
import pathlib

class StyleManager:
    def __init__(self, style_file):
        with open(style_file, "r") as f:
            self.styles = json.load(f)

    def get_style(self, widget_type, state="default"):
        return self.styles.get(widget_type, {}).get(state, {})
    
class Event:
    def __init__(self, type, data = {}):
        self.type = type
        self.data = data
    
class UIEventRegistry:
    def __init__(self):
        self.registry: dict[str, list[Callable]] = {}
        self.event_queue: list[Event] = []

    def register(self, event_type, callback):
        if event_type not in self.registry:
            self.registry[event_type] = []
        self.registry[event_type].append(callback)
    
    def dispatch(self, event: Event):
        if event.type in self.registry:
            for callback in self.registry[event.type]:
                callback(**event.data)
    
    def process_next_event(self):
        if self.event_queue:
            event = self.event_queue.pop(0)
            self.dispatch(event)

GlobalEventRegistry = UIEventRegistry()

class Widget:
    def __init__(self, rect, style, name = ""):
        self.rect = pygame.Rect(rect)
        self.style = style
        self.state = "default"
        self.visible = True
        self.name = name

    def apply_style(self, style):
        self.style.update(style)

    def handle_event(self, event):
        
        pass

    def draw(self, surface):
        if not self.visible:
            return
        bg = self.style.get("bg_color", None)
        if bg:
            pygame.draw.rect(surface, bg, self.rect)


class Button(Widget):
    def __init__(self, rect, style, text, fire_event="", name = "", border_radius = 0, font: Optional[str] = None, font_size: Optional[int] = None):
        super().__init__(rect, style, name)
        self.text = text
        self.callback = fire_event
        self.font = pygame.font.SysFont(font or self.style.get("font", None), font_size or self.style.get("font_size", 24))
        self.border_radius = border_radius

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self.state = "pressed"
            if self.callback:
                GlobalEventRegistry.dispatch(Event(self.callback))
        elif event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(event.pos):
                self.state = "hover"
            else:
                self.state = "default"

    def draw(self, surface):
        if not self.visible:
            return
        if self.state in self.style:
            self.apply_style(self.style[self.state])
        bg = self.style.get("bg_color", (200, 200, 200))
        fg = self.style.get("fg_color", (0, 0, 0))
        pygame.draw.rect(surface, bg, self.rect, border_radius=self.border_radius)
        text_surf = self.font.render(self.text, True, fg)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


class Label(Widget):
    def __init__(self, rect, style, text, name = "", font: Optional[str] = None, font_size: Optional[int] = None):
        super().__init__(rect, style, name)
        self.text = text
        self.font = pygame.font.SysFont(font or self.style.get("font", None), font_size or self.style.get("font_size", 24))

    def set_text(self, text):
        self.text = text

    def draw(self, surface):
        if not self.visible:
            return
        fg = self.style.get("fg_color", (255, 255, 255))
        text_surf = self.font.render(self.text, True, fg)
        text_rect = text_surf.get_rect(topleft=self.rect.topleft)
        surface.blit(text_surf, text_rect)


class TextBox(Widget):
    def __init__(self, rect, style, text="", name = "", border_radius = 0, font: Optional[str] = None, font_size: Optional[int] = None):
        super().__init__(rect, style, name)
        self.text = text
        self.font = pygame.font.SysFont(font or self.style.get("font", None), font_size or self.style.get("font_size", 24))
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0
        self.border_radius = border_radius
        self.mod = {
            "shift": False,
            "ctrl": False,
            "backspace": False
        }
    
    def _backspace_helper(self):
        def backspace():
            i = 0
            length = len(self.text)
            while length > 0 and self.mod["backspace"]:
                length = len(self.text)
                self.text = self.text[:-1]
                i += 1
                time.sleep((0.5 / i))
        
        threading.Thread(target=backspace).start()
            

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if self.active and event.type == pygame.KEYDOWN:
            if self.mod["ctrl"] and event.key == pygame.K_v:
                # Paste from clipboard
                try:
                    clip = pygame.scrap.get(pygame.SCRAP_TEXT)
                    if clip:
                        raw_text = clip.decode("utf-8")
                        clean_text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', raw_text)
                        self.text += clean_text
                except Exception:
                    pass
            elif event.key == pygame.K_BACKSPACE:
                self.mod["backspace"] = True
                self._backspace_helper()
            elif event.key == pygame.K_RETURN:
                self.active = False
            elif event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
                self.mod["shift"] = True
            elif event.key == pygame.K_LCTRL or event.key == pygame.K_RCTRL:
                self.mod["ctrl"] = True
            else:
                self.text += event.unicode
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
                self.mod["shift"] = False
            elif event.key == pygame.K_LCTRL or event.key == pygame.K_RCTRL:
                self.mod["ctrl"] = False
            elif event.key == pygame.K_BACKSPACE:
                self.mod["backspace"] = False

    def draw(self, surface):
        bg = self.style.get("bg_color", (255, 255, 255))
        fg = self.style.get("fg_color", (0, 0, 0))
        pygame.draw.rect(surface, bg, self.rect, border_radius=self.border_radius)
        pygame.draw.rect(surface, (0, 0, 0), self.rect, 2 if self.active else 1, border_radius=self.border_radius)

        text_surf = self.font.render(self.text, True, fg)
        surface.blit(text_surf, (self.rect.x + 5, self.rect.y + 5))

        # blinking cursor
        if self.active:
            self.cursor_timer = (self.cursor_timer + 1) % 60
            if self.cursor_timer < 30:
                cursor_x = self.rect.x + 5 + text_surf.get_width() + 2
                cursor_y = self.rect.y + 5
                pygame.draw.line(surface, fg, (cursor_x, cursor_y), (cursor_x, cursor_y + text_surf.get_height()), 2)


class Slider(Widget):
    def __init__(self, rect, style, min_val=0, max_val=100, start_val=50, fire_event="", name = "", border_radius = 0):
        super().__init__(rect, style, name)
        self.min_val = min_val
        self.max_val = max_val
        self.value = start_val
        self.callback = fire_event
        self.dragging = False
        self.border_radius = border_radius

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            rel_x = event.pos[0] - self.rect.x
            pct = max(0, min(1, rel_x / self.rect.width))
            self.value = self.min_val + pct * (self.max_val - self.min_val)
            if self.callback:
                GlobalEventRegistry.dispatch(Event(self.callback, {"value": self.value}))

    def draw(self, surface):
        track_color = self.style.get("track_color", (180, 180, 180))
        knob_color = self.style.get("knob_color", (80, 80, 80))
        pygame.draw.rect(surface, track_color, self.rect, border_radius=self.border_radius)

        knob_width = 10

        pct = (self.value - self.min_val) / (self.max_val - self.min_val)
        knob_x = self.rect.x + int(pct * self.rect.width)
        knob_rect = pygame.Rect(knob_x - (knob_width/2), self.rect.y, knob_width, self.rect.height)
        pygame.draw.rect(surface, knob_color, knob_rect, border_radius=math.floor(self.border_radius/2))

class Container(Widget):
    def __init__(self, rect, style, widgets=[], name = ""):
        super().__init__(rect, style, name)
        self.widgets = widgets
        self.surface = pygame.Surface((self.rect.w, self.rect.h))

    def handle_event(self, event):
        for w in self.widgets:
            w.handle_event(event)

    def draw(self, surf):
        for w in self.widgets:
            w.draw(self.surface)

class UIManager:
    def __init__(self):
        self.widgets = []

    def add(self, widget):
        self.widgets.append(widget)

    def handle_event(self, event):
        for w in self.widgets:
            w.handle_event(event)

    def draw(self, surface):
        for w in self.widgets:
            w.draw(surface)

class JSONUILoader:
    def __init__(self, scene_folder: pathlib.Path | str, style_file: str = "style.json"):
        if isinstance(scene_folder, str):
            scene_folder = pathlib.Path(scene_folder)
        self.scene_folder = scene_folder
        self.scenes = {}
        self.widget_types = {
            "container": Container,
            "label": Label,
            "button": Button,
            "slider": Slider,
            "textbox": TextBox
        }
        self.style_mgr = StyleManager(style_file)

        for scene_file in scene_folder.iterdir():
            with open(scene_file, "r") as f:
                scene = json.load(f)
                self.scenes[scene_file.stem] = scene

    def reload_scenes(self):
        self.scenes = {}
        for scene_file in self.scene_folder.iterdir():
            with open(scene_file, "r") as f:
                scene = json.load(f)
                self.scenes[scene_file.stem] = scene

    def register_widget_type(self, widget_type: str, widget_class: type[Widget]):
        """
        Registers a new widget type.

        :param widget_type: The type of the widget as a string.
        :param widget_class: The class of the widget as a subclass of UI.Widget.
        """
        self.widget_types[widget_type] = widget_class

    def _scene_to_ui(self, scene: dict):
        """
        Loads a UI from a JSON scene definition.

        Args:
            scene (dict): JSON scene definition

        Returns:
            UIManager: The loaded UI
        """
        ui = UIManager()
        for key, widget in scene["widgets"].items():
            widget_class = self.widget_types[widget["type"]]
            args = widget
            args["name"] = key
            args["style"] = self.style_mgr.get_style(widget["type"], widget.get("state", "default"))
            args.pop("type")
            ui.add(widget_class(**args))
        return ui

    def load_scene(self, scene_name: str):
        """
        Load a scene from the scene folder and return its UI representation.

        :param scene_name: The name of the scene to load.
        :return: The UI representation of the scene.
        """
        return self._scene_to_ui(self.scenes[scene_name])
    
    def save_scene(self, scene_name: str, scene: dict):
        """
        Saves a scene to the scene folder.

        :param scene_name: The name of the scene to save.
        :param scene: The scene to save as a JSON dictionary.
        """
        with open(self.scene_folder / f"{scene_name}.json", "w") as f:
            json.dump(scene, f, indent=4)

    def get_scene_names(self):
        """
        Returns a list of all scene names currently loaded.

        :return: List of scene names
        """
        return list(self.scenes.keys())