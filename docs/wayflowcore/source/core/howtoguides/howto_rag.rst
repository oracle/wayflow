.. _top-rag:

============================================
How to Build RAG-Powered Assistants
============================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_rag.py
        :link-alt: RAG how-to script

        Python script/notebook for this guide.


.. admonition:: Prerequisites

    This guide assumes familiarity with

    - :doc:`Agents <../tutorials/basic_agent>`
    - :doc:`Flows <../tutorials/basic_flow>`
    - :doc:`Datastores <howto_datastores>`


Retrieval-Augmented Generation (RAG) is a powerful technique that enhances AI assistants by connecting them to external knowledge sources.
Instead of relying solely on their training data, RAG-enabled assistants can search through your specific documents, databases, or knowledge bases to provide accurate, up-to-date, and contextually relevant responses.

In this tutorial, you will:

- **Configure vector search** to enable semantic similarity matching in your data.
- **Create a searchable datastore** with embeddings for efficient retrieval.
- **Create a RAG-powered Agent** that autonomously searches for information to fulfill user requests.
- **Build a RAG-powered Flow** using SearchStep for structured retrieval workflows.
- **Control which fields are used for embeddings** to optimize search relevance.

This tutorial demonstrates RAG using Oracle Database as a persistent, production-ready vector store.
You will use OracleDatabaseDatastore and Oracle AI Vector Search throughout.


Concepts shown in this guide
============================

- :ref:`VectorRetrieverConfig<vector_retriever_config>` and :ref:`SearchConfig<search_config>` for configuring vector search
- :ref:`SearchToolBox<search_tool_box>` for providing search capabilities to Agents
- :ref:`SearchStep<searchstep>` for retrieval in Flows
- :ref:`VectorConfig<vector_config>` and :ref:`SerializerConfig<serializer_config>` for controlling embedding generation
- :ref:`Embedding models<embeddingmodel>` for converting text to vectors

Before you begin, you must connect to Oracle Database and create the table(s) needed for vector search. See below.

Step 0. OracleDatabaseDatastore: Connecting and Automated Table Preparation
===========================================================================

To use this guide, you should prepare an Oracle Database with vector search capability. This tutorial demonstrates an example for how you can automate the connection and table setup directly from Python.
To follow this guide, you just need to have a connection to Oracle Database and should be able to perform operations on the Database.

**Connection & Authentication**

The code automatically detects either mTLS or simple TLS database connectivity using environment variables. The following environment variables must be set for your Oracle connection:

.. code-block:: shell

   # For mTLS connection (Autonomous DB/Wallet)
   export ADB_CONFIG_DIR=encrypted/wallet/config
   export ADB_WALLET_DIR=encrypted/wallet
   export ADB_WALLET_SECRET='supersecret'
   export ADB_DB_USER=garage_user
   export ADB_DB_PASSWORD=secret
   export ADB_DSN="adb....oraclecloud.com"

   # Or for TLS connection
   export ADB_DB_USER=garage_user
   export ADB_DB_PASSWORD=secret
   export ADB_DSN="dbhost:port/servicename"

Reference: `Oracle Database TLS setup guide <https://docs.oracle.com/en/database/oracle/oracle-database/26/dbseg/configuring-transport-layer-security-encryption.html#GUID-8B82DD7E-7189-4FE9-8F3B-4E521706E1E4>`_

.. warning::
   Using environment variables for storing sensitive connection details is not suitable for production environments.

The code will choose the most secure available connection automatically.

**Table Schema Setup and DDL Execution**

To be able to retrieve from you data, you need it stored in a database. We can use the Oracle Database to store the entities that will be retrieved using Oracle 23AI.
To connect to it, configure the client with ``oracledb`` and specify the schema of the data.
The schema for this example is:

.. code-block:: sql

   CREATE TABLE motorcycles (
     owner_name VARCHAR2(255),
     model_name VARCHAR2(255),
     description VARCHAR2(255),
     hp INTEGER,
     serialized_text VARCHAR2(1023),
     embeddings VECTOR
   );

This schema includes both a conventional text representation (serialized_text) and a VECTOR column for semantic search. The Python code handles both the creation (and dropping) of this table and the population of its data.

.. _setting_up:

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Oracle-connection
   :end-before: .. end-##_Oracle-connection

The code:

