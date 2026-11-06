# SPDX-License-Identifier: Apache-2.0
"""Reusable components under real PySide6 (offscreen). Skipped where Qt is not installed."""
import os

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from stir_projdata_viewer.model import SliceMode  # noqa: E402
from stir_projdata_viewer.view import components as ui  # noqa: E402
from stir_projdata_viewer.view.styling import apply_theme  # noqa: E402
from stir_projdata_viewer.view.theme import DARK, LIGHT  # noqa: E402
from stir_projdata_viewer.viewmodel import COLORMAP_OPTIONS, SLICE_MODE_OPTIONS  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.mark.parametrize("make", [lambda: ui.SegmentedControl(SLICE_MODE_OPTIONS),
                                  lambda: ui.ChoiceCombo(SLICE_MODE_OPTIONS)], ids=["segmented", "combo"])
def test_choice_controls_share_one_contract(app, make):
    ctrl = make()
    seen = []
    ctrl.choiceChanged.connect(seen.append)
    ctrl.set_choice(SliceMode.VIEWGRAM)
    assert ctrl.choice() is SliceMode.VIEWGRAM and seen == []      # programmatic updates never emit


def test_segmented_click_emits_the_value(app):
    ctrl = ui.SegmentedControl(SLICE_MODE_OPTIONS)
    seen = []
    ctrl.choiceChanged.connect(seen.append)
    ctrl._buttons[2].click()
    assert seen == [SliceMode.TANGENTIAL] and ctrl.choice() is SliceMode.TANGENTIAL
    ctrl.set_choice_enabled(SliceMode.SINOGRAM, False)
    assert not ctrl._buttons[0].isEnabled()


def test_combo_activation_emits_the_value(app):
    ctrl = ui.ChoiceCombo(COLORMAP_OPTIONS)
    seen = []
    ctrl.choiceChanged.connect(seen.append)
    ctrl._combo.activated.emit(1)
    assert seen == [COLORMAP_OPTIONS.values[1]]


def test_chip_row_grows_shrinks_and_reuses_widgets(app):
    row = ui.ChipRow()
    row.set_chips(["a", "b", "c"])
    assert row.texts() == ["a", "b", "c"]
    first = row._chips[0]
    row.set_chips(["x"])
    assert row.texts() == ["x"] and row._chips[0] is first and len(row._chips) == 3


def test_metric_grid_fills_wraps_and_hides_extras(app):
    grid = ui.MetricGrid(columns=3)
    grid.set_metrics([("Min", "1"), ("Max", "2"), ("Mean", "3"), ("Std", "4")])
    assert grid.pairs() == [("Min", "1"), ("Max", "2"), ("Mean", "3"), ("Std", "4")]
    grid.set_metrics([("Only", "9")])
    assert grid.pairs() == [("Only", "9")]


def test_banner_shows_hides_and_emits_dismissed(app):
    b = ui.Banner()
    assert b.isHidden()
    b.show_message("boom")
    assert not b.isHidden() and b.label.text() == "boom"
    fired = []
    b.dismissed.connect(lambda: fired.append(1))
    b.findChild(QtWidgets.QPushButton).click()
    assert fired == [1]
    b.show_message(None)
    assert b.isHidden()


def test_card_title_and_body(app):
    assert ui.Card("Slice").title_label.text() == "SLICE" and ui.Card().title_label.isHidden()
    card = ui.Card("x")
    card.body.addWidget(QtWidgets.QLabel("hi"))
    assert card.body.count() == 1


def test_empty_state_actions_call_back(app):
    es = ui.EmptyState("t", "h")
    hits = []
    btn = es.add_action("Go", lambda: hits.append(1), primary=True)
    btn.click()
    assert hits == [1] and btn.property("variant") == "primary"


def test_dimension_control_emits_only_for_user_edits(app):
    ctrl = ui.DimensionControl()
    seen = []
    ctrl.userChanged.connect(seen.append)
    ctrl.show_state("Axial", 0, 7, 3, True)
    assert seen == [] and ctrl._spin.value() == 3 and ctrl._range.text().startswith("0")
    ctrl._spin.setValue(5)
    assert seen == [5] and ctrl._slider.value() == 5


def test_apply_theme_installs_stylesheet_and_palette(app):
    for pal in (DARK, LIGHT):
        apply_theme(app, pal)
        assert pal.accent in app.styleSheet()
        assert app.palette().window().color().name() == pal.canvas


def test_apply_theme_sets_disabled_text_colour(app):
    from PySide6 import QtGui
    apply_theme(app, DARK)
    c = app.palette().color(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText)
    assert c.name() == DARK.text_muted
