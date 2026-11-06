# SPDX-License-Identifier: Apache-2.0
"""``SwigStirGateway`` against a fake ``stir`` module (adapter logic only: real bindings are
exercised by test_real_stir_integration.py where STIR is installed)."""
import sys

import numpy as np
import pytest

from fakes import FakeProjData, make_fake_stir
from stir_projdata_viewer.stir_interface import StirNotFoundError
from stir_projdata_viewer.stir_interface.swig_gateway import ENV_VAR, SwigStirGateway, import_stir


def gateway(pd=None):
    pd = pd or FakeProjData()
    return SwigStirGateway(stir_module=make_fake_stir(pd)), pd


def test_layout_from_stir_calls():
    gw, pd = gateway()
    lay = gw.wrap(pd).layout()
    assert (lay.min_segment, lay.max_segment, lay.min_tof, lay.max_tof) == (-1, 1, -1, 1)
    assert (lay.min_view, lay.max_view, lay.min_tangential, lay.max_tangential) == (0, 3, -2, 2)
    assert lay.axial_ranges == {-1: (0, 2), 0: (0, 3), 1: (0, 2)}


def test_read_segment_matches_stir_data_and_is_float32():
    gw, pd = gateway()
    h = gw.wrap(pd)
    out = h.read_segment(1, -1)
    assert out.dtype == np.float32
    np.testing.assert_array_equal(out, pd.data[(1, -1)])


def test_open_reads_through_stir_and_names_the_handle():
    gw, _ = gateway()
    assert gw.open("ok.hs").name == "ok.hs"
    assert gw.wrap(FakeProjData()).name == "ProjData object"


def test_open_error_becomes_oserror_with_filename():
    gw, _ = gateway()
    with pytest.raises(OSError, match="missing.hs"):
        gw.open("missing.hs")


def test_wrong_axis_order_is_detected_by_shape():
    pd = FakeProjData(transpose=True)              # as_array returns (axial, view, tangential)
    gw, _ = gateway(pd)
    with pytest.raises(RuntimeError, match="unexpected array shape"):
        gw.wrap(pd).read_segment(1, 0)             # 4 views vs 3 axial: shapes differ


def test_wrong_axis_order_with_equal_dimensions_is_detected_by_sinogram_check():
    pd = FakeProjData(transpose=True)
    gw, _ = gateway(pd)
    assert pd.data[(0, 0)].shape[:2] == (4, 4)     # views == axial: shape alone can't tell
    with pytest.raises(RuntimeError, match="get_sinogram"):
        gw.wrap(pd).read_segment(0, 0)


def test_layout_check_is_done_once_not_per_read():
    gw, pd = gateway()
    h = gw.wrap(pd)
    calls = {"n": 0}
    orig = pd.get_segment_by_view

    def spy(idx):
        seg = orig(idx)
        real = seg.get_sinogram

        def counted(a):
            calls["n"] += 1
            return real(a)
        seg.get_sinogram = counted
        return seg
    pd.get_segment_by_view = spy
    h.read_segment(0, 0)
    h.read_segment(0, 1)
    h.read_segment(1, 1)
    assert calls["n"] == 1


def test_metadata_failures_are_ignored():
    pd = FakeProjData()
    pd.get_proj_data_info = lambda: (_ for _ in ()).throw(RuntimeError("not in this version"))
    gw, _ = gateway(pd)
    assert gw.wrap(pd).metadata() == {}


def test_metadata_is_collected_when_available():
    pd = FakeProjData()

    class Scanner:
        get_name = lambda self: "FakeScanner"            # noqa: E731
        get_timing_resolution = lambda self: 250         # noqa: E731

    class PDI:
        get_scanner = lambda self: Scanner()             # noqa: E731
        get_tof_mash_factor = lambda self: 2             # noqa: E731

    pd.get_proj_data_info = lambda: PDI()
    gw, _ = gateway(pd)
    assert gw.wrap(pd).metadata() == {"scanner": "FakeScanner", "timing resolution (ps)": "250",
                                      "TOF mashing factor": "2"}


def test_zero_timing_resolution_is_not_reported():
    pd = FakeProjData()

    class Scanner:
        get_name = lambda self: "S"                      # noqa: E731
        get_timing_resolution = lambda self: 0.0         # noqa: E731

    pd.get_proj_data_info = lambda: type("P", (), {"get_scanner": lambda s: Scanner()})()
    gw, _ = gateway(pd)
    assert "timing resolution (ps)" not in gw.wrap(pd).metadata()


# ---- locating the stir module --------------------------------------------------------------
def test_missing_stir_gives_actionable_error(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.setitem(sys.modules, "stir", None)   # makes `import stir` fail
    with pytest.raises(StirNotFoundError, match="conda install"):
        import_stir()


def test_nonexistent_path_is_reported(monkeypatch):
    monkeypatch.setitem(sys.modules, "stir", None)
    with pytest.raises(StirNotFoundError, match="does not exist"):
        import_stir("/definitely/not/a/dir")


def test_explicit_path_is_searched_first_and_env_var_is_honoured(tmp_path, monkeypatch):
    (tmp_path / "stir").mkdir()
    (tmp_path / "stir" / "__init__.py").write_text("MARK = 'from tmp'\n")
    monkeypatch.delitem(sys.modules, "stir", raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert import_stir(str(tmp_path)).MARK == "from tmp"
    monkeypatch.delitem(sys.modules, "stir", raising=False)
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    assert import_stir().MARK == "from tmp"
    monkeypatch.delitem(sys.modules, "stir", raising=False)
