# SPDX-License-Identifier: Apache-2.0
"""Colour scheme and stylesheet: pure Python, runs without Qt."""
import re

import pytest

from stir_projdata_viewer.view import theme
from stir_projdata_viewer.view.theme import DARK, LIGHT, PALETTES, TEXT_PAIRS, build_stylesheet, contrast_ratio

HEX = re.compile(r"^#[0-9a-f]{6}$")


@pytest.mark.parametrize("palette", PALETTES.values(), ids=lambda p: p.name)
def test_every_token_is_a_hex_colour(palette):
    colours = theme.palette_colours(palette)
    assert colours and all(HEX.match(v) for v in colours.values()), colours


@pytest.mark.parametrize("palette", PALETTES.values(), ids=lambda p: p.name)
@pytest.mark.parametrize("fg,bg", TEXT_PAIRS)
def test_text_pairs_meet_wcag_aa(palette, fg, bg):
    ratio = contrast_ratio(getattr(palette, fg), getattr(palette, bg))
    assert ratio >= 4.5, f"{palette.name}: {fg} on {bg} is {ratio:.2f}:1"


@pytest.mark.parametrize("palette", PALETTES.values(), ids=lambda p: p.name)
def test_surfaces_are_distinguishable(palette):
    assert contrast_ratio(palette.canvas, palette.surface) > 1.02
    assert contrast_ratio(palette.surface, palette.raised) > 1.02
    assert contrast_ratio(palette.surface, palette.border) > 1.1


def test_dark_is_dark_and_light_is_light():
    assert theme.luminance(DARK.canvas) < 0.05 < 0.5 < theme.luminance(LIGHT.surface)
    assert theme.DEFAULT_PALETTE is DARK


def test_contrast_ratio_known_values():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio("#777777", "#777777") == pytest.approx(1.0)
    assert contrast_ratio("#ffffff", "#000000") == contrast_ratio("#000000", "#ffffff")
    with pytest.raises(ValueError):
        theme.luminance("red")


@pytest.mark.parametrize("palette", PALETTES.values(), ids=lambda p: p.name)
def test_stylesheet_uses_only_palette_colours_and_braces_balance(palette):
    css = build_stylesheet(palette)
    assert css.count("{") == css.count("}") and "{{" not in css and "}}" not in css
    allowed = set(theme.palette_colours(palette).values())
    used = set(re.findall(r"#[0-9a-fA-F]{6}\b", css))
    assert used <= allowed, f"hard-coded colours: {used - allowed}"
    assert palette.accent in css and palette.surface in css


def test_stylesheet_covers_every_component_object_name():
    css = build_stylesheet(DARK)
    for name in ("Card", "Chip", "Tile", "Banner", "Segmented", "EmptyState", "TileValue", "CardTitle"):
        assert f"#{name}" in css, name
    assert 'segment="true"' in css and 'variant="primary"' in css


def test_light_and_dark_stylesheets_differ_only_in_colours():
    strip = lambda s: re.sub(r"#[0-9a-fA-F]{6}\b", "#X", s)       # noqa: E731
    assert strip(build_stylesheet(DARK)) == strip(build_stylesheet(LIGHT))


def test_theme_module_does_not_import_qt():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(theme))
    roots = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    roots |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not roots & {"PySide6", "pyqtgraph"}


def test_stylesheet_has_no_properties_qt_ignores():
    css = build_stylesheet(DARK)
    for unsupported in ("letter-spacing", "box-shadow", "transition", "gap:"):
        assert unsupported not in css


def test_disabled_slider_rule_uses_valid_subcontrol_order():
    assert "QSlider::sub-page:horizontal:disabled" in build_stylesheet(DARK)
    assert "QSlider:disabled::" not in build_stylesheet(DARK)


def test_disabled_text_and_monospace_rules_exist():
    css = build_stylesheet(DARK)
    assert "QLabel:disabled" in css and "QMenu::item:disabled" in css
    assert "QPlainTextEdit#Mono" in css and "QComboBox::drop-down" not in css
