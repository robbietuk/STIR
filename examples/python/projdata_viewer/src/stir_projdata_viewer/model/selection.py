# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""What the user has selected, as an immutable value. All index clamping rules live here."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .info import ProjDataInfo

DIMENSIONS = ("segment", "axial", "view", "tangential", "tof")


class SliceMode(Enum):
    SINOGRAM = "Sinogram"            # fixed axial position  -> image (view x tangential)
    VIEWGRAM = "Viewgram"            # fixed view            -> image (axial x tangential)
    TANGENTIAL = "Tangential slice"  # fixed tangential pos. -> image (view x axial)

    @property
    def fixed_dimension(self) -> str:
        return {"SINOGRAM": "axial", "VIEWGRAM": "view", "TANGENTIAL": "tangential"}[self.name]


class TofMode(Enum):
    BIN = "Single TOF bin"
    SUM = "Sum over TOF bins"
    MEAN = "Mean over TOF bins"
    MAX = "Max over TOF bins"


@dataclass(frozen=True)
class Selection:
    """Indices are *bin numbers* in the source's own numbering, not 0-based positions.

    Instances are immutable; every ``with_*`` method returns a new, clamped selection.
    """

    segment: int
    axial: int
    view: int
    tangential: int
    tof: int
    slice_mode: SliceMode = SliceMode.SINOGRAM
    tof_mode: TofMode = TofMode.BIN

    @classmethod
    def initial(cls, info: ProjDataInfo) -> "Selection":
        """Segment 0 (if present), central axial/view/TOF bin, tangential 0 (if present)."""
        segment = 0 if info.min_segment <= 0 <= info.max_segment else info.min_segment
        a_lo, a_hi = info.axial_range(segment)
        tangential = 0 if info.min_tangential <= 0 <= info.max_tangential else info.min_tangential
        return cls(segment=segment,
                   axial=(a_lo + a_hi) // 2,
                   view=(info.min_view + info.max_view) // 2,
                   tangential=tangential,
                   tof=(info.min_tof + info.max_tof) // 2)

    def get(self, dim: str) -> int:
        if dim not in DIMENSIONS:
            raise KeyError(dim)
        return getattr(self, dim)

    @property
    def active_dimension(self) -> str:
        """The dimension that picks the slice in the current slice mode."""
        return self.slice_mode.fixed_dimension

    def range(self, info: ProjDataInfo, dim: str) -> tuple[int, int]:
        """Inclusive valid range of ``dim``; the axial range depends on the selected segment."""
        if dim == "segment":
            return info.min_segment, info.max_segment
        if dim == "axial":
            return info.axial_range(self.segment)
        if dim == "view":
            return info.min_view, info.max_view
        if dim == "tangential":
            return info.min_tangential, info.max_tangential
        if dim == "tof":
            return info.min_tof, info.max_tof
        raise KeyError(dim)

    def with_value(self, info: ProjDataInfo, dim: str, value: int) -> "Selection":
        """Set ``dim`` to ``value`` clamped into range; changing segment re-clamps axial."""
        lo, hi = self.range(info, dim)
        new = replace(self, **{dim: int(min(max(value, lo), hi))})
        if dim == "segment":
            a_lo, a_hi = new.range(info, "axial")
            new = replace(new, axial=min(max(new.axial, a_lo), a_hi))
        return new

    def with_slice_mode(self, mode: SliceMode) -> "Selection":
        return replace(self, slice_mode=mode)

    def with_tof_mode(self, mode: TofMode) -> "Selection":
        return replace(self, tof_mode=mode)

    def step_tof(self, info: ProjDataInfo, delta: int = 1) -> "Selection":
        """Advance the TOF bin by ``delta`` with wrap-around (for playback)."""
        lo, hi = info.min_tof, info.max_tof
        return replace(self, tof=lo + (self.tof - lo + delta) % (hi - lo + 1))

    def is_valid_for(self, info: ProjDataInfo) -> bool:
        return all(lo <= self.get(d) <= hi for d in DIMENSIONS for lo, hi in [self.range(info, d)])
