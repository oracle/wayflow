.. _events:

Events
======

This page presents all APIs and classes related to events in WayFlow.

Events
------

.. _event:
.. autoclass:: wayflowcore.events.event.Event

.. _llmgenerationrequestevent:
.. autoclass:: wayflowcore.events.event.LlmGenerationRequestEvent
   :exclude-members: to_tracing_info

.. _llmgenerationresponseevent:
.. autoclass:: wayflowcore.events.event.LlmGenerationResponseEvent
   :exclude-members: to_tracing_info

.. _conversationalcomponentexecutionstartedevent:
.. autoclass:: wayflowcore.events.event.ConversationalComponentExecutionStartedEvent
   :exclude-members: to_tracing_info

.. _conversationalcomponentexecutionfinishedevent:
.. autoclass:: wayflowcore.events.event.ConversationalComponentExecutionFinishedEvent
   :exclude-members: to_tracing_info

.. _conversationcreatedevent:
.. autoclass:: wayflowcore.events.event.ConversationCreatedEvent
   :exclude-members: to_tracing_info

.. _conversationmessageaddedevent:
.. autoclass:: wayflowcore.events.event.ConversationMessageAddedEvent
   :exclude-members: to_tracing_info

.. _conversationmessagestreamstartedevent:
.. autoclass:: wayflowcore.events.event.ConversationMessageStreamStartedEvent
   :exclude-members: to_tracing_info

.. _conversationmessagestreamchunkevent:
.. autoclass:: wayflowcore.events.event.ConversationMessageStreamChunkEvent
   :exclude-members: to_tracing_info

.. _conversationmessagestreamendedevent:
.. autoclass:: wayflowcore.events.event.ConversationMessageStreamEndedEvent
   :exclude-members: to_tracing_info

.. _conversationexecutionstartedevent:
.. autoclass:: wayflowcore.events.event.ConversationExecutionStartedEvent
   :exclude-members: to_tracing_info

.. _conversationexecutionfinishedevent:
.. autoclass:: wayflowcore.events.event.ConversationExecutionFinishedEvent
   :exclude-members: to_tracing_info

.. _toolexecutionstartevent:
.. autoclass:: wayflowcore.events.event.ToolExecutionStartEvent
   :exclude-members: to_tracing_info

.. _toolexecutionstreamingchunkreceivedevent:
.. autoclass:: wayflowcore.events.event.ToolExecutionStreamingChunkReceivedEvent
   :exclude-members: to_tracing_info

.. _toolexecutionresultevent:
.. autoclass:: wayflowcore.events.event.ToolExecutionResultEvent
   :exclude-members: to_tracing_info

.. _toolconfirmationrequeststartevent:
.. autoclass:: wayflowcore.events.event.ToolConfirmationRequestStartEvent
   :exclude-members: to_tracing_info

.. _toolconfirmationrequestendevent:
.. autoclass:: wayflowcore.events.event.ToolConfirmationRequestEndEvent
   :exclude-members: to_tracing_info

.. _stepinvocationstartevent:
.. autoclass:: wayflowcore.events.event.StepInvocationStartEvent
   :exclude-members: to_tracing_info

.. _stepinvocationresultevent:
.. autoclass:: wayflowcore.events.event.StepInvocationResultEvent
   :exclude-members: to_tracing_info

.. _contextproviderexecutionrequestevent:
.. autoclass:: wayflowcore.events.event.ContextProviderExecutionRequestEvent
   :exclude-members: to_tracing_info

.. _contextproviderexecutionresultevent:
.. autoclass:: wayflowcore.events.event.ContextProviderExecutionResultEvent
   :exclude-members: to_tracing_info

.. _flowexecutioniterationstartedevent:
.. autoclass:: wayflowcore.events.event.FlowExecutionIterationStartedEvent
   :exclude-members: to_tracing_info

.. _flowexecutioniterationfinishedevent:
.. autoclass:: wayflowcore.events.event.FlowExecutionIterationFinishedEvent
   :exclude-members: to_tracing_info

.. _agentexecutioniterationstartedevent:
.. autoclass:: wayflowcore.events.event.AgentExecutionIterationStartedEvent
   :exclude-members: to_tracing_info

.. _agentexecutioniterationfinishedevent:
.. autoclass:: wayflowcore.events.event.AgentExecutionIterationFinishedEvent
   :exclude-members: to_tracing_info

.. _exceptionraisedevent:
.. autoclass:: wayflowcore.events.event.ExceptionRaisedEvent
   :exclude-members: to_tracing_info

.. _agentnextactiondecisionstartevent:
.. autoclass:: wayflowcore.events.event.AgentNextActionDecisionStartEvent
   :exclude-members: to_tracing_info

.. _agentdecidednextactionevent:
.. autoclass:: wayflowcore.events.event.AgentDecidedNextActionEvent
   :exclude-members: to_tracing_info

.. seealso::
   See the table of supported events with one line description for each in the :ref:`How to Use the Event System <listofsupportedevents>`.

.. _eventlisteners:

Event Listeners
---------------

.. _eventlistener:
.. autoclass:: wayflowcore.events.eventlistener.EventListener

.. _genericeventlistener:
.. autoclass:: wayflowcore.events.eventlistener.GenericEventListener

.. _registereventlisteners:
.. autofunction:: wayflowcore.events.eventlistener.register_event_listeners

.. _geteventlisteners:
.. autofunction:: wayflowcore.events.eventlistener.get_event_listeners

.. _recordevent:
.. autofunction:: wayflowcore.events.eventlistener.record_event
