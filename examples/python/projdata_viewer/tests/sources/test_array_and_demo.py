# SPDX-License-Identifier: Apache-2.0
import numpy as np
import pytest

from fakes import small_demo
from stir_projdata_viewer.sources import ArraySource, make_demo_source


def test_demo_info():
    i = small_demo(num_tangential=21, axial_base=10).info
    assert (i.min_segment, i.max_segment) == (-1, 1)
    assert i.num_views == 12 and i.num_tangential == 21 and i.num_tof_bins == 5 and i.is_tof
    assert (i.min_tangential, i.max_tangential) == (-10, 10)          # centred like STIR
    assert i.num_axial(0) == 10 and i.num_axial(1) == 6


def test_demo_is_deterministic_and_seed_dependent():
    a, b, c = small_demo(), small_demo(), small_demo(seed=3)
    np.testing.assert_array_equal(a.get_segment(0, 2), b.get_segment(0, 2))
    assert not np.array_equal(a.get_segment(0, 2), c.get_segment(0, 2))


def test_demo_arrays_are_float32_nonnegative_and_correct_shape():
    src = small_demo()
    for s in src.info.segments:
        for k in src.info.tof_bins:
            a = src.get_segment(s, k)
            assert a.dtype == np.float32 and a.shape == src.info.expected_shape(s) and a.min() >= 0


def test_demo_tof_bins_sum_to_non_tof_ridge():
    """Collapsing TOF bins of a spot gives a bin-independent total: the TOF kernel only redistributes."""
    src = make_demo_source(num_segments=1, num_views=8, num_tangential=41, axial_base=10, tof_bins=15, seed=0)
    total = sum(src.get_segment(0, k) for k in src.info.tof_bins)
    # with the TOF centre grid wide enough, each view carries (almost) the same total counts
    per_view = total.sum(axis=(1, 2))
    assert per_view.std() / per_view.mean() < 0.35


def test_demo_rejects_even_segment_count():
    with pytest.raises(ValueError):
        make_demo_source(num_segments=4)


def test_array_source_accepts_3d_and_4d():
    a3 = np.zeros((6, 3, 5))
    a4 = np.zeros((2, 6, 3, 5))
    assert ArraySource({0: a3}).info.num_tof_bins == 1
    assert ArraySource({0: a4}).info.num_tof_bins == 2


@pytest.mark.parametrize("segments", [
    {},
    {0: np.zeros((4, 4))},                                           # 2D
    {0: np.zeros((4, 3, 5)), 1: np.zeros((4, 3, 6))},                # tangential mismatch
    {0: np.zeros((4, 3, 5)), 1: np.zeros((5, 3, 5))},                # view mismatch
    {0: np.zeros((4, 3, 5)), 1: np.zeros((2, 4, 3, 5))},             # TOF bin mismatch
    {0: np.zeros((4, 3, 5)), 2: np.zeros((4, 3, 5))},                # gap in segment numbers
])
def test_array_source_validation(segments):
    with pytest.raises(ValueError):
        ArraySource(segments)


def test_array_source_returns_float32_and_respects_tof_offset():
    arr = np.arange(2 * 3 * 2 * 4, dtype=np.float64).reshape(2, 3, 2, 4)
    src = ArraySource({0: arr})
    np.testing.assert_array_equal(src.get_segment(0, 1), arr[1].astype(np.float32))
    assert src.get_segment(0, 0).dtype == np.float32


def test_npy_and_npz_roundtrip(tmp_path):
    arr = small_demo().get_segment(0, 0)
    np.save(tmp_path / "a.npy", arr)
    s = ArraySource.from_file(tmp_path / "a.npy")
    assert s.info.num_views == 12 and s.info.name == "a.npy"
    np.savez(tmp_path / "b.npz", segment_0=arr, segment_1=arr[:, :4, :], **{"segment_-1": arr[:, :4, :]})
    s = ArraySource.from_file(tmp_path / "b.npz")
    assert (s.info.min_segment, s.info.max_segment) == (-1, 1) and s.info.num_axial(1) == 4


def test_npz_with_bad_key_and_unknown_suffix(tmp_path):
    np.savez(tmp_path / "c.npz", foo=np.zeros((4, 3, 5)))
    with pytest.raises(ValueError, match="segment_<n>"):
        ArraySource.from_file(tmp_path / "c.npz")
    with pytest.raises(ValueError, match="unsupported"):
        ArraySource.from_file(tmp_path / "d.txt")
