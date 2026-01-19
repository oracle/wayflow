# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import random
from typing import List, Optional

import httpx
import pytest
from opentelemetry.sdk.trace import ReadableSpan as OtelSdkReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter as OtelSdkSpanExporter
from opentelemetry.sdk.trace.export import SpanExportResult as OtelSdkSpanExportResult

from wayflowcore.events.event import _PII_TEXT_MASK as EVENT_MASKING_TOKEN
from wayflowcore.events.event import EndSpanEvent
from wayflowcore.tracing.opentelemetry import OtelBatchSpanProcessor, OtelSimpleSpanProcessor
from wayflowcore.tracing.span import _PII_TEXT_MASK as SPAN_MASKING_TOKEN
from wayflowcore.tracing.span import record_event
from wayflowcore.tracing.trace import Trace

from ..conftest import MyCustomEvent, MyCustomSpan


class OTLPSpanExporter(OtelSdkSpanExporter):

    def __init__(self, endpoint: Optional[str] = None):
        self._endpoint = endpoint or "localhost"

    def export(self, spans: List[OtelSdkReadableSpan]) -> OtelSdkSpanExportResult:
        responses = []
        for span in spans:
            responses.append(
                httpx.post(f"http://{self._endpoint}/v1/traces", json=json.loads(span.to_json()))
            )
        if any(200 <= response.status_code < 300 for response in responses):
            return OtelSdkSpanExportResult.SUCCESS
        return OtelSdkSpanExportResult.FAILURE

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


@pytest.mark.parametrize(
    "span_processor_class",
    [OtelSimpleSpanProcessor, OtelBatchSpanProcessor],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_spans_get_exported_correctly_to_otel_collector(
    otel_server, span_processor_class, mask_sensitive_information
) -> None:
    span_processor = span_processor_class(
        span_exporter=OTLPSpanExporter(endpoint=otel_server),
        mask_sensitive_information=mask_sensitive_information,
    )
    trace_id = random.randint(1, 1000000000000)
    span_id = 1000000000000 - trace_id + 1
    with Trace(trace_id=str(trace_id), span_processors=[span_processor]) as trace:
        with MyCustomSpan(span_id=str(span_id), name="Hey!", custom_attribute=24) as span:
            record_event(MyCustomEvent(name="MyTestCustomEvent", custom_attribute={"a": 1}))
            span.record_end_span_event(EndSpanEvent())

    with httpx.Client(timeout=1.0) as client:
        response = client.post(f"http://{otel_server}/v1/getspan", json={"span_id": span_id})
    assert 200 <= response.status_code < 300
    response_json = response.json()
    assert "name" in response_json and response_json["name"] == "Hey!"
    assert "context" in response_json
    assert "span_id" in response_json["context"]
    assert int(response_json["context"]["span_id"], 16) == span_id + 1
    assert "attributes" in response_json
    assert "custom_attribute" in response_json["attributes"]
    assert "custom_secret_attribute" in response_json["attributes"]
    if mask_sensitive_information:
        assert response_json["attributes"]["custom_secret_attribute"] == SPAN_MASKING_TOKEN
    else:
        assert response_json["attributes"]["custom_secret_attribute"] != SPAN_MASKING_TOKEN
    assert "events" in response_json
    assert len(response_json["events"]) == 3
    # The custom event is the one between start and end
    my_custom_event = response_json["events"][1]
    assert "name" in my_custom_event
    assert my_custom_event["name"] == "MyTestCustomEvent"
    assert "attributes" in my_custom_event
    assert "custom_attribute.a" in my_custom_event["attributes"]
    assert "custom_secret_attribute" in my_custom_event["attributes"]
    if mask_sensitive_information:
        assert my_custom_event["attributes"]["custom_secret_attribute"] == EVENT_MASKING_TOKEN
    else:
        assert my_custom_event["attributes"]["custom_secret_attribute"] != EVENT_MASKING_TOKEN
