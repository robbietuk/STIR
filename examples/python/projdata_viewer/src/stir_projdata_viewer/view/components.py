# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Reusable widgets. None knows about the view model; the window wires them to it.

Shared behaviour is written once:
* ``ChoiceControl`` is the common interface of every control that picks one value from a
  ``ChoiceOptions`` (``SegmentedControl``, ``ChoiceCombo``): ``choiceChanged(value)`` fires for user
  input only, ``set_choice(value)`` updates silently.
* ``silently`` runs a widget update with its signals blocked (used by every programmatic update).
"""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..viewmodel.options import ChoiceOptions


def silently(widget: QtWidgets.QWidget, fn) -> None:
    """Run ``fn`` with the widget's signals blocked."""
    was = widget.blockSignals(True)
    try:
        fn()
    finally:
        widget.blockSignals(was)


class ChoiceControl(QtWidgets.QWidget):
    """Interface + shared state for choice widgets."""

    choiceChanged = QtCore.Signal(object)

    def __init__(self, options: ChoiceOptions, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.options = options

    def set_choice(self, value) -> None:           # pragma: no cover - interface
        raise NotImplementedError

    def choice(self):                               # pragma: no cover - interface
        raise NotImplementedError


class SegmentedControl(ChoiceControl):
    def __init__(self, options: ChoiceOptions, parent: QtWidgets.QWidget | None = None):
        super().__init__(options, parent)
        frame = QtWidgets.QFrame(self)
        frame.setObjectName("Segmented")
        row = QtWidgets.QHBoxLayout(frame)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(2)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)
        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QtWidgets.QPushButton] = []
        for i, label in enumerate(options.labels):
            b = QtWidgets.QPushButton(label)
            b.setCheckable(True)
            b.setProperty("segment", "true")
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self._group.addButton(b, i)
            row.addWidget(b, 1)
            self._buttons.append(b)
        self._group.idClicked.connect(lambda i: self.choiceChanged.emit(self.options.value_at(i)))

    def set_choice(self, value) -> None:
        self._buttons[self.options.index_of(value)].setChecked(True)

    def choice(self):
        i = self._group.checkedId()
        return self.options.value_at(i) if i >= 0 else None

    def set_choice_enabled(self, value, enabled: bool) -> None:
        self._buttons[self.options.index_of(value)].setEnabled(enabled)


class ChoiceCombo(ChoiceControl):
    def __init__(self, options: ChoiceOptions, parent: QtWidgets.QWidget | None = None):
        super().__init__(options, parent)
        self._combo = QtWidgets.QComboBox()
        self._combo.addItems(list(options.labels))
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._combo)
        self._combo.activated.connect(lambda i: self.choiceChanged.emit(self.options.value_at(i)))

    def set_choice(self, value) -> None:
        silently(self._combo, lambda: self._combo.setCurrentIndex(self.options.index_of(value)))

    def choice(self):
        return self.options.value_at(self._combo.currentIndex())


class Card(QtWidgets.QFrame):
    """Titled container. Add content with ``card.body.addWidget(...)``."""

    def __init__(self, title: str = "", parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)
        self.title_label = QtWidgets.QLabel(title.upper())
        self.title_label.setObjectName("CardTitle")
        self.title_label.setVisible(bool(title))
        lay.addWidget(self.title_label)
        self.body = QtWidgets.QVBoxLayout()
        self.body.setSpacing(8)
        lay.addLayout(self.body)


