# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Apply a ``Palette`` to the whole application (Qt palette + stylesheet) and to pyqtgraph plots."""
from __future__ import annotations

import pyqtgraph as pg
from PySide6 import QtGui, QtWidgets

from .theme import DEFAULT_PALETTE, Palette, build_stylesheet


def apply_theme(app: QtWidgets.QApplication, palette: Palette = DEFAULT_PALETTE) -> None:
    app.setStyle("Fusion")                    # consistent base on every OS; the stylesheet does the rest
    qp = QtGui.QPalette()
    role = QtGui.QPalette.ColorRole
    for r, colour in ((role.Window, palette.canvas), (role.Base, palette.raised), (role.AlternateBase, palette.surface),
                      (role.Button, palette.raised), (role.Text, palette.text), (role.WindowText, palette.text),
                      (role.ButtonText, palette.text), (role.ToolTipBase, palette.raised),
                      (role.ToolTipText, palette.text), (role.Highlight, palette.accent),
                      (role.HighlightedText, palette.on_accent), (role.PlaceholderText, palette.text_muted)):
        qp.setColor(r, QtGui.QColor(colour))
    disabled = QtGui.QPalette.ColorGroup.Disabled
    for r in (role.WindowText, role.Text, role.ButtonText):
        qp.setColor(disabled, r, QtGui.QColor(palette.text_muted))
    app.setPalette(qp)
    app.setStyleSheet(build_stylesheet(palette))


def style_plot(plot_item: pg.PlotItem, palette: Palette) -> None:
    """Axis and title colours for a pyqtgraph PlotItem."""
    for name in ("left", "bottom"):
        axis = plot_item.getAxis(name)
        axis.setPen(pg.mkPen(palette.plot_axis))
        axis.setTextPen(pg.mkPen(palette.plot_axis))
    title = plot_item.titleLabel.text
    if title:
        plot_item.setTitle(title, color=palette.text)      # re-render: setAttr alone leaves existing text as is
    else:
        plot_item.titleLabel.setAttr("color", palette.text)


def style_histogram(hist: pg.HistogramLUTItem, palette: Palette) -> None:
    hist.axis.setPen(pg.mkPen(palette.plot_axis))
    hist.axis.setTextPen(pg.mkPen(palette.plot_axis))


def style_graphics_widget(widget: pg.GraphicsView, palette: Palette) -> None:
    widget.setBackground(palette.canvas)
