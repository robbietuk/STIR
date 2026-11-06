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


DEFAULT_CACHE_BYTES = 1 << 30          # 1 GiB for raw segments, the same again at most for reductions


class ProjDataset:
    def __init__(self, source: ProjDataSource, cache_segments: int = 8, cache_bytes: int | None = DEFAULT_CACHE_BYTES):
        self.source = source
        self.info: ProjDataInfo = source.info
        # (segment, tof_bin) -> array. Room for all bins of one segment (so TOF playback does not reload)
        # unless that exceeds ``cache_bytes``; then the least recently used bins are dropped and re-read.
        self._raw: LRUCache[np.ndarray] = LRUCache(max(cache_segments, self.info.num_tof_bins + 1), cache_bytes)
        self._reduced: LRUCache[np.ndarray] = LRUCache(cache_segments, cache_bytes)
        # (segment, axial, tof_bin) -> sinogram (views, tangential), for cheap per-LOR TOF profiles
        self._sinograms: LRUCache[np.ndarray] = LRUCache(max(64, 4 * self.info.num_tof_bins))
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
        """(min, max) of the finite values of the whole data set as displayed in ``sel.tof_mode``:
        for single TOF bins over all segments *and all TOF bins* (so the colour scale stays put while
        stepping or playing through bins); for Sum/Mean/Max over all reduced segments.
        Reads everything once and caches the result; (0, 1) if there are no finite values."""
        key = sel.tof_mode
        if key not in self._global:
            lo, hi = np.inf, -np.inf
            for s in self.info.segments:
                parts = ([self.segment_array(s, TofMode.BIN, k) for k in self.info.tof_bins]
                         if sel.tof_mode is TofMode.BIN else [self.segment_array(s, sel.tof_mode)])
                for part in parts:
                    r = finite_range(part)
                    if r is not None:
                        lo, hi = min(lo, r[0]), max(hi, r[1])
            self._global[key] = (lo, hi) if lo <= hi else (0.0, 1.0)
        return self._global[key]

    def _sinogram(self, segment: int, axial: int, tof_bin: int) -> np.ndarray:
        """One sinogram (views, tangential). Served from a cached segment if there is one, else read on its
        own when the source can (``get_sinogram``), which is much cheaper than a whole segment."""
        a_lo, _ = self.info.axial_range(segment)
        raw = self._raw.get((segment, tof_bin))
        if raw is not None:
            return raw[:, axial - a_lo, :]
        reader = getattr(self.source, "get_sinogram", None)
        if reader is None:
            return self._raw_segment(segment, tof_bin)[:, axial - a_lo, :]
        key = (segment, axial, tof_bin)
        sino = self._sinograms.get(key)
        if sino is None:
            sino = np.asarray(reader(segment, axial, tof_bin), dtype=np.float32)
            expected = (self.info.num_views, self.info.num_tangential)
            if sino.shape != expected:
                raise ValueError(f"source returned sinogram shape {sino.shape} for segment {segment}, "
                                 f"axial {axial}, expected {expected}")
            self._sinograms.put(key, sino)
        return sino

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
            self._sinogram(segment, axial, k)[view - i.min_view, tangential - i.min_tangential]
            for k in i.tof_bins
        ], dtype=np.float64)
