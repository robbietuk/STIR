# SPDX-License-Identifier: Apache-2.0
import numpy as np
import pytest

from stir_projdata_viewer.model import SliceImage, compute_stats
from stir_projdata_viewer.model.cache import LRUCache


def image(rows=4, cols=6, row0=0, col0=-3):
    return SliceImage(np.arange(rows * cols, dtype=np.float32).reshape(rows, cols), "t", "view", "tangential",
                      row0, col0)


def test_compute_stats_known_values():
    s = compute_stats(np.array([[0.0, 2.0], [0.0, 4.0]]))
    assert (s.minimum, s.maximum, s.mean, s.total, s.nonzero_fraction) == (0.0, 4.0, 1.5, 6.0, 0.5)
    assert s.std == pytest.approx(np.std([0, 2, 0, 4]))


def test_compute_stats_rejects_empty_and_uses_float64():
    with pytest.raises(ValueError):
        compute_stats(np.empty((0, 3)))
    big = np.full((1000, 1000), 16777217.0, dtype=np.float32)   # not representable summing in float32
    assert compute_stats(big).total == pytest.approx(big.size * float(big[0, 0]))


def test_value_at_bounds():
    img = image()
    assert img.value_at(0, 0) == 0.0 and img.value_at(3, 5) == 23.0
    for r, c in [(-1, 0), (0, -1), (4, 0), (0, 6)]:
        assert img.value_at(r, c) is None


def test_pixel_from_axes_roundtrips_pixel_centres():
    img = image(row0=2, col0=-3)
    for row in range(4):
        for col in range(6):
            x, y = img.col_origin + col, img.row_origin + row      # integer axis value = pixel centre
            assert img.pixel_from_axes(x, y) == (row, col)
            assert img.pixel_from_axes(x + 0.49, y - 0.49) == (row, col)    # anywhere inside the pixel


def test_pixel_from_axes_outside_is_outside():
    img = image()
    row, col = img.pixel_from_axes(-100, -100)
    assert img.value_at(row, col) is None


def test_lru_evicts_least_recently_used():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1            # touch a, so b is now oldest
    c.put("c", 3)
    assert "b" not in c and "a" in c and "c" in c and len(c) == 2
    assert c.get("missing") is None
    c.clear()
    assert len(c) == 0


def test_lru_rejects_zero_size():
    with pytest.raises(ValueError):
        LRUCache(0)


def test_stats_ignore_non_finite_values_without_warnings():
    import warnings
    d = np.array([[1.0, np.nan], [np.inf, 3.0]])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        s = compute_stats(d)
    assert (s.minimum, s.maximum, s.mean, s.total) == (1.0, 3.0, 2.0, 4.0) and s.nonzero_fraction == 0.5
    allbad = compute_stats(np.full((2, 2), np.nan))
    assert np.isnan(allbad.minimum) and allbad.total == 0.0


def test_finite_range():
    from stir_projdata_viewer.model import finite_range
    assert finite_range(np.array([np.nan, 2.0, np.inf, -1.0])) == (-1.0, 2.0)
    assert finite_range(np.array([np.nan, np.inf])) is None
