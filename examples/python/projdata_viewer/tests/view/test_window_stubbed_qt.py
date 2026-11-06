# SPDX-License-Identifier: Apache-2.0
"""Exercise the window's *binding logic* with stand-ins for PySide6/pyqtgraph, so it runs anywhere.

This proves our wiring (which property drives which widget call, no feedback loops, timer control),
not that the real Qt API accepts our calls: ``test_window_real_qt.py`` covers that where Qt exists.
"""
import importlib
import sys
import types

import pytest

from fakes import non_tof_source, small_demo
from stir_projdata_viewer.model import SliceMode, TofMode
from stir_projdata_viewer.viewmodel import LevelMode, ViewerViewModel


class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Dummy()


class Dummy(metaclass=_Meta):
    """Accepts any construction, attribute access and call; can be subclassed."""

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Dummy()

    def __call__(self, *a, **k):
        return Dummy()


def _stub_module(name):
    m = types.ModuleType(name)

    def getattr_(attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return Dummy
    m.__getattr__ = getattr_
    return m


class Recorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: self.calls.append((name, a)) or False

    def names(self):
        return [n for n, _ in self.calls]


def _view_modules():
    """The view package only: 'stir_projdata_viewer.viewmodel' must NOT match (enums would be duplicated)."""
    return [m for m in sys.modules if m == "stir_projdata_viewer.view" or m.startswith("stir_projdata_viewer.view.")]


@pytest.fixture
def window_module(monkeypatch):
    for name in ("PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "pyqtgraph"):
        monkeypatch.setitem(sys.modules, name, _stub_module(name))
    for sub in ("QtCore", "QtGui", "QtWidgets"):
        sys.modules["PySide6"].__dict__[sub] = sys.modules[f"PySide6.{sub}"]
    for name in _view_modules():
        monkeypatch.delitem(sys.modules, name)
    yield importlib.import_module("stir_projdata_viewer.view.window")
    for name in _view_modules():
        sys.modules.pop(name, None)       # never leave stub-bound modules behind for later tests


class Harness:
    def __init__(self, module, source=None):
        self.vm = ViewerViewModel(lambda o: o)
        self.win = module.ViewerWindow(self.vm)
        w = self.win
        self.timer, self.status = Recorder(), Recorder()
        self.set_levels, self.set_image, self.info, self.pixel = [], [], [], []
        self.curve, self.rect, self.marker = [], [], []
        self.levels_widget = (0.0, 1.0)
        w._timer = self.timer
        w.statusBar = lambda: self.status
        w.hist.setLevels = lambda lo, hi: self.set_levels.append((lo, hi, w._applying_levels))
        w.hist.getLevels = lambda: self.levels_widget
        w.img.setImage = lambda data, autoLevels=False: self.set_image.append(data.shape)
        w.img.setRect = lambda r: self.rect.append(r)
        w.info_view.setPlainText = self.info.append
        w._pixel_label.setText = self.pixel.append
        w.tof_curve.setData = lambda x, y: self.curve.append((list(x), list(y)))
        w.tof_marker_line.setValue = self.marker.append
        w.fps_spin.setValue = lambda v: None
        if source is not None:
            self.vm.load(source)


def test_load_paints_image_levels_info_and_status(window_module):
    h = Harness(window_module, small_demo())
    assert h.set_image[-1] == (12, 15) and len(h.rect) >= 1
    assert h.set_levels and h.set_levels[-1][:2] == h.vm.levels
    assert "Current slice" in h.info[-1]
    assert "showMessage" in h.status.names()


def test_levels_are_applied_with_the_echo_guard_set(window_module):
    h = Harness(window_module, small_demo())
    assert h.set_levels[-1][2] is True and h.win._applying_levels is False


def test_user_drag_becomes_manual_levels_but_programmatic_setlevels_is_ignored(window_module):
    h = Harness(window_module, small_demo())
    h.levels_widget = (1.0, 2.0)
    h.win._on_user_levels()
    assert h.vm.level_mode is LevelMode.MANUAL and h.vm.levels == (1.0, 2.0)
    h.win._applying_levels = True
    h.levels_widget = (7.0, 9.0)
    h.win._on_user_levels()                    # ignored while we are the ones setting levels
    assert h.vm.levels == (1.0, 2.0)


def test_timer_follows_playing_and_fps(window_module):
    h = Harness(window_module, small_demo())
    h.timer.calls.clear()
    h.vm.set_playing(True)
    assert h.timer.calls == [("start", (250,))]          # 4 fps by default
    h.timer.calls.clear()
    h.vm.set_tof_mode(TofMode.SUM)
    assert "stop" in h.timer.names()


def test_timer_callback_ticks_the_view_model(window_module):
    h = Harness(window_module, small_demo())
    h.win._on_timer()                                   # not playing: a stale timer event does nothing
    assert h.vm.selection.tof == 2
    h.vm.set_playing(True)
    before = h.vm.selection.tof
    h.win._on_timer()
    assert h.vm.selection.tof == (before + 1) % 5
    assert h.marker[-1] == h.vm.selection.tof


def test_mouse_move_inside_the_plot_drives_hover_and_profile(window_module):
    h = Harness(window_module, small_demo())

    class P:
        def x(self): return -7.0
        def y(self): return 3.0

    h.win.plot.vb = types.SimpleNamespace(sceneBoundingRect=lambda: types.SimpleNamespace(contains=lambda p: True),
                                          mapSceneToView=lambda p: P())
    h.win._on_mouse_moved(object())
    assert h.pixel[-1].startswith("view 3, tangential -7:")
    assert h.curve and len(h.curve[-1][0]) == 5


def test_mouse_move_outside_the_plot_clears_the_pixel_readout(window_module):
    h = Harness(window_module, small_demo())
    h.vm.hover_at(-7.0, 3.0)
    assert h.vm.pixel_text != ""
    h.win.plot.vb = types.SimpleNamespace(sceneBoundingRect=lambda: types.SimpleNamespace(contains=lambda p: False))
    h.win._on_mouse_moved(object())
    assert h.vm.pixel_text == "" and h.pixel[-1] == ""


def test_tof_visibility_follows_the_data(window_module):
    h = Harness(window_module, small_demo())
    recorded = {}
    h.win.tof_dock.setVisible = lambda v: recorded.__setitem__("dock", v)
    h.win.tof_box.setVisible = lambda v: recorded.__setitem__("box", v)
    h.vm.load(non_tof_source())
    assert recorded == {"dock": False, "box": False}
    h.vm.load(small_demo())
    assert recorded == {"dock": True, "box": True}


def test_error_goes_to_the_inline_banner_and_dismiss_clears_it(window_module):
    h = Harness(window_module)
    shown = []
    h.win.banner.show_message = shown.append
    h.vm._factory = lambda o: (_ for _ in ()).throw(OSError("bad file"))
    h.vm.load("x")
    assert shown and "bad file" in shown[-1]
    h.vm.clear_error()
    assert shown[-1] is None


def test_loaded_switches_page_and_enables_save(window_module):
    h = Harness(window_module)
    pages, save = [], []
    h.win.pages.setCurrentIndex = pages.append
    h.win.act_save.setEnabled = save.append
    h.vm.load(small_demo())
    assert pages == [h.win.PAGE_VIEWER] and save == [True]


def test_metrics_and_context_chips_reach_their_components(window_module):
    h = Harness(window_module)
    metrics, chips = [], []
    h.win.metrics.set_metrics = metrics.append
    h.win.chips.set_chips = chips.append
    h.vm.load(small_demo())
    assert dict(metrics[-1])["Max"] and "Sinogram" in chips[-1] and "TOF bin 2" in chips[-1]


def test_every_observable_property_is_bound(window_module):
    h = Harness(window_module)
    assert h.win.bindings.unbound() == frozenset()


def test_level_mode_control_follows_the_view_model(window_module):
    h = Harness(window_module, small_demo())
    chosen, enabled = [], []
    h.win.level_control.set_choice = chosen.append
    h.win.level_control.set_choice_enabled = lambda v, e: enabled.append((v, e))
    h.vm.set_manual_levels(1.0, 2.0)
    assert chosen[-1] is LevelMode.MANUAL and enabled[-1] == (LevelMode.MANUAL, True)
    h.vm.set_level_mode(LevelMode.AUTO)
    assert enabled[-1] == (LevelMode.MANUAL, False)


def test_typed_path_and_demo_go_through_view_model_commands(window_module):
    h = Harness(window_module)
    loaded = []
    h.vm.load = lambda obj: loaded.append(obj)
    h.vm.load_demo = lambda: loaded.append("<demo>")
    h.win.path_edit.text = lambda: "  /data/x.hs  "
    h.win._load_typed_path()
    h.win.path_edit.text = lambda: "   "
    h.win._load_typed_path()                       # blank input does nothing
    h.win._run(h.vm.load_demo)
    assert loaded == ["/data/x.hs", "<demo>"]


def test_path_box_shows_file_paths_only_never_data_set_labels(window_module, tmp_path):
    """Review finding: after the demo the box said "demo phantom (synthetic)", which Load then tried to open."""
    import numpy as np
    h = Harness(window_module)
    shown, titles = [], []
    h.win.path_edit.setText = shown.append
    h.win.title_label.setText = titles.append
    h.vm.load(small_demo())
    assert all(t == "" for t in shown) and "demo" in titles[-1]   # the label goes to the title, never the path box
    f = tmp_path / "a.npy"
    np.save(f, np.zeros((4, 3, 5), dtype=np.float32))
    h.vm._factory = __import__("stir_projdata_viewer.sources.loader", fromlist=["x"]).make_source
    h.vm.load(str(f))
    assert shown[-1] == str(f)


def test_level_edits_follow_levels_without_echo(window_module):
    h = Harness(window_module, small_demo())
    values = {}
    for key, edit in h.win.level_edits.items():
        edit.set_value = (lambda k: lambda v: values.__setitem__(k, v))(key)
    h.vm.set_manual_levels(1.5, 4.5)
    assert values == {"low": 1.5, "high": 4.5}
    assert h.vm.levels == (1.5, 4.5)


def test_commands_from_widgets_go_through_the_wait_cursor_wrapper(window_module):
    h = Harness(window_module, small_demo())
    cursor = []
    window_module.QtWidgets.QApplication = types.SimpleNamespace(
        setOverrideCursor=lambda c: cursor.append("busy"), restoreOverrideCursor=lambda: cursor.append("done"))
    h.win._run(h.vm.set_slice_mode, SliceMode.VIEWGRAM)
    assert cursor == ["busy", "done"] and h.vm.slice_mode is SliceMode.VIEWGRAM


def test_wait_cursor_is_restored_even_when_a_command_raises(window_module):
    h = Harness(window_module, small_demo())
    cursor = []
    window_module.QtWidgets.QApplication = types.SimpleNamespace(
        setOverrideCursor=lambda c: cursor.append("busy"), restoreOverrideCursor=lambda: cursor.append("done"))
    with pytest.raises(ValueError):
        h.win._run(h.vm.set_colormap, "jet")
    assert cursor == ["busy", "done"]


def test_dimension_control_states_reach_the_widgets(window_module):
    h = Harness(window_module)
    seen = {}
    for name, ctrl in h.win.dim_controls.items():
        ctrl.show_state = (lambda n: lambda label, lo, hi, value, enabled: seen.__setitem__(n, (lo, hi, value, enabled)))(name)
    h.vm.load(small_demo())
    assert seen["axial"] == (0, 7, 3, True) and seen["view"][3] is False and seen["tof"] == (0, 4, 2, True)


def test_slice_and_display_cards_are_disabled_until_loaded(window_module):
    h = Harness(window_module)
    states = []
    h.win.slice_card.setEnabled = states.append
    h.win.display_card.setEnabled = states.append
    h.vm.load(small_demo())
    assert states == [True, True]


def test_save_failure_goes_through_the_view_model_so_dismiss_works(window_module, monkeypatch):
    h = Harness(window_module, small_demo())
    shown = []
    h.win.banner.show_message = shown.append
    window_module.QtWidgets.QFileDialog = types.SimpleNamespace(getSaveFileName=lambda *a, **k: ("/ro/x.png", ""))
    import builtins
    real_import = builtins.__import__

    def failing(name, *a, **k):
        if name == "pyqtgraph.exporters":
            raise OSError("read-only")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", failing)
    h.win._save_image()
    monkeypatch.setattr(builtins, "__import__", real_import)
    assert h.vm.error and "read-only" in shown[-1]
    h.vm.clear_error()
    assert shown[-1] is None


def test_theme_switch_applies_stylesheet_and_restyles_every_plot(window_module):
    h = Harness(window_module, small_demo())
    calls = []
    window_module.apply_theme = lambda app, pal: calls.append(("theme", pal.name))
    window_module.style_plot = lambda plot, pal: calls.append(("plot", pal.name))
    window_module.style_histogram = lambda hist, pal: calls.append(("hist", pal.name))
    window_module.style_graphics_widget = lambda w, pal: calls.append(("glw", pal.name))
    h.win.set_palette(window_module.LIGHT)
    kinds = [k for k, name in calls if name == "light"]
    assert kinds.count("plot") == 2 and {"theme", "hist", "glw"} <= set(kinds)


def test_tof_profile_is_cleared_when_the_view_model_clears_it(window_module):
    h = Harness(window_module, small_demo())
    h.vm.hover_at(-7.0, 3.0)
    assert h.curve[-1][0]
    h.vm.load(small_demo())
    assert h.curve[-1] == ([], [])
