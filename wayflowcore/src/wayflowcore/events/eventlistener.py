# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from copy import copy
from typing import Callable, Iterator, List, Optional, Type

from wayflowcore.events.event import Event, ExceptionRaisedEvent


class EventListener(ABC):
    """
    Base class for EventListeners.

    An EventListener is a Callable that gets called every time an Event is recorded.
    """

    @abstractmethod
    def __call__(self, event: Event) -> None:
        """
        The method called every time an Event is recorded.

        Parameters
        ----------
        event:
            The event that is being recorded
        """


class GenericEventListener(EventListener):

    def __init__(self, event_classes: List[Type[Event]], function: Callable[["Event"], None]):
        """
        Special implementation of EventListener that calls a function every time an event
        whose type is among the given event classes is recorded.

        Parameters
        ----------
        event_classes:
            The list of Event classes that will trigger the function call when recorded
        function:
            The function to be called. It must have a single argument of type Event, that will contain
            the event being recorded, it is not supposed to have any return value.
        """
        self.event_classes = event_classes
        self.function = function

    def _event_listener_is_triggered(self, event: Event) -> bool:
        for event_type in self.event_classes:
            if isinstance(event, event_type):
                return True
        return False

    def __call__(self, event: Event) -> None:
        if self._event_listener_is_triggered(event=event):
            self.function(event)


_EVENT_LISTENERS_REGISTRY: ContextVar[List[List["EventListener"]]] = ContextVar(
    "_EVENT_LISTENERS_REGISTRY", default=[]
)

_LAST_THROWN_EXCEPTION: ContextVar[Optional[Exception]] = ContextVar(
    "_LAST_THROWN_EXCEPTION",
    default=None,
)


def _get_event_listeners_registry(return_copy: bool = True) -> List[List["EventListener"]]:
    event_listeners_registry = _EVENT_LISTENERS_REGISTRY.get()
    return copy(event_listeners_registry) if return_copy else event_listeners_registry


def _register_event_listeners(event_listeners: List[EventListener]) -> None:
    # We need to copy the list because when the context is copied,
    # a shallow copy of the context dictionary (i.e., the available ContextVars) is done.
    # This means that the reference to the same list is copied in every context,
    # and modifying one of them will have side effects on the others.
    event_listeners_registry = _get_event_listeners_registry(return_copy=True)
    event_listeners_registry.append(event_listeners)
    _EVENT_LISTENERS_REGISTRY.set(event_listeners_registry)


def _deregister_last_event_listeners() -> None:
    event_listeners_registry = _get_event_listeners_registry(return_copy=True)
    event_listeners_registry.pop()
    _EVENT_LISTENERS_REGISTRY.set(event_listeners_registry)


@contextmanager
def register_event_listeners(event_listeners: List[EventListener]) -> Iterator[None]:
    """
    Register event listeners to be called for all events recorded inside the context manager's scope

    Parameters
    ----------
    event_listeners:
        The list of EventListeners to be called
    """
    try:
        _register_event_listeners(event_listeners)
        yield
    finally:
        _deregister_last_event_listeners()


def get_event_listeners() -> List[EventListener]:
    """
    Get all the event listeners that are registered in the current context

    Returns
    -------
        The list of EventListeners registered in the current context
    """
    return [
        event_listener
        for event_listener_list in _get_event_listeners_registry(return_copy=False)
        for event_listener in event_listener_list
    ]


def record_event(event: Event) -> None:
    """
    Record the event and execute all the event listeners that are registered in the current context

    Parameters
    ----------
    event:
        The Event being recorded
    """
    for event_listener in get_event_listeners():
        event_listener(event=event)


def _record_exception(exception: Exception) -> None:
    if exception is not _LAST_THROWN_EXCEPTION.get():
        _LAST_THROWN_EXCEPTION.set(exception)
        record_event(
            ExceptionRaisedEvent(
                exception=exception,
            )
        )
