.. _top-howtoplugins:

====================================
How to Create New WayFlow Components
====================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_plugins.py
        :link-alt: WayFlow plugins how-to script

        Python script/notebook for this guide.


.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`LLM configuration <../howtoguides/llm_from_different_providers>`
    - :doc:`Using agents <agents>`

WayFlow Plugins are the expected mean that users can use to introduce new concepts and components, or extensions to existing ones,
such that they can be integrated seamlessly into the serialization, deserialization, and Agent Spec conversion processes
of WayFlow.

In this guide, you will learn how to build a WayFlow plugin to introduce a new custom component in WayFlow, and make sure
that it can be serialized, deserialized, and converted to Agent Spec.

You are going to build a specialized :ref:`ServerTool <servertool>` that reads the content of a file given its path.
Then we are going to use this tool as part of an :ref:`Agent <agent>`, build the plugins, and show how to use them
for WayFlow's serialization and Agent Spec conversion.

Basic usage
===========

As first step, we build our new tool extension. We call it ``ReadFileTool``, and we give it an attribute
to specify which file extensions are allowed to be read. The tool implementation in this example is mocked,
and it just returns the content of two predefined filepaths.

.. literalinclude:: ../code_examples/howto_plugins.py
    :language: python
    :start-after: .. start-##_Create_the_new_tool_to_read_a_file
    :end-before: .. end-##_Create_the_new_tool_to_read_a_file

In this example we extended ``Tool``, but a new component that does not inherit from existing concepts can be created,
and it can be connected to the serialization mechanism by simply extending the ``SerializableObject`` interface.
Note that there are also extensions of the ``SerializableObject`` class, like the ``SerializableDataclass``,
which offers basic serialization implementation for ``dataclass`` annotated classes.

We can now build our agent: we select the LLM we want to use to orchestrate it, write custom instructions to
inform it about which files are available, and give it instructions to read them if needed.

.. literalinclude:: ../code_examples/howto_plugins.py
    :language: python
    :start-after: .. start-##_Create_the_agent
    :end-before: .. end-##_Create_the_agent

As already mentioned at the beginning of this guide, WayFlow plugins take also care of the Agent Spec conversion.
Therefore, in order to create complete WayFlow plugins, we have to create the new tool also in Agent Spec.
To do that, we extend the ``ServerTool`` implementation from ``pyagentspec`` and we add the ``allowed_extensions`` attribute.
Then we create the Agent Spec plugins that will take care of the serialization/deserialization to/from Agent Spec.

.. literalinclude:: ../code_examples/howto_plugins.py
    :language: python
    :start-after: .. start-##_Create_Agent_Spec_components_and_plugins
    :end-before: .. end-##_Create_Agent_Spec_components_and_plugins

Now that the Agent Spec plugins are ready, we can use them in our WayFlow plugins for the ReadFileTool.
We build the :ref:`WayflowSerializationPlugin <wayflowserializationplugin>` and the :ref:`WayflowDeserializationPlugin <wayflowdeserializationplugin>`
by specifying a plugin name, a version, the Agent Spec plugins (if any) that are required to serialize and deserialize
the new Tool, and implement the conversion logic for it.

.. literalinclude:: ../code_examples/howto_plugins.py
    :language: python
    :start-after: .. start-##_Create_Wayflow_plugins_for_serialization_and_Agent_Spec_conversion
    :end-before: .. end-##_Create_Wayflow_plugins_for_serialization_and_Agent_Spec_conversion

Now that we have built the plugins, we can use them in serialization and deserialization.

.. literalinclude:: ../code_examples/howto_plugins.py
    :language: python
    :start-after: .. start-##_Serialize_and_deserialize_the_agent
    :end-before: .. end-##_Serialize_and_deserialize_the_agent

Finally, we can try to run our agent and ask it some information contained in a file.

.. literalinclude:: ../code_examples/howto_plugins.py
    :language: python
    :start-after: .. start-##_Agent_Execution
    :end-before: .. end-##_Agent_Execution


Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_plugins.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_plugins.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_plugins.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_plugins.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``AgentPlugin``
    - ``MessageTransformPlugin``
    - ``PromptTemplatePlugin``
    - ``OutputParserPlugin``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


Next steps
==========

Now that you have learned how to build WayFlow plugins, you may proceed to
:doc:`Load and Execute an Agent Spec Configuration <howto_execute_agentspec_with_wayflowcore>`.


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoplugins>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_plugins.py
    :language: python
    :linenos:
