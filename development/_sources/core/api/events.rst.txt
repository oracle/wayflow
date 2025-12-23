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
