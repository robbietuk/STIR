# SPDX-License-Identifier: Apache-2.0
import numpy as np

from stir_projdata_viewer.viewmodel import ObservableObject, Observed


class Thing(ObservableObject):
    a = Observed(0)
    b = Observed("x")
    arr = Observed(None)


def record(obj):
    seen = []
    obj.subscribe(seen.append)
    return seen


def test_assignment_notifies_with_property_name():
    t = Thing()
    seen = record(t)
    t.a = 1
    assert seen == [frozenset({"a"})] and t.a == 1


def test_same_value_does_not_notify():
    t = Thing()
    seen = record(t)
    t.a = 0
    t.b = "x"
    assert seen == []


def test_type_change_counts_as_change():
    t = Thing()
    seen = record(t)
    t.a = False                   # 0 == False in Python, but this is a different value to a view
    t.a = 0.0
    assert len(seen) == 2


def test_numpy_values_notify_unless_same_object():
    t = Thing()
    seen = record(t)
    x = np.zeros(3)
    t.arr = x
    t.arr = x
    t.arr = np.zeros(3)
    assert len(seen) == 2


def test_defaults_are_per_class_and_values_per_instance():
    t1, t2 = Thing(), Thing()
    t1.a = 5
    assert t2.a == 0 and Thing.a.default == 0


def test_transaction_batches_into_one_notification():
    t = Thing()
    seen = record(t)
    with t.transaction():
        t.a = 1
        t.b = "y"
        t.a = 2
        assert seen == []
    assert seen == [frozenset({"a", "b"})]


def test_nested_transactions_flush_only_at_the_outermost():
    t = Thing()
    seen = record(t)
    with t.transaction():
        with t.transaction():
            t.a = 1
        assert seen == []
        t.b = "z"
    assert len(seen) == 1 and seen[0] == frozenset({"a", "b"})


def test_transaction_flushes_even_if_the_body_raises():
    t = Thing()
    seen = record(t)
    try:
        with t.transaction():
            t.a = 1
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert seen == [frozenset({"a"})]
    t.b = "q"                      # and the object still works afterwards
    assert len(seen) == 2


def test_empty_transaction_does_not_notify():
    t = Thing()
    seen = record(t)
    with t.transaction():
        pass
    assert seen == []


def test_unsubscribe_and_multiple_subscribers():
    t = Thing()
    a, b = [], []
    unsub_a = t.subscribe(a.append)
    t.subscribe(b.append)
    t.a = 1
    unsub_a()
    unsub_a()                      # idempotent
    t.a = 2
    assert len(a) == 1 and len(b) == 2


def test_subscriber_can_unsubscribe_during_delivery():
    t = Thing()
    calls = []

    def once(names):
        calls.append(names)
        unsub()
    unsub = t.subscribe(once)
    t.a = 1
    t.a = 2
    assert len(calls) == 1
