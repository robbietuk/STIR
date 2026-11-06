# SPDX-License-Identifier: Apache-2.0
"""``StirProjDataSource`` / ``open_stir_source``: handle -> model source, using fake gateways only."""
import numpy as np
import pytest

from fakes import FakeGateway, FakeHandle, small_demo
from stir_projdata_viewer.model import ProjDataset, Selection, TofMode
from stir_projdata_viewer.stir_interface import StirProjDataSource, open_stir_source


def test_info_maps_layout_and_metadata():
    base = small_demo()
    src = StirProjDataSource(FakeHandle(base, name="a.hs", meta={"scanner": "X"}))
    i, j = src.info, base.info
    assert i.name == "a.hs" and i.extra == {"scanner": "X"}
    for field in ("min_segment", "max_segment", "min_view", "max_view", "min_tangential", "max_tangential",
                  "min_tof", "max_tof", "axial_ranges"):
        assert getattr(i, field) == getattr(j, field)


def test_get_segment_delegates_to_handle():
    base = small_demo()
    h = FakeHandle(base)
    src = StirProjDataSource(h)
    np.testing.assert_array_equal(src.get_segment(1, 3), base.get_segment(1, 3))
    assert h.reads == 1


def test_info_does_not_alias_handle_metadata():
    h = FakeHandle(small_demo(), meta={"k": "v"})
    src = StirProjDataSource(h)
    h._meta["k"] = "changed"
    assert src.info.extra == {"k": "v"}


def test_open_stir_source_dispatches_path_vs_object():
    gw = FakeGateway()
    open_stir_source("a.hs", gateway=gw)
    open_stir_source(object(), gateway=gw)
    assert gw.opened == ["a.hs"] and len(gw.wrapped) == 1


def test_open_stir_source_accepts_pathlike(tmp_path):
    gw = FakeGateway()
    open_stir_source(tmp_path / "b.hs", gateway=gw)
    assert gw.opened == [str(tmp_path / "b.hs")]


def test_open_errors_propagate():
    with pytest.raises(OSError, match="missing"):
        open_stir_source("missing.hs", gateway=FakeGateway())


def test_adapter_feeds_the_model_end_to_end():
    src = open_stir_source("a.hs", gateway=FakeGateway(small_demo()))
    ds = ProjDataset(src)
    img = ds.slice(Selection.initial(ds.info).with_tof_mode(TofMode.SUM))
    assert img.shape == (12, 15) and img.data.sum() > 0
