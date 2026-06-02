<a id="tracing"></a>

# Tracing

This page presents all APIs and classes related to tracing in WayFlow.

## Trace

<a id="get-trace"></a>

### wayflowcore.tracing.trace.get_trace()

Get the Trace object active in the current context.

* **Return type:**
  `Optional`[[`Trace`](#wayflowcore.tracing.trace.Trace)]
* **Returns:**
  The active Trace object

<a id="id2"></a>

### *class* wayflowcore.tracing.trace.Trace(name=None, trace_id=<factory>, span_processors=<factory>, shutdown_on_exit=True)

The root of a collection of Spans.

It is used to group together all the spans and events emitted during the execution of
a workflow of interest.

* **Parameters:**
  * **name** (*str* *|* *None*)
  * **trace_id** (*str*)
  * **span_processors** (*List* *[*[*SpanProcessor*](#wayflowcore.tracing.spanprocessor.SpanProcessor) *]*)
  * **shutdown_on_exit** (*bool*)

#### name *: `Optional`[`str`]* *= None*

The name of the trace

#### shutdown_on_exit *: `bool`* *= True*

Whether to call shutdown on span processors when the trace context is closed

#### span_processors *: `List`[[`SpanProcessor`](#wayflowcore.tracing.spanprocessor.SpanProcessor)]*

The list of SpanProcessors active on this trace

#### trace_id *: `str`*

A unique identifier for the trace

## Spans

<a id="get-current-span"></a>

### wayflowcore.tracing.span.get_current_span()

Retrieve the currently active span in this context.

* **Return type:**
  `Optional`[[`Span`](#wayflowcore.tracing.span.Span)]
* **Returns:**
  The active span in this context

<a id="get-active-span-stack"></a>

### wayflowcore.tracing.span.get_active_span_stack(return_copy=True)

Retrieve the stack of active spans in this context.

* **Return type:**
  `List`[[`Span`](#wayflowcore.tracing.span.Span)]
* **Returns:**
  The stack of active spans in this context
* **Parameters:**
  **return_copy** (*bool*)

<a id="span"></a>

### *class* wayflowcore.tracing.span.Span(span_id=<factory>, name=None, start_time=None, end_time=None, events=<factory>, \_parent_span=None, \_end_event_was_triggered=False, \_span_was_appended_to_active_stack=False, \_started_span_processors=<factory>)

A Span represents a single operation within a Trace.

* **Parameters:**
  * **span_id** (*str*)
  * **name** (*str* *|* *None*)
  * **start_time** (*int* *|* *None*)
  * **end_time** (*int* *|* *None*)
  * **events** (*List* *[*[*Event*](events.md#wayflowcore.events.event.Event) *]*)
  * **\_parent_span** ([*Span*](#wayflowcore.tracing.span.Span) *|* *None*)
  * **\_end_event_was_triggered** (*bool*)
  * **\_span_was_appended_to_active_stack** (*bool*)
  * **\_started_span_processors** (*List* *[*[*SpanProcessor*](#wayflowcore.tracing.spanprocessor.SpanProcessor) *]*)

#### end(exception=None)

End the span.

This includes calling the `on_end` method of the active SpanProcessors,
and recording the StartSpanEvent.

If the `record_end_span_event` method was not called for this span, it is
called automatically with a default EndSpanEvent, and a warning is raised.

* **Parameters:**
  **exception** (`Optional`[`Exception`]) – The exception that was raised during the execution of the span.
* **Return type:**
  `None`

#### end_time *: `Optional`[`int`]* *= None*

The timestamp of when the span was closed

#### events *: `List`[[`Event`](events.md#wayflowcore.events.event.Event)]*

The list of events recorded in the scope of this span

#### name *: `Optional`[`str`]* *= None*

The name of the span

#### *abstract* record_end_span_event(\*args, \*\*kwargs)

Record the given event as the closing event for this Span.

Note that this method is supposed to be called only once per Span instance.

* **Return type:**
  `None`
* **Parameters:**
  * **args** (*Any*)
  * **kwargs** (*Any*)

#### span_id *: `str`*

A unique identifier for the span

#### start()

Start the span.

This includes calling the `on_start` method of the active SpanProcessors,
and recording the StartSpanEvent.

* **Return type:**
  `None`

#### start_time *: `Optional`[`int`]* *= None*

The timestamp of when the span was started

#### to_tracing_info(mask_sensitive_information=True)

Return a serialized version of the span’s information to be used for tracing.

* **Parameters:**
  **mask_sensitive_information** (`bool`) – Whether to mask potentially sensitive information from the span and its events
* **Return type:**
  `Dict`[`str`, `Any`]
* **Returns:**
  A dictionary containing the serialized information of this span

<a id="llm-generation-span"></a>

### *class* wayflowcore.tracing.span.LlmGenerationSpan(span_id=<factory>, name=None, start_time=None, end_time=None, events=<factory>, \_parent_span=None, \_end_event_was_triggered=False, \_span_was_appended_to_active_stack=False, \_started_span_processors=<factory>, llm=<factory>, prompt=<factory>)

Span for the generation of an LLM

* **Parameters:**
  * **span_id** (*str*)
  * **name** (*str* *|* *None*)
  * **start_time** (*int* *|* *None*)
  * **end_time** (*int* *|* *None*)
  * **events** (*List* *[*[*Event*](events.md#wayflowcore.events.event.Event) *]*)
  * **\_parent_span** ([*Span*](#wayflowcore.tracing.span.Span) *|* *None*)
  * **\_end_event_was_triggered** (*bool*)
  * **\_span_was_appended_to_active_stack** (*bool*)
  * **\_started_span_processors** (*List* *[*[*SpanProcessor*](#wayflowcore.tracing.spanprocessor.SpanProcessor) *]*)
  * **llm** ([*LlmModel*](llmmodels.md#wayflowcore.models.llmmodel.LlmModel))
  * **prompt** ([*Prompt*](llmmodels.md#wayflowcore.models.Prompt))

#### llm *: [`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)*

The LLM model that is generating

#### prompt *: [`Prompt`](llmmodels.md#wayflowcore.models.Prompt)*

The prompt that was given to the LLM

#### record_end_span_event(completion)

Record a LlmGenerationResponseEvent with the given information
as the closing event for this Span.

Note that this method is supposed to be called only once per Span instance.

* **Parameters:**
  **completion** ([`LlmCompletion`](llmmodels.md#wayflowcore.models.LlmCompletion)) – The completion returned by the LLM
* **Return type:**
  `None`

#### to_tracing_info(mask_sensitive_information=True)

Return a serialized version of the span’s information to be used for tracing.

* **Parameters:**
  **mask_sensitive_information** (`bool`) – Whether to mask potentially sensitive information from the span and its events
* **Return type:**
  `Dict`[`str`, `Any`]
* **Returns:**
  A dictionary containing the serialized information of this span

<a id="conversational-component-execution-span"></a>

### *class* wayflowcore.tracing.span.ConversationalComponentExecutionSpan(span_id=<factory>, name=None, start_time=None, end_time=None, events=<factory>, \_parent_span=None, \_end_event_was_triggered=False, \_span_was_appended_to_active_stack=False, \_started_span_processors=<factory>, conversational_component=<factory>)

Span for the execution of a ConversationalComponent

* **Parameters:**
  * **span_id** (*str*)
  * **name** (*str* *|* *None*)
  * **start_time** (*int* *|* *None*)
  * **end_time** (*int* *|* *None*)
  * **events** (*List* *[*[*Event*](events.md#wayflowcore.events.event.Event) *]*)
  * **\_parent_span** ([*Span*](#wayflowcore.tracing.span.Span) *|* *None*)
  * **\_end_event_was_triggered** (*bool*)
  * **\_span_was_appended_to_active_stack** (*bool*)
  * **\_started_span_processors** (*List* *[*[*SpanProcessor*](#wayflowcore.tracing.spanprocessor.SpanProcessor) *]*)
  * **conversational_component** ([*ConversationalComponent*](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent))

#### conversational_component *: [`ConversationalComponent`](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent)*

The ConversationalComponent being executed

#### record_end_span_event(execution_status)

Record a ConversationalComponentExecutionFinishedEvent with the given information
as the closing event for this Span.

Note that this method is supposed to be called only once per Span instance.

* **Parameters:**
  **execution_status** ([`ExecutionStatus`](conversation.md#wayflowcore.executors.executionstatus.ExecutionStatus)) – Indicates the status of the conversation (finished, yielding, etc.)
* **Return type:**
  `None`

#### to_tracing_info(mask_sensitive_information=True)

Return a serialized version of the span’s information to be used for tracing.

* **Parameters:**
  **mask_sensitive_information** (`bool`) – Whether to mask potentially sensitive information from the span and its events
* **Return type:**
  `Dict`[`str`, `Any`]
* **Returns:**
  A dictionary containing the serialized information of this span

<a id="conversation-span"></a>

### *class* wayflowcore.tracing.span.ConversationSpan(span_id=<factory>, name=None, start_time=None, end_time=None, events=<factory>, \_parent_span=None, \_end_event_was_triggered=False, \_span_was_appended_to_active_stack=False, \_started_span_processors=<factory>, conversation=<factory>)

* **Parameters:**
  * **span_id** (*str*)
  * **name** (*str* *|* *None*)
  * **start_time** (*int* *|* *None*)
  * **end_time** (*int* *|* *None*)
  * **events** (*List* *[*[*Event*](events.md#wayflowcore.events.event.Event) *]*)
  * **\_parent_span** ([*Span*](#wayflowcore.tracing.span.Span) *|* *None*)
  * **\_end_event_was_triggered** (*bool*)
  * **\_span_was_appended_to_active_stack** (*bool*)
  * **\_started_span_processors** (*List* *[*[*SpanProcessor*](#wayflowcore.tracing.spanprocessor.SpanProcessor) *]*)
  * **conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation))

#### conversation *: [`Conversation`](conversation.md#wayflowcore.conversation.Conversation)*

The conversation being executed

#### record_end_span_event(execution_status)

Record the given event as the closing event for this Span.

Note that this method is supposed to be called only once per Span instance.

* **Return type:**
  `None`
* **Parameters:**
  **execution_status** ([*ExecutionStatus*](conversation.md#wayflowcore.executors.executionstatus.ExecutionStatus))

#### to_tracing_info(mask_sensitive_information=True)

Return a serialized version of the span’s information to be used for tracing.

* **Parameters:**
  **mask_sensitive_information** (`bool`) – Whether to mask potentially sensitive information from the span and its events
* **Return type:**
  `Dict`[`str`, `Any`]
* **Returns:**
  A dictionary containing the serialized information of this span

<a id="tool-execution-span"></a>

### *class* wayflowcore.tracing.span.ToolExecutionSpan(span_id=<factory>, name=None, start_time=None, end_time=None, events=<factory>, \_parent_span=None, \_end_event_was_triggered=False, \_span_was_appended_to_active_stack=False, \_started_span_processors=<factory>, tool=<factory>, tool_request=<factory>)

* **Parameters:**
  * **span_id** (*str*)
  * **name** (*str* *|* *None*)
  * **start_time** (*int* *|* *None*)
  * **end_time** (*int* *|* *None*)
  * **events** (*List* *[*[*Event*](events.md#wayflowcore.events.event.Event) *]*)
  * **\_parent_span** ([*Span*](#wayflowcore.tracing.span.Span) *|* *None*)
  * **\_end_event_was_triggered** (*bool*)
  * **\_span_was_appended_to_active_stack** (*bool*)
  * **\_started_span_processors** (*List* *[*[*SpanProcessor*](#wayflowcore.tracing.spanprocessor.SpanProcessor) *]*)
  * **tool** ([*Tool*](tools.md#wayflowcore.tools.tools.Tool))
  * **tool_request** ([*ToolRequest*](tools.md#wayflowcore.tools.tools.ToolRequest))

#### record_end_span_event(output)

Record the given event as the closing event for this Span.

Note that this method is supposed to be called only once per Span instance.

* **Return type:**
  `None`
* **Parameters:**
  **output** (*Any*)

#### to_tracing_info(mask_sensitive_information=True)

Return a serialized version of the span’s information to be used for tracing.

* **Parameters:**
  **mask_sensitive_information** (`bool`) – Whether to mask potentially sensitive information from the span and its events
* **Return type:**
  `Dict`[`str`, `Any`]
* **Returns:**
  A dictionary containing the serialized information of this span

#### tool *: [`Tool`](tools.md#wayflowcore.tools.tools.Tool)*

The tool being executed

#### tool_request *: [`ToolRequest`](tools.md#wayflowcore.tools.tools.ToolRequest)*

The tool request (ID and arguments) with which the tool is being executed

<a id="step-invocation-span"></a>

### *class* wayflowcore.tracing.span.StepInvocationSpan(span_id=<factory>, name=None, start_time=None, end_time=None, events=<factory>, \_parent_span=None, \_end_event_was_triggered=False, \_span_was_appended_to_active_stack=False, \_started_span_processors=<factory>, step=<factory>, inputs=<factory>)

* **Parameters:**
  * **span_id** (*str*)
  * **name** (*str* *|* *None*)
  * **start_time** (*int* *|* *None*)
  * **end_time** (*int* *|* *None*)
  * **events** (*List* *[*[*Event*](events.md#wayflowcore.events.event.Event) *]*)
  * **\_parent_span** ([*Span*](#wayflowcore.tracing.span.Span) *|* *None*)
  * **\_end_event_was_triggered** (*bool*)
  * **\_span_was_appended_to_active_stack** (*bool*)
  * **\_started_span_processors** (*List* *[*[*SpanProcessor*](#wayflowcore.tracing.spanprocessor.SpanProcessor) *]*)
  * **step** ([*Step*](flows.md#wayflowcore.steps.step.Step))
  * **inputs** (*Dict* *[**str* *,* *Any* *]*)

#### inputs *: `Dict`[`str`, `Any`]*

The inputs with which the step is being executed

#### record_end_span_event(step_result)

Record the given event as the closing event for this Span.

Note that this method is supposed to be called only once per Span instance.

* **Return type:**
  `None`
* **Parameters:**
  **step_result** ([*StepResult*](flows.md#wayflowcore.steps.step.StepResult))

#### step *: [`Step`](flows.md#wayflowcore.steps.step.Step)*

The step being executed

#### to_tracing_info(mask_sensitive_information=True)

Return a serialized version of the span’s information to be used for tracing.

* **Parameters:**
  **mask_sensitive_information** (`bool`) – Whether to mask potentially sensitive information from the span and its events
* **Return type:**
  `Dict`[`str`, `Any`]
* **Returns:**
  A dictionary containing the serialized information of this span

<a id="context-provider-execution-span"></a>

### *class* wayflowcore.tracing.span.ContextProviderExecutionSpan(span_id=<factory>, name=None, start_time=None, end_time=None, events=<factory>, \_parent_span=None, \_end_event_was_triggered=False, \_span_was_appended_to_active_stack=False, \_started_span_processors=<factory>, context_provider=<factory>)

* **Parameters:**
  * **span_id** (*str*)
  * **name** (*str* *|* *None*)
  * **start_time** (*int* *|* *None*)
  * **end_time** (*int* *|* *None*)
  * **events** (*List* *[*[*Event*](events.md#wayflowcore.events.event.Event) *]*)
  * **\_parent_span** ([*Span*](#wayflowcore.tracing.span.Span) *|* *None*)
  * **\_end_event_was_triggered** (*bool*)
  * **\_span_was_appended_to_active_stack** (*bool*)
  * **\_started_span_processors** (*List* *[*[*SpanProcessor*](#wayflowcore.tracing.spanprocessor.SpanProcessor) *]*)
  * **context_provider** ([*ContextProvider*](contextproviders.md#wayflowcore.contextproviders.contextprovider.ContextProvider))

#### context_provider *: [`ContextProvider`](contextproviders.md#wayflowcore.contextproviders.contextprovider.ContextProvider)*

The context provider being executed

#### record_end_span_event(output)

Record the given event as the closing event for this Span.

Note that this method is supposed to be called only once per Span instance.

* **Return type:**
  `None`
* **Parameters:**
  **output** (*Any*)

#### to_tracing_info(mask_sensitive_information=True)

Return a serialized version of the span’s information to be used for tracing.

* **Parameters:**
  **mask_sensitive_information** (`bool`) – Whether to mask potentially sensitive information from the span and its events
* **Return type:**
  `Dict`[`str`, `Any`]
* **Returns:**
  A dictionary containing the serialized information of this span

## Span Processors

<a id="spanprocessor"></a>

### *class* wayflowcore.tracing.spanprocessor.SpanProcessor

Interface which allows hooks for Span start and end method invocations.

#### *abstract* force_flush(timeout_millis=30000)

Export all ended spans to the configured Exporter that have not yet been exported.

* **Parameters:**
  **timeout_millis** (`int`) – The time conceded to perform the flush
* **Return type:**
  `bool`
* **Returns:**
  False if the timeout is exceeded, True otherwise

#### *abstract* on_end(span)

Called when a Span is ended.

* **Parameters:**
  **span** ([`Span`](#wayflowcore.tracing.span.Span)) – The spans that ends
* **Return type:**
  `None`

#### *abstract* on_start(span)

Called when a Span is started.

* **Parameters:**
  **span** ([`Span`](#wayflowcore.tracing.span.Span)) – The spans that starts
* **Return type:**
  `None`

#### *abstract* shutdown()

Called when a Trace is shutdown.

* **Return type:**
  `None`

#### *abstract* startup()

Called when a Trace is started.

* **Return type:**
  `None`

<a id="simplespanprocessor"></a>

### *class* wayflowcore.tracing.spanprocessor.SimpleSpanProcessor(span_exporter, mask_sensitive_information=True)

Simple SpanProcessor implementation.

SimpleSpanProcessor is an implementation of SpanProcessor that
passes ended spans directly to the configured SpanExporter.

* **Parameters:**
  * **span_exporter** ([`SpanExporter`](#wayflowcore.tracing.spanexporter.SpanExporter)) – The SpanExporter to call at the end of each span
  * **mask_sensitive_information** (`bool`) – Whether to mask potentially sensitive information from the span and its events

#### force_flush(timeout_millis=30000)

Export all ended spans to the configured Exporter that have not yet been exported.

* **Parameters:**
  **timeout_millis** (`int`) – The time conceded to perform the flush
* **Return type:**
  `bool`
* **Returns:**
  False if the timeout is exceeded, True otherwise

#### on_end(span)

Called when a Span is ended.

* **Parameters:**
  **span** ([`Span`](#wayflowcore.tracing.span.Span)) – The spans that ends
* **Return type:**
  `None`

#### on_start(span)

Called when a Span is started.

* **Parameters:**
  **span** ([`Span`](#wayflowcore.tracing.span.Span)) – The spans that starts
* **Return type:**
  `None`

#### shutdown()

Called when a Trace is shutdown.

* **Return type:**
  `None`

#### startup()

Called when a Trace is started.

* **Return type:**
  `None`

## Span Exporter

<a id="spanexporter"></a>

### *class* wayflowcore.tracing.spanexporter.SpanExporter

Interface for exporting spans.

Interface to be implemented by services that want to export in their own format
the spans being recorded.

#### *abstract* export(spans, mask_sensitive_information=True)

Exports a batch of telemetry data.

* **Parameters:**
  * **spans** (`List`[[`Span`](#wayflowcore.tracing.span.Span)]) – The spans to be exported
  * **mask_sensitive_information** (`bool`) – Whether to mask potentially sensitive information from the span and its events
* **Return type:**
  `None`

#### *abstract* force_flush(timeout_millis=30000)

Ensure that all the pending exports are completed as soon as possible.

* **Parameters:**
  **timeout_millis** (`int`) – The time conceded to perform the flush
* **Return type:**
  `bool`
* **Returns:**
  False if the timeout is exceeded, True otherwise

#### *abstract* shutdown()

Shut down the exporter.

* **Return type:**
  `None`

#### *abstract* startup()

Start the exporter.

* **Return type:**
  `None`

## OpenTelemetry

<a id="otelsimplespanprocessor"></a>

### *class* wayflowcore.tracing.opentelemetry.spanprocessor.OtelSimpleSpanProcessor(span_exporter, resource=None, mask_sensitive_information=True)

WayFlow wrapper for the OpenTelemetry SimpleSpanProcessor

WayFlow wrapper for the OpenTelemetry SpanProcessor.

This class forwards the calls to WayFlow’s span processors to an OpenTelemetry one.

* **Parameters:**
  * **span_exporter** (`SpanExporter`) – The OpenTelemetry SpanExporter to use to export spans.
  * **resource** (`Optional`[`Resource`]) – The OpenTelemetry Resource to use in Spans.
  * **mask_sensitive_information** (`bool`) – Whether to mask potentially sensitive information from the span and its events

<a id="otelbatchspanprocessor"></a>

### *class* wayflowcore.tracing.opentelemetry.spanprocessor.OtelBatchSpanProcessor(span_exporter, resource=None, mask_sensitive_information=True)

WayFlow wrapper for the OpenTelemetry BatchSpanProcessor

WayFlow wrapper for the OpenTelemetry SpanProcessor.

This class forwards the calls to WayFlow’s span processors to an OpenTelemetry one.

* **Parameters:**
  * **span_exporter** (`SpanExporter`) – The OpenTelemetry SpanExporter to use to export spans.
  * **resource** (`Optional`[`Resource`]) – The OpenTelemetry Resource to use in Spans.
  * **mask_sensitive_information** (`bool`) – Whether to mask potentially sensitive information from the span and its events
