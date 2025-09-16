# Pygame UI Framework  

A lightweight, JSON-styled wrapper for building widget-based UIs in `pygame`.  

This framework provides:  
- **Widget base class** for reusable UI components  
- **JSON-driven styling** for flexible skinning  
- **UIManager** for centralized event handling & rendering  
- **Extensible architecture** (add new widgets by subclassing `Widget`)  
- **Built-in widgets**: Button, Label, TextBox, Slider  

---

## Installation  

Clone or copy `ui_framework.py` into your project and ensure `pygame` is installed:  

```bash
pip install pygame
```

---

## Basic Usage  

### 1. Create a Style JSON  

`styles.json` defines widget appearance by **type** and **state**:  

```json
{
  "Button": {
    "default": {
      "bg_color": [180, 180, 180],
      "fg_color": [0, 0, 0],
      "font_size": 24
    },
    "hover": {
      "bg_color": [200, 200, 250]
    },
    "pressed": {
      "bg_color": [100, 100, 200]
    }
  },
  "Label": {
    "default": {
      "fg_color": [255, 255, 255],
      "font_size": 20
    }
  },
  "TextBox": {
    "default": {
      "bg_color": [255, 255, 255],
      "fg_color": [0, 0, 0],
      "font_size": 22
    }
  },
  "Slider": {
    "default": {
      "track_color": [200, 200, 200],
      "knob_color": [80, 80, 200]
    }
  }
}
```

### 2. Initialize the Framework  

```python
import pygame
from ui_framework import UIManager, Button, Label, TextBox, Slider, StyleManager

pygame.init()
screen = pygame.display.set_mode((600, 400))
clock = pygame.time.Clock()

styles = StyleManager("styles.json")
ui = UIManager()
```

### 3. Create Widgets  

```python
def on_click():
    print("Button clicked!")

btn = Button(
    rect=(200, 50, 200, 60), 
    style=styles.get_style("Button"), 
    text="Click Me", 
    callback=on_click
)
ui.add(btn)

label = Label(
    rect=(200, 120, 200, 40),
    style=styles.get_style("Label"),
    text="Hello, World!"
)
ui.add(label)

textbox = TextBox(
    rect=(200, 170, 200, 40),
    style=styles.get_style("TextBox")
)
ui.add(textbox)

def on_slide(value):
    print("Slider value:", int(value))

slider = Slider(
    rect=(200, 230, 200, 20),
    style=styles.get_style("Slider"),
    min_val=0, max_val=100, start_val=50,
    callback=on_slide
)
ui.add(slider)
```

### 4. Main Loop  

```python
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        ui.handle_event(event)

    screen.fill((30, 30, 30))
    ui.draw(screen)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
```

---

## API Reference  

### `StyleManager(style_file: str)`  
Loads and manages styles from a JSON file.  

- `get_style(widget_type: str, state="default") -> dict`  
  Returns a dictionary of style attributes for the given widget type and state.  

---

### `Widget`  
Base class for all widgets.  

**Attributes**:  
- `rect` – `pygame.Rect` bounding box  
- `style` – dictionary of visual properties  
- `state` – `"default" | "hover" | "pressed"` (custom states allowed)  
- `visible` – whether to draw the widget  

**Methods**:  
- `apply_style(style: dict)` – update style dynamically  
- `handle_event(event)` – process `pygame` events  
- `draw(surface)` – render widget  

---

### `Button(Widget)`  
Clickable button with hover and press states.  

**Extra attributes**:  
- `text` – label string  
- `callback` – function called when pressed  

---

### `Label(Widget)`  
Simple non-interactive text label.  

**Extra attributes**:  
- `text` – displayed string  

**JSON keys**:  
- `fg_color` → text color  
- `font_size` → font size  

---

### `TextBox(Widget)`  
Editable text input field with blinking cursor.  

**Extra attributes**:  
- `text` – current content  
- `active` – focused state  

**JSON keys**:  
- `bg_color` → background color  
- `fg_color` → text color  
- `font_size` → font size  

---

### `Slider(Widget)`  
Adjustable value widget with draggable knob.  

**Extra attributes**:  
- `min_val` / `max_val` – numeric range  
- `value` – current value  
- `callback` – function called on value change  

**JSON keys**:  
- `track_color` → slider background  
- `knob_color` → draggable knob color  

---

### `UIManager`  
Central controller for widgets.  

**Methods**:  
- `add(widget)` – register a widget  
- `handle_event(event)` – forward events to widgets  
- `draw(surface)` – draw all widgets  

---

## Extending the Framework  

To add custom widgets (checkboxes, dropdowns, etc.):  

1. Subclass `Widget`  
2. Implement `handle_event` and `draw`  
3. Add style keys in JSON  

---

## Roadmap / Possible Extensions  

- Text input validation & multiline text areas  
- Checkboxes & toggles  
- Sliders (vertical, ranged)  
- Layout managers (grid, vertical, horizontal)  
- Nested containers for grouping widgets  

---

## License  

Free to use and modify for any purpose.  
