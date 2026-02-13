.. _top-howtolongmessage:

============================================
How to Enable Agents to Handle Long Contexts
============================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_long_context.py
        :link-alt: Long message how-to script

        Python script/notebook for this guide.


.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`LLM configuration <../howtoguides/llm_from_different_providers>`
    - :doc:`Using agents <agents>`
    - :doc:`Advanced Prompting Techniques <howto_prompttemplate>`


In agentic systems, conversations can become lengthy, building up extensive context over many interactions.
Large Language Models (LLMs) have limits on the context they can process effectively, which may result in reduced
performance or errors when these limits are surpassed. Long context also incur higher costs.

To address these performance issues and reduce cost, you can apply techniques that reduce the context size while retaining key information.

This guide demonstrates three methods for reducing context size using built-in transforms:

- **Summarizing long messages** using :ref:`MessageSummarizationTransform <messagesummarizationtransform>`: Individual messages that exceed size limits (such as large tool outputs or long user inputs) are automatically summarized using an LLM.
- **Summarizing long conversations** using :ref:`ConversationSummarizationTransform <conversationsummarizationtransform>`: When conversations become too lengthy, older messages are summarized to maintain context while keeping the total size manageable.
- **Using both transforms together**: Combining both approaches for comprehensive context management.


This guide shows how to use built-in :ref:`MessageTransform <messagetransform>` objects to reduce the context size in agents.

Introduction
============

Message Transforms
~~~~~~~~~~~~~~~~~~

A :ref:`MessageTransform <MessageTransform>` is a transformation applied to a list of messages before they are sent to the LLM powering the agent. You can learn
more about them in the :doc:`Advanced Prompting Techniques <howto_prompttemplate>` guide.

In this guide, we use built-in message transforms to adjust the agent's chat history by passing them directly to the :ref:`Agent <agent>` constructor.

LLM Setup
~~~~~~~~~

There are multiple ways to define an LLM in WayFlow depending on the provider.
Choose the one adapted to your needs:

.. include:: ../_components/llm_config_tabs.rst

In this guide, we will use `VllmModel`.  We can use two different LLMs - a capable LLM as the agent and a fast LLM as the summarizer. Note that if conversations include images, the summarization LLM should support image processing:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Define_LLMS
    :end-before: .. end-##_Define_LLMS



Summarizing Long Messages
=========================

We use the built-in :ref:`MessageSummarizationTransform <messagesummarizationtransform>` to automatically summarize individual messages that exceed a specified size limit, including tool outputs, user messages and images.

.. literalinclude:: ../code_examples/howto_long_context.py
   :language: python
   :start-after: .. start-##_Create_MessageSummarizationTransform
   :end-before: .. end-##_Create_MessageSummarizationTransform

.. note::
   When creating :ref:`MessageSummarizationTransform <messagesummarizationtransform>` without specifying a ``datastore``, it will initialize a default :ref:`InMemoryDatastore <inmemorydatastore>` for caching, which is only suitable for prototyping. This will raise a user warning indicating that in-memory datastores are not recommended for production systems.
   For production systems, you can use :ref:`OracleDatabaseDatastore <oracledatabasedatastore>` or :ref:`PostgresDatabaseDatastore <postgresdatabasedatastore>`.

Let's integrate the :ref:`MessageSummarizationTransform <messagesummarizationtransform>` into the :ref:`Agent <agent>`:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Create_Agent
    :end-before: .. end-##_Create_Agent

Before seeing an example, let's define a token counting event listener that will help us see the impact of our summarizer on token consumption.

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Create_Token_Event_Listener
    :end-before: .. end-##_Create_Token_Event_Listener

In this example, we run a conversation where the agent uses a tool that returns a very long log output. The :ref:`MessageSummarizationTransform <messagesummarizationtransform>` automatically summarizes this long message to stay within size limits. The agent then answers questions about the error, demonstrating that key information is preserved despite the summarization.

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Run_Agent_With_MessageSummarizationTransform
    :end-before: .. end-##_Run_Agent_With_MessageSummarizationTransform

To compare, let's run the same conversation without any transforms to see the difference in token usage.

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Create_Agent_Without_Transform
    :end-before: .. end-##_Create_Agent_Without_Transform

After one user message, we have used the following number of tokens:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Run_Agent_Without_Transform
    :end-before: .. end-##_Run_Agent_Without_Transform

And after the second user message:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Run_Agent_Without_Transform_Round2
    :end-before: .. end-##_Run_Agent_Without_Transform_Round2

- **After one user message**, both approaches show high token usage:

  - Without :ref:`MessageSummarizationTransform <messagesummarizationtransform>`: the agent LLM must process the full long tool output (around 12,800 tokens)

  - With :ref:`MessageSummarizationTransform <messagesummarizationtransform>`: the summarization LLM generates a summary (around 8,900 tokens)

- **After a second message**, the difference becomes significant:

  - Without the transform: token usage doubles to about 25,300 tokens as the agent LLM must reprocess the long tool output

  - With the transform: token usage only increases slightly to about 9,400 tokens due to summaries being cached in datastores and not regenerated.

This demonstrates that the messages were effectively summarized and cached.

Summarizing Long Conversations
==============================

This method uses the built-in :ref:`ConversationSummarizationTransform <conversationsummarizationtransform>` to summarize older messages when conversations become too long, preserving historical information while keeping the context manageable.

.. literalinclude:: ../code_examples/howto_long_context.py
   :language: python
   :start-after: .. start-##_Create_ConversationSummarizationTransform
   :end-before: .. end-##_Create_ConversationSummarizationTransform

Let's integrate the :ref:`MessageTransform <messagetransform>` into the :ref:`Agent <agent>`:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Run_Agent_With_ConversationSummarizationTransform
    :end-before: .. end-##_Run_Agent_With_ConversationSummarizationTransform

If you want to check that the :ref:`ConversationSummarizationTransform <conversationsummarizationtransform>` is really summarizing old messages together, you either use the same ``TokenLister`` as in the previous section to measure tokens or you can also create your own ``EventListener`` that prints the conversation.

Using Both Transforms Together
==============================

For comprehensive context management, you can apply both transforms together. The :ref:`MessageSummarizationTransform <messagesummarizationtransform>` will first handle individual long messages, and then the :ref:`ConversationSummarizationTransform <conversationsummarizationtransform>` will manage the overall conversation length.

.. literalinclude:: ../code_examples/howto_long_context.py
   :language: python
   :start-after: .. start-##_Create_Both_Transforms
   :end-before: .. end-##_Create_Both_Transforms

Let’s integrate the :ref:`MessageTransform <messagetransform>` into the :ref:`Agent <agent>`:

.. literalinclude:: ../code_examples/howto_long_context.py
   :language: python
   :start-after: .. start-##_Run_Agent_With_Both_Transforms
   :end-before: .. end-##_Run_Agent_With_Both_Transforms


Next Steps
==========

We have seen in this how-to how to leverage :ref:`MessageSummarizationTransform <messagesummarizationtransform>` and :ref:`ConversationSummarizationTransform <conversationsummarizationtransform>` to reduce the size of the LLM context.
We have also seen how to use event listeners to measure LLM token consumption. With this new knowledge, you can proceed to :doc:`How to Build Assistants with Tools <howto_build_assistants_with_tools>`.


Full Code
=========

Click the card at the :ref:`top of this page <top-howtolongmessage>` to download the complete code for this guide, or copy it below.

.. literalinclude:: ../end_to_end_code_examples/howto_long_context.py
    :language: python
    :linenos:
