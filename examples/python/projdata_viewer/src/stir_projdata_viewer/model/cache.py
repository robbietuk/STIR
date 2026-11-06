# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
from __future__ import annotations

from collections import OrderedDict
from typing import Generic, Hashable, TypeVar

V = TypeVar("V")


def _nbytes(value) -> int:
    return int(getattr(value, "nbytes", 0))


class LRUCache(Generic[V]):
    """Small least-recently-used cache, bounded by entry count and (optionally) by total bytes.

    ``max_bytes`` counts ``value.nbytes`` (numpy arrays); the most recently added entry is always kept,
    even if it alone exceeds the budget, so a single large segment can still be displayed.
    """

    def __init__(self, maxsize: int, max_bytes: int | None = None):
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        if max_bytes is not None and max_bytes < 0:
            raise ValueError("max_bytes must be >= 0")
        self.maxsize = maxsize
        self.max_bytes = max_bytes
        self._d: OrderedDict[Hashable, V] = OrderedDict()
        self._bytes = 0

    @property
    def nbytes(self) -> int:
        return self._bytes

    def get(self, key: Hashable) -> V | None:
        if key in self._d:
            self._d.move_to_end(key)
            return self._d[key]
        return None

    def put(self, key: Hashable, value: V) -> None:
        if key in self._d:
            self._bytes -= _nbytes(self._d[key])
        self._d[key] = value
        self._bytes += _nbytes(value)
        self._d.move_to_end(key)
        while len(self._d) > 1 and (len(self._d) > self.maxsize
                                    or (self.max_bytes is not None and self._bytes > self.max_bytes)):
            _, old = self._d.popitem(last=False)
            self._bytes -= _nbytes(old)

    def clear(self) -> None:
        self._d.clear()
        self._bytes = 0

    def __len__(self) -> int:
        return len(self._d)

    def __contains__(self, key: Hashable) -> bool:
        return key in self._d