* Detects your connection configuration (mTLS/TLS)
* Creates the target table in Oracle using your credentials with:
   * the table fields to match the entity schema (see next section)
   * an additional `serial_text` TEXT field to store the string used for embeddings
   * an additional `embeddings` VECTOR field for the vector search

Note that if you already have a table configured with the same name, you will need to drop the table before running this code.
Refer to the :ref:`Cleaning Up section<cleanup>` to see how this can be done.

**Required Privileges**

Make sure your user has privileges to drop, create, insert, update, and select on the target table (motorcycles).

Also make sure you have installed `oracledb <https://github.com/oracle/python-oracledb>`_.

.. note::
   You can install the required package using pip:

   .. code-block:: shell

      pip install oracledb

Setting Up RAG
==============

A Retrieval-Augmented Generation (RAG) system is composed of two core components: a retriever and an LLM (Large Language Model).
The retriever is responsible for searching your data for relevant information, while the LLM uses the retriever as a tool to supplement its responses with up-to-date knowledge.
To achieve this, we would thus need both a retriever with an embedding model and an LLM to perform end-to-end RAG.

Before creating these RAG-powered assistants, you will need to set up the data source which supports vector search capabilities.

Step 1. Configure models
------------------------

You need an embedding model for the retriever as it converts your text data into embeddings (vector representations).
The retriever uses these embeddings to perform semantic searches, enabling the system to retrieve relevant information based on meaning rather than just keywords.

Configure the embedding model for vector search:


.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Embedding-config
   :end-before: .. end-##_Embedding-config

Configure your LLM:

The LLM (Large Language Model) plays two crucial roles in RAG.
First, it generates a suitable retrieval query to fetch relevant information from your datastore.
Then, after retrieval, the LLM formats and integrates the retrieved text into a coherent, user-facing response.
Understanding the role of the LLM is key to grasping why RAG involves both retrieval and generative capabilities: retrieval brings in up-to-date,
domain-specific knowledge, while the LLM ensures information is expressed in conversational form for the user.

.. include:: ../_components/llm_config_tabs.rst

Step 2. Define searchable data
------------------------------

First, define the schema for your data. Note that the collection and property names defined below should match the table and column names configured in Oracle Database (see the table we created in step 0).

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Entity-define
   :end-before: .. end-##_Entity-define

Next, we configure a vector and search config for searching in this data. A few things to note:

* If you have configured a vector index, ensure you put the same distance metric in the ``distance_metric`` parameter of the :ref:`VectorRetrieverConfig<vector_retriever_config>`. Without doing so, the approximate search will not work.
* The embedding model passed in either the :ref:`VectorConfig<vector_config>` or the :ref:`VectorRetrieverConfig<vector_retriever_config>` should be the same as the model used to generate the corresponding embeddings column. If you specify an embedding model in both the classes, the embedding models must match.
* You can configure the ``vectors`` parameter in the :ref:`VectorRetrieverConfig<vector_retriever_config>` to explicitly specify the vector column or :ref:`VectorConfig<vector_config>` you want to search.
* If ``vectors`` is `None`, the vector column to search will be inferred by either an existing vector config with the same collection name or a vector column in the collection. If there are two or more matching vector configurations, an error will be raised.
* If you do not specify a ``collection_name`` in the :ref:`VectorConfig<vector_config>`, the config is applicable to all collections in your datastore.

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Search-config
   :end-before: .. end-##_Search-config

Then, you can create the datastore with search capability by passing the search configuration. To fill the data, we perform serialization of fields using the :ref:`ConcatSerializerConfig<concat_serializer_config>`.
For each motorcycle entity, this will concatenate all fields and their values into a single string called ``serialized_text``, which is then embedded by the model. The resulting embedding vector is assigned to the ``embeddings`` field.
This approach gives you control over what text is represented in your vector index and is transparent/easy to audit.

By default, all text fields in your entities are used to generate embeddings. However, you may want to exclude certain fields like IDs, prices, or metadata from the embedding calculation while still returning them in search results.
This can be achieved by configuring the ``columns_to_exclude`` parameter in :ref:`ConcatSerializerConfig<concat_serializer_config>`.

Note that ``datastore.create()`` is used here for demonstration only and is not the recommended way to load data into Oracle Database tables.
For real applications, populate your tables with ``SQL`` (e.g., bulk INSERT/UPDATE), then use the Datastore APIs to index, search, and take advantage of WayFlow features.

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Datastore-create-rag
   :end-before: .. end-##_Datastore-create-rag

