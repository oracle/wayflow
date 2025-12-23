.. _top-howtoserializeconversations:

==============================================
How to Serialize and Deserialize Conversations
==============================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_serialize_conversations.py
        :link-alt: Serialize conversation how-to script

        Python script/notebook for this guide.



.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Agents <../tutorials/basic_agent>`
    - :doc:`Flows <../tutorials/basic_flow>`

When building AI assistants, it id=s often necessary to save the state of a conversation to disk and restore it later.
This is essential for creating persistent applications that can:

- Resume conversations after an application restart
- Save user sessions for later continuation
- Implement conversation history and analytics
- Support multi-session workflows

In this tutorial, you will learn how to:

- **Serialize Agent conversations** to JSON files
- **Serialize Flow conversations** at any point during execution
- **Deserialize and resume** both types of conversations
- **Build persistent conversation loops** that survive application restarts

Concepts shown in this guide
============================

- :ref:`serialize <serialize>` to convert conversations to storable format
- :ref:`autodeserialize <autodeserialize>` to restore conversations from storage
- Handling conversation state persistence for both Agents and Flows

Basic Serialization
===================

Step 1. Add imports and configure LLM
-------------------------------------

Start by importing the necessary packages for serialization:

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Imports_for_this_guide
   :end-before: .. end-##_Imports_for_this_guide

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst


Step 2. Create storage functions
--------------------------------

Define helper functions to store and load conversations:

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Create_storage_functions
   :end-before: .. end-##_Create_storage_functions

These functions:

- Use WayFlow's ``serialize()`` to convert conversations to a storable format
- Store multiple conversations in a single JSON file indexed by conversation ID
- Use ``autodeserialize()`` to restore the original conversation objects

Serializing Agent conversations
===============================

Agent conversations can be serialized at any point during execution:

Step 1. Create an Agent
-----------------------

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Creating_an_agent
   :end-before: .. end-##_Creating_an_agent

Step 2. Run the conversation
----------------------------

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Run_the_agent
   :end-before: .. end-##_Run_the_agent


Step 3. Serialize the conversation
----------------------------------

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Serialize_the_conversation
   :end-before: .. end-##_Serialize_the_conversation

Step 4. Deserialize the conversation
------------------------------------

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Deserialize_the_conversation
   :end-before: .. end-##_Deserialize_the_conversation


Key points:

- Each conversation has a unique ``conversation_id``
- The entire conversation state is preserved, including message history
- Loaded conversations retain their complete state and can resume execution
- Access messages through ``conversation.message_list.messages``

Serializing Flow Conversations
==============================

Flow conversations require special attention as they can be serialized mid-execution:

Step 1. Create a Flow
---------------------

First, create a flow using the builder function.

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Creating_a_flow
   :end-before: .. end-##_Creating_a_flow

Step 2. Run the conversation
----------------------------

Then start and run the flow conversation.

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Run_the_flow
   :end-before: .. end-##_Run_the_flow


Step 3. Serialize during execution
----------------------------------

You can now serialize the conversation during its execution, for instance
here the flow is requesting the user to input some information but you can
serialize the conversation and resume it later.

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Serialize_before_providing_user_input
   :end-before: .. end-##_Serialize_before_providing_user_input


Step 4. Deserialize the conversation
------------------------------------

You can now load back the serialized conversation.

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Deserialize_the_flow_conversation
   :end-before: .. end-##_Deserialize_the_flow_conversation

Step 5. Resume the conversation execution
-----------------------------------------

You can resume the conversation from its state before serializing it.

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Resume_the_conversation_execution
   :end-before: .. end-##_Resume_the_conversation_execution


Important considerations:

- Flows can be serialized while waiting for user input
- The loaded Flow conversation resumes exactly where it left off
- User input can be provided to the loaded conversation to continue execution

Building persistent applications
================================

For real-world applications, you'll want to create persistent conversation loops:


.. literalinclude:: ../code_examples/howto_serialize_conversations.py
   :language: python
   :start-after: .. start-##_Creating_a_persistent_conversation_loop
   :end-before: .. end-##_Creating_a_persistent_conversation_loop

This function:

- Loads existing conversations or starts new ones
- Saves state before waiting for user input
- Allows users to exit and resume later
- Returns the conversation ID for future reference

Best Practices
==============

1. **Save before user input**: Always serialize conversations before waiting for user input to prevent data loss.

2. **Use unique IDs**: Store conversations using their built-in ``conversation_id`` to avoid conflicts.

3. **Handle errors gracefully**: Wrap deserialization in try-except blocks to handle missing or corrupted data.

4. **Consider storage format**: While JSON is human-readable, consider other formats for production use.

5. **Version your serialization**: Consider adding version information to handle future schema changes.

Limitations
===========

- **Tool state**: When using tools with Agents, ensure tools are stateless or their state is managed separately.
- **Large conversations**: Very long conversations may result in large serialized files.
- **Binary data**: The default JSON serialization does not handle binary data directly.

Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_serialize_conversations.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_serialize_conversations.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_serialize_conversations.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_serialize_conversations.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config



Next steps
==========

In this guide, you learned how to:

- Serialize both Agent and Flow conversations
- Restore conversations and continue execution
- Build persistent conversation loops
- Handle conversation state across application restarts

Having learned how to serialize a conversation, you may now proceed to :doc:`How to Serialize and Deserialize Flows and Agents <howto_serdeser>`.

- :doc:`Serialization <howto_serdeser>`


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoserializeconversations>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/tutorial_agent.py
   :language: python
   :linenos:
