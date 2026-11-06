# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Choice lists shared by every control that offers the same choices (Qt-free).

One ``ChoiceOptions`` describes a closed set of choices: what the user sees, what the view model
stores, and how to convert between them. The view's segmented controls and combo boxes are built
from it, so labels and ordering exist in exactly one place.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, Hashable, Sequence, TypeVar

from ..model import SliceMode, TofMode

T = TypeVar("T", bound=Hashable)

COLORMAPS = ("viridis", "inferno", "magma", "plasma", "cividis", "grey")


class LevelMode(Enum):
    AUTO = "Auto (per slice)"
    FIXED = "Fixed (global range)"
    MANUAL = "Manual (drag in histogram)"


@dataclass(frozen=True)
class ChoiceOptions(Generic[T]):
    """An ordered, immutable set of ``(value, label)`` choices."""

    values: tuple
    labels: tuple

    def __post_init__(self) -> None:
        if len(self.values) != len(self.labels):
            raise ValueError("values and labels must have the same length")
        if not self.values:
            raise ValueError("a choice set needs at least one choice")
        if len(set(self.values)) != len(self.values):
            raise ValueError("choice values must be unique")

    @classmethod
    def from_enum(cls, enum_type: type[Enum], labels: dict | None = None) -> "ChoiceOptions":
        members = tuple(enum_type)
        return cls(members, tuple((labels or {}).get(m, m.value) for m in members))

    @classmethod
    def from_values(cls, values: Sequence, labels: Sequence[str] | None = None) -> "ChoiceOptions":
        values = tuple(values)
        return cls(values, tuple(labels) if labels is not None else tuple(str(v) for v in values))

    def __len__(self) -> int:
        return len(self.values)

    def index_of(self, value) -> int:
        try:
            return self.values.index(value)
        except ValueError:
            raise KeyError(f"{value!r} is not one of {self.values}") from None

    def value_at(self, index: int):
        if not 0 <= index < len(self.values):
            raise IndexError(f"choice index {index} out of range 0..{len(self.values) - 1}")
        return self.values[index]

    def label_of(self, value) -> str:
        return self.labels[self.index_of(value)]


SLICE_MODE_OPTIONS = ChoiceOptions.from_enum(
    SliceMode, {SliceMode.SINOGRAM: "Sinogram", SliceMode.VIEWGRAM: "Viewgram", SliceMode.TANGENTIAL: "Tangential"})
TOF_MODE_OPTIONS = ChoiceOptions.from_enum(
    TofMode, {TofMode.BIN: "Bin", TofMode.SUM: "Sum", TofMode.MEAN: "Mean", TofMode.MAX: "Max"})
LEVEL_MODE_OPTIONS = ChoiceOptions.from_enum(
    LevelMode, {LevelMode.AUTO: "Auto", LevelMode.FIXED: "Global", LevelMode.MANUAL: "Manual"})
COLORMAP_OPTIONS = ChoiceOptions.from_values(COLORMAPS)