class LabeledRow(QtWidgets.QWidget):
    """Caption on the left, any control on the right (used for display options)."""

    def __init__(self, caption: str, control: QtWidgets.QWidget, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.caption = QtWidgets.QLabel(caption)
        self.caption.setObjectName("Muted")
        row.addWidget(self.caption)
        row.addStretch(1)
        row.addWidget(control)
        self.control = control


class Chip(QtWidgets.QFrame):
    def __init__(self, text: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Chip")
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        self.label = QtWidgets.QLabel(text)
        lay.addWidget(self.label)


class ChipRow(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._row = QtWidgets.QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(6)
        self._row.addStretch(1)
        self._chips: list[Chip] = []

    def texts(self) -> list[str]:
        return [c.label.text() for c in self._chips if not c.isHidden()]

    def set_chips(self, texts) -> None:
        texts = list(texts)
        while len(self._chips) < len(texts):
            chip = Chip("")
            self._row.insertWidget(len(self._chips), chip)
            self._chips.append(chip)
        for chip, text in zip(self._chips, texts):
            chip.label.setText(text)
            chip.setVisible(True)
        for chip in self._chips[len(texts):]:
            chip.setVisible(False)


class MetricTile(QtWidgets.QFrame):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Tile")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 8)
        lay.setSpacing(0)
        self.name = QtWidgets.QLabel("")
        self.name.setObjectName("TileLabel")
        self.value = QtWidgets.QLabel("")
        self.value.setObjectName("TileValue")
        lay.addWidget(self.name)
        lay.addWidget(self.value)


class MetricGrid(QtWidgets.QWidget):
    """Grid of label/value tiles filled from ``((label, value), ...)``."""

    def __init__(self, columns: int = 3, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._columns = columns
        self._grid = QtWidgets.QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        self._tiles: list[MetricTile] = []

    def pairs(self) -> list[tuple[str, str]]:
        return [(t.name.text(), t.value.text()) for t in self._tiles if not t.isHidden()]

    def set_metrics(self, pairs) -> None:
        pairs = list(pairs)
        while len(self._tiles) < len(pairs):
            tile = MetricTile()
            n = len(self._tiles)
            self._grid.addWidget(tile, n // self._columns, n % self._columns)
            self._tiles.append(tile)
        for tile, (name, value) in zip(self._tiles, pairs):
            tile.name.setText(name)
            tile.value.setText(value)
            tile.setVisible(True)
        for tile in self._tiles[len(pairs):]:
            tile.setVisible(False)


class Banner(QtWidgets.QFrame):
    """Inline, dismissable error message (replaces modal error dialogs)."""

    dismissed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Banner")
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(12, 8, 6, 8)
        self.label = QtWidgets.QLabel("")
        self.label.setWordWrap(True)
        close = QtWidgets.QPushButton("✕")
        close.setToolTip("Dismiss")
        close.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.dismissed)
        row.addWidget(self.label, 1)
        row.addWidget(close)
        self.setVisible(False)

    def show_message(self, text: str | None) -> None:
        self.label.setText(text or "")
        self.setVisible(bool(text))


class EmptyState(QtWidgets.QWidget):
    """Shown before any data is loaded."""

    def __init__(self, title: str, hint: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("EmptyState")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setObjectName("EmptyTitle")
        self.hint_label = QtWidgets.QLabel(hint)
        self.hint_label.setObjectName("EmptyHint")
        for lbl in (self.title_label, self.hint_label):
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lbl)
        self.actions = QtWidgets.QHBoxLayout()
        self.actions.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay.addLayout(self.actions)

    def add_action(self, text: str, slot, primary: bool = False) -> QtWidgets.QPushButton:
        b = QtWidgets.QPushButton(text)
        if primary:
            b.setProperty("variant", "primary")
        b.clicked.connect(lambda _=False: slot())
        self.actions.addWidget(b)
        return b


class DimensionControl(QtWidgets.QWidget):
    """Label + slider + spin box for one index.

    ``userChanged`` fires only for user edits; ``show_state`` updates the widgets without firing it.
    """

    userChanged = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._label = QtWidgets.QLabel("")
        self._range = QtWidgets.QLabel("")
        self._range.setObjectName("Muted")
        self._slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._spin = QtWidgets.QSpinBox()
        self._spin.setFixedWidth(76)
        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self._label)
        head.addStretch(1)
        head.addWidget(self._range)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._slider, 1)
        row.addWidget(self._spin)
        col = QtWidgets.QVBoxLayout(self)
        col.setContentsMargins(0, 2, 0, 2)
        col.setSpacing(4)
        col.addLayout(head)
        col.addLayout(row)
        self._slider.valueChanged.connect(self._spin.setValue)
        self._spin.valueChanged.connect(self._slider.setValue)
        self._spin.valueChanged.connect(self.userChanged)

    def show_state(self, label: str, lo: int, hi: int, value: int, enabled: bool) -> None:
        def apply() -> None:
            for w in (self._slider, self._spin):
                w.setRange(lo, hi)
                w.setValue(value)
        silently(self._slider, lambda: silently(self._spin, apply))
        self._label.setText(label)
        self._range.setText(f"{lo} – {hi}")
        self.setEnabled(enabled)
