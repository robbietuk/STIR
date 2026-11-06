# SPDX-License-Identifier: Apache-2.0
"""Regression tests for the second independent code review (findings numbered as in that review)."""
import sys
import warnings

import numpy as np
import pytest

from fakes import CountingSource, FakeProjData, SinogramCountingSource, make_fake_stir, small_demo
from stir_projdata_viewer.model import ProjDataset, Selection, SliceMode, TofMode
from stir_projdata_viewer.model.cache import LRUCache
from stir_projdata_viewer.sources import ArraySource
from stir_projdata_viewer.sources.array_source import standard_segment_sequence
from stir_projdata_viewer.stir_interface import StirNotFoundError
from stir_projdata_viewer.stir_interface.swig_gateway import ENV_VAR, SwigStirGateway, import_stir
from stir_projdata_viewer.viewmodel import LevelMode, ViewerViewModel
from stir_projdata_viewer.viewmodel.viewer_viewmodel import clean_path


class FailOn:
    """Source wrapper that fails reads matching ``pred(segment, tof_bin)``."""

    def __init__(self, inner, pred):
        self.inner, self.info, self.pred = inner, inner.info, pred

    def get_segment(self, segment, tof_bin):
        if self.pred(segment, tof_bin):
            raise OSError("disk went away")
        return self.inner.get_segment(segment, tof_bin)


def vm_with(source):
    vm = ViewerViewModel(lambda o: o)
    assert vm.load(source)
    return vm


# ---- 1: a failed first read must not half-replace the data set ---------------------------------
def test_1_load_whose_first_slice_fails_keeps_the_previous_data_set_entirely():
    a = small_demo()
    vm = vm_with(a)
    title, image, info, ds = vm.window_title, vm.image, vm.info_text, vm.dataset
    b = FailOn(small_demo(num_views=7), lambda s, t: True)
    assert vm.load(b) is False
    assert "Could not load" in vm.error
    assert vm.dataset is ds and vm.window_title == title and vm.image is image and vm.info_text == info
    vm.hover_at(0, 3)                                   # hover still refers to A, consistently
    assert vm.pixel_text and "view 3" in vm.pixel_text


# ---- 2: a failed slice read must not move the selection ----------------------------------------
@pytest.mark.parametrize("change", [
    lambda vm: vm.set_value("segment", 1),
    lambda vm: vm.set_slice_mode(SliceMode.VIEWGRAM),
    lambda vm: vm.set_tof_mode(TofMode.SUM),
    lambda vm: (vm.set_playing(True), vm.tick()),
], ids=["set_value", "set_slice_mode", "set_tof_mode", "tick"])
def test_2_failed_read_keeps_selection_controls_and_picture_consistent(change):
    fail = {"on": False}
    src = FailOn(small_demo(), lambda s, t: fail["on"])
    vm = vm_with(src)
    vm.set_value("segment", 0)
    before_sel, before_img, before_dims = vm.selection, vm.image, vm.dimensions
    seen = []
    vm.subscribe(lambda names: seen.append(set(names)))
    fail["on"] = True
    vm.dataset._raw.clear()                             # every change below must really read
    vm.dataset._reduced.clear()
    change(vm)
    assert vm.error and "Could not read" in vm.error
    assert vm.selection == before_sel and vm.image is before_img and vm.dimensions == before_dims
    assert vm.slice_mode is before_sel.slice_mode and vm.tof_mode is before_sel.tof_mode
    assert not vm.playing
    assert any("dimensions" in n for n in seen)          # the view is told to put its widgets back


def test_2_failed_global_level_mode_is_not_left_selected():
    fail = {"on": False}
    src = FailOn(small_demo(), lambda s, t: fail["on"] and s != 0)
    vm = vm_with(src)
    fail["on"] = True
    vm.set_level_mode(LevelMode.FIXED)                  # needs every segment: fails
    assert vm.level_mode is LevelMode.AUTO and vm.error


# ---- 4: global levels cover all TOF bins -------------------------------------------------------
def test_4_global_levels_do_not_change_during_playback_and_cover_every_bin():
    demo = small_demo()
    vm = vm_with(demo)
    vm.set_level_mode(LevelMode.FIXED)
    levels = {vm.levels}
    vm.set_playing(True)
    for _ in range(demo.info.num_tof_bins + 1):
        vm.tick()
        levels.add(vm.levels)
    assert len(levels) == 1
    lo, hi = levels.pop()
    everything = np.stack([demo.get_segment(s, k).ravel().max() for s in demo.info.segments for k in demo.info.tof_bins])
    assert hi == pytest.approx(float(everything.max()))
    assert lo == pytest.approx(min(float(demo.get_segment(s, k).min()) for s in demo.info.segments
                                   for k in demo.info.tof_bins))


