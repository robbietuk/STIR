# SPDX-License-Identifier: Apache-2.0
"""One contract, run against every ``StirProjDataHandle`` implementation we can build here.

The real-STIR variant lives in test_real_stir_integration.py and reuses ``check_handle_contract``.
"""
import numpy as np
import pytest

from fakes import FakeHandle, FakeProjData, make_fake_stir, small_demo
from stir_projdata_viewer.stir_interface import ProjDataLayout, StirProjDataHandle
from stir_projdata_viewer.stir_interface.swig_gateway import SwigStirGateway


def check_handle_contract(h: StirProjDataHandle) -> None:
    assert isinstance(h, StirProjDataHandle)
    assert isinstance(h.name, str) and h.name
    lay = h.layout()
    assert isinstance(lay, ProjDataLayout)
    assert lay.min_segment <= lay.max_segment and lay.min_view <= lay.max_view
    assert lay.min_tangential <= lay.max_tangential and lay.min_tof <= lay.max_tof
    assert set(lay.axial_ranges) == set(range(lay.min_segment, lay.max_segment + 1))
    assert all(lo <= hi for lo, hi in lay.axial_ranges.values())
    meta = h.metadata()
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in meta.items())

    n_view = lay.max_view - lay.min_view + 1
    n_tang = lay.max_tangential - lay.min_tangential + 1
    for seg, (lo, hi) in lay.axial_ranges.items():
        for tof in (lay.min_tof, lay.max_tof):
            a = h.read_segment(seg, tof)
            assert a.dtype == np.float32
            assert a.shape == (n_view, hi - lo + 1, n_tang)
            assert np.isfinite(a).all()
            np.testing.assert_array_equal(a, h.read_segment(seg, tof))      # repeatable
    with pytest.raises(Exception):                                          # noqa: B017 - any failure is fine
        h.read_segment(lay.max_segment + 5, lay.min_tof)


def _fake_handle():
    return FakeHandle(small_demo(), meta={"scanner": "demo"})


def _swig_over_fake_stir():
    pd = FakeProjData()
    return SwigStirGateway(stir_module=make_fake_stir(pd)).wrap(pd)


@pytest.mark.parametrize("make", [_fake_handle, _swig_over_fake_stir], ids=["fake-handle", "swig-gateway-fake-stir"])
def test_handle_contract(make):
    check_handle_contract(make())
