.. _top-howtodatastores:

======================================
How to Connect Assistants to Your Data
======================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

   .. grid-item-card:: |python-icon| Download In-Memory Script
      :link: ../end_to_end_code_examples/howto_datastores.py
      :link-alt: In-memory datastore how-to script

      Python script/notebook for the In-Memory Datastore example in this guide.
   .. grid-item-card:: |python-icon| Download Oracle Database Script
      :link: ../end_to_end_code_examples/howto_connect_to_oracle_database.py
      :link-alt: Oracle Database datastore how-to script

      Python script/notebook for Oracle Database Datastore  example in this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with

    - :doc:`Agents <../tutorials/basic_agent>`
    - :doc:`Flows <../tutorials/basic_flow>`


Agents rely on access to relevant data to function effectively.
Without a steady stream of high-quality data, AI models are unable to learn, reason, or make informed decisions.
Connecting an Agent or Flow to data sources is therefore a critical step in developing functional AI systems.
This connection enables agents to perceive their environment, update their knowledge or the underlying data source, and adapt to changing conditions.

In this tutorial, you will:

- **Define Entities** that an Agent or Flow can access and manipulate.
- **Populate a Datastore** with entities for development and testing.
- **Use Datastores in Flows and Agents** to create two types of inventory management assistants.

To ensure reproducibility of this tutorial, you will use an in-memory data source.
Check out the section :ref:`Using Oracle Database Datastore <using-oracle-datastore>` to see how to configure an
Oracle Database connection for persistent storage.

Concepts shown in this guide
============================

- :ref:`Entities <entity>` to model data
- :ref:`Datastore <datastore>` and :ref:`InMemoryDatastore <inmemorydatastore>` to manipulate collections of data
- Steps to use datastores in Agents and Flows (:ref:`DatastoreListStep <datastoreliststep>`, :ref:`DatastoreCreateStep <datastorecreatestep>`, :ref:`DatastoreUpdateStep <datastoreupdatestep>`, :ref:`DatastoreDeleteStep <datastoredeletestep>`)

.. note::
   The :ref:`InMemoryDatastore <inmemorydatastore>` is mainly suitable for testing and development,
   or other use-cases where data persistence across assistants and conversations is not a requirement.
   For production use-cases, the :ref:`OracleDatabaseDatastore <oracledatabasedatastore>` provides a
   robust and scalable persistence layer in Oracle Database.

   Note that there are a few key differences between an in-memory and a database ``Datastore``:

   - With database Datastores, all tables relevant to the assistant must already be created in the database prior to connecting to it.
   - You may choose to only model a subset of the tables available in the database via the :ref:`Entity <entity>` construct.
   - Database Datastores offer an additional ``query`` method (and the corresponding :ref:`DatastoreQueryStep <datastorequerystep>`),
     that enables flexible execution of SQL queries that cannot be modelled by the ``list`` operation on the in-memory datastore

Datastores in Flows
===================

In this section, you will build a simple Flow that performs operations on an inventory database based on user input.
This Flow helps users keep product descriptions up to date by leveraging an LLM for the creative writing component.

Step 1. Add imports and LLM configuration
-----------------------------------------

Import the required packages:

.. literalinclude:: ../code_examples/howto_datastores.py
   :language: python
   :linenos:
   :start-after: .. start-##_Imports
   :end-before: .. end-##_Imports

In this assistant, you need to use an LLM.
WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

.. important::
    API keys should not be stored anywhere in the code. Use environment variables and/or tools such as `python-dotenv <https://pypi.org/project/python-dotenv/>`_.

Step 2. Define data
-------------------

Start by defining the schema for your data using the :ref:`Entity <entity>` construct.
In this example, you will manage products in an inventory, so a single collection is sufficient.
Datastores also support managing multiple collections at the same time if needed.

.. literalinclude:: ../code_examples/howto_datastores.py
   :language: python
   :linenos:
   :start-after: .. start-##_Create_entities
   :end-before: .. end-##_Create_entities

