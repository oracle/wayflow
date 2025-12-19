====================================
How to Configure Agents Instructions
====================================

.. admonition:: Prerequisites

    This guide assumes familiarity with :doc:`Agents <../tutorials/basic_agent>`.

Agents can be configured to tackle many scenarios.
Proper configuration of their instructions is essential.

In this how to guide, we will learn how to:

- Configure the instructions of an :ref:`Agent <Agent>`.
- Set up instructions that vary with each ``Conversation``.
- Maintain instructions that are consistently updated and refreshed.

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Basic implementation
====================

Assuming you need an agent to assist a user in writing articles, use the implementation below for that purpose:

.. literalinclude:: ../code_examples/howto_agents.py
    :language: python
    :start-after: .. start-agent:
    :end-before: .. end-agent

Then execute it:

.. literalinclude:: ../code_examples/howto_agents.py
    :language: python
    :start-after: .. start-execute:
    :end-before: .. end-execute

Sometimes, there is contextual information relevant to the conversation.
Assume a user is interacting with the assistant named "Jerry."
To make the assistant more context-aware, define a variable or expression in the ``custom_instruction`` Jinja template, and pass it when creating the conversation:

.. note::

    Jinja templating introduces security concerns that are addressed by WayFlow by restricting Jinja's rendering capabilities.
    Please check our guide on :ref:`How to write secure prompts with Jinja templating <securejinjatemplating>` for more information.

.. literalinclude:: ../code_examples/howto_agents.py
    :language: python
    :start-after: .. start-conversation:
    :end-before: .. end-conversation

.. note::
  It is useful to use the same :class:`Agent`, but change some part of the ``custom_instruction`` for each different conversation.

Finally, incorporating dynamic context into the agent's instructions can significantly improve its responsiveness.
For example, the instructions can contain the current time making the agent more aware of the situation.
The time value is constantly changing, so you need to make sure it is always up-to-date.
To do this, use the ``ContextProvider``:

.. literalinclude:: ../code_examples/howto_agents.py
    :language: python
    :start-after: .. start-context:
    :end-before: .. end-context

You successfully customized the prompt of your agent.

Recap
=====

In this guide, you learned how to configure :ref:`Agent <Agent>` instructions with:

- pure text instructions;
- specific variables for each ``Conversation``;
- instructions with variables that needs to be always updated.

.. collapse:: Below is the complete code from this guide.

    .. literalinclude:: ../code_examples/howto_agents.py
        :language: python
        :start-after: .. start-llm:
        :end-before: .. end-llm

    .. literalinclude:: ../code_examples/howto_agents.py
        :language: python
        :start-after: .. start-agent:
        :end-before: .. end-agent

    .. literalinclude:: ../code_examples/howto_agents.py
        :language: python
        :start-after: .. start-execute:
        :end-before: .. end-execute

    .. literalinclude:: ../code_examples/howto_agents.py
        :language: python
        :start-after: .. start-conversation:
        :end-before: .. end-conversation

    .. literalinclude:: ../code_examples/howto_agents.py
        :language: python
        :start-after: .. start-context:
        :end-before: .. end-context


Next steps
==========

Having learned how to configure agent instructions, you may now proceed to:

- :doc:`How to Build Assistants with Tools <howto_build_assistants_with_tools>`
- :doc:`How to Use Agents in Flows <howto_agents_in_flows>`
