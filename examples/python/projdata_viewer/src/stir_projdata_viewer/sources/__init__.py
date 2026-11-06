# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Data providers that implement the model's ``ProjDataSource`` without STIR."""
from .array_source import ArraySource
from .demo import make_demo_source

__all__ = ["ArraySource", "make_demo_source"]
