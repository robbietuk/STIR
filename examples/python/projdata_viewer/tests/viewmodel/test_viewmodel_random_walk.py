# SPDX-License-Identifier: Apache-2.0
"""Seeded random command sequences: invariants must hold after every single command."""
import random

import pytest

from fakes import non_tof_source, small_demo
from stir_projdata_viewer.model import DIMENSIONS, SliceMode, TofMode
from stir_projdata_viewer.viewmodel import LevelMode, ViewerViewModel


def random_command(vm, rng):
    dim = rng.choice(DIMENSIONS)
    return rng.choice([
        lambda: vm.set_value(dim, rng.randint(-50, 50)),
        lambda: vm.step(dim, rng.choice([-3, -1, 1, 3])),
        lambda: vm.step_active(rng.choice([-1, 1])),
        lambda: vm.set_slice_mode(rng.choice(list(SliceMode))),
        lambda: vm.set_tof_mode(rng.choice(list(TofMode))),
        lambda: vm.set_playing(rng.random() < 0.5),
        lambda: vm.toggle_play(),
        lambda: vm.tick(),
        lambda: vm.set_fps(rng.randint(-5, 60)),
        lambda: vm.set_level_mode(rng.choice(list(LevelMode))),
        lambda: vm.set_log_display(rng.random() < 0.5),
        lambda: vm.set_manual_levels(rng.uniform(-1, 3), rng.uniform(-1, 3)),
        lambda: vm.hover_at(rng.uniform(-20, 20), rng.uniform(-5, 20)),
        lambda: vm.hover_leave(),
    ])


def check_invariants(vm):
    sel, info = vm.selection, vm.dataset.info
    assert sel.is_valid_for(info)
    for d in vm.dimensions:
        assert d.lo <= d.value <= d.hi and d.value == sel.get(d.name)
        assert not d.enabled or d.hi > d.lo
    assert sum(1 for d in vm.dimensions if d.enabled and d.name not in ("segment", "tof")) <= 1
    assert vm.can_play == (info.is_tof and sel.tof_mode is TofMode.BIN)
    assert not vm.playing or vm.can_play
    assert (vm.tof_marker is not None) == vm.can_play
    assert 1 <= vm.fps <= 30
    lo, hi = vm.levels
    assert hi > lo
    assert vm.image.data.shape == (int(vm.image.height), int(vm.image.width))
    assert vm.image.data.dtype.name == "float32" and vm.image.data.size > 0
    assert vm.slice_mode is sel.slice_mode and vm.tof_mode is sel.tof_mode
    assert vm.error is None


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("source", [small_demo, non_tof_source], ids=["tof", "non-tof"])
def test_invariants_hold_under_random_commands(seed, source):
    rng = random.Random(seed)
    vm = ViewerViewModel(lambda o: o)
    vm.load(source())
    for _ in range(250):
        random_command(vm, rng)()
        check_invariants(vm)
