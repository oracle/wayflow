.. _top-howtoagentsinflows:

==========================
How to Use Agents in Flows
==========================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_agents_in_flows.py
        :link-alt: Agents in Flows how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Flows <../tutorials/basic_flow>`
    - :doc:`Agents <../tutorials/basic_agent>`

Usually, flows serve as pipelines to ensure the robustness of agentic workloads.
Employing an agent for a specific task is desirable because of its ability to invoke tools when necessary and autonomously select parameters for certain actions.

WayFlow enables the use of agents within flows, combining the predictability of flows with the adaptability of agents.
This guide demonstrates how to utilize the :ref:`AgentExecutionStep <AgentExecutionStep>` to embed an agent within a flow to execute a specific task.

.. image:: ../_static/howto/agentstep.svg
    :align: center
    :scale: 120%
    :alt: Flow diagram of a pipeline that uses agents

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst


Basic implementation
====================

Assuming you want to write an article.
Writing an article typically involves the following steps:

1. Find the topic for the article.
2. Write the article. This stage typically includes looking for sources on the web, drafting the entire text, reviewing, checking grammar, sources, proofreading.
3. Submit the article by sending it via email to the editor.

Steps 1 and 3 are straightforward and can be managed using standard procedures.
However, Step 2 involves complex tasks beyond a simple LLM generation, such as web browsing and content review.
To address this, you can use ``AgentExecutionStep`` that allows an agent to flexibly utilize tools for web browsing and article review.

Assuming you already have the following tools to browse the web and to proofread the text:

.. literalinclude:: ../code_examples/howto_agents_in_flows.py
    :language: python
    :start-after: .. start-##_Define_the_tools
    :end-before: .. end-##_Define_the_tools

Continue creating the agent, specifying the agent's expected output using the ``outputs`` argument:

.. literalinclude:: ../code_examples/howto_agents_in_flows.py
    :language: python
    :start-after: .. start-##_Define_the_agent
    :end-before: .. end-##_Define_the_agent

The agent should operate within a flow without user interaction.
For that, set the ``caller_input_mode`` mode to ``CallerInputMode.NEVER``.

.. literalinclude:: ../code_examples/howto_agents_in_flows.py
    :language: python
    :start-after: .. start-##_Define_the_agent_step
    :end-before: .. end-##_Define_the_agent_step

Now finalize the entire flow:

.. literalinclude:: ../code_examples/howto_agents_in_flows.py
    :language: python
    :start-after: .. start-##_Define_the_Flow
    :end-before: .. end-##_Define_the_Flow

After completing the previous configurations, execute the flow.

.. literalinclude:: ../code_examples/howto_agents_in_flows.py
    :language: python
    :start-after: .. start-##_Execute_the_flow
    :end-before: .. end-##_Execute_the_flow

As expected, the final execution message should be the email to be sent to the editor.


Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_agents_in_flows.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec

Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_agents_in_flows.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_agents_in_flows.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_agents_in_flows.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginInputMessageNode``
    - ``PluginOutputMessageNode``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


Next steps
==========

Having learned how to use Agents inside Flows, you may now proceed to:

- :doc:`How to Create Conditional Transitions in Flows <conditional_flows>` to branch out depending on the agent's response.


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoagentsinflows>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_agents_in_flows.py
    :language: python
    :linenos:
