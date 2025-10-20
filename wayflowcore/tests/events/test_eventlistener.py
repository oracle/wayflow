# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass

from wayflowcore.events.event import Event
from wayflowcore.events.eventlistener import (
    EventListener,
    get_event_listeners,
    record_event,
    register_event_listeners,
)

from .conftest import MyCustomEvent, create_generic_event_listener_with_list_of_triggered_events


@dataclass(frozen=True)
class MySecondCustomEvent(Event):
    pass


def test_eventlisteners_are_registered() -> None:
    event_listener_1, _ = create_generic_event_listener_with_list_of_triggered_events()
    event_listener_2, _ = create_generic_event_listener_with_list_of_triggered_events()
    event_listener_3, _ = create_generic_event_listener_with_list_of_triggered_events()
    registered_event_listeners = get_event_listeners()
    # Note that by default we have the event listener that adds events to spans
    assert len(registered_event_listeners) == 1
    with register_event_listeners([event_listener_1]):
        with register_event_listeners([event_listener_2, event_listener_3]):
            registered_event_listeners = get_event_listeners()
            assert len(registered_event_listeners) == 4
            assert all(
                el in registered_event_listeners
                for el in [event_listener_1, event_listener_2, event_listener_3]
            )
        registered_event_listeners = get_event_listeners()
        assert len(registered_event_listeners) == 2
        assert all(el in registered_event_listeners for el in [event_listener_1])
        assert all(
            el not in registered_event_listeners for el in [event_listener_2, event_listener_3]
        )
    registered_event_listeners = get_event_listeners()
    assert len(registered_event_listeners) == 1


def test_eventlistener_is_registered_and_triggered() -> None:
    event_listener, events_triggered = create_generic_event_listener_with_list_of_triggered_events(
        [MyCustomEvent]
    )
    event = MyCustomEvent()
    with register_event_listeners([event_listener]):
        record_event(event)
    assert len(events_triggered) == 1
    assert events_triggered[0] == event


def test_eventlistener_is_registered_and_not_triggered() -> None:
    event_listener, events_triggered = create_generic_event_listener_with_list_of_triggered_events(
        [MyCustomEvent]
    )
    event = MySecondCustomEvent()
    with register_event_listeners([event_listener]):
        record_event(event)
    assert len(events_triggered) == 0


def test_eventlistener_is_registered_and_triggered_multiple_times() -> None:
    event_listener, events_triggered = create_generic_event_listener_with_list_of_triggered_events(
        [MyCustomEvent]
    )
    event = MyCustomEvent()
    with register_event_listeners([event_listener, event_listener]):
        with register_event_listeners([event_listener]):
            record_event(event)
    assert len(events_triggered) == 3
    assert all(event_triggered == event for event_triggered in events_triggered)


def test_eventlistener_is_registered_on_event_parent_and_triggered() -> None:
    class MyChildCustomEvent(MyCustomEvent):
        pass

    event_listener, events_triggered = create_generic_event_listener_with_list_of_triggered_events(
        [MyCustomEvent]
    )
    event = MyChildCustomEvent()
    with register_event_listeners([event_listener]):
        record_event(event)
    assert len(events_triggered) == 1
    assert event in events_triggered


def test_nested_eventlisteners_are_registered_and_triggered_correctly() -> None:
    event_listener, events_triggered = create_generic_event_listener_with_list_of_triggered_events()
    second_event_listener, second_events_triggered = (
        create_generic_event_listener_with_list_of_triggered_events()
    )
    event_1 = MyCustomEvent()
    event_2 = MyCustomEvent()
    with register_event_listeners([event_listener]):
        with register_event_listeners([second_event_listener]):
            record_event(event_1)
        record_event(event_2)
    assert len(events_triggered) == 2
    assert event_1 in events_triggered
    assert event_1 in second_events_triggered
    assert len(second_events_triggered) == 1
    assert event_2 in events_triggered
    assert event_2 not in second_events_triggered


def test_multiple_eventlisteners_are_registered_and_triggered_correctly_on_different_events() -> (
    None
):
    event_listener, events_triggered = create_generic_event_listener_with_list_of_triggered_events(
        [MyCustomEvent]
    )
    second_event_listener, second_events_triggered = (
        create_generic_event_listener_with_list_of_triggered_events([MySecondCustomEvent])
    )
    event_1 = MyCustomEvent()
    event_2 = MySecondCustomEvent()
    with register_event_listeners([event_listener, second_event_listener]):
        record_event(event_1)
        record_event(event_2)
    assert len(events_triggered) == 1
    assert event_1 in events_triggered
    assert event_2 not in events_triggered
    assert len(second_events_triggered) == 1
    assert event_1 not in second_events_triggered
    assert event_2 in second_events_triggered


def test_eventlistener_is_deregistered_when_eventlistener_raises_exception() -> None:

    @dataclass
    class EventListenerRaisingException(EventListener):
        def __call__(self, event: Event) -> None:
            raise RuntimeError("This is an error")

    event_listener = EventListenerRaisingException()
    event = MyCustomEvent()
    registered_event_listeners = get_event_listeners()
    # Note that by default we have the event listener that adds events to spans
    assert len(registered_event_listeners) == 1
    try:
        with register_event_listeners([event_listener]):
            registered_event_listeners = get_event_listeners()
            assert len(registered_event_listeners) == 2
            record_event(event)
    except Exception:
        pass
    registered_event_listeners = get_event_listeners()
    assert len(registered_event_listeners) == 1


def test_eventlistener_is_deregistered_when_an_exception_is_raised() -> None:
    event_listener, events_triggered = create_generic_event_listener_with_list_of_triggered_events()
    registered_event_listeners = get_event_listeners()
    event = MyCustomEvent()
    # Note that by default we have the event listener that adds events to spans
    assert len(registered_event_listeners) == 1
    try:
        with register_event_listeners([event_listener]):
            registered_event_listeners = get_event_listeners()
            assert len(registered_event_listeners) == 2
            record_event(event)
            raise ValueError("Exception!")
    except ValueError:
        pass
    registered_event_listeners = get_event_listeners()
    assert len(registered_event_listeners) == 1
    assert len(events_triggered) == 1
    assert event in events_triggered
