# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Connect To Oracle Database
# --------------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_connect_to_oracle_database.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.






# %%[markdown]
## Define the llm

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## imports:

# %%
from textwrap import dedent


from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

from wayflowcore.datastore import (
    Entity,
    MTlsOracleDatabaseConnectionConfig,
    OracleDatabaseDatastore,
    TlsOracleDatabaseConnectionConfig,
)
from wayflowcore.datastore.entity import nullable
from wayflowcore.flow import Flow
from wayflowcore.property import (
    FloatProperty,
    IntegerProperty,
    ObjectProperty,
    StringProperty,
)
from wayflowcore.steps import OutputMessageStep, PromptExecutionStep
from wayflowcore.steps.datastoresteps import DatastoreQueryStep

# %%[markdown]
## TLS Connection:

# %%
connection_config = TlsOracleDatabaseConnectionConfig(
    user="<db user>",  # Replace with your DB user
    password="<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    dsn="<db connection string>",  # e.g. "(description=(retry_count=2)..."
    # This is optional, but helpful to re-configure credentials when loading the AgentSpec config for this object
    id="oracle_datastore_connection_config",
)

# %%[markdown]
## mTLS Connection:

# %%
from wayflowcore.datastore import MTlsOracleDatabaseConnectionConfig

connection_config = MTlsOracleDatabaseConnectionConfig(
    config_dir="./oracle-wallet",
    dsn="<dbname>",  # Entry in tnsnames.ora
    wallet_location="./oracle-wallet",
    wallet_password="<your wallet password>",  # Replace with your wallet password  # nosec: this is just a placeholder
    user="<db user>",  # Replace with your DB user
    password="<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    # This is optional, but helpful to re-configure credentials when loading the AgentSpec config for this object
    id="oracle_datastore_connection_config",
)
# Datastore and Entity definitions

# %%[markdown]
## Schema

# %%
table_definition = """CREATE TABLE products (
    ID NUMBER PRIMARY KEY,
    title VARCHAR2(255) NOT NULL,
    description VARCHAR2(255) NOT NULL,
    price NUMBER NOT NULL,
    category VARCHAR2(255) DEFAULT NULL,
    external_system_id NUMBER DEFAULT NULL
)"""

with connection_config.get_connection() as connection:
    connection.cursor().execute(table_definition)

product = Entity(
    properties={
        "ID": IntegerProperty(description="Unique product identifier"),
        # Descriptions can be helpful if an LLM needs to fill these fields,
        # or generally disambiguate non-obvious property names
        "title": StringProperty(description="Brief summary of the product"),
        "description": StringProperty(),
        "price": FloatProperty(default_value=0.1),
        # Use nullable to define optional properties
        "category": nullable(StringProperty()),
    },
)

datastore = OracleDatabaseDatastore(
    schema={"products": product}, connection_config=connection_config
)

dummy_data = [
    {
        "ID": 0,
        "title": "Broccoli",
        "description": "Healthy and delicious cruciferous vegetable!",
        "price": 1.5,
        "category": "Produce",
    },
    {
        "ID": 1,
        "title": "Oranges",
        # We introduce a typo in this entity for the Assistant to fix
        "description": "Vitamin C-filled cirus fruits",
        "price": 1.8,
        "category": "Produce",
    },
    {
        "ID": 2,
        "title": "Shampoo",
        "description": "Shiny smooth hair in just 10 applications!",
        "price": 4.5,
        "category": "Personal hygiene",
    },
    {
        "ID": 3,
        "title": "Crushed ice",
        "description": "Cool any drink in seconds!",
        "price": 4.5,
        "category": "Food",
    },
]

# Create supports both bulk-creation, as well as single element creation
datastore.create(collection_name="products", entities=dummy_data)

# %%[markdown]
## Create Datastore step and flow

# %%
datastore_query_step = DatastoreQueryStep(
    datastore,
    "SELECT title, description FROM products WHERE category = :product_category",
    name="product_selection_step",
    input_descriptors=[
        ObjectProperty("bind_variables", properties={"product_category": StringProperty("")})
    ],
)

detect_issues_prompt_template = dedent(
    """You are an inventory assistant.

    Your task:
        - Summarize potential inconsistencies across descriptions of products in the same category.
          For example, identify typos and highlight improvement opportunities
    Important:
        - Be helpful and concise in your messages

    Here are the product descriptions:
    {{ products }}
    """
)

llm_issue_detection_step = PromptExecutionStep(
    prompt_template=detect_issues_prompt_template,
    llm=llm,
)

user_output_step = OutputMessageStep(
    message_template="The following issues have been identified: {{ issues }}",
)

assistant = Flow(
    begin_step=datastore_query_step,
    control_flow_edges=[
        ControlFlowEdge(
            source_step=datastore_query_step, destination_step=llm_issue_detection_step
        ),
        ControlFlowEdge(source_step=llm_issue_detection_step, destination_step=user_output_step),
        ControlFlowEdge(source_step=user_output_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            datastore_query_step, DatastoreQueryStep.RESULT, llm_issue_detection_step, "products"
        ),
        DataFlowEdge(
            llm_issue_detection_step, PromptExecutionStep.OUTPUT, user_output_step, "issues"
        ),
    ],
)

# %%[markdown]
## Execute flow

# %%
conversation = assistant.start_conversation({"bind_variables": {"product_category": "Produce"}})
conversation.execute()
print(conversation.get_last_message().content)

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(assistant)

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
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_flow, components_registry=component_registry)
