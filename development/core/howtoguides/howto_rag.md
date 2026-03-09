<a id="top-rag"></a>

# How to Build RAG-Powered Assistants![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[RAG how-to script](../end_to_end_code_examples/howto_rag.py)

#### Prerequisites
This guide assumes familiarity with

- [Agents](../tutorials/basic_agent.md)
- [Flows](../tutorials/basic_flow.md)
- [Datastores](howto_datastores.md)

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

## Concepts shown in this guide
- [VectorRetrieverConfig](../api/search.md#vector-retriever-config) and [SearchConfig](../api/search.md#search-config) for configuring vector search
- [SearchToolBox](../api/search.md#search-tool-box) for providing search capabilities to Agents
- [SearchStep](../api/flows.md#searchstep) for retrieval in Flows
- [VectorConfig](../api/search.md#vector-config) and [SerializerConfig](../api/search.md#serializer-config) for controlling embedding generation
- [Embedding models](../api/embeddingmodels.md#id1) for converting text to vectors

Before you begin, you must connect to Oracle Database and create the table(s) needed for vector search. See below.

## Step 0. OracleDatabaseDatastore: Connecting and Automated Table Preparation

To use this guide, you should prepare an Oracle Database with vector search capability. This tutorial demonstrates an example for how you can automate the connection and table setup directly from Python.
To follow this guide, you just need to have a connection to Oracle Database and should be able to perform operations on the Database.

**Connection & Authentication**

The code automatically detects either mTLS or simple TLS database connectivity using environment variables. The following environment variables must be set for your Oracle connection:

```shell
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
```

Reference: [Oracle Database TLS setup guide](https://docs.oracle.com/en/database/oracle/oracle-database/26/dbseg/configuring-transport-layer-security-encryption.html#GUID-8B82DD7E-7189-4FE9-8F3B-4E521706E1E4)

#### WARNING
Using environment variables for storing sensitive connection details is not suitable for production environments.

The code will choose the most secure available connection automatically.

**Table Schema Setup and DDL Execution**

To be able to retrieve from you data, you need it stored in a database. We can use the Oracle Database to store the entities that will be retrieved using Oracle 23AI.
To connect to it, configure the client with `oracledb` and specify the schema of the data.
The schema for this example is:

```sql
CREATE TABLE motorcycles (
  owner_name VARCHAR2(255),
  model_name VARCHAR2(255),
  description VARCHAR2(255),
  hp INTEGER,
  serialized_text VARCHAR2(1023),
  embeddings VECTOR
);
```

This schema includes both a conventional text representation (serialized_text) and a VECTOR column for semantic search. The Python code handles both the creation (and dropping) of this table and the population of its data.

<a id="setting-up"></a>
```python
import os
import oracledb

from wayflowcore.datastore.oracle import MTlsOracleDatabaseConnectionConfig, TlsOracleDatabaseConnectionConfig

def environment_config():
    mtls_vars = (
        "ADB_CONFIG_DIR",
        "ADB_WALLET_DIR",
        "ADB_WALLET_SECRET",
        "ADB_DB_USER",
        "ADB_DB_PASSWORD",
        "ADB_DSN",
    )
    tls_vars = ("ADB_DB_USER", "ADB_DB_PASSWORD", "ADB_DSN")
    if all(v in os.environ for v in mtls_vars):
        return MTlsOracleDatabaseConnectionConfig(
            config_dir=os.environ["ADB_CONFIG_DIR"],
            wallet_location=os.environ["ADB_WALLET_DIR"],
            wallet_password=os.environ["ADB_WALLET_SECRET"],
            user=os.environ["ADB_DB_USER"],
            password=os.environ["ADB_DB_PASSWORD"],
            dsn=os.environ["ADB_DSN"],
            id="oracle_datastore_connection_config",
        )
    if all(v in os.environ for v in tls_vars):
        return TlsOracleDatabaseConnectionConfig(
            user=os.environ["ADB_DB_USER"],
            password=os.environ["ADB_DB_PASSWORD"],
            dsn=os.environ["ADB_DSN"],
            id="oracle_datastore_connection_config",
        )
    raise Exception("Required OracleDB environment variables not found")


connection_config = environment_config()

ORACLE_DB_DDL = """
    CREATE TABLE motorcycles (
    owner_name VARCHAR2(255),
    model_name VARCHAR2(255),
    description VARCHAR2(255),
    hp INTEGER,
    serialized_text VARCHAR2(1023),
    embeddings VECTOR
)"""

with connection_config.get_connection() as conn:
    with conn.cursor() as cursor:
        try:
            cursor.execute(ORACLE_DB_DDL)
        except oracledb.DatabaseError as e:
            print(f"DDL execution warning: {e}")
```

The code:

* Detects your connection configuration (mTLS/TLS)
* Creates the target table in Oracle using your credentials with:
  : * the table fields to match the entity schema (see next section)
    * an additional serial_text TEXT field to store the string used for embeddings
    * an additional embeddings VECTOR field for the vector search

Note that if you already have a table configured with the same name, you will need to drop the table before running this code.
Refer to the [Cleaning Up section](#cleanup) to see how this can be done.

**Required Privileges**

Make sure your user has privileges to drop, create, insert, update, and select on the target table (motorcycles).

Also make sure you have installed [oracledb](https://github.com/oracle/python-oracledb).

#### NOTE
You can install the required package using pip:

```shell
pip install oracledb
```

## Setting Up RAG

A Retrieval-Augmented Generation (RAG) system is composed of two core components: a retriever and an LLM (Large Language Model).
The retriever is responsible for searching your data for relevant information, while the LLM uses the retriever as a tool to supplement its responses with up-to-date knowledge.
To achieve this, we would thus need both a retriever with an embedding model and an LLM to perform end-to-end RAG.

Before creating these RAG-powered assistants, you will need to set up the data source which supports vector search capabilities.

### Step 1. Configure models

You need an embedding model for the retriever as it converts your text data into embeddings (vector representations).
The retriever uses these embeddings to perform semantic searches, enabling the system to retrieve relevant information based on meaning rather than just keywords.

Configure the embedding model for vector search:

```python
from wayflowcore.embeddingmodels import VllmEmbeddingModel
# Configure embedding model for vector search
embedding_model = VllmEmbeddingModel(base_url="EMBEDDING_API_URL", model_id="model-id")
```

Configure your LLM:

The LLM (Large Language Model) plays two crucial roles in RAG.
First, it generates a suitable retrieval query to fetch relevant information from your datastore.
Then, after retrieval, the LLM formats and integrates the retrieved text into a coherent, user-facing response.
Understanding the role of the LLM is key to grasping why RAG involves both retrieval and generative capabilities: retrieval brings in up-to-date,
domain-specific knowledge, while the LLM ensures information is expressed in conversational form for the user.




OCI GenAI

```python
from wayflowcore.models import OCIGenAIModel, OCIClientConfigWithApiKey

llm = OCIGenAIModel(
    model_id="provider.model-id",
    compartment_id="compartment-id",
    client_config=OCIClientConfigWithApiKey(
        service_endpoint="https://url-to-service-endpoint.com",
    ),
)
```

vLLM

```python
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)
```

Ollama

```python
from wayflowcore.models import OllamaModel

llm = OllamaModel(
    model_id="model-id",
)
```

### Step 2. Define searchable data

First, define the schema for your data. Note that the collection and property names defined below should match the table and column names configured in Oracle Database (see the table we created in step 0).

```python
# Define the motorcycle entity schema
from wayflowcore.datastore import Entity
from wayflowcore.property import IntegerProperty, StringProperty, VectorProperty

motorcycles = Entity(
    description="Motorcycles in our garage",
    properties={
        "owner_name": StringProperty(description="Name of the motorcycle owner"),
        "model_name": StringProperty(description="Motorcycle model and brand"),
        "description": StringProperty(description="Detailed description of the motorcycle"),
        "hp": IntegerProperty(description="Horsepower of the motorcycle"),
        "serialized_text": StringProperty(description="Concatenated string of all columns"),
        "embeddings": VectorProperty(description="Generated embeddings for serialized_text"),
    },
)
```

Next, we configure a vector and search config for searching in this data. A few things to note:

* If you have configured a vector index, ensure you put the same distance metric in the `distance_metric` parameter of the [VectorRetrieverConfig](../api/search.md#vector-retriever-config). Without doing so, the approximate search will not work.
* The embedding model passed in either the [VectorConfig](../api/search.md#vector-config) or the [VectorRetrieverConfig](../api/search.md#vector-retriever-config) should be the same as the model used to generate the corresponding embeddings column. If you specify an embedding model in both the classes, the embedding models must match.
* You can configure the `vectors` parameter in the [VectorRetrieverConfig](../api/search.md#vector-retriever-config) to explicitly specify the vector column or [VectorConfig](../api/search.md#vector-config) you want to search.
* If `vectors` is None, the vector column to search will be inferred by either an existing vector config with the same collection name or a vector column in the collection. If there are two or more matching vector configurations, an error will be raised.
* If you do not specify a `collection_name` in the [VectorConfig](../api/search.md#vector-config), the config is applicable to all collections in your datastore.

```python
from wayflowcore.search import SearchConfig, VectorRetrieverConfig, VectorConfig

# Configure Vector Config for Search
vector_config = VectorConfig(
    model=embedding_model,
    collection_name="motorcycles",
    vector_property="embeddings"
)

# Configure vector search for semantic similarity matching
search_config = SearchConfig(
    name="motorcycle_search",
    retriever=VectorRetrieverConfig(
        model=embedding_model,
        collection_name="motorcycles",
        distance_metric="cosine_distance",
    ),
)
```

Then, you can create the datastore with search capability by passing the search configuration. To fill the data, we perform serialization of fields using the [ConcatSerializerConfig](../api/search.md#concat-serializer-config).
For each motorcycle entity, this will concatenate all fields and their values into a single string called `serialized_text`, which is then embedded by the model. The resulting embedding vector is assigned to the `embeddings` field.
This approach gives you control over what text is represented in your vector index and is transparent/easy to audit.

By default, all text fields in your entities are used to generate embeddings. However, you may want to exclude certain fields like IDs, prices, or metadata from the embedding calculation while still returning them in search results.
This can be achieved by configuring the `columns_to_exclude` parameter in [ConcatSerializerConfig](../api/search.md#concat-serializer-config).

Note that `datastore.create()` is used here for demonstration only and is not the recommended way to load data into Oracle Database tables.
For real applications, populate your tables with `SQL` (e.g., bulk INSERT/UPDATE), then use the Datastore APIs to index, search, and take advantage of WayFlow features.

```python
from wayflowcore.datastore import OracleDatabaseDatastore
from wayflowcore.search.config import ConcatSerializerConfig

# Create Oracle Database datastore with vector search capability
datastore = OracleDatabaseDatastore(
    connection_config=connection_config,
    schema={"motorcycles": motorcycles},
    search_configs=[search_config],
    vector_configs=[vector_config],
)

# Sample motorcycle data
motorcycle_data = [
    {
        "owner_name": "John Smith",
        "model_name": "Galaxion Thunderchief",
        "hp": 87,
        "description": "Classic American touring motorcycle with chrome details and comfortable seating.",
    },
    {
        "owner_name": "Sarah Johnson",
        "model_name": "Starlite Apex-R7",
        "hp": 118,
        "description": "High-performance supersport motorcycle designed for track racing.",
    },
    {
        "owner_name": "Mike Chen",
        "model_name": "Orion CX 1300 Helix",
        "hp": 136,
        "description": "Premium adventure touring motorcycle with advanced electronics.",
    },
    {
        "owner_name": "Emily Davis",
        "model_name": "Nebula Trailrunner 500",
        "hp": 45,
        "description": "Street-legal dirt bike perfect for off-road adventures.",
    },
    {
        "owner_name": "Carlos Rodriguez",
        "model_name": "Vortex Momentum X1",
        "hp": 214,
        "description": "Italian superbike with MotoGP-derived technology and stunning performance.",
    },
]
# Configure Serializer to serialize columns into a string
serializer = ConcatSerializerConfig()
# Generate serialized_text and embeddings
for entity in motorcycle_data:
    entity["serialized_text"] = serializer.serialize(entity)
    entity["embeddings"] = embedding_model.embed([entity["serialized_text"]])[0]

# Populate the OracleDB datastore
datastore.create(collection_name="motorcycles", entities=motorcycle_data)
```

**Create a Vector Index for Efficient Vector Search**

For production semantic search, it is also recommended that you create a vector index on the embeddings field using Oracle’s HNSW (or IVF) index.
Having a vector index configured is not necessary for search to work, but it will speed things up as it will use approximate search rather than using exact search.
Note that if you want to use the vector index as intended, the distance metric configured in the index should be the same as the distance metric used in the [VectorRetrieverConfig](../api/search.md#vector-retriever-config) (you can use
[SimilarityMetric](../api/search.md#similarity-metric) for simplicity).
The code below creates this index programmatically and commits it to your Oracle DB. (Skip this step for in-memory datastores.)

```python
import oracledb

# Configure Vector Index
VECTOR_INDEX_DDL = """
    CREATE VECTOR INDEX hnsw_image
    ON motorcycles (embeddings)
    ORGANIZATION INMEMORY NEIGHBOR GRAPH
    DISTANCE COSINE
    WITH TARGET ACCURACY 95;
"""
with connection_config.get_connection() as connection:
    with connection.cursor() as cursor:
        try:
            cursor.execute(VECTOR_INDEX_DDL)
            connection.commit()
        except oracledb.DatabaseError as e:
            print(f"Vector Index Creation warning: {e}")
```

You can test the search directly:

```python
# Example of direct vector search
results = datastore.search(
    collection_name="motorcycles", query="high performance sport bike for racing", k=3
)

print("Direct search results:")
for result in results:
    print(f"- {result['model_name']}")

# Direct search results:
# - Starlite Apex-R7
# - Vortex Momentum X1
# - Nebula Trailrunner 500
```

With your RAG-ready datastore in place, the next step is to use it in real applications. In WayFlow, the two primary patterns for Retrieval-Augmented Generation are:

- Integrating RAG capabilities into conversational Agents for dynamic, dialogue-driven retrieval
- Building Flows for more structured and predictable retrieval workflows.

In the next sections, you’ll see hands-on how to use both approaches, starting with Agents.

## RAG in Agents

We’ll start by showing how to empower your Agents with retrieval capabilities, allowing them to proactively fetch and reason over domain-specific information as part of their decision-making.
Agents provide a flexible approach to RAG by autonomously deciding when and how to search for information based on the conversation context.

### Step 1. Create search tools for the Agent

Convert your searchable datastore into tools that an Agent can use:

```python
# Create search tools for the agent
search_toolbox = datastore.get_search_toolbox(k=3)
```

The `get_search_tools` method creates a [SearchToolBox](../api/search.md#search-tool-box) that:

- Dynamically generates search tools for each collection
- Respects the `k` parameter to limit result count
- Returns results as JSON for easy parsing by the LLM

### Step 2. Create the RAG Agent

Create an Agent with search capabilities:

```python
from textwrap import dedent
from wayflowcore.agent import Agent

# Create RAG-powered agent
rag_agent = Agent(
    tools=search_toolbox.get_tools(),
    llm=llm,
    custom_instruction=dedent(
        """
        You are a helpful motorcycle garage assistant with access to our motorcycle database.

        IMPORTANT:
        - Always search for relevant information before answering questions about motorcycles
        - Base your answers on the search results
        - If you can't find relevant information, say so clearly
        - Be specific and mention details from the search results

        You have access to search tools that can find information about:
        - Motorcycle models and specifications
        - Owners of motorcycles
        - Horsepower and performance details
        - Descriptions and features
        """
    ),
    initial_message="Hello! I'm your RAG-powered motorcycle assistant. I can search our database to answer your questions about the motorcycles in our garage.",
)
```

This Agent will:

- Automatically use search tools when it needs information
- Combine search results with its reasoning capabilities
- Provide accurate answers based on your specific data

Test the Agent:

```python
# Test the agent
agent_conversation = rag_agent.start_conversation(messages="Who owns the Orion motorcycle?")
status = agent_conversation.execute()
print(f"\nAgent Answer: {status.message.content}")

# Agent Answer: The Orion motorcycle is owned by Mike Chen. He owns a premium adventure touring motorcycle with advanced electronics, the Orion CX 1300 Helix, which has 136 horsepower.
```

The Agent autonomously decides when to search, what to search for, and how to use the results to answer questions.

## RAG in Flows

While Agents offer flexibility, Flows provide a structured approach to RAG with predictable retrieval workflows ideal for specific use cases.

### Step 1. Create the RAG Flow

Create a Flow that searches for relevant information before generating a response:

```python
from textwrap import dedent
from wayflowcore.flow import Flow
from wayflowcore.steps import CompleteStep, InputMessageStep, PromptExecutionStep, StartStep
from wayflowcore.steps.searchstep import SearchStep
# Define flow steps for RAG
start_step = StartStep()

user_input_step = InputMessageStep(
    message_template=dedent(
        """
        Hello! I'm your motorcycle garage assistant powered by RAG.

        I have access to information about all motorcycles in our garage.
        What would you like to know?
        """
    )
)

search_step = SearchStep(
    datastore=datastore, collection_name="motorcycles", k=3, search_config="motorcycle_search"
)

llm_response_step = PromptExecutionStep(
    prompt_template=dedent(
        """
        You are a knowledgeable motorcycle garage assistant.
        Answer the user's question based ONLY on the retrieved motorcycle information.

        User's question: {{ user_query }}

        Retrieved motorcycle information:
        {% for doc in retrieved_documents %}
        - Model: {{ doc.model_name }}
        Owner: {{ doc.owner_name }}
        Horsepower: {{ doc.hp }} HP
        Description: {{ doc.description }}
        {% endfor %}

        Instructions:
        - Base your answer strictly on the retrieved information
        - If the information doesn't answer the question, say so clearly
        - Be specific and mention relevant details from the motorcycles
        """
    ),
    llm=llm,
)
```

Key points:

- The [SearchStep](../api/flows.md#searchstep) uses semantic search to find relevant documents based on the user’s query.
- The `k` parameter limits the number of documents retrieved.
- Retrieved documents are passed to the LLM along with the original query for contextualized responses.

### Step 2. Build and test the Flow

Build the complete Flow with control and data connections:

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

# Build the RAG flow
complete_step = CompleteStep()

steps = {
    "start": start_step,
    "input": user_input_step,
    "search": search_step,
    "respond": llm_response_step,
    "complete": complete_step,
}

control_flow_edges = [
    ControlFlowEdge(source_step=start_step, destination_step=user_input_step),
    ControlFlowEdge(source_step=user_input_step, destination_step=search_step),
    ControlFlowEdge(source_step=search_step, destination_step=llm_response_step),
    ControlFlowEdge(source_step=llm_response_step, destination_step=complete_step),
]

data_flow_edges = [
    # Pass user query to search step
    DataFlowEdge(
        source_step=user_input_step,
        source_output=InputMessageStep.USER_PROVIDED_INPUT,
        destination_step=search_step,
        destination_input=SearchStep.QUERY,
    ),
    # Pass user query to LLM for context
    DataFlowEdge(
        source_step=user_input_step,
        source_output=InputMessageStep.USER_PROVIDED_INPUT,
        destination_step=llm_response_step,
        destination_input="user_query",
    ),
    # Pass retrieved documents to LLM
    DataFlowEdge(
        source_step=search_step,
        source_output=SearchStep.DOCUMENTS,
        destination_step=llm_response_step,
        destination_input="retrieved_documents",
    ),
]

rag_flow = Flow(
    begin_step=start_step,
    steps=steps,
    control_flow_edges=control_flow_edges,
    data_flow_edges=data_flow_edges,
)

# Test the flow
conversation = rag_flow.start_conversation()
conversation.execute()
conversation.append_user_message("Which motorcycle has the most horsepower?")
result = conversation.execute()
print(f"\nRAG Flow Answer: {result.output_values[PromptExecutionStep.OUTPUT]}")
# RAG Flow Answer: Based on the retrieved information, the motorcycle with the most horsepower is the Vortex Momentum X1, which has 214 HP.
# This Italian superbike features MotoGP-derived technology and stunning performance, indicating its high power output.
```

The Flow provides a predictable pipeline: user input → search → response generation.

## Advanced RAG Techniques

### Filtering search results

You can filter search results based on metadata:

```python
# Filter search results by owner
filtered_results = datastore.search(
    collection_name="motorcycles", query="sport bike", k=5, where={"owner_name": "Sarah Johnson"}
)
```

### Multiple search configurations

Create specialized search configurations for different use cases:

```python
from wayflowcore.datastore import OracleDatabaseDatastore
from wayflowcore.search import SearchConfig, VectorRetrieverConfig, VectorConfig

# Configure Vector Config for Search
vector_config = VectorConfig(model=embedding_model, collection_name="motorcycles", vector_property="embeddings")

# Multiple search configurations for different use cases
precise_search = SearchConfig(
    name="precise_search",
    retriever=VectorRetrieverConfig(
        model=embedding_model,
        collection_name="motorcycles",
        distance_metric="cosine_distance",
    ),
)

broad_search = SearchConfig(
    name="broad_search",
    retriever=VectorRetrieverConfig(
        model=embedding_model,
        collection_name="motorcycles",
        distance_metric="l2_distance",
        vectors = vector_config, # You can put your vector config directly in the Vector Retriever Config
    ),
)

# Create OracleDB datastore with multiple search configs
multi_search_datastore = OracleDatabaseDatastore(
    connection_config=connection_config,
    schema={"motorcycles": motorcycles},
    search_configs=[precise_search, broad_search],
    vector_configs=[vector_config],
)
```

**How multiple search configs work:**

- Each [SearchConfig](../api/search.md#search-config) must have a unique name (auto-generated if not provided)
- Search configs can target the same collection with different settings (distance metrics, vector configs)
- Search Configs can also target multiple collections if no collection name is specified, provided there does not exist another search config which matches the collection name to search on.
- When calling [Datastore.search()](../api/datastores.md#datastore), you specify which config to use via the `search_config` parameter
- If no `search_config` is specified, the system looks for a default config for that collection, given that a `collection_name` is specified
- The first config that matches the collection (or has no specific collection) becomes the default

**When to use each config**

- `precise_search`: Uses cosine similarity for semantic matching (best for meaning-based searches)
- `broad_search`: Uses Euclidean distance for broader matches (considers all dimensions equally)
- You explicitly choose which to use: `datastore.search(..., search_config="precise_search")`

### Customizing search behavior in Agents

Create specialized search toolboxes with different parameters:

```python
# Create specialized search toolboxes
detailed_search = datastore.get_search_toolbox(k=10)
quick_search = datastore.get_search_toolbox(k=1)

# Agent with multiple search strategies
advanced_agent = Agent(
    tools=[detailed_search, quick_search],
    llm=llm,
    custom_instruction=dedent(
    """
    You are an advanced motorcycle assistant with two search modes:
    - Use detailed search for comprehensive questions requiring multiple examples
    - Use quick search for simple factual questions about a specific motorcycle

    Choose the appropriate search mode based on the user's question.
    """
    ),
)
```

**How specialized toolboxes work:**

- Each toolbox creates different search functions with fixed parameters
- `detailed_search`: Always returns 10 results (k=10) for comprehensive analysis
- `quick_search`: Always returns 1 result (k=1) for focused answers
- The Agent sees these as different tools: `search_motorcycles_detailed` vs `search_motorcycles_quick`

**When each toolbox is used:**

- The Agent autonomously decides based on:
  - The user’s question complexity
  - Instructions in `custom_instruction`
  - Context of the conversation
- For “tell me about all sport bikes” → likely uses `detailed_search`
- For “who owns the Vortex?” → likely uses `quick_search`
- The Agent’s reasoning determines the choice, guided by your instructions

### Manual Serialization of Fields for Embeddings

In this example, we show a manual serialization approach that performs cross-field logic that cannot be expressed with [ConcatSerializerConfig](../api/search.md#concat-serializer-config).
Instead of merely concatenating fields, we:
- Compute derived attributes (e.g., performance class and hp bands from numeric horsepower)
- Conditionally weight salient tokens (repeat model name for high-HP bikes)
- Inject domain keywords based on the description semantics
- Reorder fields and output a structured, sectioned Markdown document

This goes beyond per-field preprocessing and simple separators; it uses the full entity structure at once and conditional logic across multiple fields.

```python
# Advanced manual serialization that uses domain-specific, cross-field logic.
# This goes beyond simple concatenation and cannot be reproduced with ConcatSerializerConfig,
# which operates per-field and via string pre/post-processors without access to the full structured entity.
from typing import Dict, Any, List

def serialize_motorcycle_advanced(entity: Dict[str, Any]) -> str:
    """
    Produce a Markdown-formatted string with:
    - Conditional weighting: repeat model name tokens based on horsepower bands
    - Derived fields: performance class and hp_band computed from numeric hp
    - Conditional keyword injection from description semantics
    - Field re-ordering and sectioned formatting for domain salience
    """
    model = str(entity.get("model_name", "")).strip()
    desc = str(entity.get("description", "")).strip()
    owner = str(entity.get("owner_name", "")).strip()
    try:
        hp = int(entity.get("hp") or 0)
    except Exception:
        hp = 0

    # Derived performance class and weighting based on hp
    if hp >= 170:
        performance = "track-ready superbike"
        weight_repeats = 3
    elif hp >= 120:
        performance = "high-performance sport bike"
        weight_repeats = 2
    elif hp >= 70:
        performance = "standard road motorcycle"
        weight_repeats = 1
    else:
        performance = "lightweight commuter / trail bike"
        weight_repeats = 1

    # Keyword injection (conditional, cross-field)
    lower_desc = desc.lower()
    keywords: List[str] = []
    if "race" in lower_desc or "sport" in lower_desc or hp >= 150:
        keywords += ["sport bike", "supersport", "track-focused"]
    if "touring" in lower_desc or "comfortable" in lower_desc or "adventure" in lower_desc:
        keywords += ["touring", "long-distance", "comfort"]
    if "dirt" in lower_desc or "off-road" in lower_desc or "trail" in lower_desc:
        keywords += ["off-road", "dual-sport", "trail"]

    # Deduplicate while preserving order
    seen = set()
    deduped_keywords: List[str] = []
    for kw in keywords:
        if kw not in seen:
            deduped_keywords.append(kw)
            seen.add(kw)

    # Compose Markdown with intentional ordering and sections
    title = f"# {model}"
    # Token weighting via repetition (helps some embedding models emphasize salient tokens)
    if weight_repeats > 1 and model:
        title = title + (" " + model) * (weight_repeats - 1)

    body_lines: List[str] = [
        f"## Performance: {performance}",
        f"hp_band: {max(0, (hp // 10) * 10)}+ HP",
        f"owner: {owner}" if owner else "",
        "## Description",
        desc,
    ]
    if deduped_keywords:
        body_lines += ["## Keywords", ", ".join(deduped_keywords)]

    # Join non-empty lines
    body = "\n".join([line for line in body_lines if line and line.strip()])

    return f"{title}\n{body}"

# Example usage (when you want to manually control embeddings):
# for entity in motorcycle_data:
#     entity["serialized_text"] = serialize_motorcycle_advanced(entity)
#     entity["embeddings"] = embedding_model.embed([entity["serialized_text"]])[0]
```

Example usage when generating embeddings:

```python
for entity in motorcycle_data:
    entity["serialized_text"] = serialize_motorcycle_advanced(entity)
    entity["embeddings"] = embedding_model.embed([entity["serialized_text"]])[0]
```

**Why use explicit serialization?**

- Cross-field logic: derive fields (e.g., performance class from hp) and conditionally add keywords.
- Conditional weighting: repeat or emphasize tokens under certain conditions (e.g., horsepower thresholds).
- Structured formatting: generate Markdown sections and control field ordering for domain salience.
- Auditable and deterministic: the exact text used for embeddings is transparent and reproducible.

Limitations of ConcatSerializerConfig and when to choose manual serialization:

- ConcatSerializerConfig is powerful for per-field concatenation with simple pre/post processing and exclusion of columns.
- It does not perform arbitrarily complex cross-field computations, conditional token weighting, or multi-field derived features.
- Choose manual serialization whenever you need entity-level reasoning to craft the embedding text, beyond simple concatenation and formatting.

#### NOTE
Selective field embedding—using serializers to specify which fields participate in embedding generation—is best supported and straightforward in the [InMemoryDatastore](../api/datastores.md#inmemorydatastore) backend (see its API for serializer support).
For [OracleDatabaseDatastore](../api/datastores.md#oracledatabasedatastore), you are responsible for constructing and storing the embeddings explicitly, and there is no out-of-the-box field-level selection.
For configuring the serialized text and embeddings column externally, you can make use of [ConcatSerializerConfig](../api/search.md#concat-serializer-config)
outside the Datastore while generating the serialized text for the embeddings. [OracleDatabaseDatastore](../api/datastores.md#oracledatabasedatastore) assumes that the embedding column has already been generated and does not implicitly create embeddings.

#### NOTE
For rapid prototyping, use [InMemoryDatastore](../api/datastores.md#inmemorydatastore) with custom serializers for full flexibility, then migrate to [OracleDatabaseDatastore](../api/datastores.md#oracledatabasedatastore) for production workloads that require persistence and scalability.

## Agent Spec Exporting/Loading

You can export the agent configuration to its Agent Spec configuration using the [AgentSpecExporter](../api/agentspec.md#agentspecexporter).

```python
# Export the RAG agent to Agent Spec JSON
from wayflowcore.agentspec import AgentSpecExporter

rag_agent_ir_json = AgentSpecExporter().to_json(rag_agent)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
    "component_type": "ExtendedAgent",
    "id": "cefee4ec-cb9d-4bc5-8361-a34860ced665",
    "name": "agent_52e70c67__auto",
    "description": "",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [],
    "outputs": [],
    "llm_config": {
        "component_type": "VllmConfig",
        "id": "1d26dfa9-f35f-4e21-8c30-248213ac0601",
        "name": "llm_70781625__auto",
        "description": null,
        "metadata": {
            "__metadata_info__": {}
        },
        "default_generation_parameters": {
            "max_tokens": 512
        },
        "url": "host_urls.com",
        "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct"
    },
    "system_prompt": "\nYou are a helpful motorcycle garage assistant with access to our motorcycle database.\n\nIMPORTANT:\n- Always search for relevant information before answering questions about motorcycles\n- Base your answers on the search results\n- If you can't find relevant information, say so clearly\n- Be specific and mention details from the search results\n\nYou have access to search tools that can find information about:\n- Motorcycle models and specifications\n- Owners of motorcycles\n- Horsepower and performance details\n- Descriptions and features\n",
    "tools": [
        {
            "component_type": "PluginToolFromToolBox",
            "id": "5c4bf7fb-79ba-4e3e-a671-e2e2945b7600",
            "name": "search_motorcycles",
            "description": "Search for Motorcycles in our garage in the database using semantic similarity.\n\nThis tool searches the motorcycles collection for entities that match the given query.\nIt returns exactly 3 matching records with their properties and similarity scores.\nUse this tool when you need to find information about Motorcycles in our garage.\n\nParameters\n----------\nquery : str\n    The search query string to find relevant Motorcycles in our garage.\n",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
            "outputs": [],
            "tool_name": "search_motorcycles",
            "toolbox": {
                "component_type": "PluginSearchToolBox",
                "id": "54f6a02a-9dba-480a-a9f0-4d86fff937a5",
                "name": "search_toolbox5f99358b__auto",
                "description": null,
                "metadata": {},
                "collection_names": null,
                "k": 3,
                "datastore": {
                    "component_type": "PluginOracleDatabaseDatastore",
                    "id": "de87d17c-9654-47ce-a43f-0c827e52b5f6",
                    "name": "oracle_datastoreed7b27dc__auto",
                    "description": null,
                    "metadata": {},
                    "datastore_schema": {
                        "motorcycles": {
                            "description": "Motorcycles in our garage",
                            "title": "",
                            "properties": {
                                "description": {
                                    "type": "string",
                                    "description": "Detailed description of the motorcycle"
                                },
                                "owner_name": {
                                    "description": "Name of the motorcycle owner",
                                    "type": "string"
                                },
                                "model_name": {
                                    "description": "Motorcycle model and brand",
                                    "type": "string"
                                },
                                "hp": {
                                    "description": "Horsepower of the motorcycle",
                                    "type": "integer"
                                },
                                "serialized_text": {
                                    "description": "Concatenated string of all columns",
                                    "type": "string"
                                },
                                "embeddings": {
                                    "description": "Generated embeddings for serialized_text",
                                    "type": "array",
                                    "items": {
                                        "type": "number"
                                    },
                                    "x_vector_property": true
                                }
                            }
                        }
                    },
                    "connection_config": {
                        "component_type": "PluginTlsOracleDatabaseConnectionConfig",
                        "id": "8dbd3707-cd10-44f8-bbc1-15b69ac83c14",
                        "name": "PluginTlsOracleDatabaseConnectionConfig",
                        "description": null,
                        "metadata": {},
                        "user": "user",
                        "password": "password",
                        "dsn": "dsn",
                        "config_dir": null,
                        "component_plugin_name": "DatastorePlugin",
                        "component_plugin_version": "25.4.1"
                    },
                    "search_configs": [
                        {
                            "component_type": "PluginSearchConfig",
                            "id": "c983247b-bc7a-43c3-af16-b952fa9714e5",
                            "name": "motorcycle_search",
                            "description": null,
                            "metadata": {},
                            "retriever": {
                                "component_type": "PluginVectorRetrieverConfig",
                                "id": "e26ea01e-e501-4f09-b5f4-8a96cd3daa77",
                                "name": "motorcycles",
                                "description": null,
                                "metadata": {},
                                "model": {
                                    "component_type": "PluginVllmEmbeddingConfig",
                                    "id": "fe1e8f74-cf16-4dea-8ba5-08f4629aea0a",
                                    "name": "embedding_modeledf13d6a__auto",
                                    "description": null,
                                    "metadata": {},
                                    "url": "model_url.com",
                                    "model_id": "intfloat/e5-large-v2",
                                    "component_plugin_name": "EmbeddingModelPlugin",
                                    "component_plugin_version": "25.4.1"
                                },
                                "collection_name": "motorcycles",
                                "vectors": null,
                                "distance_metric": "cosine_distance",
                                "index_params": {},
                                "component_plugin_name": "VectorRetrieverConfigPlugin",
                                "component_plugin_version": "25.4.1"
                            },
                            "component_plugin_name": "SearchConfigPlugin",
                            "component_plugin_version": "25.4.1"
                        }
                    ],
                    "vector_configs": [],
                    "component_plugin_name": "DatastorePlugin",
                    "component_plugin_version": "25.4.1"
                },
                "component_plugin_name": "SearchToolBoxPlugin",
                "component_plugin_version": "25.4.1"
            },
            "component_plugin_name": "ToolFromToolBoxPlugin",
            "component_plugin_version": "25.4.1"
        }
    ],
    "toolboxes": [],
    "context_providers": null,
    "can_finish_conversation": false,
    "max_iterations": 10,
    "initial_message": "Hello! I'm your RAG-powered motorcycle assistant. I can search our database to answer your questions about the motorcycles in our garage.",
    "caller_input_mode": "always",
    "agents": [],
    "flows": [],
    "agent_template": {
        "component_type": "PluginPromptTemplate",
        "id": "c8d2fd47-ab10-468f-9c55-c8fa2c459c1a",
        "name": "",
        "description": null,
        "metadata": {
            "__metadata_info__": {}
        },
        "messages": [
            {
                "role": "system",
                "contents": [
                    {
                        "type": "text",
                        "content": "{%- if __TOOLS__ -%}\nEnvironment: ipython\nCutting Knowledge Date: December 2023\n\nYou are a helpful assistant with tool calling capabilities. Only reply with a tool call if the function exists in the library provided by the user. If it doesn't exist, just reply directly in natural language. When you receive a tool call response, use the output to format an answer to the original user question.\n\nYou have access to the following functions. To call a function, please respond with JSON for a function call.\nRespond in the format {\"name\": function name, \"parameters\": dictionary of argument name and its value}.\nDo not use variables.\n\n[{% for tool in __TOOLS__%}{{tool.to_openai_format() | tojson}}{{', ' if not loop.last}}{% endfor %}]\n{%- endif -%}\n"
                    }
                ],
                "tool_requests": null,
                "tool_result": null,
                "display_only": false,
                "sender": null,
                "recipients": [],
                "time_created": "2025-10-29T10:19:45.987272+00:00",
                "time_updated": "2025-10-29T10:19:45.987272+00:00"
            },
            {
                "role": "system",
                "contents": [
                    {
                        "type": "text",
                        "content": "{%- if custom_instruction -%}Additional instructions:\n{{custom_instruction}}{%- endif -%}"
                    }
                ],
                "tool_requests": null,
                "tool_result": null,
                "display_only": false,
                "sender": null,
                "recipients": [],
                "time_created": "2025-10-29T10:19:45.987302+00:00",
                "time_updated": "2025-10-29T10:19:45.987302+00:00"
            },
            {
                "role": "system",
                "contents": [
                    {
                        "type": "text",
                        "content": "$$__CHAT_HISTORY_PLACEHOLDER__$$"
                    }
                ],
                "tool_requests": null,
                "tool_result": null,
                "display_only": false,
                "sender": null,
                "recipients": [],
                "time_created": "2025-10-29T10:19:45.983942+00:00",
                "time_updated": "2025-10-29T10:19:45.983943+00:00"
            },
            {
                "role": "system",
                "contents": [
                    {
                        "type": "text",
                        "content": "{% if __PLAN__ %}The current plan you should follow is the following: \n{{__PLAN__}}{% endif %}"
                    }
                ],
                "tool_requests": null,
                "tool_result": null,
                "display_only": false,
                "sender": null,
                "recipients": [],
                "time_created": "2025-10-29T10:19:45.987326+00:00",
                "time_updated": "2025-10-29T10:19:45.987326+00:00"
            }
        ],
        "output_parser": {
            "component_type": "PluginJsonToolOutputParser",
            "id": "e5ed717a-bb76-4c13-b443-640444b98d3b",
            "name": "jsontool_outputparser",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "tools": null,
            "component_plugin_name": "OutputParserPlugin",
            "component_plugin_version": "25.4.1"
        },
        "inputs": [
            {
                "description": "\"__TOOLS__\" input variable for the template",
                "title": "__TOOLS__"
            },
            {
                "description": "\"custom_instruction\" input variable for the template",
                "type": "string",
                "title": "custom_instruction"
            },
            {
                "description": "\"__PLAN__\" input variable for the template",
                "type": "string",
                "title": "__PLAN__",
                "default": ""
            },
            {
                "type": "array",
                "items": {},
                "title": "__CHAT_HISTORY__"
            }
        ],
        "pre_rendering_transforms": null,
        "post_rendering_transforms": [
            {
                "component_type": "PluginRemoveEmptyNonUserMessageTransform",
                "id": "73631f33-9ade-420f-8cc1-775a24dd47d3",
                "name": "removeemptynonusermessage_messagetransform",
                "description": null,
                "metadata": {
                    "__metadata_info__": {}
                },
                "component_plugin_name": "MessageTransformPlugin",
                "component_plugin_version": "25.4.1"
            },
            {
                "component_type": "PluginCoalesceSystemMessagesTransform",
                "id": "9c65df01-2987-46e0-b2d1-082b79ee9a34",
                "name": "coalescesystemmessage_messagetransform",
                "description": null,
                "metadata": {
                    "__metadata_info__": {}
                },
                "component_plugin_name": "MessageTransformPlugin",
                "component_plugin_version": "25.4.1"
            },
            {
                "component_type": "PluginLlamaMergeToolRequestAndCallsTransform",
                "id": "9f3e25ea-73e9-4cee-bcbc-60b95720c023",
                "name": "llamamergetoolrequestandcalls_messagetransform",
                "description": null,
                "metadata": {
                    "__metadata_info__": {}
                },
                "component_plugin_name": "MessageTransformPlugin",
                "component_plugin_version": "25.4.1"
            }
        ],
        "tools": null,
        "native_tool_calling": false,
        "response_format": null,
        "native_structured_generation": true,
        "generation_config": null,
        "component_plugin_name": "PromptTemplatePlugin",
        "component_plugin_version": "25.4.1"
    },
    "component_plugin_name": "AgentPlugin",
    "component_plugin_version": "25.4.1",
    "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: ExtendedAgent
id: 6be99be6-1540-4a0f-897e-2036b7c459b0
name: agent_f607ea30__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
llm_config:
  component_type: VllmConfig
  id: 5461e0f4-7270-449b-983a-1fdb41e15845
  name: llm_ce3b3e36__auto
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters:
    max_tokens: 512
  url: host_url.com
  model_id: meta-llama/Meta-Llama-3.1-8B-Instruct
system_prompt: '

  You are a helpful motorcycle garage assistant with access to our motorcycle database.


  IMPORTANT:

  - Always search for relevant information before answering questions about motorcycles

  - Base your answers on the search results

  - If you can''t find relevant information, say so clearly

  - Be specific and mention details from the search results


  You have access to search tools that can find information about:

  - Motorcycle models and specifications

  - Owners of motorcycles

  - Horsepower and performance details

  - Descriptions and features

  '
tools:
- component_type: PluginToolFromToolBox
  id: e6901838-1fd1-44fe-bfa3-214727719124
  name: search_motorcycles
  description: "Search for Motorcycles in our garage in the database using semantic\
    \ similarity.\n\nThis tool searches the motorcycles collection for entities that\
    \ match the given query.\nIt returns exactly 3 matching records with their properties\
    \ and similarity scores.\nUse this tool when you need to find information about\
    \ Motorcycles in our garage.\n\nParameters\n----------\nquery : str\n    The search\
    \ query string to find relevant Motorcycles in our garage.\n"
  metadata:
    __metadata_info__: {}
  inputs: []
  outputs: []
  tool_name: search_motorcycles
  toolbox:
    component_type: PluginSearchToolBox
    id: d09ff0dc-3ed5-40ae-8dd2-9d66fa08c460
    name: search_toolbox6abbf352__auto
    description: null
    metadata: {}
    collection_names: null
    k: 3
    datastore:
      component_type: PluginOracleDatabaseDatastore
      id: cea31a0d-ea61-4730-b982-18ee3572d036
      name: oracle_datastorebac11430__auto
      description: null
      metadata: {}
      datastore_schema:
        motorcycles:
          description: Motorcycles in our garage
          title: ''
          properties:
            description:
              type: string
              description: Detailed description of the motorcycle
            owner_name:
              description: Name of the motorcycle owner
              type: string
            model_name:
              description: Motorcycle model and brand
              type: string
            hp:
              description: Horsepower of the motorcycle
              type: integer
            serialized_text:
              description: Concatenated string of all columns
              type: string
            embeddings:
              description: Generated embeddings for serialized_text
              type: array
              items:
                type: number
              x_vector_property: true
      connection_config:
        component_type: PluginTlsOracleDatabaseConnectionConfig
        id: a4c8fc8a-6200-4b1b-88f2-489419b5a8cb
        name: PluginTlsOracleDatabaseConnectionConfig
        description: null
        metadata: {}
        user: user
        password: password
        dsn: dsn
        config_dir: null
        component_plugin_name: DatastorePlugin
        component_plugin_version: 25.4.1
      search_configs:
      - component_type: PluginSearchConfig
        id: a5f4ce97-150f-4b76-bae9-5e157d11d64a
        name: motorcycle_search
        description: null
        metadata: {}
        retriever:
          component_type: PluginVectorRetrieverConfig
          id: 893ddb4a-0350-45ad-a01b-2222a4bbb71f
          name: motorcycles
          description: null
          metadata: {}
          model:
            component_type: PluginVllmEmbeddingConfig
            id: df506ab3-5d76-47b5-80b8-19d9b293a067
            name: embedding_modeld79566c9__auto
            description: null
            metadata: {}
            url: model_url.com
            model_id: intfloat/e5-large-v2
            component_plugin_name: EmbeddingModelPlugin
            component_plugin_version: 25.4.1
          collection_name: motorcycles
          vectors: null
          distance_metric: cosine_distance
          index_params: {}
          component_plugin_name: VectorRetrieverConfigPlugin
          component_plugin_version: 25.4.1
        component_plugin_name: SearchConfigPlugin
        component_plugin_version: 25.4.1
      vector_configs: []
      component_plugin_name: DatastorePlugin
      component_plugin_version: 25.4.1
    component_plugin_name: SearchToolBoxPlugin
    component_plugin_version: 25.4.1
  component_plugin_name: ToolFromToolBoxPlugin
  component_plugin_version: 25.4.1
toolboxes: []
context_providers: null
can_finish_conversation: false
max_iterations: 10
initial_message: Hello! I'm your RAG-powered motorcycle assistant. I can search our
  database to answer your questions about the motorcycles in our garage.
caller_input_mode: always
agents: []
flows: []
agent_template:
  component_type: PluginPromptTemplate
  id: 31ba4592-5627-4d8e-ba21-cd39e2a4cf56
  name: ''
  description: null
  metadata:
    __metadata_info__: {}
  messages:
  - role: system
    contents:
    - type: text
      content: '{%- if __TOOLS__ -%}

        Environment: ipython

        Cutting Knowledge Date: December 2023


        You are a helpful assistant with tool calling capabilities. Only reply with
        a tool call if the function exists in the library provided by the user. If
        it doesn''t exist, just reply directly in natural language. When you receive
        a tool call response, use the output to format an answer to the original user
        question.


        You have access to the following functions. To call a function, please respond
        with JSON for a function call.

        Respond in the format {"name": function name, "parameters": dictionary of
        argument name and its value}.

        Do not use variables.


        [{% for tool in __TOOLS__%}{{tool.to_openai_format() | tojson}}{{'', '' if
        not loop.last}}{% endfor %}]

        {%- endif -%}

        '
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-10-29T10:21:46.793553+00:00'
    time_updated: '2025-10-29T10:21:46.793554+00:00'
  - role: system
    contents:
    - type: text
      content: '{%- if custom_instruction -%}Additional instructions:

        {{custom_instruction}}{%- endif -%}'
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-10-29T10:21:46.793585+00:00'
    time_updated: '2025-10-29T10:21:46.793585+00:00'
  - role: system
    contents:
    - type: text
      content: $$__CHAT_HISTORY_PLACEHOLDER__$$
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-10-29T10:21:46.790207+00:00'
    time_updated: '2025-10-29T10:21:46.790208+00:00'
  - role: system
    contents:
    - type: text
      content: "{% if __PLAN__ %}The current plan you should follow is the following:\
        \ \n{{__PLAN__}}{% endif %}"
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-10-29T10:21:46.793609+00:00'
    time_updated: '2025-10-29T10:21:46.793609+00:00'
  output_parser:
    component_type: PluginJsonToolOutputParser
    id: b7249231-a601-42b9-8a6d-61ec5d9d4799
    name: jsontool_outputparser
    description: null
    metadata:
      __metadata_info__: {}
    tools: null
    component_plugin_name: OutputParserPlugin
    component_plugin_version: 25.4.1
  inputs:
  - description: '"__TOOLS__" input variable for the template'
    title: __TOOLS__
  - description: '"custom_instruction" input variable for the template'
    type: string
    title: custom_instruction
  - description: '"__PLAN__" input variable for the template'
    type: string
    title: __PLAN__
    default: ''
  - type: array
    items: {}
    title: __CHAT_HISTORY__
  pre_rendering_transforms: null
  post_rendering_transforms:
  - component_type: PluginRemoveEmptyNonUserMessageTransform
    id: 929d8caf-ef98-4328-b961-658f9b027603
    name: removeemptynonusermessage_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 25.4.1
  - component_type: PluginCoalesceSystemMessagesTransform
    id: 68ff19d3-c152-47a1-98fa-0597fbe6fd8c
    name: coalescesystemmessage_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 25.4.1
  - component_type: PluginLlamaMergeToolRequestAndCallsTransform
    id: 68024b92-c2fd-4ec4-ada8-42589c54b480
    name: llamamergetoolrequestandcalls_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 25.4.1
  tools: null
  native_tool_calling: false
  response_format: null
  native_structured_generation: true
  generation_config: null
  component_plugin_name: PromptTemplatePlugin
  component_plugin_version: 25.4.1
component_plugin_name: AgentPlugin
component_plugin_version: 25.4.1
agentspec_version: 25.4.1
```

</details>

#### WARNING
The Oracle Database Connection Config objects contain several sensitive values
(like username, password, wallet location) that will not be serialized by the `AgentSpecExporter`.
These will be serialized as references that must be resolved at loading time, by specifying the values
of these sensitive fields in the `component_registry` argument of the loader:

```python
component_registry = {
    # We map the ID of the sensitive fields in the connection config to their values
    "oracle_datastore_connection_config.user": "<db user>",  # Replace with your DB user
    "oracle_datastore_connection_config.password": "<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    "oracle_datastore_connection_config.dsn": "<db connection string>",  # e.g. "(description=(retry_count=2)..."
}
```

You can then load the configuration back to an assistant using the [AgentSpecLoader](../api/agentspec.md#agentspecloader).

```python
# Load an agent from Agent Spec JSON
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {tool.name: tool for tool in search_toolbox.get_tools()}
new_rag_agent = AgentSpecLoader(tool_registry=tool_registry).load_json(rag_agent_ir_json, components_registry=component_registry)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- [PluginToolFromToolBox](../api/agentspec.md#agentspectoolfromtoolbox)
- [PluginSearchToolBox](../api/agentspec.md#agentspecsearchtoolbox)
- [PluginOracleDatabaseDatastore](../api/agentspec.md#agentspecoracledatabasedatastore)
- [PluginSearchConfig](../api/agentspec.md#agentspecsearchconfig)
- [PluginVectorRetrieverConfig](../api/agentspec.md#agentspecvectorretrieverconfig)
- [PluginVllmEmbeddingConfig](../api/agentspec.md#agentspec-vllm-embedding-model-config)
- [PluginPromptTemplate](../api/agentspec.md#agentspecprompttemplate)
- [PluginJsonToolOutputParser](../api/agentspec.md#agentspecjsontooloutputparser)
- [PluginRemoveEmptyNonUserMessageTransform](../api/agentspec.md#agentspecremoveemptynonusermessagetransform)
- [PluginCoalesceSystemMessagesTransform](../api/agentspec.md#agentspeccoalescesystemmessagestransform)
- [PluginLlamaMergeToolRequestAndCallsTransform](../api/agentspec.md#agentspecllamamergetoolrequestsandcallstransform)

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

<a id="cleanup"></a>

## Cleaning Up Datastore

Before moving on, you may want to cleanup the table created in Oracle Database for this tutorial. For cleaning up, you can use the following code below.
This code will drop the `motorcycles` from your Oracle Database using the `environment_config` function defined in the [Setting Up](#setting-up) section.

```python
ORACLE_DB_CLEANUP = "DROP TABLE IF EXISTS motorcycles cascade constraints"
def cleanup_oracle_datastore():
    connection_config = environment_config()
    conn = connection_config.get_connection()
    conn.cursor().execute(ORACLE_DB_CLEANUP)
    conn.close()

cleanup_oracle_datastore()
```

## Recap

In this guide, you learned how to build RAG-powered assistants using WayFlow:

The key difference between Agents and Flows for RAG:

- **Agents** offer dynamic, autonomous retrieval based on the conversation context - ideal when you want the AI to decide when and what to search
- **Flows** provide predictable, structured retrieval workflows - ideal when you want consistent behavior for specific use cases

Key techniques covered:

- **Basic RAG**: Using all fields for embeddings and search
- **Filtered search**: Limiting results based on metadata
- **Multiple search configs**: Different strategies for different use cases with explicit selection
- **Multiple toolboxes**: Allowing Agents to choose between different search strategies autonomously

#### IMPORTANT
**Before deploying your RAG application to production, you MUST:**

1. **Configure Oracle AI Vector Search** for scalable vector operations
2. **Test performance** with production-scale data
3. **Implement proper error handling** and monitoring

For development and testing, you can use the `InMemoryDataStore`, the same APIs work with both datastores:

```python
# Development (NOT for production)
datastore = InMemoryDatastore(schema={"motorcycles": motorcycles})

# Production (use this instead)
datastore = OracleDatabaseDatastore(
    connection_string="your_oracle_connection",
    schema={"motorcycles": motorcycles}
    # connection db params
)
```

See the OracleDatabaseDatastore guide for complete migration instructions.

## Next steps

Deployment Considerations: Now your application is backed by OracleDatabaseDatastore from the start.
Your setup is production-ready, persistent, and scalable using Oracle AI Vector Search.

- Always test with your own database connection and schema for production.
- Ensure your Oracle user has all necessary table privileges.
- For advanced vector functionality, see the OracleDatabaseDatastore API guide.

## Full code

Click on the card at the [top of this page](#top-rag) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to build RAG-Powered Assistants
# ----------------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.2.0.dev0" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_rag.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.





# %%[markdown]
## Embedding-config

# %%
from wayflowcore.embeddingmodels import VllmEmbeddingModel
# Configure embedding model for vector search
embedding_model = VllmEmbeddingModel(base_url="EMBEDDING_API_URL", model_id="model-id")



# %%[markdown]
## Llm-config

# %%
# Configure LLM
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)



# %%[markdown]
## Entity-define

# %%
# Define the motorcycle entity schema
from wayflowcore.datastore import Entity
from wayflowcore.property import IntegerProperty, StringProperty, VectorProperty

motorcycles = Entity(
    description="Motorcycles in our garage",
    properties={
        "owner_name": StringProperty(description="Name of the motorcycle owner"),
        "model_name": StringProperty(description="Motorcycle model and brand"),
        "description": StringProperty(description="Detailed description of the motorcycle"),
        "hp": IntegerProperty(description="Horsepower of the motorcycle"),
        "serialized_text": StringProperty(description="Concatenated string of all columns"),
        "embeddings": VectorProperty(description="Generated embeddings for serialized_text"),
    },
)



# %%[markdown]
## Search-config

# %%
from wayflowcore.search import SearchConfig, VectorRetrieverConfig, VectorConfig

# Configure Vector Config for Search
vector_config = VectorConfig(
    model=embedding_model,
    collection_name="motorcycles",
    vector_property="embeddings"
)

# Configure vector search for semantic similarity matching
search_config = SearchConfig(
    name="motorcycle_search",
    retriever=VectorRetrieverConfig(
        model=embedding_model,
        collection_name="motorcycles",
        distance_metric="cosine_distance",
    ),
)



# %%[markdown]
## Oracle-connection

# %%
import os
import oracledb

from wayflowcore.datastore.oracle import MTlsOracleDatabaseConnectionConfig, TlsOracleDatabaseConnectionConfig

def environment_config():
    mtls_vars = (
        "ADB_CONFIG_DIR",
        "ADB_WALLET_DIR",
        "ADB_WALLET_SECRET",
        "ADB_DB_USER",
        "ADB_DB_PASSWORD",
        "ADB_DSN",
    )
    tls_vars = ("ADB_DB_USER", "ADB_DB_PASSWORD", "ADB_DSN")
    if all(v in os.environ for v in mtls_vars):
        return MTlsOracleDatabaseConnectionConfig(
            config_dir=os.environ["ADB_CONFIG_DIR"],
            wallet_location=os.environ["ADB_WALLET_DIR"],
            wallet_password=os.environ["ADB_WALLET_SECRET"],
            user=os.environ["ADB_DB_USER"],
            password=os.environ["ADB_DB_PASSWORD"],
            dsn=os.environ["ADB_DSN"],
            id="oracle_datastore_connection_config",
        )
    if all(v in os.environ for v in tls_vars):
        return TlsOracleDatabaseConnectionConfig(
            user=os.environ["ADB_DB_USER"],
            password=os.environ["ADB_DB_PASSWORD"],
            dsn=os.environ["ADB_DSN"],
            id="oracle_datastore_connection_config",
        )
    raise Exception("Required OracleDB environment variables not found")


connection_config = environment_config()

ORACLE_DB_DDL = """
    CREATE TABLE motorcycles (
    owner_name VARCHAR2(255),
    model_name VARCHAR2(255),
    description VARCHAR2(255),
    hp INTEGER,
    serialized_text VARCHAR2(1023),
    embeddings VECTOR
)"""

with connection_config.get_connection() as conn:
    with conn.cursor() as cursor:
        try:
            cursor.execute(ORACLE_DB_DDL)
        except oracledb.DatabaseError as e:
            print(f"DDL execution warning: {e}")


# %%[markdown]
## Datastore-create-rag

# %%
from wayflowcore.datastore import OracleDatabaseDatastore
from wayflowcore.search.config import ConcatSerializerConfig

# Create Oracle Database datastore with vector search capability
datastore = OracleDatabaseDatastore(
    connection_config=connection_config,
    schema={"motorcycles": motorcycles},
    search_configs=[search_config],
    vector_configs=[vector_config],
)

# Sample motorcycle data
motorcycle_data = [
    {
        "owner_name": "John Smith",
        "model_name": "Galaxion Thunderchief",
        "hp": 87,
        "description": "Classic American touring motorcycle with chrome details and comfortable seating.",
    },
    {
        "owner_name": "Sarah Johnson",
        "model_name": "Starlite Apex-R7",
        "hp": 118,
        "description": "High-performance supersport motorcycle designed for track racing.",
    },
    {
        "owner_name": "Mike Chen",
        "model_name": "Orion CX 1300 Helix",
        "hp": 136,
        "description": "Premium adventure touring motorcycle with advanced electronics.",
    },
    {
        "owner_name": "Emily Davis",
        "model_name": "Nebula Trailrunner 500",
        "hp": 45,
        "description": "Street-legal dirt bike perfect for off-road adventures.",
    },
    {
        "owner_name": "Carlos Rodriguez",
        "model_name": "Vortex Momentum X1",
        "hp": 214,
        "description": "Italian superbike with MotoGP-derived technology and stunning performance.",
    },
]
# Configure Serializer to serialize columns into a string
serializer = ConcatSerializerConfig()
# Generate serialized_text and embeddings
for entity in motorcycle_data:
    entity["serialized_text"] = serializer.serialize(entity)
    entity["embeddings"] = embedding_model.embed([entity["serialized_text"]])[0]

# Populate the OracleDB datastore
datastore.create(collection_name="motorcycles", entities=motorcycle_data)


# %%[markdown]
## Create-vector-index

# %%
import oracledb

# Configure Vector Index
VECTOR_INDEX_DDL = """
    CREATE VECTOR INDEX hnsw_image
    ON motorcycles (embeddings)
    ORGANIZATION INMEMORY NEIGHBOR GRAPH
    DISTANCE COSINE
    WITH TARGET ACCURACY 95;
"""
with connection_config.get_connection() as connection:
    with connection.cursor() as cursor:
        try:
            cursor.execute(VECTOR_INDEX_DDL)
            connection.commit()
        except oracledb.DatabaseError as e:
            print(f"Vector Index Creation warning: {e}")


# %%[markdown]
## Direct-search-example

# %%
# Example of direct vector search
results = datastore.search(
    collection_name="motorcycles", query="high performance sport bike for racing", k=3
)

print("Direct search results:")
for result in results:
    print(f"- {result['model_name']}")

# Direct search results:
# - Starlite Apex-R7
# - Vortex Momentum X1
# - Nebula Trailrunner 500

# RAG AGENT IMPLEMENTATION


# %%[markdown]
## Agent Tools Rag

# %%
# Create search tools for the agent
search_toolbox = datastore.get_search_toolbox(k=3)



# %%[markdown]
## Agent Create Rag

# %%
from textwrap import dedent
from wayflowcore.agent import Agent

# Create RAG-powered agent
rag_agent = Agent(
    tools=search_toolbox.get_tools(),
    llm=llm,
    custom_instruction=dedent(
        """
        You are a helpful motorcycle garage assistant with access to our motorcycle database.

        IMPORTANT:
        - Always search for relevant information before answering questions about motorcycles
        - Base your answers on the search results
        - If you can't find relevant information, say so clearly
        - Be specific and mention details from the search results

        You have access to search tools that can find information about:
        - Motorcycle models and specifications
        - Owners of motorcycles
        - Horsepower and performance details
        - Descriptions and features
        """
    ),
    initial_message="Hello! I'm your RAG-powered motorcycle assistant. I can search our database to answer your questions about the motorcycles in our garage.",
)



# %%[markdown]
## Agent Test Rag

# %%
# Test the agent
agent_conversation = rag_agent.start_conversation(messages="Who owns the Orion motorcycle?")
status = agent_conversation.execute()
print(f"\nAgent Answer: {status.message.content}")

# Agent Answer: The Orion motorcycle is owned by Mike Chen. He owns a premium adventure touring motorcycle with advanced electronics, the Orion CX 1300 Helix, which has 136 horsepower.


# %%[markdown]
## Export Config to Agent Spec

# %%
# Export the RAG agent to Agent Spec JSON
from wayflowcore.agentspec import AgentSpecExporter

rag_agent_ir_json = AgentSpecExporter().to_json(rag_agent)

# %%[markdown]
## Provide sensitive information when loading the Agent Spec config

# %%
component_registry = {
    # We map the ID of the sensitive fields in the connection config to their values
    "oracle_datastore_connection_config.user": "<db user>",  # Replace with your DB user
    "oracle_datastore_connection_config.password": "<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    "oracle_datastore_connection_config.dsn": "<db connection string>",  # e.g. "(description=(retry_count=2)..."
}

# %%[markdown]
## Load Agent Spec Config

# %%
# Load an agent from Agent Spec JSON
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {tool.name: tool for tool in search_toolbox.get_tools()}
new_rag_agent = AgentSpecLoader(tool_registry=tool_registry).load_json(rag_agent_ir_json, components_registry=component_registry)

# RAG FLOW IMPLEMENTATION


# %%[markdown]
## Flow Steps Rag

# %%
from textwrap import dedent
from wayflowcore.flow import Flow
from wayflowcore.steps import CompleteStep, InputMessageStep, PromptExecutionStep, StartStep
from wayflowcore.steps.searchstep import SearchStep
# Define flow steps for RAG
start_step = StartStep()

user_input_step = InputMessageStep(
    message_template=dedent(
        """
        Hello! I'm your motorcycle garage assistant powered by RAG.

        I have access to information about all motorcycles in our garage.
        What would you like to know?
        """
    )
)

search_step = SearchStep(
    datastore=datastore, collection_name="motorcycles", k=3, search_config="motorcycle_search"
)

llm_response_step = PromptExecutionStep(
    prompt_template=dedent(
        """
        You are a knowledgeable motorcycle garage assistant.
        Answer the user's question based ONLY on the retrieved motorcycle information.

        User's question: {{ user_query }}

        Retrieved motorcycle information:
        {% for doc in retrieved_documents %}
        - Model: {{ doc.model_name }}
        Owner: {{ doc.owner_name }}
        Horsepower: {{ doc.hp }} HP
        Description: {{ doc.description }}
        {% endfor %}

        Instructions:
        - Base your answer strictly on the retrieved information
        - If the information doesn't answer the question, say so clearly
        - Be specific and mention relevant details from the motorcycles
        """
    ),
    llm=llm,
)


# %%[markdown]
## Flow Build Rag

# %%
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

# Build the RAG flow
complete_step = CompleteStep()

steps = {
    "start": start_step,
    "input": user_input_step,
    "search": search_step,
    "respond": llm_response_step,
    "complete": complete_step,
}

control_flow_edges = [
    ControlFlowEdge(source_step=start_step, destination_step=user_input_step),
    ControlFlowEdge(source_step=user_input_step, destination_step=search_step),
    ControlFlowEdge(source_step=search_step, destination_step=llm_response_step),
    ControlFlowEdge(source_step=llm_response_step, destination_step=complete_step),
]

data_flow_edges = [
    # Pass user query to search step
    DataFlowEdge(
        source_step=user_input_step,
        source_output=InputMessageStep.USER_PROVIDED_INPUT,
        destination_step=search_step,
        destination_input=SearchStep.QUERY,
    ),
    # Pass user query to LLM for context
    DataFlowEdge(
        source_step=user_input_step,
        source_output=InputMessageStep.USER_PROVIDED_INPUT,
        destination_step=llm_response_step,
        destination_input="user_query",
    ),
    # Pass retrieved documents to LLM
    DataFlowEdge(
        source_step=search_step,
        source_output=SearchStep.DOCUMENTS,
        destination_step=llm_response_step,
        destination_input="retrieved_documents",
    ),
]

rag_flow = Flow(
    begin_step=start_step,
    steps=steps,
    control_flow_edges=control_flow_edges,
    data_flow_edges=data_flow_edges,
)

# Test the flow
conversation = rag_flow.start_conversation()
conversation.execute()
conversation.append_user_message("Which motorcycle has the most horsepower?")
result = conversation.execute()
print(f"\nRAG Flow Answer: {result.output_values[PromptExecutionStep.OUTPUT]}")
# RAG Flow Answer: Based on the retrieved information, the motorcycle with the most horsepower is the Vortex Momentum X1, which has 214 HP.
# This Italian superbike features MotoGP-derived technology and stunning performance, indicating its high power output.

# ADVANCED RAG TECHNIQUES


# %%[markdown]
## Advanced Filtering

# %%
# Filter search results by owner
filtered_results = datastore.search(
    collection_name="motorcycles", query="sport bike", k=5, where={"owner_name": "Sarah Johnson"}
)


# %%[markdown]
## Advanced Multi Config

# %%
from wayflowcore.datastore import OracleDatabaseDatastore
from wayflowcore.search import SearchConfig, VectorRetrieverConfig, VectorConfig

# Configure Vector Config for Search
vector_config = VectorConfig(model=embedding_model, collection_name="motorcycles", vector_property="embeddings")

# Multiple search configurations for different use cases
precise_search = SearchConfig(
    name="precise_search",
    retriever=VectorRetrieverConfig(
        model=embedding_model,
        collection_name="motorcycles",
        distance_metric="cosine_distance",
    ),
)

broad_search = SearchConfig(
    name="broad_search",
    retriever=VectorRetrieverConfig(
        model=embedding_model,
        collection_name="motorcycles",
        distance_metric="l2_distance",
        vectors = vector_config, # You can put your vector config directly in the Vector Retriever Config
    ),
)

# Create OracleDB datastore with multiple search configs
multi_search_datastore = OracleDatabaseDatastore(
    connection_config=connection_config,
    schema={"motorcycles": motorcycles},
    search_configs=[precise_search, broad_search],
    vector_configs=[vector_config],
)


# %%[markdown]
## Advanced Custom Toolbox

# %%
# Create specialized search toolboxes
detailed_search = datastore.get_search_toolbox(k=10)
quick_search = datastore.get_search_toolbox(k=1)

# Agent with multiple search strategies
advanced_agent = Agent(
    tools=[detailed_search, quick_search],
    llm=llm,
    custom_instruction=dedent(
    """
    You are an advanced motorcycle assistant with two search modes:
    - Use detailed search for comprehensive questions requiring multiple examples
    - Use quick search for simple factual questions about a specific motorcycle

    Choose the appropriate search mode based on the user's question.
    """
    ),
)


# %%[markdown]
## Manual Serialization Advanced

# %%
# Advanced manual serialization that uses domain-specific, cross-field logic.
# This goes beyond simple concatenation and cannot be reproduced with ConcatSerializerConfig,
# which operates per-field and via string pre/post-processors without access to the full structured entity.
from typing import Dict, Any, List

def serialize_motorcycle_advanced(entity: Dict[str, Any]) -> str:
    """
    Produce a Markdown-formatted string with:
    - Conditional weighting: repeat model name tokens based on horsepower bands
    - Derived fields: performance class and hp_band computed from numeric hp
    - Conditional keyword injection from description semantics
    - Field re-ordering and sectioned formatting for domain salience
    """
    model = str(entity.get("model_name", "")).strip()
    desc = str(entity.get("description", "")).strip()
    owner = str(entity.get("owner_name", "")).strip()
    try:
        hp = int(entity.get("hp") or 0)
    except Exception:
        hp = 0

    # Derived performance class and weighting based on hp
    if hp >= 170:
        performance = "track-ready superbike"
        weight_repeats = 3
    elif hp >= 120:
        performance = "high-performance sport bike"
        weight_repeats = 2
    elif hp >= 70:
        performance = "standard road motorcycle"
        weight_repeats = 1
    else:
        performance = "lightweight commuter / trail bike"
        weight_repeats = 1

    # Keyword injection (conditional, cross-field)
    lower_desc = desc.lower()
    keywords: List[str] = []
    if "race" in lower_desc or "sport" in lower_desc or hp >= 150:
        keywords += ["sport bike", "supersport", "track-focused"]
    if "touring" in lower_desc or "comfortable" in lower_desc or "adventure" in lower_desc:
        keywords += ["touring", "long-distance", "comfort"]
    if "dirt" in lower_desc or "off-road" in lower_desc or "trail" in lower_desc:
        keywords += ["off-road", "dual-sport", "trail"]

    # Deduplicate while preserving order
    seen = set()
    deduped_keywords: List[str] = []
    for kw in keywords:
        if kw not in seen:
            deduped_keywords.append(kw)
            seen.add(kw)

    # Compose Markdown with intentional ordering and sections
    title = f"# {model}"
    # Token weighting via repetition (helps some embedding models emphasize salient tokens)
    if weight_repeats > 1 and model:
        title = title + (" " + model) * (weight_repeats - 1)

    body_lines: List[str] = [
        f"## Performance: {performance}",
        f"hp_band: {max(0, (hp // 10) * 10)}+ HP",
        f"owner: {owner}" if owner else "",
        "## Description",
        desc,
    ]
    if deduped_keywords:
        body_lines += ["## Keywords", ", ".join(deduped_keywords)]

    # Join non-empty lines
    body = "\n".join([line for line in body_lines if line and line.strip()])

    return f"{title}\n{body}"

# Example usage (when you want to manually control embeddings):
# for entity in motorcycle_data:
#     entity["serialized_text"] = serialize_motorcycle_advanced(entity)
#     entity["embeddings"] = embedding_model.embed([entity["serialized_text"]])[0]


# %%[markdown]
## Cleanup datastore

# %%
ORACLE_DB_CLEANUP = "DROP TABLE IF EXISTS motorcycles cascade constraints"
def cleanup_oracle_datastore():
    connection_config = environment_config()
    conn = connection_config.get_connection()
    conn.cursor().execute(ORACLE_DB_CLEANUP)
    conn.close()

cleanup_oracle_datastore()
```
