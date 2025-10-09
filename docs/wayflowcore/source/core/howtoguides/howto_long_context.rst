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

This guide demonstrates three methods for reducing context size:

- **Discarding old messages**: For long conversations, a straightforward approach is to remove older messages and retain only the most recent ones.
- **Summarizing tool outputs**: Tool outputs are often lengthy and include details that might not be relevant anymore after a few rounds of conversation. Summarizing them to extract the key points will shorten the context and can help the agent stay focused in extended conversations.
- **Summarizing old messages**: Rather than discarding old messages entirely, summarizing old messages can allow the agent to retain historical information.


This guide shows how to create :ref:`MessageTransform <messagetransform>` objects to reduce the context size in agents.

Introduction
============

Message Transforms
~~~~~~~~~~~~~~~~~~

A :ref:`MessageTransform <MessageTransform>` is a transformation applied to a :ref:`PromptTemplate <PromptTemplate>`. It modifies the list of messages before they are sent to the LLM powering the agent. You can learn
more about them in the :doc:`Advanced Prompting Techniques <howto_prompttemplate>` guide.

In this guide, we define new message transforms to adjust the agent's chat history by setting them as ``pre_rendering_transforms`` on the agent's :ref:`PromptTemplate <prompttemplate>`.

LLM Setup
~~~~~~~~~

In this guide, we use an LLM for both the agent and summarization tasks:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Define_the_llm
    :end-before: .. end-##_Define_the_llm


Discarding Old Messages
=======================

Creating the MessageTransform
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This method employs a ``MessageTransform`` that discards older messages, keeping only the latest ones.

A key consideration is to avoid dropping tool requests, as some LLM providers may fail if they receive tool results without matching requests. Here's a helper function to split messages while maintaining consistency:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Keep_Messages_Consistent
    :end-before: .. end-##_Keep_Messages_Consistent

The message transform can then be defined as follows:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Drop_Old_Message_Transform
    :end-before: .. end-##_Drop_Old_Message_Transform


Integrating the MessageTransform into the Agent
===============================================

After defining the ``MessageTransform``, incorporate it into the agent's prompt template, then run the agent:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Drop_Old_Message_Transform_Run
    :end-before: .. end-##_Drop_Old_Message_Transform_Run


.. note::
    We use a ``pre_rendering`` message transform as these ones are applied to the chat history. Here,
    we only want to modify the chat history, not the potential system messages / formatting of the tools
    for the LLM.
    In general, ``pre_rendering`` transforms are to change the chat history, while ``post_rendering`` transforms
    are about formatting the prompt in a certain way for the LLM.

.. note::
    Using ``append=True`` means that the message transform will be added as the first message transform of
    the list. The order in which message transforms are configured is important, since each might modify
    the content of what the next transforms gets.
    Therefore, to avoid cache misses, it is better to set message transforms that use caching as early
    as possible in the list of template




Summarizing Tool Outputs
========================

Creating the MessageTransform
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This approach uses a ``MessageTransform`` that splits large tool results into chunks, summarizes each chunk sequentially with an LLM, and replaces the original messages with summarized versions.

The following ``MessageTransform`` is an example that can be customized for other scenarios.

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Creating_the_message_transform
    :end-before: .. end-##_Creating_the_message_transform

Integrating the MessageTransform into the Agent
===============================================

After defining the ``MessageTransform``, add it to the agent's prompt template as shown below:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Creating_the_agent
    :end-before: .. end-##_Creating_the_agent

Then, run the agent like this:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Running_the_agent
    :end-before: .. end-##_Running_the_agent

A natural extension of this transform could be to only summarize long tool results when they are old, so that
we keep them intact when the agent is asking for it for the first time.


Summarizing Old Messages
========================

Creating the MessageTransform
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This technique uses a ``MessageTransform`` to summarize older messages, similar to the discarding method but preserving some past information.

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Summarize_Old_Message_Transform
    :end-before: .. end-##_Summarize_Old_Message_Transform

Integrating the MessageTransform into the Agent
===============================================

After defining the ``MessageTransform``, add it to the agent's prompt template, then run the agent:

.. literalinclude:: ../code_examples/howto_long_context.py
    :language: python
    :start-after: .. start-##_Summarize_Old_Message_Transform_Run
    :end-before: .. end-##_Summarize_Old_Message_Transform_Run


Agent Spec Exporting/Loading
============================

Due to the custom ``MessageTransform``, the agent cannot be exported to an Agent Spec
configuration.


Next Steps
==========

With your new knowledge of using ``MessageTransform`` to manage large message contents, proceed
to :doc:`How to Build Assistants with Tools <howto_build_assistants_with_tools>`.


Full Code
=========

Click the card at the :ref:`top of this page <top-howtolongmessage>` to download the complete code for this guide, or copy it below.

.. literalinclude:: ../end_to_end_code_examples/howto_long_context.py
    :language: python
    :linenos:
