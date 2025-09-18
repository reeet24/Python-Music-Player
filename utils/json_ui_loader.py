import utils.ui_framework as UI
import json
import pathlib

GlobalEventRegistry = UI.GlobalEventRegistry

class JSONUILoader:
    def __init__(self, scene_folder: pathlib.Path | str, style_file: str = "style.json"):
        if isinstance(scene_folder, str):
            scene_folder = pathlib.Path(scene_folder)
        self.scene_folder = scene_folder
        self.scenes = {}
        self.widget_types = {
            "container": UI.Container,
            "label": UI.Label,
            "button": UI.Button,
            "slider": UI.Slider,
            "textbox": UI.TextBox
        }
        self.style_mgr = UI.StyleManager(style_file)

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

    def register_widget_type(self, widget_type: str, widget_class: type[UI.Widget]):
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
        ui = UI.UIManager()
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