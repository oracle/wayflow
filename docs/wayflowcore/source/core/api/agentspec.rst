.. _agentspec_adapters:

Agent Spec Adapters
===================

This page presents all APIs and classes related to Agent Spec and WayFlow.


.. |agentspec-icon| image:: ../../_static/icons/agentspec-icon.svg
   :width: 100px

.. grid:: 1

    .. grid-item-card:: |agentspec-icon|
        :link: https://oracle.github.io/agent-spec/api/index.html
        :link-alt: Agent Spec - API Reference

        Visit the Agent Spec API Documentation to learn more about the native Agent Spec Components.


.. tip::

    Click the button above ↑ to visit the `Agent Spec Documentation <https://oracle.github.io/agent-spec/index.html>`_



.. _agentspecexporter:
.. autoclass:: wayflowcore.agentspec.agentspecexporter.AgentSpecExporter


.. _agentspecloader:
.. autoclass:: wayflowcore.agentspec.runtimeloader.AgentSpecLoader


Agent Spec Tracing
==================

This event listener makes WayFlow components emit traces according to the Agent Spec Tracing standard.

.. _agentspeceventlistener:
.. autoclass:: wayflowcore.agentspec.tracing.AgentSpecEventListener


Custom Components
=================

These are example of custom Agent Spec components that can be used in Agent Spec configurations and
loaded/executed in WayFlow.

.. note::
    Both extended and plugin components are introduced to allow assistant developers to export
    their WayFlow assistants to Agent Spec.

    They may be added as native Agent Spec components with modified component name and fields.

Extended Components
-------------------

Extended components are Agent Spec components extended with additional fields.

.. _agentspecagent:
.. autoclass:: wayflowcore.agentspec.components.agent.ExtendedAgent
    :exclude-members: model_post_init, model_config

.. _agentspecflow:
.. autoclass:: wayflowcore.agentspec.components.flow.ExtendedFlow
    :exclude-members: model_post_init, model_config

.. _agentspectoolnode:
.. autoclass:: wayflowcore.agentspec.components.nodes.ExtendedToolNode
    :exclude-members: model_post_init, model_config

.. _agentspecllmnode:
.. autoclass:: wayflowcore.agentspec.components.nodes.ExtendedLlmNode
    :exclude-members: model_post_init, model_config

.. _agentspecmapnode:
.. autoclass:: wayflowcore.agentspec.components.nodes.ExtendedMapNode
    :exclude-members: model_post_init, model_config


Plugin Components
-----------------

Plugin components are new components that are not natively supported in Agent Spec.


Agentic patterns
^^^^^^^^^^^^^^^^

.. _agentspecswarmpattern:
.. autoclass:: wayflowcore.agentspec.components.swarm.PluginSwarm
    :exclude-members: model_post_init, model_config


Messages
^^^^^^^^

.. _agentspecmessage:
.. autoclass:: wayflowcore.agentspec.components.messagelist.PluginMessage
    :exclude-members: model_post_init, model_config

.. _agentspectextcontent:
.. autoclass:: wayflowcore.agentspec.components.messagelist.PluginTextContent
    :exclude-members: model_post_init, model_config

.. _agentspecimagecontent:
.. autoclass:: wayflowcore.agentspec.components.messagelist.PluginImageContent
    :exclude-members: model_post_init, model_config

.. _agentspecregexpattern:
.. autoclass:: wayflowcore.agentspec.components.outputparser.PluginRegexPattern
    :exclude-members: model_post_init, model_config

.. _agentspecoutputparser:
.. autoclass:: wayflowcore.agentspec.components.outputparser.PluginOutputParser

.. _agentspecregexoutputparser:
.. autoclass:: wayflowcore.agentspec.components.outputparser.PluginRegexOutputParser
    :exclude-members: model_post_init, model_config

.. _agentspecjsonoutputparser:
.. autoclass:: wayflowcore.agentspec.components.outputparser.PluginJsonOutputParser
    :exclude-members: model_post_init, model_config

.. _agentspectooloutputparser:
.. autoclass:: wayflowcore.agentspec.components.outputparser.PluginToolOutputParser
    :exclude-members: model_post_init, model_config

.. _agentspecjsontooloutputparser:
.. autoclass:: wayflowcore.agentspec.components.outputparser.PluginJsonToolOutputParser
    :exclude-members: model_post_init, model_config

.. _agentspecpythontooloutputparser:
.. autoclass:: wayflowcore.agentspec.components.outputparser.PluginPythonToolOutputParser
    :exclude-members: model_post_init, model_config

