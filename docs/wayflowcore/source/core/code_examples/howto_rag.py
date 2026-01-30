# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors

# docs-title: WayFlow Code Example - How to build RAG-Powered Assistants


# .. start-##_Embedding-config
from wayflowcore.embeddingmodels import VllmEmbeddingModel
# Configure embedding model for vector search
embedding_model = VllmEmbeddingModel(base_url="EMBEDDING_API_URL", model_id="model-id")
# .. end-##_Embedding-config
(embedding_model, ) = _update_globals(["embedding_model"]) # docs-skiprow


# .. start-##_Llm-config
# Configure LLM
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)
# .. end-##_Llm-config

llm: VllmModel # docs-skiprow
(llm, ) = _update_globals(["llm_small"]) # docs-skiprow

# .. start-##_Entity-define
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
# .. end-##_Entity-define


# .. start-##_Search-config
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
# .. end-##_Search-config


# .. start-##_Oracle-connection
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
# .. end-##_Oracle-connection

# .. start-##_Datastore-create-rag
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
# .. end-##_Datastore-create-rag

# .. start-##_Create-vector-index
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
# .. end-##_Create-vector-index

# .. start-##_Direct-search-example
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
# .. end-##_Direct-search-example

# RAG AGENT IMPLEMENTATION

# .. start-##_Agent_Tools_Rag
# Create search tools for the agent
search_toolbox = datastore.get_search_toolbox(k=3)
# .. end-##_Agent_Tools_Rag


# .. start-##_Agent_Create_Rag
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
# .. end-##_Agent_Create_Rag


# .. start-##_Agent_Test_Rag
# Test the agent
agent_conversation = rag_agent.start_conversation(messages="Who owns the Orion motorcycle?")
status = agent_conversation.execute()
print(f"\nAgent Answer: {status.message.content}")

# Agent Answer: The Orion motorcycle is owned by Mike Chen. He owns a premium adventure touring motorcycle with advanced electronics, the Orion CX 1300 Helix, which has 136 horsepower.
# .. end-##_Agent_Test_Rag

# .. start-##_Export_Config_to_Agent_Spec
# Export the RAG agent to Agent Spec JSON
from wayflowcore.agentspec import AgentSpecExporter

rag_agent_ir_json = AgentSpecExporter().to_json(rag_agent)
# .. end-##_Export_Config_to_Agent_Spec
# .. start-##_Provide_sensitive_information_when_loading_the_Agent_Spec_config
component_registry = {
    # We map the ID of the sensitive fields in the connection config to their values
    "oracle_datastore_connection_config.user": "<db user>",  # Replace with your DB user
    "oracle_datastore_connection_config.password": "<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    "oracle_datastore_connection_config.dsn": "<db connection string>",  # e.g. "(description=(retry_count=2)..."
}
# .. end-##_Provide_sensitive_information_when_loading_the_Agent_Spec_config
component_registry = {  # docs-skiprow
    "oracle_datastore_connection_config.user": os.environ["ADB_DB_USER"],  # docs-skiprow
    "oracle_datastore_connection_config.password": os.environ["ADB_DB_PASSWORD"],  # docs-skiprow
    "oracle_datastore_connection_config.dsn": os.environ["ADB_DSN"],  # docs-skiprow
}  # docs-skiprow
if isinstance(connection_config, MTlsOracleDatabaseConnectionConfig):  # docs-skiprow
    component_registry.update(  # docs-skiprow
        {  # docs-skiprow
            'oracle_datastore_connection_config.config_dir':os.environ["ADB_CONFIG_DIR"],  # docs-skiprow
            'oracle_datastore_connection_config.wallet_location':os.environ["ADB_WALLET_DIR"],  # docs-skiprow
            'oracle_datastore_connection_config.wallet_password':os.environ["ADB_WALLET_SECRET"]  # docs-skiprow
        }  # docs-skiprow
    )  # docs-skiprow
# .. start-##_Load_Agent_Spec_Config
# Load an agent from Agent Spec JSON
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {tool.name: tool for tool in search_toolbox.get_tools()}
new_rag_agent = AgentSpecLoader(tool_registry=tool_registry).load_json(rag_agent_ir_json, components_registry=component_registry)
# .. end-##_Load_Agent_Spec_Config

# RAG FLOW IMPLEMENTATION

# .. start-##_Flow_Steps_Rag
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
# .. end-##_Flow_Steps_Rag

# .. start-##_Flow_Build_Rag
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
# .. end-##_Flow_Build_Rag

# ADVANCED RAG TECHNIQUES

# .. start-##_Advanced_Filtering
# Filter search results by owner
filtered_results = datastore.search(
    collection_name="motorcycles", query="sport bike", k=5, where={"owner_name": "Sarah Johnson"}
)
# .. end-##_Advanced_Filtering

# .. start-##_Advanced_Multi_Config
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
# .. end-##_Advanced_Multi_Config

# .. start-##_Advanced_Custom_Toolbox
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
# .. end-##_Advanced_Custom_Toolbox

# .. start-##_Manual_Serialization_Advanced
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
# .. end-##_Manual_Serialization_Advanced

# .. start-##_Cleanup_datastore
ORACLE_DB_CLEANUP = "DROP TABLE IF EXISTS motorcycles cascade constraints"
def cleanup_oracle_datastore():
    connection_config = environment_config()
    conn = connection_config.get_connection()
    conn.cursor().execute(ORACLE_DB_CLEANUP)
    conn.close()

cleanup_oracle_datastore()
# .. end-##_Cleanup_datastore
