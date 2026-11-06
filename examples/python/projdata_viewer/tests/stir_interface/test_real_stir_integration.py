# SPDX-License-Identifier: Apache-2.0
"""Runs only where the real ``stir`` module is importable. Point it at data with
``STIR_TEST_PROJDATA=/path/file.hs`` (default: STIR's own recon_demo/smalllong.hs)."""
import os

import numpy as np
import pytest

stir = pytest.importorskip("stir")

from stir_projdata_viewer.model import ProjDataset, Selection, SliceMode, TofMode  # noqa: E402
from stir_projdata_viewer.stir_interface import open_stir_source  # noqa: E402
from stir_projdata_viewer.stir_interface.swig_gateway import SwigStirGateway  # noqa: E402
from stir_projdata_viewer.viewmodel import ViewerViewModel  # noqa: E402

from test_gateway_contract import check_handle_contract  # noqa: E402


def _projdata_path() -> str:
    env = os.environ.get("STIR_TEST_PROJDATA")
    if env:
        return env
    try:
        return os.path.join(stir.get_STIR_examples_dir(), "recon_demo", "smalllong.hs")
    except Exception:  # noqa: BLE001
        return ""


PATH = _projdata_path()
pytestmark = pytest.mark.skipif(not os.path.exists(PATH), reason="no projection data file available")


def test_real_handle_satisfies_the_contract():
    check_handle_contract(SwigStirGateway(stir_module=stir).open(PATH))


def test_axis_order_matches_stirs_own_accessors():
    """The assumption the whole viewer rests on: as_array() is (view, axial, tangential)."""
    pd = stir.ProjData.read_from_file(PATH)
    seg = pd.get_segment_by_view(stir.SegmentIndices(0, 0))
    arr = np.asarray(seg.as_array())
    lo, hi = pd.get_min_axial_pos_num(0), pd.get_max_axial_pos_num(0)
    for ax in (lo, (lo + hi) // 2, hi):
        np.testing.assert_array_equal(arr[:, ax - lo, :], np.asarray(seg.get_sinogram(ax).as_array()))
    for view in (pd.get_min_view_num(), pd.get_max_view_num()):
        np.testing.assert_array_equal(arr[view - pd.get_min_view_num()],
                                      np.asarray(seg.get_viewgram(view).as_array()))


def test_viewer_stack_on_real_data():
    src = open_stir_source(PATH, gateway=SwigStirGateway(stir_module=stir))
    ds = ProjDataset(src)
    for mode in SliceMode:
        img = ds.slice(Selection.initial(ds.info).with_slice_mode(mode))
        assert img.data.size > 0 and np.isfinite(img.data).all()
    summed = ds.segment_array(0, TofMode.SUM)
    assert summed.shape == ds.info.expected_shape(0)


def test_view_model_loads_a_real_file():
    from stir_projdata_viewer.sources.loader import make_source
    vm = ViewerViewModel(make_source)
    assert vm.load(PATH) and vm.image is not None and vm.error is None
