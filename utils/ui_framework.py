# ui_framework.py
from typing import Any, Callable
import pygame
import json
import re

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
    def __init__(self, rect, style, text, fire_event="", name = ""):
        super().__init__(rect, style, name)
        self.text = text
        self.callback = fire_event
        self.font = pygame.font.Font(self.style.get("font", None), self.style.get("font_size", 24))

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
        pygame.draw.rect(surface, bg, self.rect)
        text_surf = self.font.render(self.text, True, fg)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


class Label(Widget):
    def __init__(self, rect, style, text, name = ""):
        super().__init__(rect, style, name)
        self.text = text
        self.font = pygame.font.Font(None, self.style.get("font_size", 24))

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
    def __init__(self, rect, style, text="", name = ""):
        super().__init__(rect, style, name)
        self.text = text
        self.font = pygame.font.Font(None, self.style.get("font_size", 24))
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if self.active and event.type == pygame.KEYDOWN:
            if (event.mod & pygame.KMOD_CTRL) and event.key == pygame.K_v:
                # Paste from clipboard
                try:
                    pygame.scrap.init()
                    clip = pygame.scrap.get(pygame.SCRAP_TEXT)
                    if clip:
                        raw_text = clip.decode("utf-8")
                        clean_text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', raw_text)
                        self.text += clean_text
                except Exception:
                    pass
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                self.active = False
            else:
                self.text += event.unicode

    def draw(self, surface):
        bg = self.style.get("bg_color", (255, 255, 255))
        fg = self.style.get("fg_color", (0, 0, 0))
        pygame.draw.rect(surface, bg, self.rect, border_radius=5)
        pygame.draw.rect(surface, (0, 0, 0), self.rect, 2 if self.active else 1)

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
    def __init__(self, rect, style, min_val=0, max_val=100, start_val=50, fire_event="", name = ""):
        super().__init__(rect, style, name)
        self.min_val = min_val
        self.max_val = max_val
        self.value = start_val
        self.callback = fire_event
        self.dragging = False

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
        pygame.draw.rect(surface, track_color, self.rect)

        pct = (self.value - self.min_val) / (self.max_val - self.min_val)
        knob_x = self.rect.x + int(pct * self.rect.width)
        knob_rect = pygame.Rect(knob_x - 5, self.rect.y, 10, self.rect.height)
        pygame.draw.rect(surface, knob_color, knob_rect)

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