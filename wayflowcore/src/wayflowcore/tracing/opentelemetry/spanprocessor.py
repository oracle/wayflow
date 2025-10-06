# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from abc import ABC, abstractmethod
from typing import Optional

from opentelemetry.sdk.resources import Resource as OtelSdkResource
from opentelemetry.sdk.trace.export import BatchSpanProcessor as OtelSdkBatchSpanProcessor
from opentelemetry.sdk.trace.export import SimpleSpanProcessor as OtelSdkSimpleSpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter as OtelSdkSpanExporter
from opentelemetry.sdk.trace.export import SpanProcessor as OtelSdkSpanProcessor  # type: ignore

from wayflowcore.tracing.opentelemetry.span import convert_wayflow_span_into_otel_span
from wayflowcore.tracing.span import Span
from wayflowcore.tracing.spanprocessor import SpanProcessor


class _OtelSpanProcessor(SpanProcessor, ABC):

    def __init__(
        self,
        span_exporter: OtelSdkSpanExporter,
        resource: Optional[OtelSdkResource] = None,
        mask_sensitive_information: bool = True,
    ) -> None:
        """
        WayFlow wrapper for the OpenTelemetry SpanProcessor.

        This class forwards the calls to WayFlow's span processors to an OpenTelemetry one.

        Parameters
        ----------
        span_exporter:
            The OpenTelemetry SpanExporter to use to export spans.
        resource:
            The OpenTelemetry Resource to use in Spans.
        mask_sensitive_information
            Whether to mask potentially sensitive information from the span and its events
        """
        self.span_exporter = span_exporter
        self.resource = resource
        self.mask_sensitive_information = mask_sensitive_information
        self.span_processor = self._create_otel_span_processor(span_exporter=span_exporter)

    @abstractmethod
    def _create_otel_span_processor(
        self, span_exporter: OtelSdkSpanExporter
    ) -> OtelSdkSpanProcessor:
        pass

    def on_start(self, span: "Span") -> None:
        """
        Method called at the start of a Span.

        It converts the given WayFlow span to an equivalent OpenTelemetry span,
        and it forwards the ``start`` call to the internal OpenTelemetry span processor.

        Parameters
        ----------
        span:
            The WayFlow span that is starting
        """
        otel_span = convert_wayflow_span_into_otel_span(
            span=span,
            resource=self.resource,
            mask_sensitive_information=self.mask_sensitive_information,
        )
        otel_span.start(start_time=span.start_time)
        self.span_processor.on_start(span=otel_span)

    def on_end(self, span: "Span") -> None:
        """
        Method called at the end of a Span.

        It converts the given WayFlow span to an equivalent OpenTelemetry span,
        and it forwards the ``end`` call to the internal OpenTelemetry span processor.

        Parameters
        ----------
        span:
            The WayFlow span that is ending
        """
        # In order to avoid keeping track of the stack of OpenTelemetry spans, we manually create a span
        # with the information contained in Wayflow's span, and we start + end it here to simulate the correct behavior
        otel_span = convert_wayflow_span_into_otel_span(
            span=span,
            resource=self.resource,
            mask_sensitive_information=self.mask_sensitive_information,
        )
        otel_span.start(start_time=span.start_time)
        otel_span.end(end_time=span.end_time)
        self.span_processor.on_end(span=otel_span)

    def startup(self) -> None:
        """Called when a `Trace` is started."""

    def shutdown(self) -> None:
        """Called when a `Trace` is shutdown."""
        self.span_processor.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """
        Export all ended spans to the configured Exporter that have not yet been exported.

        Forwards the call to the internal OpenTelemetry span processor.
        """
        return self.span_processor.force_flush(timeout_millis=timeout_millis)


class OtelSimpleSpanProcessor(_OtelSpanProcessor):
    """WayFlow wrapper for the OpenTelemetry SimpleSpanProcessor"""

    def _create_otel_span_processor(
        self, span_exporter: OtelSdkSpanExporter
    ) -> OtelSdkSpanProcessor:
        return OtelSdkSimpleSpanProcessor(span_exporter=span_exporter)


class OtelBatchSpanProcessor(_OtelSpanProcessor):
    """WayFlow wrapper for the OpenTelemetry BatchSpanProcessor"""

    def _create_otel_span_processor(
        self, span_exporter: OtelSdkSpanExporter
    ) -> OtelSdkSpanProcessor:
        return OtelSdkBatchSpanProcessor(span_exporter=span_exporter)
