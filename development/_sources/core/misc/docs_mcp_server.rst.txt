.. _docs_mcp_server:

===============
Docs MCP Server
===============

WayFlow includes a documentation-focused MCP server in ``examples/mcp/docs_mcp.py``.
It exposes a single tool, ``get_docs``, that lets coding assistants safely navigate
the published WayFlow Markdown docs bundle and the generated end-to-end example files.

This is useful when you want an assistant to answer questions grounded in the current
WayFlow documentation, inspect example code before writing new code, or locate the
right guide/API page without giving the assistant unrestricted shell access.


What the server does
====================

The ``get_docs`` tool accepts a constrained shell-like command and runs it against the
downloaded docs bundle. Supported commands are:

* ``ls [PATH]`` or ``ls -la [PATH]``
* ``rg --files [-g/--glob PATTERN] [PATH]``
* ``sed -n 'START,ENDp' FILE``
* ``head FILE`` or ``head -n N FILE``
* ``tail FILE`` or ``tail -n N FILE``
* exactly one pipe from a supported producer into ``head``, ``tail``, or filtering ``rg``

The server is intentionally narrow in scope:

* it refreshes the Markdown bundle at startup from the base docs URL;
* it only allows navigation inside that bundle;
* it supports exactly one pipe and still blocks redirects, command chaining, and subshell syntax.

The intended workflow is:

1. discover folders with ``ls``;
2. locate the relevant page or example with ``rg --files`` or ``| rg`` filtering;
3. read or trim excerpts with ``sed -n``, ``head``, or ``tail``.

Typical pipeline examples include:

* ``rg --files core/howtoguides | rg mcp``
* ``rg --files -g '*.md' core | head -n 20``
* ``sed -n '1,220p' core/howtoguides/howto_mcp.md | rg StdioTransport``


Adding the server to Codex
==========================

The example file includes the minimal Codex setup instructions at the top.

From the ``examples/mcp`` directory:

.. code-block:: bash

   codex mcp add wayflow_docs -- python docs_mcp.py --base-docs-url https://oracle.github.io/wayflow/development

If you prefer to edit the Codex configuration manually:

.. code-block:: toml

   [mcp_servers.wayflow_docs]
   command = "python"
   args = ["docs_mcp.py", "--base-docs-url", "https://oracle.github.io/wayflow/development"]


If you launch Codex from the repository root instead, use
``examples/mcp/docs_mcp.py`` as the script path.

If you prefer a ``uv``-based setup that does not require a local checkout of the
WayFlow repository, you can run the server directly from GitHub:

.. code-block:: bash

   codex mcp add wayflow_docs -- uv run --with mcp -- https://raw.githubusercontent.com/oracle/wayflow/refs/heads/main/examples/mcp/docs_mcp.py --base-docs-url https://oracle.github.io/wayflow/development

Equivalent Codex configuration:

.. code-block:: toml

   [mcp_servers.wayflow_docs]
   command = "uv"
   args = [
       "run", "--with", "mcp",
       "--",
       "https://raw.githubusercontent.com/oracle/wayflow/refs/heads/main/examples/mcp/docs_mcp.py",
       "--base-docs-url",
       "https://oracle.github.io/wayflow/development",
   ]


Using it from a WayFlow Agent
=============================

The docs MCP server can also be consumed from WayFlow through :ref:`MCPTool <mcptool>`
and the :ref:`StdioTransport <stdiotransport>`.

The example below starts the docs MCP server as a local subprocess, connects a
single ``get_docs`` tool to an :ref:`Agent <agent>`, and lets the agent inspect the
docs before answering.

.. code-block:: python

   from wayflowcore.agent import Agent
   from wayflowcore.executors.executionstatus import UserMessageRequestStatus
   from wayflowcore.mcp import MCPTool, StdioTransport, enable_mcp_without_auth
   from wayflowcore.models import VllmModel

   llm = VllmModel(
       model_id="LLAMA_MODEL_ID",
       host_port="LLAMA_API_URL",
   )

   enable_mcp_without_auth()
   docs_transport = StdioTransport(
       command="python",
       args=[
           "examples/mcp/docs_mcp.py",
           "--base-docs-url",
           "https://oracle.github.io/wayflow/development",
       ],
       cwd="/path/to/wayflow",
   )

   docs_tool = MCPTool(
       name="get_docs",
       client_transport=docs_transport,
   )

   assistant = Agent(
       llm=llm,
       tools=[docs_tool],
       custom_instruction=(
           "Use the get_docs tool to inspect the WayFlow docs and examples before "
           "answering. Prefer ls, rg --files, head, tail, and short sed excerpts. "
           "You may use a single pipe into head, tail, or filtering rg when helpful."
       ),
   )

   conversation = assistant.start_conversation()
   conversation.append_user_message(
       "Find the MCP how-to and write a minimal stdio example for a WayFlow agent."
   )
   status = conversation.execute()

   if isinstance(status, UserMessageRequestStatus):
       print(conversation.get_last_message().content)

