===========================================================
How to Do Remote API Calls with Potentially Expiring Tokens
===========================================================


.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_remote_tool_expired_token.py
        :link-alt: MCP how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites
    This guide assumes familiarity with:

    - :doc:`Building Assistants with Tools <howto_build_assistants_with_tools>`

When building assistants with tools that reply on remote API calls, it is important to handle the authentication failures gracefully—especially those caused by expired access tokens.
In this guide, you will build an assistant that calls a mock service requiring a valid token for authentication.

Setup
=====

To demonstrate the concept in a safe environment, we first set up a local mock API server (here, using Starlette).
This simulates an endpoint that requires and validates an authentication token. If the token provided is:

* a valid token (`valid-token`): the service responds with a success message.
* an expired token (`expired-token`) or invalid token: the `401 Unauthorized` error is returned with details.

.. literalinclude:: ../code_examples/howto_remote_tool_expired_token.py
    :language: python
    :start-after: .. start-##_Mock_server
    :end-before: .. end-##_Mock_server
    :linenos:

Basic implementation
====================

In this example, you will build a simple :ref:`Agent <Agent>` that includes a :ref:`Flow <Flow>` with three steps:

* A start step to get the user name
* A step to trigger a client tool that collects a token from the user
* A step to call a remote API given the user name and the token

This guide requires the use of an LLM.
WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Importing libraries
-------------------
First import what is needed for this tutorial:

.. literalinclude:: ../code_examples/howto_remote_tool_expired_token.py
    :language: python
    :start-after: .. start-##_Import_libraries
    :end-before: .. end-##_Import_libraries
    :linenos:

Creating the steps
------------------
Define the variable names and steps.

.. literalinclude:: ../code_examples/howto_remote_tool_expired_token.py
    :language: python
    :start-after: .. start-##_Variable_names
    :end-before: .. end-##_Variable_names
    :linenos:

.. literalinclude:: ../code_examples/howto_remote_tool_expired_token.py
    :language: python
    :start-after: .. start-##_Defining_steps
    :end-before: .. end-##_Defining_steps
    :linenos:

In this simple example, we manually input the user name and the token in the code.
For a more interactive approach, consider using :ref:`InputMessageStep <InputMessageStep>` to prompt the user to enter these values during execution.

Creating the flow
-----------------

.. literalinclude:: ../code_examples/howto_remote_tool_expired_token.py
    :language: python
    :start-after: .. start-##_Defining_flow
    :end-before: .. end-##_Defining_flow
    :linenos:

This flow simply proceeds through three steps as defined in the ``control_flow_edges``.
The ``data_flow_edges`` connect the outputs of each step—the user name from ``start_step`` and the token from ``get_token_tool_step``—to the inputs required by ``call_api_step``.

Testing the flow
----------------

.. literalinclude:: ../code_examples/howto_remote_tool_expired_token.py
    :language: python
    :start-after: .. start-##_Testing_flow
    :end-before: .. end-##_Testing_flow
    :linenos:

To simulate a valid user, provide ``auth_token = "valid-token"``.
To test expiry handling, use ``auth_token = "expired-token"``, which is expected to raise an error.
The flow should pause at the token step, mimicking a credential input prompt, then proceed upon receiving input.

Creating an agent
-----------------
Now, create an agent that includes the defined flow:

.. literalinclude:: ../code_examples/howto_remote_tool_expired_token.py
    :language: python
    :start-after: .. start-##_Defining_agent
    :end-before: .. end-##_Defining_agent
    :linenos:

Testing the agent
-----------------

.. literalinclude:: ../code_examples/howto_remote_tool_expired_token.py
    :language: python
    :start-after: .. start-##_Testing_agent
    :end-before: .. end-##_Testing_agent
    :linenos:

The code block above demonstrates an interaction flow between a user and the agent, simulating how the assistant processes a remote, authenticated API call.
During the first execution, the agent determines that a token is required and issues a tool request to the client. This is reflected by the ``status`` being an instance of ``ToolRequestStatus``.
After the client provides the required credential (the token), the second execution resumes the conversation.
If authentication is successful, the agent proceeds to call the API, processes the response, and generates a user message as its reply.
At this stage, the ``status`` should be ``UserMessageRequestStatus``, which indicates that the agent has completed processing and is now ready to present a message to the user or wait for the next user prompt.
Checking for ``UserMessageRequestStatus`` ensures that your code only tries to access the assistant's reply when it is actually available.


Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_remote_tool_expired_token.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_remote_tool_expired_token.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_remote_tool_expired_token.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_remote_tool_expired_token.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config


.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginPromptTemplate``
    - ``PluginRemoveEmptyNonUserMessageTransform``
    - ``ExtendedToolNode``
    - ``ExtendedAgent``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`



Next steps
==========

In this guide, you learned how to define a simple flow that retrieves a token from the user and uses it to authenticate remote API calls.
To continue learning, checkout:

- :doc:`How to Catch Exceptions in Flows <catching_exceptions>`.

Full code
=========

.. literalinclude:: ../end_to_end_code_examples/howto_remote_tool_expired_token.py
    :language: python
    :linenos:
