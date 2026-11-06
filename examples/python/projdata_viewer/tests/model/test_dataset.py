# SPDX-License-Identifier: Apache-2.0
import dataclasses

import numpy as np
import pytest

from fakes import CountingSource, non_tof_source, small_demo
from stir_projdata_viewer.model import ProjDataset, Selection, SliceMode, TofMode


@pytest.fixture
def demo():
    return small_demo()


@pytest.fixture
def ds(demo):
    return ProjDataset(demo)


def sel(ds, **kw):
    s = Selection.initial(ds.info)
    mode = kw.pop("slice_mode", None)
    tof_mode = kw.pop("tof_mode", None)
    for k, v in kw.items():
        s = s.with_value(ds.info, k, v)
    if mode:
        s = s.with_slice_mode(mode)
    if tof_mode:
        s = s.with_tof_mode(tof_mode)
    return s


def test_slice_shapes_and_axes(ds):
    sino = ds.slice(sel(ds))
    assert sino.shape == (12, 15) and (sino.row_axis, sino.col_axis) == ("view", "tangential")
    vg = ds.slice(sel(ds, slice_mode=SliceMode.VIEWGRAM))
    assert vg.shape == (8, 15) and (vg.row_axis, vg.col_axis) == ("axial", "tangential")
    tg = ds.slice(sel(ds, slice_mode=SliceMode.TANGENTIAL))
    assert tg.shape == (12, 8) and (tg.row_axis, tg.col_axis) == ("view", "axial")


def test_slice_values_match_raw_array(ds, demo):
    raw = demo.get_segment(0, 2)
    np.testing.assert_array_equal(ds.slice(sel(ds, axial=3)).data, raw[:, 3, :])
    np.testing.assert_array_equal(ds.slice(sel(ds, view=5, slice_mode=SliceMode.VIEWGRAM)).data, raw[5])
    np.testing.assert_array_equal(
        ds.slice(sel(ds, tangential=-4, slice_mode=SliceMode.TANGENTIAL)).data, raw[:, :, -4 + 7])


def test_slice_origins_are_real_bin_numbers(ds):
    img = ds.slice(sel(ds))
    assert img.indices_at(0, 0) == {"view": 0, "tangential": -7}
    tg = ds.slice(sel(ds, slice_mode=SliceMode.TANGENTIAL))
    assert tg.indices_at(2, 3) == {"view": 2, "axial": 3}


def test_slice_titles_mention_tof_only_for_tof_data(ds):
    assert "TOF bin 2" in ds.slice(sel(ds)).title
    assert "sum over" in ds.slice(sel(ds, tof_mode=TofMode.SUM)).title.lower()
    assert "TOF" not in ProjDataset(non_tof_source()).slice(Selection.initial(non_tof_source().info)).title


def test_invalid_selection_rejected(ds):
    with pytest.raises(ValueError, match="outside"):
        ds.slice(dataclasses.replace(sel(ds), view=999))


@pytest.mark.parametrize("mode,fn", [(TofMode.SUM, np.sum), (TofMode.MEAN, np.mean), (TofMode.MAX, np.max)])
@pytest.mark.parametrize("segment", [-1, 0, 1])
def test_tof_reductions_match_numpy(ds, demo, mode, fn, segment):
    bins = np.stack([demo.get_segment(segment, k) for k in demo.info.tof_bins])
    np.testing.assert_allclose(ds.segment_array(segment, mode), fn(bins, axis=0), rtol=1e-5)


def test_single_bin_returns_that_bin(ds, demo):
    np.testing.assert_array_equal(ds.segment_array(0, TofMode.BIN, 3), demo.get_segment(0, 3))


def test_sum_over_tof_equals_non_tof_for_single_bin():
    src = non_tof_source()
    ds = ProjDataset(src)
    for mode in (TofMode.SUM, TofMode.MEAN, TofMode.MAX):
        np.testing.assert_allclose(ds.segment_array(0, mode), src.get_segment(0, 0), rtol=1e-6)


def test_reduction_does_not_mutate_cached_raw_data(demo):
    ds = ProjDataset(demo)
    before = ds.segment_array(0, TofMode.BIN, 0).copy()
    ds.segment_array(0, TofMode.SUM)
    ds.segment_array(0, TofMode.MAX)
    np.testing.assert_array_equal(ds.segment_array(0, TofMode.BIN, 0), before)


