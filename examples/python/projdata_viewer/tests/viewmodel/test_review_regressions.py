# SPDX-License-Identifier: Apache-2.0
"""Regression tests for defects found by the independent code review."""
import numpy as np
import pytest

from fakes import CountingSource, small_demo
from stir_projdata_viewer.model import ProjDataset, Selection, TofMode
from stir_projdata_viewer.sources import ArraySource
from stir_projdata_viewer.viewmodel import LevelMode, ViewerViewModel


def make_vm(source=None):
    vm = ViewerViewModel(lambda o: o, demo_factory=small_demo)
    vm.load(source or small_demo())
    return vm


def test_tof_profile_is_not_stale_after_the_selection_changes():
    vm = make_vm()
    vm.hover_at(0, 3)
    assert "axial 3" in vm.tof_profile.title or f"axial {vm.selection.axial}" in vm.tof_profile.title
    vm.set_value("axial", 1)
    vm.hover_at(0, 3)                                   # same pixel, different slice
    assert "axial 1" in vm.tof_profile.title


def test_tof_profile_refreshes_after_playback_tick_and_slice_mode_change():
    vm = make_vm()
    vm.hover_at(0, 3)
    first = vm.tof_profile
    vm.set_value("segment", 1)
    vm.hover_at(0, 3)
    assert vm.tof_profile is not first and "segment 1" in vm.tof_profile.title


def test_a_read_error_stops_playback():
    src = CountingSource(small_demo())
    vm = make_vm(src)
    vm.set_playing(True)
    src.fail = True
    vm.dataset._raw.clear()
    vm.tick()
    assert vm.error and not vm.playing
    errors = []
    vm.subscribe(lambda n: errors.append(n) if "error" in n else None)
    vm.tick()                                            # a stale timer firing must not pile up errors
    assert errors == []


def test_nan_and_inf_do_not_poison_the_levels():
    arr = np.arange(4 * 3 * 5, dtype=np.float32).reshape(4, 3, 5)
    arr[0, 0, 0] = np.nan
    arr[1, 1, 1] = np.inf
    vm = make_vm(ArraySource({0: arr}))
    lo, hi = vm.levels
    assert np.isfinite([lo, hi]).all() and hi > lo
    vm.set_level_mode(LevelMode.FIXED)
    lo, hi = vm.levels
    assert np.isfinite([lo, hi]).all() and hi > lo


def test_all_nan_slice_still_gets_valid_levels():
    vm = make_vm(ArraySource({0: np.full((4, 3, 5), np.nan, dtype=np.float32)}))
    lo, hi = vm.levels
    assert np.isfinite([lo, hi]).all() and hi > lo


def test_global_range_ignores_non_finite_values():
    arr = np.ones((4, 3, 5), dtype=np.float32)
    arr[0, 0, 0] = np.nan
    arr[0, 0, 1] = -np.inf
    ds = ProjDataset(ArraySource({0: arr}))
    assert ds.global_range(Selection.initial(ds.info)) == (1.0, 1.0)


def test_loading_new_data_leaves_manual_mode_consistent():
    vm = make_vm()
    vm.set_manual_levels(1.0, 2.0)
    vm.load(small_demo())
    assert vm.level_mode is LevelMode.AUTO and vm.levels != (1.0, 2.0)


def test_load_demo_command_uses_the_injected_factory():
    vm = ViewerViewModel(lambda o: o, demo_factory=small_demo)
    assert vm.load_demo() and vm.loaded
    assert not ViewerViewModel(lambda o: o).load_demo()          # no demo factory configured -> reported, not raised


def test_levels_can_be_typed_in_via_numeric_commands():
    vm = make_vm()
    vm.set_level_bounds(low=0.5)
    assert vm.level_mode is LevelMode.MANUAL and vm.levels[0] == 0.5
    hi = vm.levels[1]
    vm.set_level_bounds(high=hi + 5)
    assert vm.levels == (0.5, hi + 5)
    vm.set_level_bounds(low=hi + 100)                           # would invert the range: ignored
    assert vm.levels == (0.5, hi + 5)
