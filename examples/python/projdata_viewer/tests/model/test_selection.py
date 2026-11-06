# SPDX-License-Identifier: Apache-2.0
import dataclasses

import pytest

from fakes import non_tof_source, small_demo
from stir_projdata_viewer.model import DIMENSIONS, Selection, SliceMode, TofMode


@pytest.fixture
def info():
    return small_demo().info


def test_initial_is_central_and_valid(info):
    s = Selection.initial(info)
    assert s.segment == 0 and s.tangential == 0
    assert s.axial == (0 + 7) // 2 and s.view == (0 + 11) // 2 and s.tof == 2
    assert s.slice_mode is SliceMode.SINOGRAM and s.tof_mode is TofMode.BIN
    assert s.is_valid_for(info)


def test_initial_when_segment_zero_or_tangential_zero_absent():
    from stir_projdata_viewer.model import ProjDataInfo
    info = ProjDataInfo("x", 1, 2, 0, 3, 5, 9, {1: (0, 3), 2: (0, 1)})
    s = Selection.initial(info)
    assert (s.segment, s.tangential) == (1, 5) and s.is_valid_for(info)


def test_selection_is_immutable(info):
    s = Selection.initial(info)
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.segment = 3   # type: ignore[misc]
    t = s.with_value(info, "view", 4)
    assert s.view != 4 and t.view == 4


@pytest.mark.parametrize("dim", DIMENSIONS)
def test_with_value_clamps_both_ends(info, dim):
    s = Selection.initial(info)
    lo, hi = s.range(info, dim)
    assert s.with_value(info, dim, hi + 100).get(dim) == hi
    assert s.with_value(info, dim, lo - 100).get(dim) == lo
    assert s.with_value(info, dim, lo).get(dim) == lo


def test_changing_segment_reclamps_axial(info):
    s = Selection.initial(info).with_value(info, "axial", 7)
    assert s.range(info, "axial") == (0, 7)
    t = s.with_value(info, "segment", 1)          # segment +-1 has fewer axial positions
    assert t.range(info, "axial") == (0, 3) and t.axial == 3 and t.is_valid_for(info)


def test_unknown_dimension_raises(info):
    s = Selection.initial(info)
    with pytest.raises(KeyError):
        s.get("nope")
    with pytest.raises(KeyError):
        s.range(info, "nope")


@pytest.mark.parametrize("mode,dim", [(SliceMode.SINOGRAM, "axial"), (SliceMode.VIEWGRAM, "view"),
                                      (SliceMode.TANGENTIAL, "tangential")])
def test_active_dimension(info, mode, dim):
    assert Selection.initial(info).with_slice_mode(mode).active_dimension == dim


def test_step_tof_wraps_both_directions(info):
    s = Selection.initial(info).with_value(info, "tof", info.max_tof)
    assert s.step_tof(info, 1).tof == info.min_tof
    assert s.step_tof(info, -1).tof == info.max_tof - 1
    assert Selection.initial(info).with_value(info, "tof", info.min_tof).step_tof(info, -1).tof == info.max_tof
    assert s.step_tof(info, info.num_tof_bins).tof == s.tof          # full cycle is the identity


def test_step_tof_on_non_tof_data_is_identity():
    info = non_tof_source().info
    s = Selection.initial(info)
    assert s.step_tof(info, 5) == s


def test_is_valid_for_detects_out_of_range(info):
    assert not dataclasses.replace(Selection.initial(info), view=999).is_valid_for(info)
