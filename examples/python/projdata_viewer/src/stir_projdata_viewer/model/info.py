# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Description of projection data and the interface every data source implements.

The model never talks to STIR directly: it only needs a ``ProjDataSource``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class ProjDataInfo:
    """Index ranges (inclusive) and descriptive metadata of a projection data set.

    Axial ranges depend on the segment, all other ranges do not.
    TOF bin numbers are whatever the source uses (STIR may use negative values);
    non-TOF data has a single bin, ``min_tof == max_tof``.
    """

    name: str
    min_segment: int
    max_segment: int
    min_view: int
    max_view: int
    min_tangential: int
    max_tangential: int
    axial_ranges: dict[int, tuple[int, int]]
    min_tof: int = 0
    max_tof: int = 0
    # free-form (label, value) pairs shown in the info panel, e.g. scanner name
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def segments(self) -> range:
        return range(self.min_segment, self.max_segment + 1)

    @property
    def tof_bins(self) -> range:
        return range(self.min_tof, self.max_tof + 1)

    @property
    def num_segments(self) -> int:
        return self.max_segment - self.min_segment + 1

    @property
    def num_views(self) -> int:
        return self.max_view - self.min_view + 1

    @property
    def num_tangential(self) -> int:
        return self.max_tangential - self.min_tangential + 1

    @property
    def num_tof_bins(self) -> int:
        return self.max_tof - self.min_tof + 1

    @property
    def is_tof(self) -> bool:
        return self.num_tof_bins > 1

    def axial_range(self, segment: int) -> tuple[int, int]:
        return self.axial_ranges[segment]

    def num_axial(self, segment: int) -> int:
        lo, hi = self.axial_ranges[segment]
        return hi - lo + 1

    def expected_shape(self, segment: int) -> tuple[int, int, int]:
        """Shape of the array returned by ``get_segment``: (views, axial, tangential)."""
        return (self.num_views, self.num_axial(segment), self.num_tangential)

    @property
    def total_bins(self) -> int:
        return sum(
            self.num_views * self.num_axial(s) * self.num_tangential * self.num_tof_bins
            for s in self.segments
        )


@runtime_checkable
class ProjDataSource(Protocol):
    """What the viewer needs from a data provider."""

    info: ProjDataInfo

    def get_segment(self, segment: int, tof_bin: int) -> np.ndarray:
        """Return one segment for one TOF bin as float32, shape ``(views, axial, tangential)``.

        Index 0 along each axis corresponds to the ``min_*`` value in ``info``.

        Sources may also offer ``get_sinogram(segment, axial, tof_bin)`` returning one sinogram
        ``(views, tangential)``. It is optional (looked up with ``getattr``); when present the per-LOR TOF
        profile reads one sinogram per TOF bin instead of whole segments.
        """
        ...
