# SPDX-License-Identifier: Apache-2.0
import numpy as np

from fakes import non_tof_source, small_demo
from stir_projdata_viewer.model import ProjDataset, Selection, compute_stats
from stir_projdata_viewer.viewmodel import formatting


def test_describe_dataset_tof():
    text = formatting.describe_dataset(small_demo().info)
    for expected in ("Source:", "Segments:    3  (-1 .. 1)", "Views:       12", "TOF bins:    5  (0 .. 4)",
                     "seg -1: 4", "seg 0: 8", "Total bins:"):
        assert expected in text


def test_describe_dataset_non_tof_and_extra_fields():
    info = non_tof_source().info
    text = formatting.describe_dataset(info)
    assert "(non-TOF)" in text
    assert "format" not in text                                  # ArraySource without extra
    from stir_projdata_viewer.model import ProjDataInfo
    with_extra = ProjDataInfo("n", 0, 0, 0, 1, 0, 1, {0: (0, 0)}, extra={"scanner": "Biograph"})
    assert "scanner: Biograph" in formatting.describe_dataset(with_extra)


def test_describe_slice_reports_stats():
    ds = ProjDataset(small_demo())
    img = ds.slice(Selection.initial(ds.info))
    text = formatting.describe_slice(img, compute_stats(img.data))
    assert "12 x 15  (view x tangential)" in text and "min / max:" in text and "non-zero:" in text


def test_format_pixel_uses_real_indices():
    ds = ProjDataset(small_demo())
    img = ds.slice(Selection.initial(ds.info))
    assert formatting.format_pixel(img, 2, 3, 1.5).startswith("view 2, tangential -4:")


def test_format_profile_title():
    t = formatting.format_profile_title(0, 1, 2, 3, 4.5)
    assert t == "segment 0, view 1, axial 2, tangential 3   (sum 4.5)"


def test_numbers_use_compact_notation():
    ds = ProjDataset(small_demo())
    img = ds.slice(Selection.initial(ds.info))
    img = type(img)(img.data * 1e9, img.title, img.row_axis, img.col_axis, img.row_origin, img.col_origin)
    assert "e+" in formatting.describe_slice(img, compute_stats(img.data))
    assert np.isfinite(img.data).all()