**Create a Vector Index for Efficient Vector Search**

For production semantic search, it is also recommended that you create a vector index on the embeddings field using Oracle's HNSW (or IVF) index.
Having a vector index configured is not necessary for search to work, but it will speed things up as it will use approximate search rather than using exact search.
Note that if you want to use the vector index as intended, the distance metric configured in the index should be the same as the distance metric used in the :ref:`VectorRetrieverConfig<vector_retriever_config>` (you can use
:ref:`SimilarityMetric<similarity_metric>` for simplicity).
The code below creates this index programmatically and commits it to your Oracle DB. (Skip this step for in-memory datastores.)

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Create-vector-index
   :end-before: .. end-##_Create-vector-index

You can test the search directly:

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Direct-search-example
   :end-before: .. end-##_Direct-search-example


With your RAG-ready datastore in place, the next step is to use it in real applications. In WayFlow, the two primary patterns for Retrieval-Augmented Generation are:

- Integrating RAG capabilities into conversational Agents for dynamic, dialogue-driven retrieval
- Building Flows for more structured and predictable retrieval workflows.

In the next sections, you'll see hands-on how to use both approaches, starting with Agents.


RAG in Agents
=============

We'll start by showing how to empower your Agents with retrieval capabilities, allowing them to proactively fetch and reason over domain-specific information as part of their decision-making.
Agents provide a flexible approach to RAG by autonomously deciding when and how to search for information based on the conversation context.

Step 1. Create search tools for the Agent
-----------------------------------------

Convert your searchable datastore into tools that an Agent can use:

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Agent_Tools_Rag
   :end-before: .. end-##_Agent_Tools_Rag

The ``get_search_tools`` method creates a :ref:`SearchToolBox<search_tool_box>` that:

- Dynamically generates search tools for each collection
- Respects the ``k`` parameter to limit result count
- Returns results as JSON for easy parsing by the LLM

Step 2. Create the RAG Agent
----------------------------

Create an Agent with search capabilities:

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Agent_Create_Rag
   :end-before: .. end-##_Agent_Create_Rag

This Agent will:

- Automatically use search tools when it needs information
- Combine search results with its reasoning capabilities
- Provide accurate answers based on your specific data

Test the Agent:

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Agent_Test_Rag
   :end-before: .. end-##_Agent_Test_Rag

The Agent autonomously decides when to search, what to search for, and how to use the results to answer questions.


RAG in Flows
============

While Agents offer flexibility, Flows provide a structured approach to RAG with predictable retrieval workflows ideal for specific use cases.

Step 1. Create the RAG Flow
---------------------------

Create a Flow that searches for relevant information before generating a response:

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Flow_Steps_Rag
   :end-before: .. end-##_Flow_Steps_Rag

Key points:

- The :ref:`SearchStep<searchstep>` uses semantic search to find relevant documents based on the user's query.
- The ``k`` parameter limits the number of documents retrieved.
- Retrieved documents are passed to the LLM along with the original query for contextualized responses.

Step 2. Build and test the Flow
-------------------------------

Build the complete Flow with control and data connections:

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Flow_Build_Rag
   :end-before: .. end-##_Flow_Build_Rag

The Flow provides a predictable pipeline: user input → search → response generation.


Advanced RAG Techniques
=======================


Filtering search results
------------------------

You can filter search results based on metadata:

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Advanced_Filtering
   :end-before: .. end-##_Advanced_Filtering

Multiple search configurations
------------------------------

Create specialized search configurations for different use cases:

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Advanced_Multi_Config
   :end-before: .. end-##_Advanced_Multi_Config

**How multiple search configs work:**

- Each :ref:`SearchConfig<search_config>` must have a unique name (auto-generated if not provided)
- Search configs can target the same collection with different settings (distance metrics, vector configs)
- Search Configs can also target multiple collections if no collection name is specified, provided there does not exist another search config which matches the collection name to search on.
- When calling :ref:`Datastore.search()<datastore>`, you specify which config to use via the ``search_config`` parameter
- If no ``search_config`` is specified, the system looks for a default config for that collection, given that a ``collection_name`` is specified
- The first config that matches the collection (or has no specific collection) becomes the default

**When to use each config**

