# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Declarative property -> widget bindings (Qt-free, so the dispatch rules are unit-tested).

A view registers ``registry.bind("colormap", update_fn)`` once; the registry subscribes to the view
model and calls each binding at most once per notification, in registration order, only if one of
its property names changed. Replaces the long ``if "x" in names`` chain a window would otherwise have.
"""
from __future__ import annotations

from typing import Callable, Iterable

from .observable import Observed, ObservableObject


def observed_names(obj_or_type) -> tuple[str, ...]:
    """Names of every ``Observed`` property of a class (or instance), in definition order."""
    cls = obj_or_type if isinstance(obj_or_type, type) else type(obj_or_type)
    names: list[str] = []
    for klass in reversed(cls.__mro__):
        for name, value in vars(klass).items():
            if isinstance(value, Observed) and name not in names:
                names.append(name)
    return tuple(names)


class BindingRegistry:
    def __init__(self, vm: ObservableObject):
        self._vm = vm
        self._bindings: list[tuple[frozenset, Callable[[], None]]] = []
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def bound_names(self) -> frozenset:
        return frozenset().union(*(names for names, _ in self._bindings)) if self._bindings else frozenset()

    def bind(self, names: str | Iterable[str], update: Callable[[], None]) -> None:
        """``update()`` runs when any of ``names`` changed. It reads current values from the view model."""
        group = frozenset([names] if isinstance(names, str) else names)
        if not group:
            raise ValueError("a binding needs at least one property name")
        unknown = group - set(observed_names(self._vm))
        if unknown:
            raise KeyError(f"not observable on {type(self._vm).__name__}: {sorted(unknown)}")
        self._bindings.append((group, update))

    def start(self, initial_paint: bool = True) -> None:
        if self._unsubscribe is None:
            self._unsubscribe = self._vm.subscribe(self.dispatch)
        if initial_paint:
            self.dispatch(self.bound_names)

    def stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def dispatch(self, changed: frozenset) -> None:
        for names, update in list(self._bindings):
            if names & changed:
                update()

    def unbound(self) -> frozenset:
        """Observable properties nothing is bound to (tests assert this is empty or intentional)."""
        return frozenset(observed_names(self._vm)) - self.bound_names