.. note::

   As with the rest of the :doc:`MCP guide <../howtoguides/howto_mcp>`,
   ``enable_mcp_without_auth()`` is for local and test usage only.


Example assistant queries
=========================

Below are representative queries you can send to a code assistant equipped with the
``wayflow_docs.get_docs`` tool. The tool calls were exercised against the docs bundle
to illustrate the expected workflow and response style.


Example 1: Find the MCP guide and the recommended local transport
-----------------------------------------------------------------

**User query**

"Where is the MCP guide, and which transport should I use for a local subprocess server?"

**Example tool calls**

.. code-block:: text

   wayflow_docs.get_docs("rg --files core/howtoguides | rg mcp")
   wayflow_docs.get_docs("head -n 40 core/howtoguides/howto_mcp.md")
   wayflow_docs.get_docs("sed -n '740,820p' core/api/tools.md | rg StdioTransport")

**Result the assistant would give**

The MCP guide is in ``core/howtoguides/howto_mcp.md``. For a locally launched MCP
server, the docs recommend :ref:`StdioTransport <stdiotransport>`, which is intended
for subprocess-based communication on the same machine. The same guide also points to
the :doc:`Tools API <../api/tools>` for the transport details.


Example 2: Locate an end-to-end MCP example
-------------------------------------------

**User query**

"Show me an existing WayFlow example that connects an agent to an MCP server."

**Example tool calls**

.. code-block:: text

   wayflow_docs.get_docs("ls core/end_to_end_code_examples | rg howto_mcp")
   wayflow_docs.get_docs("head -n 40 core/end_to_end_code_examples/howto_mcp.py")

**Result the assistant would give**

There is an end-to-end example in ``core/end_to_end_code_examples/howto_mcp.py``.
The relevant section shows a WayFlow ``Agent`` configured with MCP access, including
the transport setup, the MCP tool wiring, and a simple execution loop.


Example 3: Discover what documentation areas are available
----------------------------------------------------------

**User query**

"What can you browse in the WayFlow docs bundle?"

**Example tool call**

.. code-block:: text

   wayflow_docs.get_docs("ls core | head -n 10")

**Result the assistant would give**

The bundle includes the main documentation areas such as ``api``, ``howtoguides``,
``tutorials``, ``misc``, and ``end_to_end_code_examples``, plus top-level pages like
``installation.md``, ``security.md``, and ``faqs.md``. A good next step is to narrow
the search to one area with ``rg --files`` and then read a short excerpt with ``sed``.


Example 4: Pull a glossary definition before writing code
---------------------------------------------------------

**User query**

"Before you write code, remind me what WayFlow means by an Agent."

**Example tool call**

.. code-block:: text

   wayflow_docs.get_docs("head -n 40 core/misc/glossary.md")

**Result the assistant would give**

According to the glossary, an Agent is a conversational WayFlow assistant that can
interact with users, use tools, and collaborate with other WayFlow assistants to solve
requests. It is the right building block when you want an assistant to plan tool usage
flexibly instead of following a fixed flow.


Example 5: Ask the assistant to synthesize a stdio MCP snippet
--------------------------------------------------------------

**User query**

"Use the docs to write a minimal Agent example that talks to an MCP server over stdio."

**Example tool calls**

.. code-block:: text

   wayflow_docs.get_docs("head -n 80 core/howtoguides/howto_mcp.md")
   wayflow_docs.get_docs("sed -n '740,820p' core/api/tools.md | rg StdioTransport")
   wayflow_docs.get_docs("head -n 40 core/end_to_end_code_examples/howto_mcp.py")

**Result the assistant would give**

Here is a minimal example based on the MCP how-to and the ``StdioTransport`` API:

.. code-block:: python

   from wayflowcore.agent import Agent
   from wayflowcore.executors.executionstatus import UserMessageRequestStatus
   from wayflowcore.mcp import MCPTool, StdioTransport, enable_mcp_without_auth
   from wayflowcore.models import VllmModel

   llm = VllmModel(
       model_id="LLAMA_MODEL_ID",
       host_port="LLAMA_API_URL",
   )

   enable_mcp_without_auth()
   docs_transport = StdioTransport(
       command="python",
       args=[
           "examples/mcp/docs_mcp.py",
           "--base-docs-url",
           "https://oracle.github.io/wayflow/development",
       ],
       cwd="/path/to/wayflow",
   )

   docs_tool = MCPTool(
       name="get_docs",
       client_transport=docs_transport,
   )

   assistant = Agent(
       llm=llm,
       tools=[docs_tool],
   )

   ...
