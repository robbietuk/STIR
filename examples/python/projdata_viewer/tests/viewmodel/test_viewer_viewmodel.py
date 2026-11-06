# SPDX-License-Identifier: Apache-2.0
import numpy as np
import pytest

from fakes import CountingSource, non_tof_source, small_demo
from stir_projdata_viewer.model import SliceMode, TofMode
from stir_projdata_viewer.viewmodel import COLORMAPS, LevelMode, ViewerViewModel
from stir_projdata_viewer.viewmodel.viewer_viewmodel import MAX_FPS, MIN_FPS


def make_vm(source=None, load=True):
    vm = ViewerViewModel(source_factory=lambda obj: obj)
    notes = []
    vm.subscribe(notes.append)
    if load:
        assert vm.load(source or small_demo())
        notes.clear()
    return vm, notes


# ---- before anything is loaded -------------------------------------------------------------
def test_initial_state_is_empty_and_commands_are_harmless():
    vm, notes = make_vm(load=False)
    assert not vm.loaded and vm.image is None and vm.dimensions == () and vm.selection is None
    vm.set_value("axial", 3)
    vm.step_active(1)
    vm.set_slice_mode(SliceMode.VIEWGRAM)
    vm.set_tof_mode(TofMode.SUM)
    vm.tick()
    vm.hover_at(0, 0)
    vm.set_playing(True)
    assert notes == [] and not vm.playing


# ---- loading ---------------------------------------------------------------------------------
def test_load_publishes_a_complete_state_in_one_notification():
    vm, notes = make_vm(load=False)
    assert vm.load(small_demo())
    assert len(notes) == 1
    assert {"loaded", "image", "levels", "dimensions", "info_text", "window_title"} <= notes[0]
    assert vm.loaded and "demo" in vm.window_title and vm.error is None
    assert [d.name for d in vm.dimensions] == ["segment", "axial", "view", "tangential", "tof"]
    assert vm.tof_available and vm.can_play and vm.tof_marker == 2
    assert "Source:" in vm.info_text and "Current slice" in vm.info_text


def test_image_rect_is_pixel_centred_in_bin_numbers():
    vm, _ = make_vm()
    im = vm.image
    assert (im.x0, im.y0, im.width, im.height) == (-7 - 0.5, 0 - 0.5, 15.0, 12.0)
    assert (im.row_label, im.col_label) == ("view", "tangential") and im.data.dtype == np.float32


def test_load_failure_reports_and_keeps_previous_data():
    def factory(obj):
        if obj == "bad":
            raise OSError("no such file")
        return obj
    vm = ViewerViewModel(factory)
    notes = []
    vm.load(small_demo())
    vm.subscribe(notes.append)
    before = vm.image
    assert vm.load("bad") is False
    assert "no such file" in vm.error and vm.error in vm.status
    assert vm.loaded and vm.image is before
    assert any("error" in n for n in notes)
    notes.clear()
    assert vm.load("bad") is False
    assert any("error" in n for n in notes)            # the same message is announced again


def test_load_resets_selection_playback_and_profile():
    vm, _ = make_vm()
    vm.set_value("segment", 1)
    vm.set_playing(True)
    vm.hover_at(0, 0)
    assert vm.tof_profile is not None
    vm.load(small_demo(num_views=20))
    assert vm.selection.segment == 0 and not vm.playing and vm.tof_profile is None and vm.pixel_text == ""


def test_loading_non_tof_data_disables_tof_controls():
    vm, _ = make_vm(non_tof_source())
    assert not vm.tof_available and not vm.can_play and vm.tof_marker is None
    assert not vm.dimension("tof").enabled
    vm.set_playing(True)
    vm.tick()
    assert not vm.playing


# ---- dimensions ------------------------------------------------------------------------------------
@pytest.mark.parametrize("mode,enabled", [
    (SliceMode.SINOGRAM, {"segment", "axial", "tof"}),
    (SliceMode.VIEWGRAM, {"segment", "view", "tof"}),
    (SliceMode.TANGENTIAL, {"segment", "tangential", "tof"}),
])
def test_only_relevant_dimensions_are_enabled(mode, enabled):
    vm, _ = make_vm()
    vm.set_slice_mode(mode)
    assert {d.name for d in vm.dimensions if d.enabled} == enabled
    assert vm.slice_mode is mode


def test_set_value_updates_slice_and_clamps():
    vm, _ = make_vm()
    vm.set_value("axial", 3)
    assert vm.selection.axial == 3 and "axial 3" in vm.image.title
    vm.set_value("axial", 999)
    assert vm.dimension("axial").value == vm.dimension("axial").hi == 7


def test_changing_segment_changes_the_axial_range_shown():
    vm, _ = make_vm()
    assert vm.dimension("axial").hi == 7
    vm.set_value("segment", 1)
    assert vm.dimension("axial").hi == 3


def test_step_and_step_active():
    vm, _ = make_vm()
    a = vm.selection.axial
    vm.step_active(1)
    assert vm.selection.axial == a + 1
    vm.set_slice_mode(SliceMode.VIEWGRAM)
    v = vm.selection.view
    vm.step_active(-1)
    assert vm.selection.view == v - 1 and vm.selection.axial == a + 1
    vm.step("segment", +99)
    assert vm.selection.segment == 1


def test_dimensions_with_a_single_value_are_disabled():
    vm, _ = make_vm(non_tof_source())
    assert not vm.dimension("tof").enabled          # lo == hi
    assert vm.dimension("segment").enabled
    one_segment, _ = make_vm(small_demo(num_segments=1))
    assert one_segment.dimension("segment").lo == one_segment.dimension("segment").hi
    assert not one_segment.dimension("segment").enabled     # always "wanted", but nothing to scroll


# ---- slice and TOF modes ------------------------------------------------------------------------------
def test_slice_modes_change_shape_and_labels():
    vm, _ = make_vm()
    vm.set_slice_mode(SliceMode.VIEWGRAM)
    assert vm.image.data.shape == (8, 15) and vm.image.row_label == "axial"
    vm.set_slice_mode(SliceMode.TANGENTIAL)
    assert vm.image.data.shape == (12, 8) and vm.image.col_label == "axial"


def test_tof_collapse_disables_play_and_marker():
    vm, _ = make_vm()
    vm.set_playing(True)
    assert vm.playing
    vm.set_tof_mode(TofMode.SUM)
    assert not vm.playing and not vm.can_play and vm.tof_marker is None
    assert not vm.dimension("tof").enabled and "sum over" in vm.image.title.lower()
    vm.set_tof_mode(TofMode.BIN)
    assert vm.can_play and vm.tof_marker == vm.selection.tof and vm.dimension("tof").enabled


def test_collapsed_image_equals_sum_of_bins():
    src = small_demo()
    vm, _ = make_vm(src)
    vm.set_tof_mode(TofMode.SUM)
    expect = sum(src.get_segment(0, k) for k in src.info.tof_bins)[:, vm.selection.axial, :]
    np.testing.assert_allclose(vm.image.data, expect, rtol=1e-5)


# ---- playback -----------------------------------------------------------------------------------------
def test_play_toggle_and_tick_advance_with_wraparound():
    vm, notes = make_vm()
    vm.toggle_play()
    assert vm.playing
    seen = []
    for _ in range(vm.dataset.info.num_tof_bins):
        vm.tick()
        seen.append(vm.selection.tof)
    assert seen == [3, 4, 0, 1, 2]                 # started at the centre bin 2
    vm.toggle_play()
    assert not vm.playing


def test_tick_changes_the_image_and_marker():
    vm, _ = make_vm()
    before = vm.image
    vm.set_playing(True)
    vm.tick()
    assert vm.image is not before and not np.array_equal(vm.image.data, before.data)
    assert vm.tof_marker == vm.selection.tof


def test_tick_when_play_became_impossible_stops_playback():
    vm, _ = make_vm()
    vm.set_playing(True)
    vm._selection = vm._selection.with_tof_mode(TofMode.MAX)   # simulate a stale timer firing
    vm.tick()
    assert not vm.playing


def test_fps_is_clamped_and_unchanged_value_is_silent():
    vm, notes = make_vm()
    vm.set_fps(1000)
    assert vm.fps == MAX_FPS
    vm.set_fps(-5)
    assert vm.fps == MIN_FPS
    notes.clear()
    vm.set_fps(MIN_FPS)
    assert notes == []


# ---- display options -----------------------------------------------------------------------------------
def test_colormap_validation():
    vm, _ = make_vm()
    for name in COLORMAPS:
        vm.set_colormap(name)
        assert vm.colormap == name
    with pytest.raises(ValueError, match="unknown colour map"):
        vm.set_colormap("jet")
    assert vm.colormap == COLORMAPS[-1]


def test_auto_levels_follow_the_slice():
    vm, _ = make_vm()
    assert vm.levels == (float(vm.image.data.min()), float(vm.image.data.max()))
    vm.set_value("axial", 5)
    assert vm.levels == (float(vm.image.data.min()), float(vm.image.data.max()))


def test_fixed_levels_are_the_global_range_and_do_not_move_between_slices():
    vm, _ = make_vm()
    vm.set_level_mode(LevelMode.FIXED)
    lo, hi = vm.dataset.global_range(vm.selection)
    assert vm.levels == (lo, hi)
    vm.set_value("axial", 0)
    vm.set_value("segment", 1)
    assert vm.levels == (lo, hi)


def test_log_display_transforms_values_and_levels():
    src = small_demo()
    vm, _ = make_vm(src)
    raw = vm.dataset.slice(vm.selection).data
    vm.set_log_display(True)
    np.testing.assert_allclose(vm.image.data, np.log1p(raw), rtol=1e-6)
    vm.set_level_mode(LevelMode.FIXED)
    lo, hi = vm.dataset.global_range(vm.selection)
    assert vm.levels == pytest.approx((np.log1p(lo), np.log1p(hi)))


def test_log_display_handles_negative_values():
    arr = np.full((4, 2, 5), -3.0, dtype=np.float32)
    arr[1, 1, 1] = 7.0
    from stir_projdata_viewer.sources import ArraySource
    vm, _ = make_vm(ArraySource({0: arr}))
    vm.set_log_display(True)
    assert np.isfinite(vm.image.data).all() and vm.image.data.min() == 0.0


def test_manual_levels_stick_across_slices_and_switch_the_mode():
    vm, _ = make_vm()
    vm.set_manual_levels(1.0, 2.0)
    assert vm.level_mode is LevelMode.MANUAL and vm.levels == (1.0, 2.0)
    vm.set_value("axial", 1)
    vm.tick()
    assert vm.levels == (1.0, 2.0)
    vm.set_level_mode(LevelMode.AUTO)
    assert vm.levels != (1.0, 2.0)


def test_manual_levels_reject_empty_range():
    vm, _ = make_vm()
    before = vm.levels
    vm.set_manual_levels(3.0, 3.0)
    vm.set_manual_levels(5.0, 1.0)
    assert vm.levels == before and vm.level_mode is LevelMode.AUTO


def test_toggling_log_resets_manual_levels():
    vm, _ = make_vm()
    vm.set_manual_levels(1.0, 2.0)
    vm.set_log_display(True)
    assert vm.level_mode is LevelMode.AUTO and vm.levels != (1.0, 2.0)


def test_stale_manual_levels_never_come_back_after_a_scale_change():
    vm, _ = make_vm()
    vm.set_manual_levels(1.0, 2.0)
    vm.set_log_display(True)
    vm.set_level_mode(LevelMode.MANUAL)             # user picks "Manual" again in the new scale
    assert vm.levels != (1.0, 2.0)
    assert vm.levels == (float(vm.image.data.min()), float(vm.image.data.max()))


def test_constant_slice_still_gets_a_valid_level_range():
    from stir_projdata_viewer.sources import ArraySource
    vm, _ = make_vm(ArraySource({0: np.full((4, 2, 5), 3.0)}))
    lo, hi = vm.levels
    assert hi > lo


# ---- hover --------------------------------------------------------------------------------------------------
def test_hover_reports_value_and_real_indices():
    vm, _ = make_vm()
    vm.hover_at(-7, 0)                                  # first column, first row
    assert vm.pixel_text.startswith("view 0, tangential -7:")
    value = float(vm.dataset.slice(vm.selection).data[0, 0])
    assert f"{value:.6g}" in vm.pixel_text


def test_hover_rounds_to_the_pixel_under_the_cursor():
    vm, _ = make_vm()
    vm.hover_at(-7 + 0.4, 0.4)
    assert vm.pixel_text.startswith("view 0, tangential -7:")
    vm.hover_at(-7 + 0.6, 0.6)
    assert vm.pixel_text.startswith("view 1, tangential -6:")


def test_hover_outside_clears_and_leave_clears():
    vm, _ = make_vm()
    vm.hover_at(0, 0)
    assert vm.pixel_text
    vm.hover_at(1000, 0)
    assert vm.pixel_text == ""
    vm.hover_at(0, 0)
    vm.hover_leave()
    assert vm.pixel_text == ""


def test_hover_builds_tof_profile_once_per_pixel():
    vm, _ = make_vm()
    calls = []
    real = vm.dataset.tof_profile
    vm.dataset.tof_profile = lambda *a: (calls.append(a), real(*a))[1]
    vm.hover_at(0, 3)
    p1 = vm.tof_profile
    assert p1.x == (0, 1, 2, 3, 4) and len(p1.y) == 5 and "view 3" in p1.title
    vm.hover_at(0.2, 3.1)                               # same pixel
    assert len(calls) == 1 and vm.tof_profile is p1
    vm.hover_at(1, 3)
    assert len(calls) == 2
    assert calls[0] == (0, 3, vm.selection.axial, 0)    # segment, view, axial, tangential


def test_hover_profile_uses_the_correct_lor_in_each_slice_mode():
    vm, _ = make_vm()
    vm.set_slice_mode(SliceMode.VIEWGRAM)               # rows: axial, cols: tangential; fixed: view
    vm.set_value("view", 4)
    vm.hover_at(2, 5)
    assert "view 4, axial 5, tangential 2" in vm.tof_profile.title
    vm.set_slice_mode(SliceMode.TANGENTIAL)             # rows: view, cols: axial; fixed: tangential
    vm.set_value("tangential", -2)
    vm.hover_at(6, 3)
    assert "view 3, axial 6, tangential -2" in vm.tof_profile.title


def test_hover_on_non_tof_data_has_no_profile():
    vm, _ = make_vm(non_tof_source())
    vm.hover_at(0, 0)
    assert vm.pixel_text and vm.tof_profile is None


def test_profile_sum_equals_collapsed_pixel():
    vm, _ = make_vm()
    vm.hover_at(0, 3)
    total = sum(vm.tof_profile.y)
    vm.set_tof_mode(TofMode.SUM)
    vm.hover_at(0, 3)
    assert float(vm.pixel_text.split(":")[1]) == pytest.approx(total, rel=1e-4)


# ---- failure handling ------------------------------------------------------------------------------------------
def test_read_failure_keeps_the_last_good_image_and_reports():
    src = CountingSource(small_demo())
    vm, notes = make_vm(src)
    good = vm.image
    src.fail = True
    vm.set_value("segment", 1)
    assert vm.image is good and "disk went away" in vm.error and any("error" in n for n in notes)
    src.fail = False
    vm.set_value("segment", 1)
    assert vm.image is not good and vm.selection.segment == 1


def test_profile_failure_is_reported_not_raised():
    src = CountingSource(small_demo())
    vm, _ = make_vm(src)
    vm.dataset._raw.clear()
    src.fail = True
    vm.hover_at(0, 0)
    assert "TOF profile unavailable" in vm.error


# ---- notification contract -------------------------------------------------------------------------------------
def test_every_command_notifies_at_most_once():
    vm, notes = make_vm()
    commands = [lambda: vm.set_value("view", 5), lambda: vm.set_slice_mode(SliceMode.VIEWGRAM),
                lambda: vm.set_tof_mode(TofMode.MEAN), lambda: vm.set_tof_mode(TofMode.BIN),
                lambda: vm.tick(), lambda: vm.set_log_display(True), lambda: vm.hover_at(0, 0),
                lambda: vm.set_manual_levels(0, 1), lambda: vm.set_level_mode(LevelMode.FIXED)]
    for cmd in commands:
        notes.clear()
        cmd()
        assert len(notes) <= 1


def test_view_model_state_is_published_before_notification():
    """A subscriber that reads state in its callback must see the finished command, not a half-way state."""
    vm, _ = make_vm()
    vm.set_playing(True)
    snapshots = []
    vm.subscribe(lambda names: snapshots.append((vm.selection.tof, vm.tof_marker, vm.image.title)))
    vm.tick()
    tof, marker, title = snapshots[-1]
    assert marker == tof and f"TOF bin {tof}" in title
