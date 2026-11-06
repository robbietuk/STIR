# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
from __future__ import annotations

from collections import OrderedDict
from typing import Generic, Hashable, TypeVar

V = TypeVar("V")


class LRUCache(Generic[V]):
    """Small least-recently-used cache."""

    def __init__(self, maxsize: int):
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self.maxsize = maxsize
        self._d: OrderedDict[Hashable, V] = OrderedDict()

    def get(self, key: Hashable) -> V | None:
        if key in self._d:
            self._d.move_to_end(key)
            return self._d[key]
        return None

    def put(self, key: Hashable, value: V) -> None:
        self._d[key] = value
        self._d.move_to_end(key)
        while len(self._d) > self.maxsize:
            self._d.popitem(last=False)

    def clear(self) -> None:
        self._d.clear()

    def __len__(self) -> int:
        return len(self._d)

    def __contains__(self, key: Hashable) -> bool:
        return key in self._d
