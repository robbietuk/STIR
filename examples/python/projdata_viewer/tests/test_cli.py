# SPDX-License-Identifier: Apache-2.0
import pytest

from stir_projdata_viewer.cli import build_parser


def test_positional_and_old_style_filename_options():
    p = build_parser()
    assert p.parse_args(["a.hs"]).path == "a.hs"
    assert p.parse_args(["-f", "b.hs"]).filename == "b.hs"          # the old tool's option
    assert p.parse_args(["--filename", "c.hs"]).filename == "c.hs"


def test_flags():
    a = build_parser().parse_args(["--demo", "--stir-path", "/opt/stir/python"])
    assert a.demo and a.stir_path == "/opt/stir/python" and a.path is None


def test_help_works_without_qt(capsys):
    with pytest.raises(SystemExit) as e:
        build_parser().parse_args(["-h"])
    assert e.value.code == 0 and "stir-projdata-viewer" in capsys.readouterr().out


def test_theme_option():
    p = build_parser()
    assert p.parse_args([]).theme == "dark" and p.parse_args(["--theme", "light"]).theme == "light"
    with pytest.raises(SystemExit):
        p.parse_args(["--theme", "neon"])
