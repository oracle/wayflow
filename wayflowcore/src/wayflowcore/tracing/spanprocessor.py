# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from abc import ABC, abstractmethod

from wayflowcore.tracing.span import Span
from wayflowcore.tracing.spanexporter import SpanExporter


class SpanProcessor(ABC):
    """Interface which allows hooks for `Span` start and end method invocations."""

    @abstractmethod
    def on_start(self, span: "Span") -> None:
        """
        Called when a `Span` is started.

        Parameters
        ----------
        span:
            The spans that starts
        """

    @abstractmethod
    def on_end(self, span: "Span") -> None:
        """
        Called when a `Span` is ended.

        Parameters
        ----------
        span:
            The spans that ends
        """

    @abstractmethod
    def startup(self) -> None:
        """Called when a `Trace` is started."""

    @abstractmethod
    def shutdown(self) -> None:
        """Called when a `Trace` is shutdown."""

    @abstractmethod
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """
        Export all ended spans to the configured Exporter that have not yet been exported.

        Parameters
        ----------
        timeout_millis:
            The time conceded to perform the flush

        Returns
        -------
            False if the timeout is exceeded, True otherwise
        """


class SimpleSpanProcessor(SpanProcessor):
    """Simple SpanProcessor implementation.

    SimpleSpanProcessor is an implementation of `SpanProcessor` that
    passes ended spans directly to the configured `SpanExporter`.
    """

    def __init__(self, span_exporter: SpanExporter, mask_sensitive_information: bool = True):
        """
        Parameters
        ----------
        span_exporter
            The SpanExporter to call at the end of each span
        mask_sensitive_information
            Whether to mask potentially sensitive information from the span and its events
        """
        self.span_exporter = span_exporter
        self.mask_sensitive_information = mask_sensitive_information

    def on_start(self, span: Span) -> None:
        pass

    def on_end(self, span: Span) -> None:
        self.span_exporter.export(
            [span], mask_sensitive_information=self.mask_sensitive_information
        )

    def startup(self) -> None:
        self.span_exporter.startup()

    def shutdown(self) -> None:
        self.span_exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.span_exporter.force_flush(timeout_millis=timeout_millis)
