.. _tool_use:

==================================
How to Build Assistants with Tools
==================================


.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_tooluse.py
        :link-alt: Tool use how-to script

        Python script/notebook for this guide.



.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Flows <../tutorials/basic_flow>`
    - :doc:`Agents <../tutorials/basic_agent>`

Equipping assistants with :doc:`Tools <../api/tools>` enhances their capabilities.
In WayFlow, tools can be used in both conversational assistants (also known as Agents) as well as in Flows by using the ``ToolExecutionStep`` class.

WayFlow supports **server-side**, **client-side** tools as well as **remote-tools**.

.. seealso::

    This guide focuses on using server/client tools. Read the :ref:`API Documentation <remotetool>` to learn
    more about the ``RemoteTool``.

.. image:: ../_static/howto/types_of_tools.svg
    :align: center
    :scale: 80%


In this guide, you will build a **PDF summarizer** using the different types of supported tools, both within a flow and with an agent.


Imports and LLM configuration
=============================

To get started, first import the ``PyPDF`` library.
First, install the PyPDF library:

.. code:: bash

    $ pip install pypdf

Building LLM-powered assistants with tools in WayFlow requires the following imports.

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: .. start-##_Imports_for_this_guide
    :end-before: .. end-##_Imports_for_this_guide

In this guide, you will use an LLM.

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

.. note::
    API keys should not be stored anywhere in the code. Use environment variables or tools such as `python-dotenv <https://pypi.org/project/python-dotenv/>`_.


Helper functions
================

The underlying tool used in this example is a PDF parser tool. The tool:

- loads a PDF file;
- reads the content of the pages;
- returns the extracted text.

The ``PyPDFLoader`` API from the `langchain_community Python library <https://pypi.org/project/langchain-community/>`_ is used for this purpose.

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: .. start-##_Defining_some_helper_functions
    :end-before: .. end-##_Defining_some_helper_functions


.. collapse:: Click to see the PDF content used in this example.

    .. literalinclude:: ../_static/howto/example_document.md
        :language: markdown

\

.. _overview-of-tool-types:

Overview of the types of tools
==============================

This section covers how to use the following tools:

* ``@tool`` decorator - The simplest way to create server-side tools by decorating Python functions.
* ``ServerTool`` - For tools to be executed on the server side. Use this for tools running within the WayFlow environment, including local execution.
* ``ClientTool`` - For tools to be executed on the client application.


Using the @tool Decorator
-------------------------

WayFlow provides a convenient ``@tool`` decorator that simplifies the creation of server-side tools. By decorating a Python function with ``@tool``, you automatically convert it into a ``ServerTool`` object ready to be used in your Flows and Agents.

The decorator automatically extracts information from the function:

- The function name becomes the tool name
- The function docstring becomes the tool description
- Type annotations and parameter docstrings define input parameters
- Return type annotations define the output type

In the example below, we show a few options for how to create a server-side tool using the ``@tool`` decorator:

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: .. start-##_Defining_a_tool_using_the_tool_decorator
    :end-before: .. end-##_Defining_a_tool_using_the_tool_decorator

In the above example, the decorated function ``read_pdf_server_tool`` is transformed into a ``ServerTool`` object.
The tool's name is derived from the function name, the description from the docstring, and the input parameters and output type from the type annotations.

.. tip::

    You can set the ``description_mode`` parameter of the ``@tool`` decorator to ``only_docstring`` to use the parameter signature information from
    the docstrings instead of having to manually define them using ``Annotated[Type, "description"]``.


Creating a ServerTool
---------------------

The ``ServerTool`` is defined by specifying:

- A tool name
- A tool description
- Input parameters, including names, types, and optional default values.
- A Python callable, the function executed by the tool.
- The output type.

In the example below, the tool takes two input parameters, one of which is optional, and returns a string.

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: .. start-##_Defining_a_tool_using_the_ServerTool
    :end-before: .. end-##_Defining_a_tool_using_the_ServerTool


Creating a ClientTool
---------------------

The ``ClientTool`` is defined similarly to a ``ServerTool``, except that it does not include a Python callable in its definition.
When executed, a ``ClientTool`` returns a ``ToolRequest``, which must be executed on the client side.
The client then sends the execution result back to the assistant.