Next, create an :ref:`InMemoryDatastore <inmemorydatastore>`.
For simplicity, you will use dummy data:

.. literalinclude:: ../code_examples/howto_datastores.py
   :language: python
   :linenos:
   :start-after: .. start-##_Create_datastore
   :end-before: .. end-##_Create_datastore

Step 3. Create datastore steps
------------------------------

Now that the Datastore is set up, create steps to perform different operations in the flow.
In this case, the assistant only needs to retrieve the current description of products and update it.
See :ref:`the list of all available Datastore steps <datastoresteps>` for more details.

.. literalinclude:: ../code_examples/howto_datastores.py
   :language: python
   :linenos:
   :start-after: .. start-##_Create_Datastore_step
   :end-before: .. end-##_Create_Datastore_step

Key points:

- Use ``where`` to filter which product to list and update. Configure it with a variable so that the user can dynamically choose the product title.
- In the ``DatastoreListStep``, ``limit`` and ``unpack_single_entity_from_list`` are used to assume that product titles are unique, making the output concise and easy to handle.

The input to the ``DatastoreListStep`` is the title of the product to retrieve, and the output is a single object containing the corresponding product data.
The input to the ``DatastoreUpdateStep`` includes both the title of the product to update and the updates to apply, in the form of a dictionary containing the properties and the corresponding values.
The output will be the new properties that were updated.

Step 4. Create the Flow
-----------------------

Now define the :ref:`Flow <flow>` for this assistant.

After the user enters which product they want to update, and how the description should be updated, the datastore is queried to find the matching product.
The LLM is prompted with the product details and the user's instructions.
The output is used to update the data, and the new result is returned back to the user.

.. collapse:: Click to see the rest of the code

   .. literalinclude:: ../code_examples/howto_datastores.py
      :language: python
      :linenos:
      :start-after: .. start-##_Create_flow
      :end-before: .. end-##_Create_flow

Note the use of structured generation in the ``PromptExecutionStep`` (via the ``output_descriptors`` parameter).
This ensures that the LLM generates exactly the structure expected by the ``DatastoreUpdateStep``.

Finally, verify that the Flow works:

.. literalinclude:: ../code_examples/howto_datastores.py
      :language: python
      :linenos:
      :start-after: .. start-##_Execute_flow
      :end-before: .. end-##_Execute_flow


Datastores in Agents
====================

This section assumes you have completed the previous steps on using datastores in Flows.

The Flow you built earlier is quite helpful and reliable because it performs a single, specialized task.
Next, you will see how to define an Agent for inventory management when the task is not defined in advance.
This Agent will be able to interpret the user's requests and autonomously decide which actions on the ``Datastore`` are required to fulfill each task.

Step 1. Add imports and LLM configuration
-----------------------------------------

Add the additional imports needed to use Agents:

.. literalinclude:: ../code_examples/howto_datastores.py
      :language: python
      :linenos:
      :start-after: .. start-##_Import_agents
      :end-before: .. end-##_Import_agents

Step 2. Create Datastore Flows for an Agent
-------------------------------------------

To use the  ``Datastore`` in an agent, create flows for the different operations you want the agent to perform.
In the simplest setup, you can define one flow per basic ``Datastore`` operation.
The agent will then determine the correct sequence of actions to achieve the user's goal.

Define flows for:

.. literalinclude:: ../code_examples/howto_datastores.py
      :language: python
      :linenos:
      :start-after: .. start-##_Create_agent_flows
      :end-before: .. end-##_Create_agent_flows

Notice the provided descriptions for the flows to help the agent understand the objective of each operation.

Additionally, you can incorporate more complex behaviors into these flows.
For example, you could ask for user confirmation before deleting entities, or you could provide the user with an overview, and an editing option of the updates made by the agent before they are applied.

Step 3. Create the Agent
------------------------

Finally, create the inventory management agent by combining the LLM, the datastore flows, and a custom instruction:

.. literalinclude:: ../code_examples/howto_datastores.py
      :language: python
      :linenos:
      :start-after: .. start-##_Create_the_agent
      :end-before: .. end-##_Create_the_agent

This agent can now respond to the user and perform actions on the data on their behalf.

Refer to the :doc:`WayFlow Agents Tutorial <../tutorials/basic_agent>` to see how to run this Agent.

Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_datastores.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_datastores.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_datastores.yaml
            :language: yaml


You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_datastores.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginPromptTemplate``
    - ``PluginDatastoreCreateNode``
    - ``PluginDatastoreUpdateNode``
    - ``PluginDatastoreListNode``
    - ``PluginDatastoreDeleteNode``
    - ``PluginJsonToolOutputParser``
    - ``PluginRemoveEmptyNonUserMessageTransform``
    - ``PluginCoalesceSystemMessagesTransform``
    - ``PluginLlamaMergeToolRequestAndCallsTransform``
    - ``PluginInMemoryDatastore``
    - ``ExtendedAgent``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


.. _using-oracle-datastore:

Using Oracle Database Datastore
===============================

This guide mirrors the earlier **in-memory** demo, but leverages Oracle Database
(Autonomous Database on OCI or an on-prem instance) for persistent storage.

.. admonition:: Prerequisites
   :class: tip

   * An Oracle Database instance, reachable from your development machine
   * Wallet files and/or database credentials for this instance
   * A running LLM endpoint (the examples uses vLLM, but any provider works)

Step 1. Configure the connection to the Database
------------------------------------------------

WayFlow supports two secure transport mechanisms for connecting to Oracle databases.

When using **TLS** (one-way TLS) the database presents its certificate, the client verifies it,
and the user authenticates with username and password.

.. literalinclude:: ../code_examples/howto_connect_to_oracle_database.py
   :language: python
   :linenos:
   :start-after: .. start-##_TLS_Connection
   :end-before: .. end-##_TLS_Connection

==============  =============================================================
**Parameter**   **Meaning**
--------------  -------------------------------------------------------------
``user``        Database username (e.g., ``ADMIN``).
``password``    Password for ``user``.
``dsn``         Easy-connect string or TNS alias identifying the service.
                (e.g., ``adb.us-ashburn-1.oraclecloud.com:1522/xyz_high``)
==============  =============================================================

When using **mTLS** (mutual TLS) both sides exchange certificates: the client proves its identity
with a wallet (client cert + private key) in addition to the username and password.
This gives stronger, certificate-based client authentication and is often required for
Oracle Autonomous Database in "Require mTLS" mode.

.. literalinclude:: ../code_examples/howto_connect_to_oracle_database.py
   :language: python
   :linenos:
   :start-after: .. start-##_mTLS_Connection
   :end-before: .. end-##_mTLS_Connection

======================  =============================================================
**Parameter**           **Meaning**
----------------------  -------------------------------------------------------------
``user``                Database username (e.g., ``ADMIN``).
``password``            Password for ``user``.
``dsn``                 Easy-connect string or TNS alias identifying the service.
                        Example:
                        ``adb.us-ashburn-1.oraclecloud.com:1522/xyz_high``
``config_dir``          Directory containing ``sqlnet.ora`` / ``tnsnames.ora``.
                        when you want to reference a
                        TNS alias (e.g. ``<dbname>_high``) instead of a raw DSN.
``wallet_location``     Path to the Oracle Wallet directory that contains
                        ``cwallet.sso`` / ``ewallet.p12``.
``wallet_password``     Password that protects the wallet’s private key.
======================  =============================================================

.. important::
   Do **not** hard-code any database credentials or sensitive connection details directly in your code.
   Please refer to our :doc:`Security Guidelines <../security>` for more information.

Step 2. Define the data model and Datastore
-------------------------------------------

.. warning::
   The following code snippet will create a new ``products`` table in the database.
   Ensure you are using a throwaway schema with no other table named "products" when running this example.

For this guide, we use the same data model as in the in-memory example.
It manages products in an inventory, so a single collection is sufficient.
Datastores also support managing multiple database tables at the same time if needed.

Entities map the relational schema to strongly-typed objects that Flows and
Agents can validate at runtime.
The key difference to the in-memory example is that we require the Entity of
interest to be already defined as a table in the database.

Note that, if you have some columns in the database that are not relevant to your assistant,
you may simply omit them from the Entity definition (as is done in this example with the ``external_system_id``).
However, it may not be possible for the datastore or assistant to create such entities if the omitted columns are required.

.. literalinclude:: ../code_examples/howto_connect_to_oracle_database.py
   :language: python
   :linenos:
   :start-after: .. start-##_Schema
   :end-before:  .. end-##_Schema


Step 3. Create datastore steps
------------------------------

Now that the Datastore is set up, create steps to perform different operations in the flow.
In this guide, your assistant will identify inconsistencies in product descriptions of the same category.
To do so, you will use the :ref:`DatastoreQueryStep <DatastoreQueryStep>` to fetch product information, and a :ref:`PromptExecutionStep <PromptExecutionStep>` to identify the issues.

In particular, the ``DatastoreQueryStep`` can be used with Database Datastores to execute developer-defined SQL queries.
These queries can optionally be parametrized with bind variables.
See the `bind variables guide on the python-oracledb documentation <https://python-oracledb.readthedocs.io/en/latest/user_guide/bind.html>`_ for more information.
See also :ref:`the list of all available Datastore steps <datastoresteps>` for additional operations that can be performed with Oracle Database Datastores.


.. literalinclude:: ../code_examples/howto_connect_to_oracle_database.py
   :language: python
   :linenos:
   :start-after: .. start-##_Create_Datastore_step_and_flow
   :end-before:  .. end-##_Create_Datastore_step_and_flow

Finally, verify that the Flow works as expected:

.. literalinclude:: ../code_examples/howto_connect_to_oracle_database.py
      :language: python
      :linenos:
      :start-after: .. start-##_Execute_flow
      :end-before: .. end-##_Execute_flow


Agent Spec Exporting/Loading
============================

This flow can be exported to Agent Spec using the ``AgentSpecExporter`` as you have seen in the
previous in-memory example, using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_connect_to_oracle_database.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_connect_to_oracle_database.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_connect_to_oracle_database.yaml
            :language: yaml


.. warning::

   The Oracle Database Connection Config objects contain several sensitive values
   (like username, password, wallet location) that will not be serialized by the ``AgentSpecExporter``.
   These will be serialized as references that must be resolved at loading time, by specifying the values
   of these sensitive fields in the ``component_registry`` argument of the loader:

   .. literalinclude:: ../code_examples/howto_connect_to_oracle_database.py
      :language: python
      :start-after: .. start-##_Provide_sensitive_information_when_loading_the_Agent_Spec_config
      :end-before: .. end-##_Provide_sensitive_information_when_loading_the_Agent_Spec_config

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_connect_to_oracle_database.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginDatastoreQueryNode``
    - ``PluginOracleDatabaseDatastore``
    - ``PluginTlsOracleDatabaseConnectionConfig``
    - ``PluginOutputMessageNode``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


Next steps
==========

Having learned how to connect WayFlow assistants to data sources, you may now proceed to:

- :doc:`Create Conditional Transitions in Flows <conditional_flows>`
- :doc:`Create a ServerTool from a Flow <create_a_tool_from_a_flow>`


Full code
=========

In-memory datastore
-------------------

Click on the card at the :ref:`top of this page <top-howtodatastores>`
to download the full code for this guide or copy the code below.

.. collapse:: Connecting Assistants to User Data (full code)

    .. literalinclude:: ../end_to_end_code_examples/howto_datastores.py
        :language: python
        :linenos:

Oracle Database datastore
-------------------------

Click on the card at the :ref:`top of this page <top-howtodatastores>`
to download the full code for this guide, or copy the code below.

.. collapse:: Connecting Assistants to Oracle Database (full code)

    .. literalinclude:: ../end_to_end_code_examples/howto_connect_to_oracle_database.py
        :language: python
        :linenos:
