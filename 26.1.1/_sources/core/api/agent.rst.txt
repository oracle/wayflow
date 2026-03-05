Agents
======

This page presents all APIs and classes related to WayFlow agents.


.. |agentspec-icon| image:: ../../_static/icons/agentspec-icon.svg
   :width: 100px

.. grid:: 1

    .. grid-item-card:: |agentspec-icon|
        :link: https://oracle.github.io/agent-spec/api/agent.html
        :link-alt: Agent Spec - Agents API Reference

        Visit the Agent Spec API Documentation to learn more about Agent Components.


.. tip::

    Click the button above ↑ to visit the `Agent Spec Documentation <https://oracle.github.io/agent-spec/index.html>`_


Agent related classes
---------------------

Agent class
~~~~~~~~~~~

.. _agent:
.. autoclass:: wayflowcore.agent.Agent
    :exclude-members: execute

OCI Agent class
~~~~~~~~~~~~~~~

.. _ociagent:
.. autoclass:: wayflowcore.ociagent.OciAgent
    :exclude-members: execute

A2A Agent class
~~~~~~~~~~~~~~~

.. _a2aagent:
.. autoclass:: wayflowcore.a2a.a2aagent.A2AAgent
    :exclude-members: execute

DescribedFlow
~~~~~~~~~~~~~

.. _describedflow:
.. autoclass:: wayflowcore.tools.DescribedFlow

DescribedAgent
~~~~~~~~~~~~~~

.. _describedassistant:
.. autoclass:: wayflowcore.tools.DescribedAgent

Swarm class
~~~~~~~~~~~

.. _swarm:
.. autoclass:: wayflowcore.swarm.Swarm

.. _handoffmode:
.. autoclass:: wayflowcore.swarm.HandoffMode

ManagerWorkers class
~~~~~~~~~~~~~~~~~~~~

.. _managerworkers:
.. autoclass:: wayflowcore.managerworkers.ManagerWorkers


Agent Behavior Configuration
----------------------------

.. _callerinputmode:
.. autoclass:: wayflowcore.agent.CallerInputMode
