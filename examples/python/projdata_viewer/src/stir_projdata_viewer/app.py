# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Composition root: the one place that wires model, sources, STIR interface, view model and view."""
from __future__ import annotations

import sys
from typing import Any

from PySide6 import QtWidgets

from .sources import make_demo_source
from .sources.loader import make_source
from .view.styling import apply_theme
from .view.theme import DEFAULT_PALETTE, PALETTES
from .view.window import ViewerWindow
from .viewmodel import ViewerViewModel


def build(stir_path: str | None = None, theme: str = DEFAULT_PALETTE.name) -> tuple[ViewerViewModel, ViewerWindow]:
    """Create the view model (with the real loader and demo data) and its window."""
    vm = ViewerViewModel(source_factory=lambda obj: make_source(obj, stir_path), demo_factory=make_demo_source)
    return vm, ViewerWindow(vm, PALETTES[theme])


def launch(projdata: Any = None, stir_path: str | None = None, demo: bool = False,
           theme: str = DEFAULT_PALETTE.name) -> int:
    """Open the viewer. ``projdata`` may be a path, a ``stir.ProjData`` or a ``ProjDataSource``.

    Blocks until the window is closed; returns the Qt exit code. A load failure is shown in the window.
    """
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    if theme not in PALETTES:
        raise ValueError(f"unknown theme {theme!r}; choose from {sorted(PALETTES)}")
    apply_theme(app, PALETTES[theme])
    vm, window = build(stir_path, theme)
    if demo:
        vm.load_demo()
    elif projdata is not None:
        vm.load(projdata)
    window.show()
    return app.exec()


launch_GUI = launch  # name of the entry point of the old PyQt5 tool (stir.projdata_visualisation.launch_GUI)
