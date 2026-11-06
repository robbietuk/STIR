# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Colour scheme and style tokens (no Qt import, so palettes and stylesheet are unit-tested anywhere).

Every colour in the UI comes from a ``Palette``; no widget hard-codes a colour. ``build_stylesheet``
turns a palette into one Qt stylesheet, and the plots read the same palette.
"""
from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Palette:
    name: str
    # surfaces, darkest/lowest to highest
    canvas: str        # window background and plot background
    surface: str       # cards / panels
    raised: str        # inputs, buttons, tiles
    border: str
    # text
    text: str
    text_muted: str
    # accent and states
    accent: str
    accent_hover: str
    on_accent: str     # text on accent fills
    danger: str
    on_danger: str
    success: str
    # plots
    plot_axis: str
    plot_grid: str
    curve: str
    marker: str


DARK = Palette(
    name="dark", canvas="#0f1419", surface="#171d25", raised="#212a35", border="#2f3a48",
    text="#e6edf3", text_muted="#9aa7b5", accent="#4cc2ff", accent_hover="#7bd3ff", on_accent="#04202e",
    danger="#ff7b72", on_danger="#2a0a08", success="#56d364",
    plot_axis="#9aa7b5", plot_grid="#2f3a48", curve="#4cc2ff", marker="#ffb454")

LIGHT = Palette(
    name="light", canvas="#f3f5f8", surface="#ffffff", raised="#eaeef3", border="#cdd5df",
    text="#16202b", text_muted="#4d5b6a", accent="#0a64b8", accent_hover="#0b78dc", on_accent="#ffffff",
    danger="#b3261e", on_danger="#ffffff", success="#1a7f37",
    plot_axis="#4d5b6a", plot_grid="#cdd5df", curve="#0a64b8", marker="#b45309")

PALETTES = {p.name: p for p in (DARK, LIGHT)}
DEFAULT_PALETTE = DARK

# spacing / shape tokens (px)
RADIUS = 10
RADIUS_SMALL = 6
GAP = 12
PAD = 14
FONT_FAMILY = '"Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif'
FONT_SIZE = 13
MONO_FAMILY = '"JetBrains Mono", "Cascadia Mono", Menlo, Consolas, monospace'

# (foreground, background) pairs that must stay readable; checked by the tests
TEXT_PAIRS = (("text", "canvas"), ("text", "surface"), ("text", "raised"), ("text_muted", "canvas"),
              ("text_muted", "surface"), ("text_muted", "raised"), ("on_accent", "accent"),
              ("on_danger", "danger"), ("accent", "surface"), ("danger", "surface"))


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"expected #rrggbb, got {hex_colour!r}")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two ``#rrggbb`` colours (1 .. 21)."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def palette_colours(p: Palette) -> dict[str, str]:
    return {f.name: getattr(p, f.name) for f in fields(p) if f.name != "name"}


def build_stylesheet(p: Palette) -> str:
    """One application-wide stylesheet. Widgets opt into variants through the dynamic property
    ``variant`` (``primary``, ``danger``, ``ghost``) and object names (``Card``, ``Chip``, ``Tile``...)."""
    return f"""
* {{ font-family: {FONT_FAMILY}; font-size: {FONT_SIZE}px; color: {p.text}; }}
QMainWindow, QDialog {{ background: {p.canvas}; }}
QWidget#Root, QWidget#Content {{ background: {p.canvas}; }}
QToolTip {{ background: {p.raised}; color: {p.text}; border: 1px solid {p.border}; padding: 4px 6px; }}

QMenuBar {{ background: {p.canvas}; color: {p.text}; padding: 2px 6px; }}
QMenuBar::item {{ background: transparent; padding: 5px 10px; border-radius: {RADIUS_SMALL}px; }}
QMenuBar::item:selected {{ background: {p.raised}; }}
QMenu {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: {RADIUS_SMALL}px; padding: 6px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 4px; }}
QMenu::item:selected {{ background: {p.accent}; color: {p.on_accent}; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 5px 8px; }}

QStatusBar {{ background: {p.canvas}; color: {p.text_muted}; }}
QStatusBar::item {{ border: none; }}

QFrame#Card, QFrame#Sidebar {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: {RADIUS}px; }}
QFrame#Card QLabel, QFrame#Sidebar QLabel {{ background: transparent; }}
QLabel#CardTitle {{ color: {p.text_muted}; font-size: 11px; font-weight: 600; }}
QLabel#Muted {{ color: {p.text_muted}; }}
QLabel#Title {{ font-size: 15px; font-weight: 600; }}
QLabel#PixelReadout {{ color: {p.text_muted}; font-family: {MONO_FAMILY}; }}
QPlainTextEdit#Mono {{ font-family: {MONO_FAMILY}; }}
QLabel:disabled, QCheckBox:disabled, QMenu::item:disabled {{ color: {p.text_muted}; }}

QFrame#Chip {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: 11px; }}
QFrame#Chip QLabel {{ background: transparent; color: {p.text}; font-size: 12px; padding: 1px 9px; }}

QFrame#Tile {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: {RADIUS_SMALL}px; }}
QFrame#Tile QLabel {{ background: transparent; }}
QLabel#TileLabel {{ color: {p.text_muted}; font-size: 11px; }}
QLabel#TileValue {{ font-size: 14px; font-weight: 600; }}

QFrame#Banner {{ background: {p.danger}; border-radius: {RADIUS_SMALL}px; }}
QFrame#Banner QLabel {{ background: transparent; color: {p.on_danger}; font-weight: 600; }}
QFrame#Banner QPushButton {{ background: transparent; color: {p.on_danger}; border: none; font-weight: 700; padding: 2px 8px; }}

QWidget#EmptyState {{ background: transparent; }}
QLabel#EmptyTitle {{ font-size: 20px; font-weight: 600; }}
QLabel#EmptyHint {{ color: {p.text_muted}; }}

QPushButton {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: {RADIUS_SMALL}px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {p.accent}; }}
QPushButton:pressed {{ background: {p.border}; }}
QPushButton:disabled {{ color: {p.text_muted}; background: {p.surface}; }}
QPushButton:checked {{ background: {p.accent}; color: {p.on_accent}; border-color: {p.accent}; }}
QPushButton[variant="primary"] {{ background: {p.accent}; color: {p.on_accent}; border-color: {p.accent}; font-weight: 600; }}
QPushButton[variant="primary"]:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton[variant="primary"]:disabled {{ background: {p.border}; color: {p.text_muted}; border-color: {p.border}; }}
QPushButton[variant="ghost"] {{ background: transparent; border-color: transparent; }}
QPushButton[variant="ghost"]:hover {{ background: {p.raised}; }}
QPushButton:focus {{ border-color: {p.accent}; }}

QPushButton[segment="true"] {{ background: transparent; border: none; border-radius: 4px; padding: 5px 10px; color: {p.text_muted}; }}
QPushButton[segment="true"]:hover {{ color: {p.text}; }}
QPushButton[segment="true"]:checked {{ background: {p.accent}; color: {p.on_accent}; font-weight: 600; }}
QPushButton[segment="true"]:disabled {{ color: {p.border}; }}
QFrame#Segmented {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: {RADIUS_SMALL + 2}px; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {p.raised}; border: 1px solid {p.border}; border-radius: {RADIUS_SMALL}px; padding: 5px 8px;
    selection-background-color: {p.accent}; selection-color: {p.on_accent}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {p.accent}; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ color: {p.text_muted}; background: {p.surface}; }}
QComboBox QAbstractItemView {{ background: {p.surface}; border: 1px solid {p.border}; selection-background-color: {p.accent}; selection-color: {p.on_accent}; }}

QSlider::groove:horizontal {{ height: 4px; background: {p.border}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {p.accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {p.text}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; border: 2px solid {p.accent}; }}
QSlider::handle:horizontal:hover {{ background: {p.accent_hover}; }}
QSlider::sub-page:horizontal:disabled {{ background: {p.border}; }}
QSlider::handle:horizontal:disabled {{ background: {p.border}; border-color: {p.border}; }}

QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 32px; height: 18px; border-radius: 9px; background: {p.border}; border: 1px solid {p.border}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}
QCheckBox::indicator:disabled {{ background: {p.surface}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QSplitter::handle {{ background: transparent; }}
QPlainTextEdit {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: {RADIUS_SMALL}px; padding: 6px; }}
""".strip()