# ---- 5: level rejection is announced so widgets snap back -----------------------------------------
def test_5_rejected_level_bounds_renotify_levels_and_keep_them():
    vm = vm_with(small_demo())
    vm.set_manual_levels(1.0, 2.0)
    seen = []
    vm.subscribe(lambda names: seen.append(set(names)))
    vm.set_level_bounds(low=5.0)
    assert vm.levels == (1.0, 2.0) and any("levels" in n for n in seen) and "Ignored" in vm.status
    vm.set_manual_levels(float("nan"), 3.0)
    assert vm.levels == (1.0, 2.0)


def test_5_tiny_valued_data_gets_a_usable_level_range():
    data = np.full((4, 3, 5), 3e-9, dtype=np.float32)    # constant tiny values: hi == lo
    vm = vm_with(ArraySource({0: data}))
    lo, hi = vm.levels
    assert lo == pytest.approx(3e-9) and hi > lo and hi - lo < 1e-9


# ---- 6: STIR's own ProjData.as_array() layout ------------------------------------------------------
def test_6_standard_segment_sequence_matches_stir():
    assert standard_segment_sequence(1) == [0]
    assert standard_segment_sequence(5) == [0, 1, -1, 2, -2]


def _stir_as_array(demo):
    """Build what ProjData.as_array() returns: (tof, all sinograms in standard order, views, tang)."""
    order = standard_segment_sequence(demo.info.num_segments)
    tof = []
    for k in demo.info.tof_bins:
        parts = [demo.get_segment(s, k).transpose(1, 0, 2) for s in order]     # (axial, view, tang)
        tof.append(np.concatenate(parts, axis=0))
    return np.stack(tof), order, [demo.info.num_axial(s) for s in order]


def test_6_npz_in_stir_as_array_layout_round_trips(tmp_path):
    demo = small_demo()
    arr, order, counts = _stir_as_array(demo)
    f = tmp_path / "export.npz"
    np.savez(f, as_array=arr, axial_counts=counts)
    src = ArraySource.from_file(f)
    assert src.info.segments == demo.info.segments and src.info.num_tof_bins == demo.info.num_tof_bins
    for s in demo.info.segments:
        for k in range(demo.info.num_tof_bins):
            np.testing.assert_array_equal(src.get_segment(s, k), demo.get_segment(s, demo.info.min_tof + k))


def test_6_as_array_layout_errors_are_explicit(tmp_path):
    demo = small_demo()
    arr, order, counts = _stir_as_array(demo)
    with pytest.raises(ValueError, match="add up to"):
        ArraySource.from_stir_as_array(arr, counts[:-1] + [counts[-1] + 1])
    f = tmp_path / "x.npz"
    np.savez(f, as_array=arr)
    with pytest.raises(ValueError, match="axial_counts"):
        ArraySource.from_file(f)
    np.savez(f, segment_0=np.zeros((2, 3, 4)), bogus=np.zeros(1))
    with pytest.raises(ValueError, match="as_array"):
        ArraySource.from_file(f)


def test_6_non_symmetric_segment_order_can_be_given():
    rng = np.random.default_rng(0)
    segs = {s: rng.random((1, 4, 2 + s + 1, 3)).astype(np.float32) for s in (-1, 0, 1, 2)}
    order = [0, 1, -1, 2]
    arr = np.concatenate([segs[s][0].transpose(1, 0, 2) for s in order])[np.newaxis]
    src = ArraySource.from_stir_as_array(arr, [segs[s].shape[2] for s in order], order)
    for s in segs:
        np.testing.assert_array_equal(src.get_segment(s, 0), segs[s][0])


# ---- 7: get_segment_by_view overloads ----------------------------------------------------------------
def test_7_gateway_prefers_the_int_overload_that_every_subclass_has():
    pd = FakeProjData()
    calls = []
    real = pd.get_segment_by_view
    pd.get_segment_by_view = lambda *a: (calls.append(a), real(*a))[1]
    SwigStirGateway(stir_module=make_fake_stir(pd)).wrap(pd).read_segment(1, -1)
    assert calls == [(1, -1)]


