# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Turn whatever the user hands us (path, STIR object, source) into a ``ProjDataSource``."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..model.info import ProjDataSource
from .array_source import ArraySource


def make_source(obj: Any, stir_path: str | None = None) -> ProjDataSource:
    """``obj`` may be a path (``.npy``/``.npz``, or a STIR file such as ``.hs``), an existing
    ``ProjDataSource``, or a ``stir.ProjData`` object."""
    if isinstance(obj, (str, os.PathLike)) and Path(obj).suffix.lower() in (".npy", ".npz"):
        return ArraySource.from_file(obj)
    if not isinstance(obj, (str, os.PathLike)) and hasattr(obj, "info") and hasattr(obj, "get_segment"):
        return obj
    if isinstance(obj, (str, os.PathLike)) and not Path(obj).exists():
        # checked here so a typo is reported as such, not as a missing STIR installation
        raise FileNotFoundError(f"No such file: {os.fspath(obj)}")
    from ..stir_interface import open_stir_source  # lazy: keeps non-STIR use free of that layer
    return open_stir_source(obj, stir_path=stir_path)
