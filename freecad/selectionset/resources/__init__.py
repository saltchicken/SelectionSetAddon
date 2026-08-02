import importlib
import importlib.resources
from typing import ClassVar

import FreeCAD as App


class Resources:
    """Addon SelectionSet resource manager"""
    _pkg = importlib.resources.files(__name__)
    _gui_icons_added: ClassVar[bool] = False

    @classmethod
    def icon(cls, path: str) -> str:
        base = cls._pkg / "icons"
        return str(base.joinpath(path))

    @classmethod
    def gui_register_icons(cls) -> bool:
        if not App.GuiUp:
            return False

        if cls._gui_icons_added:
            return False

        icons = str(cls._pkg / "icons")
        App.Gui.addIconPath(icons)
        cls._gui_icons_added = True
        return True
