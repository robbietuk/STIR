# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Gateway to the real ``stir`` SWIG module. This is the ONLY file that touches ``stir`` objects.

``stir`` is a compiled extension that is not on PyPI, so it is imported lazily. Lookup order,
see ``import_stir``:

1. an explicit directory (``--stir-path`` / ``STIR_PYTHON_PATH``), i.e. the
   ``<CMAKE_INSTALL_PREFIX>/python`` of a source build;
2. whatever ``import stir`` finds in the active environment (e.g. conda-forge ``stir``).
"""
from __future__ import annotations

import importlib
import os
import sys
import warnings
from typing import Any, Callable

import numpy as np

from .gateway import ProjDataLayout, StirNotFoundError

ENV_VAR = "STIR_PYTHON_PATH"


def _add_windows_dll_dirs(python_dir: str) -> None:
    """Python >= 3.8 on Windows ignores PATH for extension-module dependencies, so register the
    install prefix's bin/lib directories explicitly (``<prefix>/python`` -> ``<prefix>/bin``, ``lib``)."""
    add = getattr(os, "add_dll_directory", None)
    if add is None:
        return
    prefix = os.path.dirname(python_dir.rstrip("\\/"))
    for sub in ("bin", "lib"):
        d = os.path.join(prefix, sub)
        if os.path.isdir(d):
            add(d)


def _module_dir(module: Any) -> str | None:
    f = getattr(module, "__file__", None)
    return os.path.dirname(os.path.dirname(os.path.abspath(f))) if f else None


def import_stir(extra_path: str | None = None):
    """Import and return the ``stir`` module.

    * ``extra_path`` (``--stir-path``) is an explicit request: it must exist, and is searched first.
    * ``$STIR_PYTHON_PATH`` is a default: if it does not exist a warning is issued and the normal
      ``import stir`` is tried instead.
    * A ``stir`` that is already imported cannot be replaced (it is a compiled extension); if it comes from
      somewhere else than ``extra_path`` a warning says which one is used.
    """
    path = extra_path
    if path is None and os.environ.get(ENV_VAR):
        env_path = os.path.abspath(os.path.expanduser(os.environ[ENV_VAR]))
        if os.path.isdir(env_path):
            path = env_path
        else:
            warnings.warn(f"${ENV_VAR}={os.environ[ENV_VAR]!r} is not a directory; ignoring it", RuntimeWarning,
                          stacklevel=2)
    if path:
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(path):
            raise StirNotFoundError(f"STIR python path does not exist: {path}")
        loaded = sys.modules.get("stir")
        if loaded is not None:
            where = _module_dir(loaded)
            if where is not None and os.path.normcase(where) != os.path.normcase(path):
                warnings.warn(f"'stir' is already imported from {where}; it cannot be replaced by the one in "
                              f"{path} in this Python session, so the already imported one is used",
                              RuntimeWarning, stacklevel=2)
            return loaded
        if path not in sys.path:
            sys.path.insert(0, path)
        _add_windows_dll_dirs(path)
    try:
        return importlib.import_module("stir")
    except ImportError as exc:
        raise StirNotFoundError(
            "Could not import the 'stir' module.\n"
            "  * conda:        conda install -c conda-forge stir   (then run inside that environment)\n"
            "  * source build: pass --stir-path <install prefix>/python (or set STIR_PYTHON_PATH) and make\n"
            "                  sure the STIR shared libraries are on LD_LIBRARY_PATH / DYLD_LIBRARY_PATH / PATH.\n"
            f"  Original error: {exc}"
        ) from exc


def _try(fn: Callable[[], Any]) -> Any:
    """Best-effort call for optional metadata; STIR API details vary between versions."""
    try:
        return fn()
    except Exception:  # noqa: BLE001 - metadata only, never fatal
        return None


class SwigProjData:
    """Handle for one ``stir.ProjData``."""

    def __init__(self, stir_module: Any, projdata: Any, name: str):
        self._stir = stir_module
        self._pd = projdata
        self.name = name
        self._layout = self._read_layout()
        self._layout_checked = False

    def _read_layout(self) -> ProjDataLayout:
        pd = self._pd
        lo, hi = pd.get_min_segment_num(), pd.get_max_segment_num()
        return ProjDataLayout(
            min_segment=lo, max_segment=hi,
            min_view=pd.get_min_view_num(), max_view=pd.get_max_view_num(),
            min_tangential=pd.get_min_tangential_pos_num(), max_tangential=pd.get_max_tangential_pos_num(),
            min_tof=pd.get_min_tof_pos_num(), max_tof=pd.get_max_tof_pos_num(),
            axial_ranges={s: (pd.get_min_axial_pos_num(s), pd.get_max_axial_pos_num(s))
                          for s in range(lo, hi + 1)},
        )

    def layout(self) -> ProjDataLayout:
        return self._layout

    def metadata(self) -> dict[str, str]:
        pd = self._pd
        extra: dict[str, str] = {}
        # every attribute access happens inside the lambda, so a missing method is also tolerated
        info = _try(lambda: pd.get_proj_data_info())
        scanner = _try(lambda: info.get_scanner()) if info is not None else None
        if scanner is not None:
            for label, getter in (("scanner", "get_name"),
                                  ("timing resolution (ps)", "get_timing_resolution")):
                value = _try(lambda g=getter: getattr(scanner, g)())
                if value not in (None, "", 0, 0.0):
                    extra[label] = str(value)
        mash = _try(lambda: info.get_tof_mash_factor()) if info is not None else None
        if mash is not None:
            extra["TOF mashing factor"] = str(mash)
        return extra

    def _segment_by_view(self, segment: int, tof_bin: int):
        # The (segment, timing_pos) overload is declared on ProjData *and* overridden by every subclass
        # (ProjDataInMemory, ProjDataFromStream, ...). The SegmentIndices overload is an inline on ProjData
        # only, which C++ name hiding (and so SWIG) does not carry over to the subclasses; it is the fallback.
        try:
            return self._pd.get_segment_by_view(segment, tof_bin)
        except TypeError:
            return self._pd.get_segment_by_view(self._stir.SegmentIndices(segment, tof_bin))

    def read_sinogram(self, segment: int, axial: int, tof_bin: int) -> np.ndarray:
        """One sinogram (views, tangential), via ``ProjData.get_sinogram(ax_pos, segment, False, timing_pos)``."""
        sino = self._pd.get_sinogram(axial, segment, False, tof_bin)
        arr = np.asarray(sino.as_array(), dtype=np.float32)
        lay = self._layout
        expected = (lay.max_view - lay.min_view + 1, lay.max_tangential - lay.min_tangential + 1)
        if arr.shape != expected:
            raise RuntimeError(f"unexpected sinogram shape {arr.shape} for segment {segment}, axial {axial}, "
                               f"expected {expected} (views, tangential)")
        return arr

    def read_segment(self, segment: int, tof_bin: int) -> np.ndarray:
        seg = self._segment_by_view(segment, tof_bin)
        arr = np.asarray(seg.as_array(), dtype=np.float32)
        lay = self._layout
        a_lo, a_hi = lay.axial_ranges[segment]
        expected = (lay.max_view - lay.min_view + 1, a_hi - a_lo + 1,
                    lay.max_tangential - lay.min_tangential + 1)
        if arr.shape != expected:
            raise RuntimeError(
                f"unexpected array shape {arr.shape} for segment {segment}, expected {expected} "
                "(views, axial, tangential). The STIR array layout may have changed.")
        if not self._layout_checked:
            self._check_axis_order(seg, arr, a_lo)
        return arr

    def _check_axis_order(self, seg, arr: np.ndarray, first_axial: int) -> None:
        """Compare against STIR's own sinogram accessor once, to catch axis-order surprises
        that the shape check cannot see (e.g. when views == axial positions)."""
        ref = _try(lambda: np.asarray(seg.get_sinogram(first_axial).as_array(), dtype=np.float32))
        if ref is not None and ref.shape == arr[:, 0, :].shape and not np.array_equal(ref, arr[:, 0, :], equal_nan=True):
            raise RuntimeError(
                "segment.as_array() does not match segment.get_sinogram(); "
                "assumed axis order (view, axial, tangential) is wrong for this STIR version.")
        self._layout_checked = True


class SwigStirGateway:
    """``StirGateway`` backed by the real ``stir`` module (or a stand-in passed as ``stir_module``)."""

    def __init__(self, stir_module: Any = None, stir_path: str | None = None):
        self._stir = stir_module if stir_module is not None else import_stir(stir_path)

    def open(self, filename: str) -> SwigProjData:
        name = os.fspath(filename)
        try:
            pd = self._stir.ProjData.read_from_file(name)
        except RuntimeError as exc:  # STIR reports I/O problems as RuntimeError
            raise OSError(f"STIR could not read '{name}': {exc}") from exc
        return SwigProjData(self._stir, pd, name)

    def wrap(self, projdata: Any) -> SwigProjData:
        return SwigProjData(self._stir, projdata, "ProjData object")