- ``precise_search``: Uses cosine similarity for semantic matching (best for meaning-based searches)
- ``broad_search``: Uses Euclidean distance for broader matches (considers all dimensions equally)
- You explicitly choose which to use: ``datastore.search(..., search_config="precise_search")``

Customizing search behavior in Agents
-------------------------------------

Create specialized search toolboxes with different parameters:

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Advanced_Custom_Toolbox
   :end-before: .. end-##_Advanced_Custom_Toolbox

**How specialized toolboxes work:**

- Each toolbox creates different search functions with fixed parameters
- ``detailed_search``: Always returns 10 results (k=10) for comprehensive analysis
- ``quick_search``: Always returns 1 result (k=1) for focused answers
- The Agent sees these as different tools: ``search_motorcycles_detailed`` vs ``search_motorcycles_quick``

**When each toolbox is used:**

- The Agent autonomously decides based on:

  - The user's question complexity
  - Instructions in ``custom_instruction``
  - Context of the conversation

- For "tell me about all sport bikes" → likely uses ``detailed_search``
- For "who owns the Vortex?" → likely uses ``quick_search``
- The Agent's reasoning determines the choice, guided by your instructions


Manual Serialization of Fields for Embeddings
---------------------------------------------

In this example, we show a manual serialization approach that performs cross-field logic that cannot be expressed with :ref:`ConcatSerializerConfig<concat_serializer_config>`.
Instead of merely concatenating fields, we:
- Compute derived attributes (e.g., performance class and hp bands from numeric horsepower)
- Conditionally weight salient tokens (repeat model name for high-HP bikes)
- Inject domain keywords based on the description semantics
- Reorder fields and output a structured, sectioned Markdown document

This goes beyond per-field preprocessing and simple separators; it uses the full entity structure at once and conditional logic across multiple fields.

.. literalinclude:: ../code_examples/howto_rag.py
   :language: python
   :linenos:
   :start-after: .. start-##_Manual_Serialization_Advanced
   :end-before: .. end-##_Manual_Serialization_Advanced

Example usage when generating embeddings:

.. code-block:: python

   for entity in motorcycle_data:
       entity["serialized_text"] = serialize_motorcycle_advanced(entity)
       entity["embeddings"] = embedding_model.embed([entity["serialized_text"]])[0]

**Why use explicit serialization?**

- Cross-field logic: derive fields (e.g., performance class from hp) and conditionally add keywords.
- Conditional weighting: repeat or emphasize tokens under certain conditions (e.g., horsepower thresholds).
- Structured formatting: generate Markdown sections and control field ordering for domain salience.
- Auditable and deterministic: the exact text used for embeddings is transparent and reproducible.

Limitations of ConcatSerializerConfig and when to choose manual serialization:

- ConcatSerializerConfig is powerful for per-field concatenation with simple pre/post processing and exclusion of columns.
- It does not perform arbitrarily complex cross-field computations, conditional token weighting, or multi-field derived features.
- Choose manual serialization whenever you need entity-level reasoning to craft the embedding text, beyond simple concatenation and formatting.

.. note::

   Selective field embedding—using serializers to specify which fields participate in embedding generation—is best supported and straightforward in the :ref:`InMemoryDatastore<inmemorydatastore>` backend (see its API for serializer support).
   For :ref:`OracleDatabaseDatastore<oracledatabasedatastore>`, you are responsible for constructing and storing the embeddings explicitly, and there is no out-of-the-box field-level selection.
   For configuring the serialized text and embeddings column externally, you can make use of :ref:`ConcatSerializerConfig<concat_serializer_config>`
   outside the Datastore while generating the serialized text for the embeddings. :ref:`OracleDatabaseDatastore<oracledatabasedatastore>` assumes that the embedding column has already been generated and does not implicitly create embeddings.

.. note::

   For rapid prototyping, use :ref:`InMemoryDatastore<inmemorydatastore>` with custom serializers for full flexibility, then migrate to :ref:`OracleDatabaseDatastore<oracledatabasedatastore>` for production workloads that require persistence and scalability.


Agent Spec Exporting/Loading
============================

You can export the agent configuration to its Agent Spec configuration using the :ref:`AgentSpecExporter<agentspecexporter>`.

.. literalinclude:: ../code_examples/howto_rag.py
    :language: python
    :start-after: .. start-##_Export_Config_to_Agent_Spec
    :end-before: .. end-##_Export_Config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_rag.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_rag.yaml
            :language: yaml