# ---- 9: hover reads sinograms, not whole segments; caches are bounded by bytes -----------------------
def test_9_tof_profile_reads_one_sinogram_per_bin_not_whole_segments():
    demo = small_demo()
    src = SinogramCountingSource(demo)
    ds = ProjDataset(src)
    prof = ds.tof_profile(1, 2, 3, 0)
    assert src.reads == 0 and src.sinogram_reads == demo.info.num_tof_bins
    expected = [demo.get_segment(1, k)[2, 3, 0 - demo.info.min_tangential] for k in demo.info.tof_bins]
    np.testing.assert_allclose(prof, expected)
    ds.tof_profile(1, 5, 3, 1)                          # same sinograms: cached
    assert src.sinogram_reads == demo.info.num_tof_bins


def test_9_tof_profile_uses_a_segment_already_in_memory():
    demo = small_demo()
    src = SinogramCountingSource(demo)
    ds = ProjDataset(src)
    for k in demo.info.tof_bins:
        ds.segment_array(0, TofMode.BIN, k)
    reads = src.reads
    ds.tof_profile(0, 1, 2, 0)
    assert src.reads == reads and src.sinogram_reads == 0


def test_9_lru_cache_respects_a_byte_budget_but_keeps_the_newest():
    c = LRUCache(10, max_bytes=250)
    for i in range(5):
        c.put(i, np.zeros(100, dtype=np.uint8))
    assert len(c) == 2 and c.nbytes == 200 and 4 in c and 3 in c
    c.put("big", np.zeros(1000, dtype=np.uint8))
    assert len(c) == 1 and "big" in c


def test_9_dataset_cache_budget_limits_memory_and_still_gives_right_answers():
    demo = small_demo()
    seg_bytes = demo.get_segment(0, demo.info.min_tof).nbytes
    src = CountingSource(demo)
    ds = ProjDataset(src, cache_bytes=2 * seg_bytes)
    total = ds.segment_array(0, TofMode.SUM)
    assert ds._raw.nbytes <= 2 * seg_bytes
    np.testing.assert_allclose(total, sum(demo.get_segment(0, k) for k in demo.info.tof_bins), rtol=1e-5)


# ---- 10: path box / typed paths --------------------------------------------------------------------
def test_10_clean_path_strips_quotes_and_expands_home(monkeypatch):
    monkeypatch.setenv("HOME", "/home/me")
    assert clean_path('  "C:\\\\data\\\\x.hs"  ') == "C:\\\\data\\\\x.hs"
    assert clean_path("'~/a b.hs'") == "/home/me/a b.hs"
    assert clean_path("   ") == ""


def test_10_source_path_is_only_set_for_files(tmp_path):
    f = tmp_path / "a.npy"
    np.save(f, np.zeros((4, 3, 5), dtype=np.float32))
    from stir_projdata_viewer.sources.loader import make_source
    vm = ViewerViewModel(make_source, demo_factory=small_demo)
    vm.load_demo()
    assert vm.source_path == "" and "demo" in vm.source_label
    assert vm.load_path(f'"{f}"') and vm.source_path == str(f)
    assert vm.load_path("   ") is False


# ---- 11: STIR lookup -------------------------------------------------------------------------------------
def test_11_bad_env_var_warns_and_falls_back_to_plain_import(monkeypatch):
    fake = make_fake_stir(FakeProjData())
    monkeypatch.setitem(sys.modules, "stir", fake)
    monkeypatch.setenv(ENV_VAR, "/does/not/exist")
    with pytest.warns(RuntimeWarning, match="not a directory"):
        assert import_stir() is fake


def test_11_bad_explicit_path_is_still_an_error(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(StirNotFoundError, match="does not exist"):
        import_stir("/does/not/exist")


def test_11_explicit_path_with_stir_already_imported_elsewhere_warns(monkeypatch, tmp_path):
    fake = make_fake_stir(FakeProjData())
    fake.__file__ = "/elsewhere/stir/__init__.py"
    monkeypatch.setitem(sys.modules, "stir", fake)
    with pytest.warns(RuntimeWarning, match="already imported from /elsewhere"):
        assert import_stir(str(tmp_path)) is fake
    fake.__file__ = str(tmp_path / "stir" / "__init__.py")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert import_stir(str(tmp_path)) is fake       # same place: no warning
