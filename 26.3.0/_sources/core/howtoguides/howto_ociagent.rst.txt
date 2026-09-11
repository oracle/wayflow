.. _top-howtoociagent:

===================================
How to Use OCI Generative AI Agents
===================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_ociagent.py
        :link-alt: OCI Agent how-to script

        Python script/notebook for this guide.


.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`LLM configuration <../howtoguides/llm_from_different_providers>`
    - :doc:`Using agents <agents>`

`OCI GenAI Agents <https://www.oracle.com/artificial-intelligence/generative-ai/agents>`_ is a service to create agents in the OCI console.
These agents are defined remotely, including their tools, prompts, and optional documents for retrieval-augmented generation (RAG), and can be used for inference.

In this guide, you will learn how to connect an OCI agent using the :ref:`OciAgent <ociagent>` class from the ``wayflowcore`` package.


Basic usage
===========

To get started, first create your OCI Agent in the OCI Console.
Consult the OCI documentation for detailed steps: https://docs.oracle.com/en-us/iaas/Content/generative-ai-agents/home.htm.

Next, create an ``OciClientConfig`` object to configure the connection to the OCI service.
See the :doc:`OCI LLM configuration <llm_from_different_providers>` for detailed instructions how to configure this object.

You will also need the ``agent_endpoint_id`` from the OCI Console.
This ID points to the agent you want to connect to, while the client configuration is about connecting to the entire service.

Once these are in place, you can create your agent in a few lines:

.. literalinclude:: ../code_examples/howto_ociagent.py
    :language: python
    :start-after: .. start-##_Creating_the_agent
    :end-before: .. end-##_Creating_the_agent

Then, use the agent as shown below:

.. literalinclude:: ../code_examples/howto_ociagent.py
    :language: python
    :start-after: .. start-##_Running_the_agent
    :end-before: .. end-##_Running_the_agent


Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_ociagent.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_ociagent.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_ociagent.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_ociagent.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config


Next steps
==========

Now that you have learned how to use OCI agents in WayFlow, you may proceed to :doc:`How to Use Agents in Flows <howto_agents_in_flows>`.


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoociagent>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_ociagent.py
    :language: python
    :linenos:
