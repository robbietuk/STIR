# SPDX-License-Identifier: Apache-2.0
"""Shared test doubles. None of these need Qt or STIR."""
from __future__ import annotations

import types

import numpy as np

from stir_projdata_viewer.model import ProjDataInfo
from stir_projdata_viewer.sources import ArraySource, make_demo_source
from stir_projdata_viewer.stir_interface import ProjDataLayout


def small_demo(**kw) -> ArraySource:
    args = dict(num_segments=3, num_views=12, num_tangential=15, axial_base=8, tof_bins=5)
    args.update(kw)
    return make_demo_source(**args)


def non_tof_source(seed: int = 1) -> ArraySource:
    rng = np.random.default_rng(seed)
    return ArraySource({-1: rng.random((6, 3, 7)), 0: rng.random((6, 4, 7)), 1: rng.random((6, 3, 7))},
                       name="non-tof")


class CountingSource:
    """Wraps a source and counts ``get_segment`` calls; can be told to fail."""

    def __init__(self, inner):
        self.inner, self.info, self.reads, self.fail = inner, inner.info, 0, False

    def get_segment(self, segment, tof_bin):
        self.reads += 1
        if self.fail:
            raise OSError("disk went away")
        return self.inner.get_segment(segment, tof_bin)


# ---- gateway-level fakes ---------------------------------------------------------------
def layout_of(info: ProjDataInfo) -> ProjDataLayout:
    return ProjDataLayout(info.min_segment, info.max_segment, info.min_view, info.max_view,
                          info.min_tangential, info.max_tangential, info.min_tof, info.max_tof,
                          dict(info.axial_ranges))


class FakeHandle:
    """A ``StirProjDataHandle`` backed by an ArraySource."""

    def __init__(self, source: ArraySource, name: str = "fake.hs", meta: dict | None = None):
        self._src, self.name, self._meta, self.reads = source, name, meta or {}, 0

    def layout(self) -> ProjDataLayout:
        return layout_of(self._src.info)

    def metadata(self) -> dict[str, str]:
        return dict(self._meta)

    def read_segment(self, segment, tof_bin):
        self.reads += 1
        return self._src.get_segment(segment, tof_bin)


class FakeGateway:
    def __init__(self, source: ArraySource | None = None):
        self.source = source or small_demo()
        self.opened: list[str] = []
        self.wrapped: list[object] = []

    def open(self, filename):
        if "missing" in filename:
            raise OSError(f"cannot read {filename}")
        self.opened.append(filename)
        return FakeHandle(self.source, name=filename)

    def wrap(self, projdata):
        self.wrapped.append(projdata)
        return FakeHandle(self.source, name="wrapped")


# ---- a fake `stir` module, mimicking the SWIG API surface the real gateway calls ----------
class FakeArray:
    def __init__(self, a):
        self._a = a

    def as_array(self):
        return self._a


class FakeSegment(FakeArray):
    """``as_array`` returns ``a``; ``get_sinogram`` is served from ``truth`` (view, axial, tang)."""

    def __init__(self, a, truth=None):
        super().__init__(a)
        self._truth = a if truth is None else truth

    def get_sinogram(self, axial):
        return FakeArray(self._truth[:, axial, :])


class FakeProjData:
    """Segments -1..1, 4 views, 5 tangential (-2..2), TOF bins -1..1; axial 3 + (1 - |s|)."""

    def __init__(self, transpose: bool = False):
        rng = np.random.default_rng(0)
        self.data = {(s, t): rng.random((4, 3 + (1 - abs(s)), 5)).astype(np.float32)
                     for s in (-1, 0, 1) for t in (-1, 0, 1)}
        self.transpose = transpose

    get_min_segment_num = lambda self: -1          # noqa: E731
    get_max_segment_num = lambda self: 1           # noqa: E731
    get_min_view_num = lambda self: 0              # noqa: E731
    get_max_view_num = lambda self: 3              # noqa: E731
    get_min_tangential_pos_num = lambda self: -2   # noqa: E731
    get_max_tangential_pos_num = lambda self: 2    # noqa: E731
    get_min_tof_pos_num = lambda self: -1          # noqa: E731
    get_max_tof_pos_num = lambda self: 1           # noqa: E731
    get_min_axial_pos_num = lambda self, s: 0      # noqa: E731
    get_max_axial_pos_num = lambda self, s: 3 + (1 - abs(s)) - 1  # noqa: E731

    def get_segment_by_view(self, idx):
        a = self.data[(idx.seg, idx.tof)]
        return FakeSegment(a.transpose(1, 0, 2).copy() if self.transpose else a, truth=a)


def make_fake_stir(pd: FakeProjData):
    class SegmentIndices:
        def __init__(self, seg, tof):
            self.seg, self.tof = seg, tof

    class ProjData:
        @staticmethod
        def read_from_file(name):
            if name == "missing.hs":
                raise RuntimeError("no such file")
            return pd

    return types.SimpleNamespace(SegmentIndices=SegmentIndices, ProjData=ProjData)
