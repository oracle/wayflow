# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import pytest

from wayflowcore import Message
from wayflowcore.events.event import EndSpanEvent, Event, StartSpanEvent
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.tracing.span import _PII_TEXT_MASK, Span
from wayflowcore.tracing.spanexporter import SpanExporter
from wayflowcore.tracing.spanprocessor import SimpleSpanProcessor

from ..conftest import VLLM_MODEL_CONFIG
from ..testhelpers.dummy import DummyModel


class SerializableDummyModel(DummyModel):

    @property
    def config(self) -> Dict[str, Any]:
        return {"model_id": self.model_id}


def create_serializable_dummy_llm_with_next_output(
    next_output: Union[
        str, List[str], Dict[Optional[str], str], Message, Dict[Optional[str], Message]
    ],
) -> DummyModel:
    llm = SerializableDummyModel()
    llm.set_next_output(next_output)
    return llm


@dataclass(frozen=True)
class MyCustomEvent(Event):

    custom_attribute: Dict[str, Any] = field(default_factory=dict)
    custom_secret_attribute: str = "this value is a secret!"

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "custom_attribute": self.custom_attribute,
            "custom_secret_attribute": (
                _PII_TEXT_MASK if mask_sensitive_information else self.custom_secret_attribute
            ),
        }


@dataclass
class MyCustomSpan(Span):

    custom_attribute: int = 1
    custom_secret_attribute: str = "this value is a secret!"

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "custom_attribute": self.custom_attribute,
            "custom_secret_attribute": (
                _PII_TEXT_MASK if mask_sensitive_information else self.custom_secret_attribute
            ),
        }

    def _create_start_span_event(self) -> "StartSpanEvent":
        return StartSpanEvent(span=self)

    def record_end_span_event(self, event: "EndSpanEvent") -> None:
        self._record_end_span_event(event=event)


class InMemorySpanExporter(SpanExporter):

    def __init__(self):
        self.startup_called: bool = False
        self.shutdown_called: bool = False
        self.force_flush_called: bool = False
        self.exported_spans: List[Dict[str, Any]] = []

    def get_exported_spans(self, span_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return [
            span
            for span in self.exported_spans
            if span_type is None or span["span_type"] == span_type
        ]

    def export(self, spans: List[Span], mask_sensitive_information: bool = True) -> None:
        self.exported_spans.extend(
            span.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
            for span in spans
        )

    def startup(self) -> None:
        self.startup_called = True
        # We reset the exported spans
        self.exported_spans = []

    def shutdown(self) -> None:
        self.shutdown_called = True

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        self.force_flush_called = True
        return True


@pytest.fixture
def default_span_exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def default_span_processor(default_span_exporter) -> SimpleSpanProcessor:
    return SimpleSpanProcessor(
        span_exporter=default_span_exporter, mask_sensitive_information=False
    )


@pytest.fixture
def llm():
    return LlmModelFactory.from_config(VLLM_MODEL_CONFIG)