.. warning::

   The Oracle Database Connection Config objects contain several sensitive values
   (like username, password, wallet location) that will not be serialized by the ``AgentSpecExporter``.
   These will be serialized as references that must be resolved at loading time, by specifying the values
   of these sensitive fields in the ``component_registry`` argument of the loader:

   .. literalinclude:: ../code_examples/howto_rag.py
      :language: python
      :start-after: .. start-##_Provide_sensitive_information_when_loading_the_Agent_Spec_config
      :end-before: .. end-##_Provide_sensitive_information_when_loading_the_Agent_Spec_config

You can then load the configuration back to an assistant using the :ref:`AgentSpecLoader<agentspecloader>`.

.. literalinclude:: ../code_examples/howto_rag.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_Config
    :end-before: .. end-##_Load_Agent_Spec_Config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - :ref:`PluginToolFromToolBox<agentspectoolfromtoolbox>`
    - :ref:`PluginSearchToolBox<agentspecsearchtoolbox>`
    - :ref:`PluginOracleDatabaseDatastore<agentspecoracledatabasedatastore>`
    - :ref:`PluginTlsOracleDatabaseConnectionConfig<agentspectlsoracledatabaseconnectionconfig>`
    - :ref:`PluginSearchConfig<agentspecsearchconfig>`
    - :ref:`PluginVectorRetrieverConfig<agentspecvectorretrieverconfig>`
    - :ref:`PluginVllmEmbeddingConfig<agentspec_vllm_embedding_model_config>`
    - :ref:`PluginPromptTemplate<agentspecprompttemplate>`
    - :ref:`PluginJsonToolOutputParser<agentspecjsontooloutputparser>`
    - :ref:`PluginRemoveEmptyNonUserMessageTransform<agentspecremoveemptynonusermessagetransform>`
    - :ref:`PluginCoalesceSystemMessagesTransform<agentspeccoalescesystemmessagestransform>`
    - :ref:`PluginLlamaMergeToolRequestAndCallsTransform<agentspecllamamergetoolrequestsandcallstransform>`

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`

.. _cleanup:

Cleaning Up Datastore
=====================

Before moving on, you may want to cleanup the table created in Oracle Database for this tutorial. For cleaning up, you can use the following code below.
This code will drop the ``motorcycles`` from your Oracle Database using the ``environment_config`` function defined in the :ref:`Setting Up<setting_up>` section.

.. literalinclude:: ../code_examples/howto_rag.py
    :language: python
    :start-after: .. start-##_Cleanup_datastore
    :end-before: .. end-##_Cleanup_datastore

Recap
=====

In this guide, you learned how to build RAG-powered assistants using WayFlow:


The key difference between Agents and Flows for RAG:

- **Agents** offer dynamic, autonomous retrieval based on the conversation context - ideal when you want the AI to decide when and what to search
- **Flows** provide predictable, structured retrieval workflows - ideal when you want consistent behavior for specific use cases

Key techniques covered:

- **Basic RAG**: Using all fields for embeddings and search
- **Filtered search**: Limiting results based on metadata
- **Multiple search configs**: Different strategies for different use cases with explicit selection
- **Multiple toolboxes**: Allowing Agents to choose between different search strategies autonomously


.. important::
   **Before deploying your RAG application to production, you MUST:**

   1. **Configure Oracle AI Vector Search** for scalable vector operations
   2. **Test performance** with production-scale data
   3. **Implement proper error handling** and monitoring

   For development and testing, you can use the ``InMemoryDataStore``, the same APIs work with both datastores:

   .. code-block:: python

      # Development (NOT for production)
      datastore = InMemoryDatastore(schema={"motorcycles": motorcycles})

      # Production (use this instead)
      datastore = OracleDatabaseDatastore(
          connection_string="your_oracle_connection",
          schema={"motorcycles": motorcycles}
          # connection db params
      )

   See the `OracleDatabaseDatastore guide` for complete migration instructions.


Next steps
==========

Deployment Considerations: Now your application is backed by OracleDatabaseDatastore from the start.
Your setup is production-ready, persistent, and scalable using Oracle AI Vector Search.

- Always test with your own database connection and schema for production.
- Ensure your Oracle user has all necessary table privileges.
- For advanced vector functionality, see the OracleDatabaseDatastore API guide.


Full code
=========

Click on the card at the :ref:`top of this page <top-rag>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_rag.py
    :language: python
    :linenos:
