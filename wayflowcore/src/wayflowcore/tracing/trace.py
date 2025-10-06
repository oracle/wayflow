# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import TracebackType
from typing import List, Optional, Type

from wayflowcore.tracing.spanprocessor import SpanProcessor

_TRACE: ContextVar[Optional["Trace"]] = ContextVar("_TRACE", default=None)


def get_trace() -> Optional["Trace"]:
    """
    Get the Trace object active in the current context.

    Returns
    -------
        The active Trace object
    """
    return _TRACE.get()


@dataclass
class Trace:
    """
    The root of a collection of Spans.

    It is used to group together all the spans and events emitted during the execution of
    a workflow of interest.
    """

    name: Optional[str] = None
    """The name of the trace"""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """A unique identifier for the trace"""
    span_processors: List[SpanProcessor] = field(default_factory=list)
    """The list of SpanProcessors active on this trace"""
    shutdown_on_exit: bool = True
    """Whether to call shutdown on span processors when the trace context is closed"""

    def __enter__(self) -> "Trace":
        self._start()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: TracebackType,
    ) -> None:
        self._end()

    def _start(self) -> None:
        if _TRACE.get() is not None:
            raise RuntimeError("A Trace already exists. Cannot create two nested Traces.")
        _TRACE.set(self)
        for span_processor in self.span_processors:
            span_processor.startup()

    def _end(self) -> None:
        _TRACE.set(None)
        if self.shutdown_on_exit:
            for span_processor in self.span_processors:
                span_processor.shutdown()
