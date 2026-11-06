# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""VIEW layer: the main window, built from ``components`` and bound to a ``ViewerViewModel``.

Rules of this file: widgets send user input to view-model commands, and redraw from view-model
properties when told they changed (declaratively, through a ``BindingRegistry``). No selection
logic, no data access, no formatting; colours come from the active ``Palette``.
"""
from __future__ import annotations

import contextlib

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from ..viewmodel import (COLORMAP_OPTIONS, LEVEL_MODE_OPTIONS, SLICE_MODE_OPTIONS, TOF_MODE_OPTIONS,
                         BindingRegistry, LevelMode, ViewerViewModel)
from . import components as ui
from .styling import apply_theme, style_graphics_widget, style_histogram, style_plot
from .theme import DARK, LIGHT, Palette

pg.setConfigOptions(imageAxisOrder="row-major", antialias=True)  # numpy rows -> screen rows

SIDEBAR_WIDTH = 340


def _colormap(name: str) -> pg.ColorMap:
    if name != "grey":
        try:
            return pg.colormap.get(name)
        except Exception:  # noqa: BLE001 - fall through to grey
            pass
    return pg.ColorMap([0.0, 1.0], [(0, 0, 0), (255, 255, 255)])


def _uses_key(widget, key) -> bool:
    """Does ``widget`` (the focused one) have its own meaning for ``key``?"""
    Key = QtCore.Qt.Key
    text_entry = (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit)
    if key == Key.Key_Space:
        return isinstance(widget, text_entry)
    return isinstance(widget, (QtWidgets.QAbstractSlider, QtWidgets.QComboBox) + text_entry)


@contextlib.contextmanager
def _wait_cursor():
    QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
    try:
        yield
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()


class ViewerWindow(QtWidgets.QMainWindow):
    PAGE_EMPTY, PAGE_VIEWER = 0, 1

    def __init__(self, vm: ViewerViewModel, palette: Palette = DARK):
        super().__init__()
        self.vm = vm
        self.palette_tokens = palette
        self.resize(1320, 840)
        self._geometry_key: tuple | None = None
        self._applying_levels = False
        self._build_menu()
        self._build_layout()
        self._pixel_label = QtWidgets.QLabel("")
        self._pixel_label.setObjectName("PixelReadout")
        self.statusBar().addPermanentWidget(self._pixel_label)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._install_shortcuts()
        self._restyle_plots()
        self.bindings = BindingRegistry(vm)
        self._declare_bindings()
        self.bindings.start()

    # ------------------------------------------------------------------ construction
    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&File")
        act_open = menu.addAction("&Open...")
        act_open.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._open_file)
        act_demo = menu.addAction("&Demo data (synthetic TOF)")
        act_demo.triggered.connect(lambda: self._run(self.vm.load_demo))
        self.act_save = menu.addAction("&Save image...")
        self.act_save.triggered.connect(self._save_image)
        menu.addSeparator()
        act_quit = menu.addAction("&Quit")
        act_quit.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        view_menu = self.menuBar().addMenu("&View")
        self.act_light = view_menu.addAction("&Light theme")
        self.act_light.setCheckable(True)
        self.act_light.setChecked(self.palette_tokens.name == "light")
        self.act_light.toggled.connect(lambda on: self.set_palette(LIGHT if on else DARK))

    def _build_layout(self) -> None:
        root = QtWidgets.QWidget()
        root.setObjectName("Root")
        row = QtWidgets.QHBoxLayout(root)
        row.setContentsMargins(12, 6, 12, 12)
        row.setSpacing(12)
        row.addWidget(self._build_sidebar())
        self.pages = QtWidgets.QStackedWidget()
        self.empty = ui.EmptyState("No projection data loaded",
                                   "Open an Interfile header (.hs), a .npy/.npz array, or try the synthetic TOF demo.")
        self.empty.add_action("Open file...", self._open_file, primary=True)
        self.empty.add_action("Load demo data", lambda: self._run(self.vm.load_demo))
        self.pages.addWidget(self.empty)
        self.pages.addWidget(self._build_viewer_page())
        main = QtWidgets.QVBoxLayout()
        main.setSpacing(12)
        self.banner = ui.Banner()          # outside the pages: visible even if the first load fails
        self.banner.dismissed.connect(lambda: self.vm.clear_error())
        main.addWidget(self.banner)
        main.addWidget(self.pages, 1)
        row.addLayout(main, 1)
        self.setCentralWidget(root)

    def _build_sidebar(self) -> QtWidgets.QWidget:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(SIDEBAR_WIDTH)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QtWidgets.QWidget()
        content.setObjectName("Content")
        col = QtWidgets.QVBoxLayout(content)
        col.setContentsMargins(0, 0, 6, 0)
        col.setSpacing(12)

        source = ui.Card("Data")
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("path to .hs / .npy / .npz")
        self.path_edit.returnPressed.connect(self._load_typed_path)
        buttons = QtWidgets.QHBoxLayout()
        browse = QtWidgets.QPushButton("Browse...")
        browse.clicked.connect(self._open_file)
        load = QtWidgets.QPushButton("Load")
        load.setProperty("variant", "primary")
        load.clicked.connect(self._load_typed_path)
        buttons.addWidget(browse)
        buttons.addWidget(load)
        source.body.addWidget(self.path_edit)
        source.body.addLayout(buttons)
        col.addWidget(source)

        self.slice_card = ui.Card("Slice")
        self.mode_control = ui.SegmentedControl(SLICE_MODE_OPTIONS)
        self.mode_control.choiceChanged.connect(lambda m: self._run(self.vm.set_slice_mode, m))
        self.slice_card.body.addWidget(self.mode_control)
        self.dim_controls: dict[str, ui.DimensionControl] = {}
        for dim in ("segment", "axial", "view", "tangential"):
            self.dim_controls[dim] = self._dimension_control(dim, self.slice_card)
        col.addWidget(self.slice_card)

        self.tof_box = ui.Card("Time of flight")
        self.tof_mode_control = ui.SegmentedControl(TOF_MODE_OPTIONS)
        self.tof_mode_control.choiceChanged.connect(lambda m: self._run(self.vm.set_tof_mode, m))
        self.tof_box.body.addWidget(self.tof_mode_control)
        self.dim_controls["tof"] = self._dimension_control("tof", self.tof_box)
        play = QtWidgets.QHBoxLayout()
        self.play_button = QtWidgets.QPushButton("Play  (Space)")
        self.play_button.setCheckable(True)
        self.play_button.toggled.connect(lambda on: self._run(self.vm.set_playing, on))
        self.fps_spin = QtWidgets.QSpinBox()
        self.fps_spin.setRange(1, 30)
        self.fps_spin.setSuffix(" fps")
        self.fps_spin.valueChanged.connect(lambda v: self._run(self.vm.set_fps, v))
        play.addWidget(self.play_button, 1)
        play.addWidget(self.fps_spin)
        self.tof_box.body.addLayout(play)
        col.addWidget(self.tof_box)

        display = self.display_card = ui.Card("Display")
        self.cmap_control = ui.ChoiceCombo(COLORMAP_OPTIONS)
        self.cmap_control.choiceChanged.connect(lambda name: self._run(self.vm.set_colormap, name))
        self.level_control = ui.SegmentedControl(LEVEL_MODE_OPTIONS)
        self.level_control.choiceChanged.connect(lambda m: self._run(self.vm.set_level_mode, m))
        self.level_control.set_choice_enabled(LEVEL_MODE_OPTIONS.values[-1], False)  # MANUAL is entered by editing
        display.body.addWidget(ui.LabeledRow("Colour map", self.cmap_control))
        display.body.addWidget(self.level_control)
        self.level_edits: dict[str, ui.NumberEdit] = {}
        for key, label in (("low", "Min level"), ("high", "Max level")):
            edit = ui.NumberEdit()                   # any magnitude, e.g. 1e-8; commits on Enter/focus-out
            edit.setFixedWidth(130)
            edit.valueEdited.connect(lambda v, k=key: self._run(self.vm.set_level_bounds, **{k: v}))
            self.level_edits[key] = edit
            display.body.addWidget(ui.LabeledRow(label, edit))
        self.log_switch = QtWidgets.QCheckBox("log(1 + x) display")
        self.log_switch.toggled.connect(lambda on: self._run(self.vm.set_log_display, on))
        display.body.addWidget(self.log_switch)
        col.addWidget(display)

        info = ui.Card("Data set")
        self.info_view = QtWidgets.QPlainTextEdit()
        self.info_view.setReadOnly(True)
        self.info_view.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.info_view.setObjectName("Mono")             # monospace comes from the stylesheet
        self.info_view.setMinimumHeight(230)
        info.body.addWidget(self.info_view)
        col.addWidget(info)
        col.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def _dimension_control(self, dim: str, card: ui.Card) -> ui.DimensionControl:
        ctrl = ui.DimensionControl()
        ctrl.userChanged.connect(lambda v, d=dim: self._run(self.vm.set_value, d, v))
        card.body.addWidget(ctrl)
        return ctrl

    def _build_viewer_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)
        header = QtWidgets.QHBoxLayout()
        self.title_label = QtWidgets.QLabel("")
        self.title_label.setObjectName("Title")
        self.chips = ui.ChipRow()
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.chips)
        col.addLayout(header)

        image_card = ui.Card()
        self.glw = pg.GraphicsLayoutWidget()
        self.plot = self.glw.addPlot(row=0, col=0)
        self.plot.setAspectLocked(False)
        self.plot.invertY(True)          # like imshow: row 0 on top
        # Shown as a fixed image (axes and ticks kept): no wheel/drag zoom or pan, no context menu,
        # no auto-range button. The range is set to the image extent in _draw_image.
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        self.img = pg.ImageItem()
        self.plot.addItem(self.img)
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.img)
        self.glw.addItem(self.hist, row=0, col=1)
        self.hist.sigLevelChangeFinished.connect(self._on_user_levels)
        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)
        image_card.body.addWidget(self.glw)
        col.addWidget(image_card, 1)

        self.metrics = ui.MetricGrid(columns=6)
        col.addWidget(self.metrics)

        self.tof_dock = ui.Card("TOF profile of the LOR under the cursor")
        self.tof_plot = pg.PlotWidget()
        self.tof_plot.setLabel("bottom", "TOF bin")
        self.tof_plot.setLabel("left", "counts")
        self.tof_plot.setTitle("hover over the image")
        self.tof_plot.setMinimumHeight(150)
        self.tof_curve = self.tof_plot.plot([], [], symbol="o", symbolSize=7)
        self.tof_marker_line = pg.InfiniteLine(angle=90, movable=False)
        self.tof_plot.addItem(self.tof_marker_line)
        self.tof_dock.body.addWidget(self.tof_plot)
        self.tof_dock.setMaximumHeight(250)
        col.addWidget(self.tof_dock)
        return page

    def _install_shortcuts(self) -> None:
        """Window-wide keys. A QShortcut pre-empts the focused widget, so when the focus is on a widget that
        uses the key itself (a slider or spin box for arrows/PgUp/PgDn, a text field for Space), the key
        is passed on to that widget instead of running the shortcut: Right on a focused segment slider
        moves the segment, not the axial position."""
        Key = QtCore.Qt.Key
        self._shortcut_commands = {
            Key.Key_Space: lambda: self._run(self.vm.toggle_play),
            Key.Key_Left: lambda: self._run(self.vm.step_active, -1),
            Key.Key_Right: lambda: self._run(self.vm.step_active, +1),
            Key.Key_PageUp: lambda: self._run(self.vm.step, "segment", +1),
            Key.Key_PageDown: lambda: self._run(self.vm.step, "segment", -1),
        }
        self._shortcuts = {}
        for key in self._shortcut_commands:
            sc = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            sc.activated.connect(lambda k=key: self._on_shortcut(k))
            self._shortcuts[key] = sc

    def _on_shortcut(self, key) -> None:
        focus = self.focusWidget()       # this window's focus child (also right when the window is not active)
        if focus is not None and _uses_key(focus, key):
            sc = self._shortcuts[key]
            sc.setEnabled(False)          # or the re-sent key would trigger this shortcut again
            try:
                for kind in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
                    QtWidgets.QApplication.sendEvent(
                        focus, QtGui.QKeyEvent(kind, key, QtCore.Qt.KeyboardModifier.NoModifier))
            finally:
                sc.setEnabled(True)
            return
        self._shortcut_commands[key]()

    # ------------------------------------------------------------------ theming
    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        apply_theme(QtWidgets.QApplication.instance(), palette)
        self._restyle_plots()

    def _restyle_plots(self) -> None:
        p = self.palette_tokens
        style_graphics_widget(self.glw, p)
        style_plot(self.plot, p)
        style_histogram(self.hist, p)
        style_plot(self.tof_plot.getPlotItem(), p)
        self.tof_plot.setBackground(p.surface)
        self.tof_curve.setPen(pg.mkPen(p.curve, width=2))
        self.tof_curve.setSymbolBrush(p.curve)
        self.tof_curve.setSymbolPen(p.curve)
        self.tof_marker_line.setPen(pg.mkPen(p.marker, width=2))

    # ------------------------------------------------------------------ user input -> commands
    def _run(self, command, *args, **kwargs) -> None:
        with _wait_cursor():
            command(*args, **kwargs)

    def _open_file(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open projection data", "", "Projection data (*.hs *.npy *.npz);;All files (*)")
        if path:
            self._run(self.vm.load, path)

    def _load_typed_path(self) -> None:
        if self.path_edit.text().strip():
            self._run(self.vm.load_path, self.path_edit.text())

    def _save_image(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save image", "slice.png",
                                                        "PNG image (*.png);;All files (*)")
        if not path:
            return
        try:
            from pyqtgraph.exporters import ImageExporter
            ImageExporter(self.plot).export(path)
        except Exception as exc:  # noqa: BLE001 - show it in the banner, don't crash the viewer
            self.vm.report_error(f"Could not save the image: {exc}")

    def _on_timer(self) -> None:
        self.vm.tick()

    def _on_user_levels(self) -> None:
        if not self._applying_levels:
            lo, hi = self.hist.getLevels()
            self.vm.set_manual_levels(lo, hi)

    def _on_mouse_moved(self, scene_pos) -> None:
        vb = self.plot.vb
        if vb.sceneBoundingRect().contains(scene_pos):
            p = vb.mapSceneToView(scene_pos)
            self.vm.hover_at(p.x(), p.y())
        else:
            self.vm.hover_leave()

    # ------------------------------------------------------------------ view-model -> widgets
    def _declare_bindings(self) -> None:
        b = self.bindings.bind
        b("window_title", lambda: self.setWindowTitle(self.vm.window_title))
        b("status", lambda: self.statusBar().showMessage(self.vm.status))
        b("source_path", lambda: self.path_edit.setText(self.vm.source_path))   # a real path or empty
        b("source_label", lambda: self.title_label.setText(self.vm.source_label))
        b("loaded", self._show_page)
        b("loaded", lambda: self.act_save.setEnabled(self.vm.loaded))
        b("loaded", self._enable_controls)
        b("error", lambda: self.banner.show_message(self.vm.error))
        b("tof_available", lambda: (self.tof_box.setVisible(self.vm.tof_available),
                                    self.tof_dock.setVisible(self.vm.tof_available)))
        b("dimensions", self._paint_dimensions)
        b("slice_mode", lambda: self.mode_control.set_choice(self.vm.slice_mode))
        b("tof_mode", lambda: self.tof_mode_control.set_choice(self.vm.tof_mode))
        b("can_play", lambda: self.play_button.setEnabled(self.vm.can_play))
        b("fps", self._paint_fps)
        b("playing", self._paint_playing)
        b("colormap", self._paint_colormap)
        b("level_mode", self._paint_level_mode)
        b("log_display", lambda: ui.silently(self.log_switch, lambda: self.log_switch.setChecked(self.vm.log_display)))
        b("image", self._draw_image)
        b("levels", self._paint_levels)
        b("info_text", lambda: self.info_view.setPlainText(self.vm.info_text))
        b("pixel_text", lambda: self._pixel_label.setText(self.vm.pixel_text))
        b("tof_profile", self._paint_tof_profile)
        b("tof_marker", self._paint_tof_marker)
        b("metrics", lambda: self.metrics.set_metrics(self.vm.metrics))
        b("context", lambda: self.chips.set_chips(self.vm.context))

    def _show_page(self) -> None:
        self.pages.setCurrentIndex(self.PAGE_VIEWER if self.vm.loaded else self.PAGE_EMPTY)

    def _enable_controls(self) -> None:
        for card in (self.slice_card, self.display_card):
            card.setEnabled(self.vm.loaded)

    def _paint_dimensions(self) -> None:
        for state in self.vm.dimensions:
            self.dim_controls[state.name].show_state(state.label, state.lo, state.hi, state.value, state.enabled)

    def _paint_fps(self) -> None:
        ui.silently(self.fps_spin, lambda: self.fps_spin.setValue(self.vm.fps))
        if self._timer.isActive():
            self._timer.start(int(1000 / self.vm.fps))

    def _paint_playing(self) -> None:
        ui.silently(self.play_button, lambda: self.play_button.setChecked(self.vm.playing))
        self.play_button.setText("Pause  (Space)" if self.vm.playing else "Play  (Space)")
        if self.vm.playing:
            self._timer.start(int(1000 / self.vm.fps))
        else:
            self._timer.stop()

    def _paint_colormap(self) -> None:
        self.hist.gradient.setColorMap(_colormap(self.vm.colormap))
        self.cmap_control.set_choice(self.vm.colormap)

    def _paint_level_mode(self) -> None:
        self.level_control.set_choice_enabled(LevelMode.MANUAL, self.vm.level_mode is LevelMode.MANUAL)
        self.level_control.set_choice(self.vm.level_mode)

    def _paint_levels(self) -> None:
        if self.vm.levels is None:
            return
        self._applying_levels = True
        try:
            self.hist.setLevels(*self.vm.levels)
            for key, value in zip(("low", "high"), self.vm.levels):
                self.level_edits[key].set_value(value)
        finally:
            self._applying_levels = False

    def _paint_tof_profile(self) -> None:
        prof = self.vm.tof_profile
        if prof is None:
            self.tof_curve.setData([], [])
            self.tof_plot.setTitle("hover over the image")
        else:
            self.tof_curve.setData(list(prof.x), list(prof.y))
            self.tof_plot.setTitle(prof.title)

    def _paint_tof_marker(self) -> None:
        marker = self.vm.tof_marker
        self.tof_marker_line.setVisible(marker is not None)
        if marker is not None:
            self.tof_marker_line.setValue(marker)

    def _draw_image(self) -> None:
        im = self.vm.image
        if im is None:
            return
        self.img.setImage(np.ascontiguousarray(im.data), autoLevels=False)
        self.img.setRect(QtCore.QRectF(im.x0, im.y0, im.width, im.height))
        self.plot.setLabel("bottom", im.col_label)
        self.plot.setLabel("left", im.row_label)
        self.plot.setTitle(im.title)
        key = (im.data.shape, im.row_label, im.col_label, im.x0, im.y0, im.width, im.height)
        if key != self._geometry_key:
            self._geometry_key = key
            self.plot.setRange(xRange=(im.x0, im.x0 + im.width), yRange=(im.y0, im.y0 + im.height),
                               padding=0)
