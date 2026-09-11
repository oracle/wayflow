.. _top-howtoa2aagent:

============================
How to Connect to A2A Agents
============================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_a2aagent.py
        :link-alt: A2A Agent how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`LLM configuration <../howtoguides/llm_from_different_providers>`
    - :doc:`Using agents <agents>`


`A2A Protocol <https://a2a-protocol.org/latest/>`_ is an open standard that defines how two agents can communicate
with each other. It covers both the serving and consumption aspects of agent interaction.

In this guide, you will learn how to connect to a remote agent using this protocol with the :ref:`A2AAgent <a2aagent>`
class from the ``wayflowcore`` package.


Basic usage
===========

To get started with an A2A agent, you need the URL of the remote server agent you wish to connect to.
Once you have this information, creating your A2A agent is straightforward and can be done in just a few lines of code:

.. literalinclude:: ../code_examples/howto_a2aagent.py
    :language: python
    :start-after: .. start-##_Creating_the_agent
    :end-before: .. end-##_Creating_the_agent

Then, use the agent as shown below:

.. literalinclude:: ../code_examples/howto_a2aagent.py
    :language: python
    :start-after: .. start-##_Running_the_agent
    :end-before: .. end-##_Running_the_agent

Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_a2aagent.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_a2aagent.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_a2aagent.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_a2aagent.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config


Next steps
==========

Now that you have learned how to use A2A Agents in WayFlow, you may proceed to :doc:`How to Use Agents in Flows <howto_agents_in_flows>`.


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoa2aagent>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_a2aagent.py
    :language: python
    :linenos:
