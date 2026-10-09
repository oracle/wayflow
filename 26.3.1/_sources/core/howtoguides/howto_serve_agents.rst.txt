.. _top-howtoserveagents:

================================
How to Serve Agents with WayFlow
================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_serve_agents.py
        :link-alt: Serve Agents how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Agents <../tutorials/basic_agent>`
    - :doc:`Datastores <../howtoguides/howto_datastores>`
    - :doc:`WayFlow Tools <../api/tools>`

WayFlow can host agents behind an
`OpenAI Responses API <https://platform.openai.com/docs/api-reference/responses>`_ compatible
endpoint. Reliable serving unlocks predictable SLAs, reusable state, and consistent security, while
letting clients keep using familiar OpenAI SDKs. Start with an in-memory setup for quick
experiments, then add persistence to reuse conversation state and layer FastAPI security controls
that fit your environment.


Create an agent to host
=======================

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

.. note::
    API keys should not be stored anywhere in the code. Use environment variables or tools such as `python-dotenv <https://pypi.org/project/python-dotenv/>`_.


Then, create or reuse an agent you want to serve. You can define it as code:

.. literalinclude:: ../code_examples/howto_serve_agents.py
    :language: python
    :start-after: .. start-##_Define_the_agent
    :end-before: .. end-##_Define_the_agent

API Reference: :ref:`Agent <agent>` | :ref:`Tool <servertool>`


Export and reload agent specs
=============================

Save your agent as an Agent Spec so you can deploy from a config file or ship it to another team.
Reloading requires a ``tool_registry`` that maps tool names back to callables.

.. literalinclude:: ../code_examples/howto_serve_agents.py
    :language: python
    :start-after: .. start-##_Export_agent_spec
    :end-before: .. end-##_Export_agent_spec

API Reference: :ref:`AgentSpecExporter <agentspecexporter>` | :ref:`AgentSpecLoader <agentspecloader>`


Run an in-memory Responses API server
=====================================

Expose the agent with :ref:`OpenAIResponsesServer <openairesponsesserver>`. The server mounts
``/v1/responses`` and ``/v1/models`` endpoints that work with the official ``openai`` SDK or
:ref:`OpenAICompatibleModel <OpenAICompatibleModel>`.

.. literalinclude:: ../code_examples/howto_serve_agents.py
    :language: python
    :start-after: .. start-##_Serve_in_memory
    :end-before: .. end-##_Serve_in_memory

You can now call the server with an OpenAI-compatible client:

.. literalinclude:: ../code_examples/howto_serve_agents.py
    :language: python
    :start-after: .. start-##_Call_the_server
    :end-before: .. end-##_Call_the_server

API Reference: :ref:`OpenAIResponsesServer <openairesponsesserver>`


Persist conversations with datastores
=====================================

To reuse conversation history across requests or server restarts, attach a datastore. Use
:ref:`ServerStorageConfig <serverstorageconfig>` to define table and column names, then pass a
supported :ref:`Datastore <Datastore>` implementation such as
:ref:`PostgresDatabaseDatastore <PostgresDatabaseDatastore>` or
:ref:`OracleDatabaseDatastore <OracleDatabaseDatastore>`.

.. literalinclude:: ../code_examples/howto_serve_agents.py
    :language: python
    :start-after: .. start-##_Persistent_storage
    :end-before: .. end-##_Persistent_storage

In production, create the table beforehand or run ``wayflow serve`` with ``--setup-datastore yes``
to let WayFlow prepare it when the backend supports schema management. It will not override any
existing table, so you will need to first delete any existing table to allow wayflow to set it up
for you.

API Reference: :ref:`ServerStorageConfig <serverstorageconfig>` | :ref:`Datastore <datastore>`


Add FastAPI security controls
=============================

:ref:`OpenAIResponsesServer <OpenAIResponsesServer>` gives you the FastAPI ``app`` instance so
you can stack your own middleware, dependencies, or routers. This example enforces a simple bearer
token check.

.. literalinclude:: ../code_examples/howto_serve_agents.py
    :language: python
    :start-after: .. start-##_Add_fastapi_security
    :end-before: .. end-##_Add_fastapi_security

Replace the token check with your own authentication handler (OAuth2, mTLS validation, signed
cookies, IP filtering, etc.) and add rate limiting or CORS rules as needed.

API Reference: :ref:`OpenAIResponsesServer <OpenAIResponsesServer>`


Use the CLI
===========

You can also serve an agent spec file directly from the CLI:

.. code-block:: bash

    wayflow serve \
      --api openai-responses \
      --agent-config hr_agent.json \
      --agent-id hr-assistant \
      --server-storage postgres-db \
      --datastore-connection-config postgres_conn.yaml \
      --setup-datastore yes


Pass ``--tool-registry`` to load your own tools, swap ``--server-storage`` to ``oracle-db`` or
``in-memory``, and set ``--server-storage-config`` to override column names. See the :ref:`API reference <cliwayflowreference>` for a
complete description of all arguments.

.. warning::
   This CLI does not implement any security features; use it only for development or inside an
   already-secured environment such as OCI agent deployments. Missing controls include:

   - **Authentication**: No verification of caller identity—anyone with network access can invoke the agent.
   - **Authorization**: No role or permission checks to restrict which users can access specific agents or actions.
   - **Rate limiting**: No protection against excessive requests that could exhaust resources or incur runaway costs.
   - **TLS/HTTPS**: Traffic is unencrypted by default, risking interception of sensitive prompts and responses.

   For production deployments, wrap the server with an API gateway, reverse proxy, or custom FastAPI middleware that enforces these controls.



Next steps
==========

- :doc:`Use Agents in Flows <howto_agents_in_flows>`
- :doc:`Connect Assistants to Your Data <howto_datastores>`
- :doc:`Build Assistants with Tools <howto_build_assistants_with_tools>`


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoserveagents>` to download the full code
for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_serve_agents.py
    :language: python
    :linenos:
