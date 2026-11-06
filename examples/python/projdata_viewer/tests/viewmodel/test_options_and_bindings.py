# SPDX-License-Identifier: Apache-2.0
import pytest

from stir_projdata_viewer.model import SliceMode, TofMode
from stir_projdata_viewer.viewmodel import (COLORMAP_OPTIONS, COLORMAPS, LEVEL_MODE_OPTIONS, SLICE_MODE_OPTIONS,
                                            TOF_MODE_OPTIONS, BindingRegistry, ChoiceOptions, LevelMode,
                                            ViewerViewModel, observed_names)
from stir_projdata_viewer.viewmodel.observable import ObservableObject, Observed


# ---- ChoiceOptions ------------------------------------------------------------------
def test_option_sets_cover_their_enums_in_order():
    assert SLICE_MODE_OPTIONS.values == tuple(SliceMode) and len(SLICE_MODE_OPTIONS.labels) == 3
    assert TOF_MODE_OPTIONS.values == tuple(TofMode)
    assert LEVEL_MODE_OPTIONS.values == tuple(LevelMode)
    assert COLORMAP_OPTIONS.values == COLORMAPS


def test_round_trip_between_index_value_and_label():
    for opts in (SLICE_MODE_OPTIONS, TOF_MODE_OPTIONS, LEVEL_MODE_OPTIONS, COLORMAP_OPTIONS):
        for i, v in enumerate(opts.values):
            assert opts.index_of(v) == i and opts.value_at(i) is v and opts.label_of(v) == opts.labels[i]


def test_lookup_errors_are_explicit():
    with pytest.raises(KeyError):
        SLICE_MODE_OPTIONS.index_of("nope")
    for bad in (-1, 3):
        with pytest.raises(IndexError):
            SLICE_MODE_OPTIONS.value_at(bad)


def test_invalid_option_sets_are_rejected():
    with pytest.raises(ValueError):
        ChoiceOptions.from_values([])
    with pytest.raises(ValueError):
        ChoiceOptions.from_values([1, 1])
    with pytest.raises(ValueError):
        ChoiceOptions.from_values([1, 2], ["a"])


def test_from_enum_uses_custom_labels_and_falls_back_to_values():
    opts = ChoiceOptions.from_enum(TofMode, {TofMode.BIN: "B"})
    assert opts.labels[0] == "B" and opts.labels[1] == TofMode.SUM.value


# ---- observed_names / BindingRegistry ---------------------------------------------------
class Tiny(ObservableObject):
    a = Observed(0)
    b = Observed(0)
    c = Observed(0)


def test_observed_names_in_definition_order_and_inherited():
    class Sub(Tiny):
        d = Observed(0)
    assert observed_names(Tiny) == ("a", "b", "c") and observed_names(Sub()) == ("a", "b", "c", "d")


def test_view_model_exposes_the_new_properties():
    names = observed_names(ViewerViewModel)
    assert {"metrics", "context", "error", "image"} <= set(names)


def test_binding_runs_only_when_one_of_its_names_changed():
    vm, calls = Tiny(), []
    reg = BindingRegistry(vm)
    reg.bind("a", lambda: calls.append("a"))
    reg.bind(("b", "c"), lambda: calls.append("bc"))
    reg.start(initial_paint=False)
    vm.a = 1
    assert calls == ["a"]
    vm.c = 2
    assert calls == ["a", "bc"]


def test_binding_runs_once_per_transaction_even_if_several_names_changed():
    vm, calls = Tiny(), []
    reg = BindingRegistry(vm)
    reg.bind(("a", "b"), lambda: calls.append(1))
    reg.start(initial_paint=False)
    with vm.transaction():
        vm.a, vm.b = 1, 1
    assert calls == [1]


def test_initial_paint_runs_every_binding_once():
    vm, calls = Tiny(), []
    reg = BindingRegistry(vm)
    reg.bind("a", lambda: calls.append("a"))
    reg.bind("b", lambda: calls.append("b"))
    reg.start()
    assert calls == ["a", "b"]


def test_bindings_run_in_registration_order():
    vm, calls = Tiny(), []
    reg = BindingRegistry(vm)
    reg.bind("a", lambda: calls.append(1))
    reg.bind("a", lambda: calls.append(2))
    reg.start(initial_paint=False)
    vm.a = 5
    assert calls == [1, 2]


def test_unknown_or_empty_binding_is_rejected():
    reg = BindingRegistry(Tiny())
    with pytest.raises(KeyError):
        reg.bind("zzz", lambda: None)
    with pytest.raises(ValueError):
        reg.bind((), lambda: None)


def test_stop_unsubscribes_and_start_is_idempotent():
    vm, calls = Tiny(), []
    reg = BindingRegistry(vm)
    reg.bind("a", lambda: calls.append(1))
    reg.start(initial_paint=False)
    reg.start(initial_paint=False)
    vm.a = 1
    assert calls == [1]
    reg.stop()
    vm.a = 2
    assert calls == [1]


def test_unbound_reports_missing_properties():
    reg = BindingRegistry(Tiny())
    reg.bind("a", lambda: None)
    assert reg.unbound() == frozenset({"b", "c"})