.. _agentspecreacttooloutputparser:
.. autoclass:: wayflowcore.agentspec.components.outputparser.PluginReactToolOutputParser
    :exclude-members: model_post_init, model_config

.. _agentspecprompttemplate:
.. autoclass:: wayflowcore.agentspec.components.template.PluginPromptTemplate
    :exclude-members: model_post_init, model_config

.. _agentspeccoalescesystemmessagestransform:
.. autoclass:: wayflowcore.agentspec.components.transforms.PluginCoalesceSystemMessagesTransform
    :exclude-members: model_post_init, model_config

.. _agentspecremoveemptynonusermessagetransform:
.. autoclass:: wayflowcore.agentspec.components.transforms.PluginRemoveEmptyNonUserMessageTransform
    :exclude-members: model_post_init, model_config

.. _agentspecappendtrailingsystemmessagetousermessagetransform:
.. autoclass:: wayflowcore.agentspec.components.transforms.PluginAppendTrailingSystemMessageToUserMessageTransform
    :exclude-members: model_post_init, model_config

.. _agentspecllamamergetoolrequestsandcallstransform:
.. autoclass:: wayflowcore.agentspec.components.transforms.PluginLlamaMergeToolRequestAndCallsTransform
    :exclude-members: model_post_init, model_config

.. _agentspecreactmergetoolrequestsandcallstransform:
.. autoclass:: wayflowcore.agentspec.components.transforms.PluginReactMergeToolRequestAndCallsTransform
    :exclude-members: model_post_init, model_config

.. _agentspeccanonicalizationmessagetransform:
.. autoclass:: wayflowcore.agentspec.components.transforms.PluginCanonicalizationMessageTransform
    :exclude-members: model_post_init, model_config

.. _agentspecsplitpromptonmarkermessagetransform:
.. autoclass:: wayflowcore.agentspec.components.transforms.PluginSplitPromptOnMarkerMessageTransform
    :exclude-members: model_post_init, model_config

Nodes
^^^^^

.. _agentspeccatchexceptionnode:
.. autoclass:: wayflowcore.agentspec.components.nodes.PluginCatchExceptionNode
    :exclude-members: model_post_init, model_config

.. _agentspecextractnode:
.. autoclass:: wayflowcore.agentspec.components.nodes.PluginExtractNode
    :exclude-members: model_post_init, model_config

.. _agentspecinputmessagenode:
.. autoclass:: wayflowcore.agentspec.components.nodes.PluginInputMessageNode
    :exclude-members: model_post_init, model_config

.. _agentspecoutputmessagenode:
.. autoclass:: wayflowcore.agentspec.components.nodes.PluginOutputMessageNode
    :exclude-members: model_post_init, model_config

.. _agentspecdatastorecreatenode:
.. autoclass:: wayflowcore.agentspec.components.datastores.nodes.PluginDatastoreCreateNode
    :exclude-members: model_post_init, model_config

.. _agentspecdatastoredeletenode:
.. autoclass:: wayflowcore.agentspec.components.datastores.nodes.PluginDatastoreDeleteNode
    :exclude-members: model_post_init, model_config

.. _agentspecdatastorelistnode:
.. autoclass:: wayflowcore.agentspec.components.datastores.nodes.PluginDatastoreListNode
    :exclude-members: model_post_init, model_config

.. _agentspecdatastorequerynode:
.. autoclass:: wayflowcore.agentspec.components.datastores.nodes.PluginDatastoreQueryNode
    :exclude-members: model_post_init, model_config

.. _agentspecdatastoreupdatenode:
.. autoclass:: wayflowcore.agentspec.components.datastores.nodes.PluginDatastoreUpdateNode
    :exclude-members: model_post_init, model_config

Context Providers
^^^^^^^^^^^^^^^^^

.. _agentspeccontextprovider:
.. autoclass:: wayflowcore.agentspec.components.contextprovider.PluginContextProvider
    :exclude-members: model_post_init, model_config

Tools
^^^^^

.. _agentspecplugintoolrequest:
.. autoclass:: wayflowcore.agentspec.components.tools.PluginToolRequest

.. _agentspecplugintoolresult:
.. autoclass:: wayflowcore.agentspec.components.tools.PluginToolResult


Context
^^^^^^^

.. autoclass:: wayflowcore.agentspec._runtimeconverter.AgentSpecToWayflowConversionContext

.. autoclass:: wayflowcore.agentspec._agentspecconverter.WayflowToAgentSpecConversionContext
