# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import json
import uuid
from typing import Any, Dict, Optional

from opentelemetry.sdk.trace import Event as OtelSdkEvent
from opentelemetry.sdk.trace import Resource as OtelSdkResource  # type: ignore
from opentelemetry.sdk.trace import Span as OtelSdkSpan
from opentelemetry.sdk.trace import SpanContext as OtelSdkSpanContext  # type: ignore
from opentelemetry.sdk.trace import _Span as _OtelSdkSpan
from opentelemetry.sdk.trace import sampling as otel_sdk_sampling
from opentelemetry.trace import TraceFlags as OtelSdkTraceFlags

from wayflowcore.tracing.span import Span


def _try_id_to_int_conversion(id_: Optional[str]) -> int:
    """
    Convert the string ID into an integer ID as per OpenTelemetry requirement

    https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/trace/api.md#spancontext
    """
    if id_ is not None:
        try:
            # First we try to get the original UUID, if the id is a compliant string
            id_ = uuid.UUID(id_)  # type: ignore
        except ValueError:
            # If it is not, we try to convert the id as it is
            pass
    try:
        # We try the conversion to int modulo 2**64 (unsigned long long, due to otel limitations), if it is not None
        # Note also the 0 is not a valid ID, so we reduce the modulo by 1 (2**64-1) and add 1 to the result
        return (int(id_) % 18446744073709551615) + 1 if id_ else id(id_)
    except Exception as e:
        # If the conversion fails, we fall back to the id, we cannot do better
        return id(id_)


def _try_json_serialization(value: Any) -> str:
    """
    Serialize the given object into the corresponding JSON string.
    If it is not JSON serializable, we simply stringify it
    """
    try:
        try:
            return json.dumps(value)
        except TypeError:
            return str(value)
    except Exception:
        return "!! This value could not be serialized !!"


def _flatten_attribute_dict(attribute: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten the complex types using OpenTelemetry conventions"""
    flattened_attribute: Dict[str, Any] = {}
    for key, value in attribute.items():
        if isinstance(value, (tuple, set, list)):
            # List-like values have to become dictionaries with the index as the key
            # This will be translated according to dict rules below (e.g., attribute_name.0, attribute_name.1, ...)
            flattened_value = dict()
            for i, inner_value in enumerate(value):
                flattened_value[i] = inner_value
            value = flattened_value
        if isinstance(value, dict):
            # Dictionary attributes are flattened by adding each dict entry
            # as a separate entry with name `attribute_name.key`
            for inner_key, inner_value in _flatten_attribute_dict(value).items():
                flattened_attribute[f"{key}.{inner_key}"] = inner_value
        else:
            flattened_attribute[key] = value
    return flattened_attribute


def _serialize_attribute_values(attributes: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize the attributes dictionary using types that OpenTelemetry supports"""
    # Note that this function performs shallow serialization, i.e., it does not apply recursively
    allowed_types = (str, int, float, bool, bytes)
    return {
        key: value if isinstance(value, allowed_types) else _try_json_serialization(value)
        for key, value in _flatten_attribute_dict(attributes).items()
    }


def convert_wayflow_span_into_otel_span(
    span: Span,
    resource: Optional[OtelSdkResource] = None,
    mask_sensitive_information: bool = True,
) -> OtelSdkSpan:
    """
    Convert a WayFlow Span into the equivalent opentelemetry Span object.

    Parameters
    ----------
    span:
        the span to convert
    resource:
        the opentelemetry Resource object to use
    mask_sensitive_information
        Whether to mask potentially sensitive information from the span and its events

    Returns
    -------
    opentelemetry.sdk.trace.Span
        The converted span
    """
    span_attributes = span.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    # We remove the tracing information we don't want to appear in the attributes, as they will be handled separately
    for attribute_to_pop in (
        "events",
        "trace_id",
        "trace_name",
        "span_id",
        "span_type",
        "parent_id",
        "name",
        "start_time",
        "end_time",
    ):
        span_attributes.pop(attribute_to_pop)
    # We create the objects required by OpenTelemetry with the expected information
    sampling_result = otel_sdk_sampling.SamplingResult(
        otel_sdk_sampling.Decision.RECORD_AND_SAMPLE,
        span_attributes,
    )
    trace_flags = (
        OtelSdkTraceFlags(OtelSdkTraceFlags.SAMPLED)
        if sampling_result.decision.is_sampled()  # type: ignore
        else OtelSdkTraceFlags(OtelSdkTraceFlags.DEFAULT)
    )
    # The IDs in otel are required to be integers, so we try to transform them
    trace_id = _try_id_to_int_conversion(span._trace.trace_id if span._trace else None)
    span_id = _try_id_to_int_conversion(span.span_id)
    return _OtelSdkSpan(
        name=span.name or span.__class__.__name__,
        context=OtelSdkSpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=False,
            trace_flags=trace_flags,
            trace_state=sampling_result.trace_state,
        ),
        parent=(
            OtelSdkSpanContext(
                trace_id=trace_id,
                span_id=_try_id_to_int_conversion(span._parent_span.span_id),
                is_remote=False,
            )
            if span._parent_span
            else None
        ),
        resource=resource,
        attributes=_serialize_attribute_values(span_attributes),
        events=[
            OtelSdkEvent(
                name=event.name or event.__class__.__name__,
                timestamp=event.timestamp,
                attributes=_serialize_attribute_values(
                    event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
                ),
            )
            for event in span.events
        ],
    )
