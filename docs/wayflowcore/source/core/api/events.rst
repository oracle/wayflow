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

.. _llmgenerationresponseevent:
.. autoclass:: wayflowcore.events.event.LlmGenerationResponseEvent

.. _conversationalcomponentexecutionstartedevent:
.. autoclass:: wayflowcore.events.event.ConversationalComponentExecutionStartedEvent

.. _conversationalcomponentexecutionfinishedevent:
.. autoclass:: wayflowcore.events.event.ConversationalComponentExecutionFinishedEvent

.. _conversationcreatedevent:
.. autoclass:: wayflowcore.events.event.ConversationCreatedEvent

.. _conversationmessageaddedevent:
.. autoclass:: wayflowcore.events.event.ConversationMessageAddedEvent

.. _conversationmessagestreamstartedevent:
.. autoclass:: wayflowcore.events.event.ConversationMessageStreamStartedEvent

.. _conversationmessagestreamchunkevent:
.. autoclass:: wayflowcore.events.event.ConversationMessageStreamChunkEvent

.. _conversationmessagestreamendedevent:
.. autoclass:: wayflowcore.events.event.ConversationMessageStreamEndedEvent

.. _conversationexecutionstartedevent:
.. autoclass:: wayflowcore.events.event.ConversationExecutionStartedEvent

.. _conversationexecutionfinishedevent:
.. autoclass:: wayflowcore.events.event.ConversationExecutionFinishedEvent

.. _toolexecutionstartevent:
.. autoclass:: wayflowcore.events.event.ToolExecutionStartEvent

.. _toolexecutionresultevent:
.. autoclass:: wayflowcore.events.event.ToolExecutionResultEvent

.. _toolconfirmationrequeststartevent:
.. autoclass:: wayflowcore.events.event.ToolConfirmationRequestStartEvent

.. _toolconfirmationrequestendevent:
.. autoclass:: wayflowcore.events.event.ToolConfirmationRequestEndEvent

.. _stepinvocationstartevent:
.. autoclass:: wayflowcore.events.event.StepInvocationStartEvent

.. _stepinvocationresultevent:
.. autoclass:: wayflowcore.events.event.StepInvocationResultEvent

.. _contextproviderexecutionrequestevent:
.. autoclass:: wayflowcore.events.event.ContextProviderExecutionRequestEvent

.. _contextproviderexecutionresultevent:
.. autoclass:: wayflowcore.events.event.ContextProviderExecutionResultEvent

.. _flowexecutioniterationstartedevent:
.. autoclass:: wayflowcore.events.event.FlowExecutionIterationStartedEvent

.. _flowexecutioniterationfinishedevent:
.. autoclass:: wayflowcore.events.event.FlowExecutionIterationFinishedEvent

.. _agentexecutioniterationstartedevent:
.. autoclass:: wayflowcore.events.event.AgentExecutionIterationStartedEvent

.. _agentexecutioniterationfinishedevent:
.. autoclass:: wayflowcore.events.event.AgentExecutionIterationFinishedEvent

.. _exceptionraisedevent:
.. autoclass:: wayflowcore.events.event.ExceptionRaisedEvent

.. _agentnextactiondecisionstartevent:
.. autoclass:: wayflowcore.events.event.AgentNextActionDecisionStartEvent

.. _agentdecidednextactionevent:
.. autoclass:: wayflowcore.events.event.AgentDecidedNextActionEvent


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
