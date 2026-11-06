# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""MODEL layer: pure domain logic. Imports only the standard library and numpy: no Qt, no STIR,
no view-model code (enforced by tests/test_architecture.py)."""
from .dataset import ProjDataset
from .info import ProjDataInfo, ProjDataSource
from .selection import DIMENSIONS, Selection, SliceMode, TofMode
from .slices import SliceImage, SliceStats, compute_stats, finite_range

__all__ = ["DIMENSIONS", "ProjDataInfo", "ProjDataSource", "ProjDataset", "Selection",
           "SliceImage", "SliceMode", "SliceStats", "TofMode", "compute_stats", "finite_range"]
