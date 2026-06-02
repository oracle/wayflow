.. _tracing:

Tracing
=======

This page presents all APIs and classes related to tracing in WayFlow.


Trace
------

.. _get_trace:
.. autofunction:: wayflowcore.tracing.trace.get_trace

.. _trace:
.. autoclass:: wayflowcore.tracing.trace.Trace


Spans
-----

.. _get_current_span:
.. autofunction:: wayflowcore.tracing.span.get_current_span

.. _get_active_span_stack:
.. autofunction:: wayflowcore.tracing.span.get_active_span_stack

.. _span:
.. autoclass:: wayflowcore.tracing.span.Span

.. _llm_generation_span:
.. autoclass:: wayflowcore.tracing.span.LlmGenerationSpan

.. _conversational_component_execution_span:
.. autoclass:: wayflowcore.tracing.span.ConversationalComponentExecutionSpan

.. _conversation_span:
.. autoclass:: wayflowcore.tracing.span.ConversationSpan

.. _tool_execution_span:
.. autoclass:: wayflowcore.tracing.span.ToolExecutionSpan

.. _step_invocation_span:
.. autoclass:: wayflowcore.tracing.span.StepInvocationSpan

.. _context_provider_execution_span:
.. autoclass:: wayflowcore.tracing.span.ContextProviderExecutionSpan

Span Processors
----------------

.. _spanprocessor:
.. autoclass:: wayflowcore.tracing.spanprocessor.SpanProcessor

.. _simplespanprocessor:
.. autoclass:: wayflowcore.tracing.spanprocessor.SimpleSpanProcessor


Span Exporter
-------------

.. _spanexporter:
.. autoclass:: wayflowcore.tracing.spanexporter.SpanExporter


OpenTelemetry
-------------

.. _otelsimplespanprocessor:
.. autoclass:: wayflowcore.tracing.opentelemetry.spanprocessor.OtelSimpleSpanProcessor

.. _otelbatchspanprocessor:
.. autoclass:: wayflowcore.tracing.opentelemetry.spanprocessor.OtelBatchSpanProcessor
