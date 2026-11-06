# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""``ProjDataset``: turns a ``ProjDataSource`` plus a ``Selection`` into slices.

Holds no UI state; the same dataset can answer any number of different selections.
"""
from __future__ import annotations

import numpy as np

from .cache import LRUCache
from .info import ProjDataInfo, ProjDataSource
from .selection import Selection, SliceMode, TofMode
from .slices import SliceImage, SliceStats, compute_stats, finite_range


class ProjDataset:
    def __init__(self, source: ProjDataSource, cache_segments: int = 8):
        self.source = source
        self.info: ProjDataInfo = source.info
        # (segment, tof_bin) -> array. Big enough for all bins of one segment, so TOF playback and the
        # per-LOR TOF profile never reload. TOF reductions are cached separately.
        self._raw: LRUCache[np.ndarray] = LRUCache(max(cache_segments, self.info.num_tof_bins + 1))
        self._reduced: LRUCache[np.ndarray] = LRUCache(cache_segments)
        self._global: dict[tuple, tuple[float, float]] = {}

    # ---- raw and reduced segments ---------------------------------------------
    def _raw_segment(self, segment: int, tof_bin: int) -> np.ndarray:
        key = (segment, tof_bin)
        arr = self._raw.get(key)
        if arr is None:
            arr = self.source.get_segment(segment, tof_bin)
            expected = self.info.expected_shape(segment)
            if arr.shape != expected:
                raise ValueError(f"source returned shape {arr.shape} for segment {segment}, expected {expected}")
            self._raw.put(key, arr)
        return arr

    def segment_array(self, segment: int, tof_mode: TofMode = TofMode.BIN, tof_bin: int | None = None) -> np.ndarray:
        """One segment, shape (views, axial, tangential), after TOF selection or reduction."""
        if tof_mode is TofMode.BIN:
            return self._raw_segment(segment, self.info.min_tof if tof_bin is None else tof_bin)
        key = (segment, tof_mode)
        cached = self._reduced.get(key)
        if cached is not None:
            return cached
        # accumulate bin by bin so only one extra array is alive at a time
        acc = None
        for k in self.info.tof_bins:
            part = self._raw_segment(segment, k)
            if acc is None:
                acc = part.astype(np.float32 if tof_mode is TofMode.MAX else np.float64, copy=True)
            elif tof_mode is TofMode.MAX:
                np.maximum(acc, part, out=acc)
            else:
                acc += part
        assert acc is not None
        if tof_mode is TofMode.MEAN:
            acc /= self.info.num_tof_bins
        result = acc.astype(np.float32)
        self._reduced.put(key, result)
        return result

    # ---- slices -----------------------------------------------------------------
    def slice(self, sel: Selection) -> SliceImage:
        if not sel.is_valid_for(self.info):
            raise ValueError(f"selection {sel} is outside the data ranges")
        arr = self.segment_array(sel.segment, sel.tof_mode, sel.tof)
        i = self.info
        a_lo, _ = i.axial_range(sel.segment)
        tof_txt = self._tof_title(sel)
        if sel.slice_mode is SliceMode.SINOGRAM:
            return SliceImage(arr[:, sel.axial - a_lo, :],
                              f"Sinogram  segment {sel.segment}, axial {sel.axial}{tof_txt}",
                              "view", "tangential", i.min_view, i.min_tangential)
        if sel.slice_mode is SliceMode.VIEWGRAM:
            return SliceImage(arr[sel.view - i.min_view, :, :],
                              f"Viewgram  segment {sel.segment}, view {sel.view}{tof_txt}",
                              "axial", "tangential", a_lo, i.min_tangential)
        return SliceImage(arr[:, :, sel.tangential - i.min_tangential],
                          f"Tangential slice  segment {sel.segment}, tangential {sel.tangential}{tof_txt}",
                          "view", "axial", i.min_view, a_lo)

    def _tof_title(self, sel: Selection) -> str:
        if not self.info.is_tof:
            return ""
        if sel.tof_mode is TofMode.BIN:
            return f", TOF bin {sel.tof}"
        return f", {sel.tof_mode.value.lower()}"

    def stats(self, image: SliceImage) -> SliceStats:
        return compute_stats(image.data)

    def global_range(self, sel: Selection) -> tuple[float, float]:
        """(min, max) of the finite values over all segments for the TOF selection of ``sel``.
        Loads everything once; (0, 1) if there are no finite values."""
        key = (sel.tof_mode, sel.tof if sel.tof_mode is TofMode.BIN else None)
        if key not in self._global:
            lo, hi = np.inf, -np.inf
            for s in self.info.segments:
                r = finite_range(self.segment_array(s, sel.tof_mode, sel.tof))
                if r is not None:
                    lo, hi = min(lo, r[0]), max(hi, r[1])
            self._global[key] = (lo, hi) if lo <= hi else (0.0, 1.0)
        return self._global[key]

    def tof_profile(self, segment: int, view: int, axial: int, tangential: int) -> np.ndarray:
        """Counts versus TOF bin for one LOR; length = number of TOF bins."""
        i = self.info
        if segment not in i.axial_ranges:
            raise ValueError(f"segment {segment} is outside {i.min_segment}..{i.max_segment}")
        a_lo, a_hi = i.axial_range(segment)
        # explicit checks: numpy would silently wrap negative indices around
        for name, value, lo, hi in (("view", view, i.min_view, i.max_view), ("axial", axial, a_lo, a_hi),
                                    ("tangential", tangential, i.min_tangential, i.max_tangential)):
            if not lo <= value <= hi:
                raise ValueError(f"{name} {value} is outside {lo}..{hi}")
        return np.array([
            self._raw_segment(segment, k)[view - i.min_view, axial - a_lo, tangential - i.min_tangential]
            for k in i.tof_bins
        ], dtype=np.float64)