In the following example, the tool execution function is also defined.
This function should be implemented based on the specific requirements of the assistant developer.

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: # .. start-##_Defining_a_tool_using_the_ClientTool
    :end-before: # .. end-##_Defining_a_tool_using_the_ClientTool


Building Flows with Tools using the `ToolExecutionStep`
=======================================================

Executing tools in Flows can be done using the :ref:`ToolExecutionStep <toolexecutionstep>`.
The step simply requires the user to specify the tool to execute when the step is invoked.

Once the tool execution step is defined, the Flow can be constructed as usual.
For more information, refer to the tutorial on :doc:`Flows <../tutorials/basic_flow>`.

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: # .. start-##_Defining_a_build_flow_helper_function
    :end-before: # .. end-##_Defining_a_build_flow_helper_function


Executing ServerTool with a Flow
--------------------------------

When using the ``ServerTool``, the tool execution is performed on the server side.
As a consequence, the flow can be executed end-to-end with a single ``execute`` instruction.

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: # .. start-##_Creating_and_running_a_flow_with_a_server_tool
    :end-before: # .. end-##_Creating_and_running_a_flow_with_a_server_tool


.. collapse:: Click to see the summarized PDF content.

    Here is the summarized PDF:

    Oracle Corporation is an American multinational computer technology company headquartered
    in Austin, Texas. It sells database software, cloud computing software and hardware, and
    enterprise software products including ERP, HCM, CRM, and SCM software.

\

Executing ClientTool with a Flow
--------------------------------

When using a ``ClientTool``, the tool execution is performed on the client side.
Upon request, the assistant sends a ``ToolRequest`` to the client, which is responsible for executing the tool.
Once completed, the client returns a ``ToolResult`` to the assistant, allowing it to continue execution until the task is complete.

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: # .. start-##_Creating_and_running_a_flow_with_a_client_tool
    :end-before: # .. end-##_Creating_and_running_a_flow_with_a_client_tool


Building Agents with Tools
==========================

Agents can be equipped with tools by specifying the list of tools the agent can access.

You do not need to mention the tools in the agent’s ``custom_instruction``, as tool descriptions are automatically added internally.

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: # .. start-##_Defining_a_build_agent_helper_function
    :end-before: # .. end-##_Defining_a_build_agent_helper_function


.. note::
    :ref:`Agents <agent>` can also be equipped with other flows and agents. This topic will be covered in a dedicated tutorial.


Executing ServerTool with an Agent
----------------------------------

Similar to executing a Flow with a ``ServerTool``, Agents can be executed end-to-end using a single ``execute`` instruction.
The key difference is that the file path is provided as a conversation message rather than as a flow input.

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: # .. start-##_Creating_and_running_an_agent_with_a_server_tool
    :end-before: # .. end-##_Creating_and_running_an_agent_with_a_server_tool


.. important::
    In this case, the LLM must correctly generate the tool call with the file path as an input parameter. Smaller LLMs may struggle to reproduce the path accurately.
    In general, assistant developers should try to avoid having LLMs to manipulate complex strings.


Executing ClientTool with an Agent
----------------------------------

Similar to executing a Flow with a ``ClientTool``, the tool request must be handled on the client side.
The only difference is that the file path is provided as a conversation message instead of as a flow input.

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: # .. start-##_Creating_and_running_an_agent_with_a_client_tool
    :end-before: # .. end-##_Creating_and_running_an_agent_with_a_client_tool

Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_tooluse.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_tooluse.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_tooluse.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config


.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginPromptTemplate``
    - ``PluginRemoveEmptyNonUserMessageTransform``
    - ``ExtendedAgent``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`



Next steps
==========

Having learned how to use ``ServerTool`` and ``ClientTool`` with assistants in WayFlow, you may now proceed to:

- :doc:`How to Create Tools with Multiple Outputs <howto_multiple_output_tool>`
- :doc:`How to Install and Use Ollama <installing_ollama>`
- :doc:`How to Connect Assistants to Data <howto_datastores>`.


Full code
=========

Click on the card at the :ref:`top of this page <tool_use>` to download the full code for this guide or copy the code below.

download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_tooluse.py
   :language: python
   :linenos:
