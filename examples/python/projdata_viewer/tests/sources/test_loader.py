# SPDX-License-Identifier: Apache-2.0
import sys

import numpy as np
import pytest

from fakes import small_demo
from stir_projdata_viewer.sources.loader import make_source
from stir_projdata_viewer.stir_interface import StirNotFoundError


def test_npy_path(tmp_path):
    np.save(tmp_path / "x.npy", np.zeros((4, 3, 5), dtype=np.float32))
    assert make_source(str(tmp_path / "x.npy")).info.num_tangential == 5


def test_suffix_check_is_case_insensitive(tmp_path):
    np.save(tmp_path / "x.npy", np.zeros((4, 3, 5), dtype=np.float32))
    (tmp_path / "x.npy").rename(tmp_path / "X.NPY")
    assert make_source(tmp_path / "X.NPY").info.num_views == 4


def test_existing_source_passes_through():
    src = small_demo()
    assert make_source(src) is src


def test_hs_without_stir_gives_helpful_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "stir", None)           # makes `import stir` fail
    monkeypatch.delenv("STIR_PYTHON_PATH", raising=False)
    with pytest.raises(StirNotFoundError, match="--stir-path"):
        make_source("some.hs")


def test_arbitrary_object_is_treated_as_stir_projdata(monkeypatch):
    monkeypatch.setitem(sys.modules, "stir", None)
    with pytest.raises(StirNotFoundError):
        make_source(object())