def test_caching_avoids_rereads(demo):
    src = CountingSource(demo)
    ds = ProjDataset(src)
    ds.segment_array(0, TofMode.SUM)
    assert src.reads == demo.info.num_tof_bins
    ds.segment_array(0, TofMode.SUM)               # reduced cache
    ds.segment_array(0, TofMode.BIN, 1)            # raw cache (a full segment's bins are retained)
    assert src.reads == demo.info.num_tof_bins


def test_playback_over_all_bins_fits_in_cache(demo):
    src = CountingSource(demo)
    ds = ProjDataset(src, cache_segments=1)
    for _ in range(3):
        for k in demo.info.tof_bins:
            ds.segment_array(0, TofMode.BIN, k)
    assert src.reads == demo.info.num_tof_bins      # no thrashing even with a tiny cache setting


def test_cache_eviction_does_not_change_results(demo):
    ds = ProjDataset(demo, cache_segments=1)
    first = ds.segment_array(0, TofMode.SUM).copy()
    ds.segment_array(1, TofMode.SUM)
    ds.segment_array(-1, TofMode.SUM)
    np.testing.assert_array_equal(first, ds.segment_array(0, TofMode.SUM))


def test_source_returning_wrong_shape_is_rejected(demo):
    class Bad:
        info = demo.info

        def get_segment(self, s, t):
            return np.zeros((1, 1, 1), dtype=np.float32)

    with pytest.raises(ValueError, match="expected"):
        ProjDataset(Bad()).segment_array(0, TofMode.BIN, 0)


def test_global_range_bounds_every_slice_and_is_cached(demo):
    src = CountingSource(demo)
    ds = ProjDataset(src)
    s = sel(ds)
    lo, hi = ds.global_range(s)
    for seg in demo.info.segments:
        a = ds.segment_array(seg, s.tof_mode, s.tof)
        assert lo <= a.min() and a.max() <= hi
    reads = src.reads
    assert ds.global_range(s) == (lo, hi) and src.reads == reads
    assert ds.global_range(sel(ds, tof_mode=TofMode.SUM))[1] > hi        # collapsed data is brighter


def test_tof_profile_peaks_where_the_phantom_says():
    # View 0 has theta=0: the hot spot at (x, y) = (8, -10) sits at tangential 8 and TOF position
    # u = y = -10; with 5 bins centred at (k-2)*5 that is bin 0. Axial centre 0.6*(8-1)=4.2 -> axial 4.
    ds = ProjDataset(small_demo(num_tangential=21))           # tangential -10..10 so that x=8 is in range
    prof = ds.tof_profile(0, view=0, axial=4, tangential=8)
    assert prof.shape == (5,) and int(np.argmax(prof)) == 0 and prof[0] > 2 * prof[1]


@pytest.mark.parametrize("kwargs", [
    dict(segment=9, view=0, axial=0, tangential=0),
    dict(segment=0, view=-1, axial=0, tangential=0),        # would wrap to the last view in numpy
    dict(segment=0, view=12, axial=0, tangential=0),
    dict(segment=0, view=0, axial=-1, tangential=0),
    dict(segment=0, view=0, axial=8, tangential=0),
    dict(segment=0, view=0, axial=0, tangential=-8),
    dict(segment=0, view=0, axial=0, tangential=8),
])
def test_tof_profile_rejects_out_of_range_lor(ds, kwargs):
    with pytest.raises(ValueError):
        ds.tof_profile(**kwargs)


def test_tof_profile_sums_to_collapsed_value(ds):
    prof = ds.tof_profile(0, view=3, axial=4, tangential=2)
    total = ds.segment_array(0, TofMode.SUM)[3, 4, 2 + 7]
    assert prof.sum() == pytest.approx(float(total), rel=1e-5)


def test_stats_of_slice(ds):
    img = ds.slice(sel(ds))
    s = ds.stats(img)
    assert s.minimum == pytest.approx(img.data.min()) and s.maximum == pytest.approx(img.data.max())
    assert 0 < s.nonzero_fraction <= 1
