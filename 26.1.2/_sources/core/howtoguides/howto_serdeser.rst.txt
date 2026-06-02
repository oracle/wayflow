.. _top-serdeser:

=================================================
How to Serialize and Deserialize Flows and Agents
=================================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_serdeser.py
        :link-alt: Serialization and deserialization how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Flows <../tutorials/basic_flow>`
    - :doc:`Agents <../tutorials/basic_agent>`

Assistant serialization is a crucial feature in WayFlow that allows you to save and load :ref:`Agents <agent>` and :ref:`Flows <flow>`,
making it easy to persist their configurations and reuse them as needed.

In this guide, you will learn how to:

- Serialize a simple Agent or Flow and deserialize it back into an executable assistant.
- Use serialization for more complex assistants using tools.

.. image:: ../_static/howto/ser_deser.svg
    :align: center
    :scale: 100%
    :alt: Serialization/deserialization of Agents and Flows in WayFlow


Saving and loading simple assistants
====================================

This section shows you how to serialize and reload WayFlow :ref:`Agents <agent>` and :ref:`Flows <flow>`.


Flows
^^^^^^

Start by creating a simple ``Flow`` that takes a user question as input and responds using an LLM.

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Simple_Flow_Creation
    :end-before: .. end-##_Simple_Flow_Creation

**API Reference:** :ref:`Flow <flow>` | :ref:`PromptExecutionStep <promptexecutionstep>`

Once you have built the flow, you can serialize it using the ``serialize`` helper function.

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Simple_Flow_Serialization
    :end-before: .. end-##_Simple_Flow_Serialization

**API Reference:** :ref:`serialize <serialize>`

Then, save the serialized flow as a regular text file.

To deserialize the flow configuration back, use the ``autodeserialize`` helper function.

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Simple_Flow_Deserialization
    :end-before: .. end-##_Simple_Flow_Deserialization

**API Reference:** :ref:`autodeserialize <autodeserialize>`

After deserialization, the flow is ready to execute like any other WayFlow assistant.

.. note::
    The serialized configuration file contains all elements that compose the :ref:`Flow <flow>`.
    However, this file is not intended to be human-readable and should only be handled using the ``serialize`` and ``autodeserialize`` functions.


Agents
^^^^^^

Continue to building a simple conversational ``Agent`` that can answer user questions.

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Simple_Agent_Creation
    :end-before: .. end-##_Simple_Agent_Creation

**API Reference:** :ref:`Agent <agent>`

Once you have built the agent, you can serialize it using the ``serialize`` helper function.

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Simple_Agent_Serialization
    :end-before: .. end-##_Simple_Agent_Serialization

**API Reference:** :ref:`serialize <serialize>`

Then, save the serialized agent as a regular text file.

To deserialize the agent configuration back, use the ``autodeserialize`` helper function.

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Simple_Agent_Deserialization
    :end-before: .. end-##_Simple_Agent_Deserialization

**API Reference:** :ref:`autodeserialize <autodeserialize>`

Similar to the Flow example above, once deserialized, the agent is ready to execute like any other WayFlow assistant.


Saving and loading assistants equipped with tools
=================================================

In this more advanced example, you will build assistants that use WayFlow Tools (such as :ref:`ServerTool <servertool>`).
These assistants require additional code to deserialize them into executable assistants.


Flows
^^^^^^

Create a ``Flow`` that asks the user for an input text, counts the number of characters, and generates a message with the result.

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Complex_Flow_Creation
    :end-before: .. end-##_Complex_Flow_Creation

**API Reference:** :ref:`InputMessageStep <inputmessagestep>` |
:ref:`OutputMessageStep <outputmessagestep>` | :ref:`ToolExecutionStep <toolexecutionstep>` |
:ref:`ServerTool <servertool>`

Serialize your flow just like any other assistant.

To deserialize the flow, you need to provide context about the tool used in the original flow.
This can be done using ``DeserializationContext``.

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Complex_Flow_Deserialization
    :end-before: .. end-##_Complex_Flow_Deserialization

After registering the tool in the dictionary of tools, pass the deserialization context to the ``autodeserialize`` function to deserialize the flow.

.. important::
    Ensure that tool names in ``DeserializationContext.registered_tools`` are unique to avoid conflicts.


Agents
^^^^^^

Create an ``Agent`` that can access a tool to count the number of characters in a given text (this agent is equivalent to the flow example above).

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Complex_Agent_Creation
    :end-before: .. end-##_Complex_Agent_Creation

**API Reference:** :ref:`ServerTool <servertool>`

Serialize your agent just like any other assistant.

Similar to the Flow example, deserializing the agent requires providing context about the tool used in the original agent.
This can be done using ``DeserializationContext``.

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Complex_Agent_Deserialization
    :end-before: .. end-##_Complex_Agent_Deserialization

After registering the tool in the dictionary of tools, pass the deserialization context to the ``autodeserialize`` function to deserialize the agent.

.. important::
    Ensure that tool names in ``DeserializationContext.registered_tools`` are unique to avoid conflicts.


Agent Spec Exporting/Loading
============================

You can export the flow or agent configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Export_Config_to_Agent_Spec
    :end-before: .. end-##_Export_Config_to_Agent_Spec

And load it back using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_serdeser.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_Config
    :end-before: .. end-##_Load_Agent_Spec_Config


Recap
=====

In this guide, you learned how to serialize WayFlow :ref:`Agents <agent>` and :ref:`Flows <flow>`, as well as how to handle deserialization for assistants that use tools.


Next steps
==========

Having learned how to serialize and deserialize assistants built with WayFlow, you may now proceed to:

- :doc:`How to Create Conditional Transitions in Flows <conditional_flows>`
- :doc:`How to Create a ServerTool from a Flow <create_a_tool_from_a_flow>`


Full code
=========

Click on the card at the :ref:`top of this page <top-serdeser>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_serdeser.py
    :language: python
    :linenos:
