# SPDX-License-Identifier: Apache-2.0
"""Real PySide6 + pyqtgraph, offscreen. Skipped where they are not installed."""
import os

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from fakes import non_tof_source, small_demo  # noqa: E402
from stir_projdata_viewer.model import SliceMode, TofMode  # noqa: E402
from stir_projdata_viewer.view.window import ViewerWindow  # noqa: E402
from stir_projdata_viewer.viewmodel import LevelMode, ViewerViewModel  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def win(app):
    vm = ViewerViewModel(lambda o: o)
    w = ViewerWindow(vm)
    vm.load(small_demo())
    yield w
    w._timer.stop()
    w.close()


def test_user_edits_flow_into_the_view_model(win):
    win.dim_controls["axial"]._spin.setValue(3)
    assert win.vm.selection.axial == 3
    win.mode_control._buttons[1].click()
    assert win.vm.slice_mode is SliceMode.VIEWGRAM
    win.tof_mode_control._buttons[list(TofMode).index(TofMode.SUM)].click()
    assert win.vm.tof_mode is TofMode.SUM and not win.play_button.isEnabled()
    win.log_switch.setChecked(True)
    assert win.vm.log_display
    win.level_control._buttons[list(LevelMode).index(LevelMode.FIXED)].click()
    assert win.vm.level_mode is LevelMode.FIXED


def test_view_model_changes_flow_into_the_widgets(win):
    vm = win.vm
    vm.set_value("axial", 5)
    assert win.dim_controls["axial"]._spin.value() == 5
    vm.set_slice_mode(SliceMode.TANGENTIAL)
    assert win.mode_control.choice() is SliceMode.TANGENTIAL
    assert win.dim_controls["tangential"].isEnabled() and not win.dim_controls["axial"].isEnabled()
    vm.set_tof_mode(TofMode.MEAN)
    assert win.tof_mode_control.choice() is TofMode.MEAN and not win.dim_controls["tof"].isEnabled()
    assert "Source" in win.info_view.toPlainText()


def test_widget_updates_do_not_echo_back_as_commands(win):
    calls = []
    orig = win.vm.set_value
    win.vm.set_value = lambda *a: (calls.append(a), orig(*a))[1]
    win.vm.set_value("view", 4)
    assert calls == [("view", 4)]                    # one command, not a feedback loop


def test_image_is_drawn_with_real_bin_coordinates(win):
    rect = win.img.boundingRect()
    assert (rect.width(), rect.height()) == (15.0, 12.0)
    assert win.img.image.shape == (12, 15)
    assert win.plot.titleLabel.text.startswith("Sinogram")


def test_playback_timer_follows_the_view_model(win):
    assert not win._timer.isActive()
    win.vm.set_playing(True)
    assert win._timer.isActive() and win.play_button.isChecked()
    before = win.vm.selection.tof
    win._on_timer()
    assert win.vm.selection.tof != before
    win.vm.set_tof_mode(TofMode.SUM)
    assert not win._timer.isActive() and not win.play_button.isChecked()


def test_user_dragging_levels_makes_them_manual_and_applying_levels_does_not_echo(win):
    win.hist.setLevels(1.0, 2.0)
    win._on_user_levels()
    assert win.vm.level_mode is LevelMode.MANUAL and win.vm.levels == (1.0, 2.0)
    win.vm.set_value("axial", 2)                     # programmatic setLevels must not re-enter set_manual_levels
    assert win.vm.levels == (1.0, 2.0)


def test_non_tof_data_hides_the_tof_controls(win):
    win.vm.load(non_tof_source())
    assert win.tof_box.isHidden()
    assert win.tof_dock.isHidden()


def test_load_error_is_shown_in_the_banner_and_can_be_dismissed(app):
    vm = ViewerViewModel(lambda o: (_ for _ in ()).throw(OSError("nope")))
    w = ViewerWindow(vm)
    assert vm.load("x") is False
    assert w.pages.currentIndex() == w.PAGE_EMPTY      # first load failed: still on the empty page
    assert w.banner.isVisibleTo(w)                    # ...and the banner is still reachable there
    assert not w.banner.isHidden() and "nope" in w.banner.label.text()
    w.banner.findChild(QtWidgets.QPushButton).click()
    assert w.banner.isHidden() and vm.error is None
    w.close()


def test_empty_state_until_data_is_loaded(app):
    vm = ViewerViewModel(lambda o: o)
    w = ViewerWindow(vm)
    assert w.pages.currentIndex() == w.PAGE_EMPTY
    vm.load(small_demo())
    assert w.pages.currentIndex() == w.PAGE_VIEWER
    assert w.metrics.pairs() and "Sinogram" in w.chips.texts()
    w.close()


def test_theme_switch_restyles_without_losing_state(win):
    from stir_projdata_viewer.view.theme import LIGHT
    win.act_light.setChecked(True)
    assert win.palette_tokens is LIGHT
    assert win.vm.loaded and win.img.image.shape == (12, 15)


def test_the_real_histogram_signal_reaches_the_view_model(win):
    """Emits pyqtgraph's own signal: guards against a wrong signal name (which would crash on startup)."""
    win.hist.setLevels(1.0, 2.0)
    win.hist.sigLevelChangeFinished.emit(win.hist)
    assert win.vm.level_mode is LevelMode.MANUAL and win.vm.levels == (1.0, 2.0)


def _type_into(edit, text):
    edit.setText(text)
    edit.editingFinished.emit()


def test_typed_level_and_path_controls(win, tmp_path):
    import numpy as np
    _type_into(win.level_edits["high"], "123")
    assert win.vm.level_mode is LevelMode.MANUAL and win.vm.levels[1] == 123.0
    np.save(tmp_path / "a.npy", np.zeros((4, 3, 5), dtype=np.float32))
    win.vm._factory = __import__("stir_projdata_viewer.sources.loader", fromlist=["x"]).make_source
    win.path_edit.setText(f'  "{tmp_path / "a.npy"}"  ')             # Windows "Copy as path" style
    win._load_typed_path()
    assert win.vm.dataset.info.num_views == 4 and win.path_edit.text() == str(tmp_path / "a.npy")


def test_level_edits_handle_tiny_values_and_snap_back_on_rejection(app):
    """Review finding: 6 fixed decimals showed 1e-8-sized data as 0/0, and a rejected bound stayed displayed."""
    import numpy as np
    from stir_projdata_viewer.sources import ArraySource
    vm = ViewerViewModel(lambda o: o)
    w = ViewerWindow(vm)
    try:
        vm.load(ArraySource({0: np.linspace(1e-9, 5e-8, 4 * 3 * 5, dtype=np.float32).reshape(4, 3, 5)}))
        lo, hi = vm.levels
        assert float(w.level_edits["low"].text()) == pytest.approx(lo, rel=1e-5)
        assert float(w.level_edits["high"].text()) == pytest.approx(hi, rel=1e-5) and hi < 1e-7
        _type_into(w.level_edits["high"], "2.5e-8")
        assert vm.levels[1] == pytest.approx(2.5e-8)
        _type_into(w.level_edits["low"], "1")                        # above high: rejected
        assert vm.levels[0] == pytest.approx(lo)
        assert float(w.level_edits["low"].text()) == pytest.approx(lo, rel=1e-5)   # box snapped back
        _type_into(w.level_edits["low"], "not a number")
        assert float(w.level_edits["low"].text()) == pytest.approx(lo, rel=1e-5)
    finally:
        w.close()


def _press(widget, key):
    from PySide6 import QtCore, QtTest
    QtTest.QTest.keyClick(widget, key)
    QtWidgets.QApplication.processEvents()


def test_arrow_keys_go_to_the_focused_slider_not_the_active_dimension(win, app):
    """Review finding: window-wide Left/Right shortcuts pre-empted a focused slider."""
    from PySide6 import QtCore
    win.show()
    app.processEvents()
    seg = win.dim_controls["segment"]._slider
    before = (win.vm.selection.segment, win.vm.selection.axial)
    seg.setFocus()
    _press(seg, QtCore.Qt.Key.Key_Left)
    assert win.vm.selection.segment == before[0] - 1 and win.vm.selection.axial == before[1]
    # focus on something without its own use for arrows (here: a button), the window steps the active dimension
    win.play_button.setFocus()
    _press(win.play_button, QtCore.Qt.Key.Key_Left)             # (Right would clamp: axial 3 is the last in segment -1)
    assert win.vm.selection.axial == before[1] - 1 and win.vm.selection.segment == before[0] - 1
    _press(win.play_button, QtCore.Qt.Key.Key_PageUp)
    assert win.vm.selection.segment == before[0]
    win.mode_control._buttons[0].setFocus()                       # Space must not re-click a focused button
    _press(win.mode_control._buttons[0], QtCore.Qt.Key.Key_Space)
    assert win.vm.playing
    _press(win.mode_control._buttons[0], QtCore.Qt.Key.Key_Space)
    assert not win.vm.playing
    win.path_edit.setFocus()                                      # ...but a text field gets its space
    _press(win.path_edit, QtCore.Qt.Key.Key_Space)
    assert not win.vm.playing and win.path_edit.text().endswith(" ")


def test_save_image_writes_a_png(win, tmp_path, monkeypatch):
    out = tmp_path / "slice.png"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    win._save_image()
    assert out.exists() and out.stat().st_size > 0


def _view_range(win):
    (x0, x1), (y0, y1) = win.plot.getViewBox().viewRange()
    return x0, x1, y0, y1


def _image_extent(win):
    im = win.vm.image
    return im.x0, im.x0 + im.width, im.y0, im.y0 + im.height


def test_image_is_fixed_no_zoom_pan_or_menu_but_keeps_axes(win, app):
    win.resize(1200, 800)
    win.show()
    app.processEvents()
    vb = win.plot.getViewBox()
    assert vb.state["mouseEnabled"] == [False, False]
    assert not win.plot.menuEnabled() and not vb.menuEnabled()
    assert not win.plot.autoBtn.isVisible()
    assert win.plot.getAxis("left").isVisible() and win.plot.getAxis("bottom").isVisible()
    assert _view_range(win) == pytest.approx(_image_extent(win))

    # a wheel event over the image must not change the range
    from PySide6 import QtCore, QtGui
    before = _view_range(win)
    view = win.glw
    centre = view.mapFromScene(vb.mapViewToScene(vb.viewRect().center()))
    ev = QtGui.QWheelEvent(QtCore.QPointF(centre), QtCore.QPointF(view.mapToGlobal(centre)), QtCore.QPoint(0, 0),
                           QtCore.QPoint(0, 240), QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier,
                           QtCore.Qt.ScrollPhase.NoScrollPhase, False)
    QtWidgets.QApplication.sendEvent(view.viewport(), ev)
    app.processEvents()
    assert _view_range(win) == pytest.approx(before)


def test_view_refits_to_the_image_when_the_slice_geometry_changes(win, app):
    for mode in SliceMode:
        win.vm.set_slice_mode(mode)
        app.processEvents()
        assert _view_range(win) == pytest.approx(_image_extent(win)), mode
