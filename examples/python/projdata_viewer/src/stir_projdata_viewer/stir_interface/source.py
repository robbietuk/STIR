# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Adapter: any ``StirProjDataHandle`` -> the model's ``ProjDataSource``."""
from __future__ import annotations

import os
from typing import Any

import numpy as np

from ..model.info import ProjDataInfo
from .gateway import StirGateway, StirProjDataHandle


class StirProjDataSource:
    def __init__(self, handle: StirProjDataHandle):
        self._handle = handle
        lay = handle.layout()
        self.info = ProjDataInfo(
            name=handle.name,
            min_segment=lay.min_segment, max_segment=lay.max_segment,
            min_view=lay.min_view, max_view=lay.max_view,
            min_tangential=lay.min_tangential, max_tangential=lay.max_tangential,
            axial_ranges=dict(lay.axial_ranges),
            min_tof=lay.min_tof, max_tof=lay.max_tof,
            extra=dict(handle.metadata()),
        )

    def get_segment(self, segment: int, tof_bin: int) -> np.ndarray:
        return self._handle.read_segment(segment, tof_bin)


def open_stir_source(obj: Any, stir_path: str | None = None, gateway: StirGateway | None = None) -> StirProjDataSource:
    """``obj`` is a filename or a ``stir.ProjData``. ``gateway`` defaults to the real SWIG one."""
    if gateway is None:
        from .swig_gateway import SwigStirGateway  # imported here so the module can be loaded without stir
        gateway = SwigStirGateway(stir_path=stir_path)
    handle = gateway.open(os.fspath(obj)) if isinstance(obj, (str, os.PathLike)) else gateway.wrap(obj)
    return StirProjDataSource(handle)
