# SPDX-License-Identifier: Apache-2.0
from fakes import non_tof_source, small_demo
from stir_projdata_viewer.model import ProjDataset, Selection, SliceMode, TofMode
from stir_projdata_viewer.model.slices import SliceStats
from stir_projdata_viewer.viewmodel import ViewerViewModel, formatting


def make_vm(src=None):
    vm = ViewerViewModel(lambda o: o)
    if src is not None:
        vm.load(src)
    return vm


def test_metrics_cover_the_six_statistics():
    vm = make_vm(small_demo())
    assert [k for k, _ in vm.metrics] == ["Min", "Max", "Mean", "Std", "Sum", "Non-zero"]
    assert all(v for _, v in vm.metrics)


def test_metrics_follow_the_slice():
    vm = make_vm(small_demo())
    before = vm.metrics
    vm.set_value("axial", 0)
    assert vm.metrics != before


def test_metrics_and_context_are_cleared_on_load_of_new_data_then_refilled():
    vm = make_vm(small_demo())
    seen = []
    vm.subscribe(lambda names: seen.append(names))
    vm.load(non_tof_source())
    assert any({"metrics", "context"} <= n for n in seen)
    assert vm.context and not any("TOF" in c for c in vm.context)


def test_context_chips_describe_mode_segment_position_and_tof():
    vm = make_vm(small_demo())
    assert vm.context == ("Sinogram", "segment 0", "axial 3", "TOF bin 2")
    vm.set_slice_mode(SliceMode.VIEWGRAM)
    assert vm.context[0] == "Viewgram" and vm.context[2].startswith("view ")
    vm.set_tof_mode(TofMode.MEAN)
    assert vm.context[-1] == "TOF mean"


def test_error_can_be_dismissed_and_reappears_on_next_failure():
    vm = ViewerViewModel(lambda o: (_ for _ in ()).throw(OSError("bad")))
    vm.load("x")
    assert "bad" in vm.error
    vm.clear_error()
    assert vm.error is None
    seen = []
    vm.subscribe(seen.append)
    vm.load("x")
    assert any("error" in n for n in seen) and vm.error


def test_clear_error_notifies_once_and_is_harmless_without_error():
    vm = make_vm(small_demo())
    seen = []
    vm.subscribe(seen.append)
    vm.clear_error()
    assert seen == []                       # nothing changed, nothing notified


def test_format_metrics_handles_nan_stats():
    nan = float("nan")
    pairs = dict(formatting.format_metrics(SliceStats(nan, nan, nan, nan, 0.0, 0.0)))
    assert pairs["Min"] == "n/a" and pairs["Sum"] == "0" and pairs["Non-zero"] == "0.0 %"


def test_format_metrics_uses_four_significant_digits():
    pairs = dict(formatting.format_metrics(SliceStats(0.123456, 1234.5678, 1.0, 0.5, 99999.0, 0.5)))
    assert pairs["Min"] == "0.1235" and pairs["Max"] == "1235" and pairs["Non-zero"] == "50.0 %"


def test_context_chips_without_tof():
    src = non_tof_source()
    ds = ProjDataset(src)
    chips = formatting.context_chips(ds.info, Selection.initial(ds.info).with_slice_mode(SliceMode.TANGENTIAL))
    assert chips[0] == "Tangential" and chips[2].startswith("tangential") and len(chips) == 3


def test_report_error_uses_the_same_channel_and_can_be_dismissed():
    vm = make_vm(small_demo())
    seen = []
    vm.subscribe(seen.append)
    vm.report_error("export failed")
    assert vm.error == "export failed" and vm.status == "export failed" and any("error" in n for n in seen)
    vm.clear_error()
    assert vm.error is None
