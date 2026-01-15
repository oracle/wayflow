# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

# docs-title: WayFlow Code Example - How to Connect To Oracle Database

import os  # docs-skiprow
import sys  # docs-skiprow


def _env_cfg():  # docs-skiprow
    mtls_vars = (  # docs-skiprow
        "ADB_CONFIG_DIR",  # docs-skiprow
        "ADB_WALLET_DIR",  # docs-skiprow
        "ADB_WALLET_SECRET",  # docs-skiprow
        "ADB_DB_USER",  # docs-skiprow
        "ADB_DB_PASSWORD",  # docs-skiprow
        "ADB_DSN",  # docs-skiprow
    )  # docs-skiprow
    tls_vars = ("ADB_DB_USER", "ADB_DB_PASSWORD", "ADB_DSN")  # docs-skiprow
    if all(v in os.environ for v in mtls_vars):  # docs-skiprow
        return MTlsOracleDatabaseConnectionConfig(  # docs-skiprow
            config_dir=os.environ["ADB_CONFIG_DIR"],  # docs-skiprow
            wallet_location=os.environ["ADB_WALLET_DIR"],  # docs-skiprow
            wallet_password=os.environ["ADB_WALLET_SECRET"],  # docs-skiprow
            user=os.environ["ADB_DB_USER"],  # docs-skiprow
            password=os.environ["ADB_DB_PASSWORD"],  # docs-skiprow
            dsn=os.environ["ADB_DSN"],  # docs-skiprow
            id="oracle_datastore_connection_config",  # docs-skiprow
        )  # docs-skiprow
    if all(v in os.environ for v in tls_vars):  # docs-skiprow
        return TlsOracleDatabaseConnectionConfig(  # docs-skiprow
            user=os.environ["ADB_DB_USER"],  # docs-skiprow
            password=os.environ["ADB_DB_PASSWORD"],  # docs-skiprow
            dsn=os.environ["ADB_DSN"],  # docs-skiprow
            id="oracle_datastore_connection_config",  # docs-skiprow
        )  # docs-skiprow
    print("Required OracleDB environment variables not found; exiting.")  # docs-skiprow
    sys.exit(0)  # docs-skiprow

from wayflowcore.models.llmmodelfactory import LlmModelFactory  # docs-skiprow
model_cfg = {  # docs-skiprow
    "model_type": "vllm",  # docs-skiprow
    "host_port": "VLLM_HOST_PORT",  # docs-skiprow
    "model_id": "/storage/models/Llama-3.1-70B-Instruct",  # docs-skiprow
}  # docs-skiprow
# .. start-##_Define_the_llm
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
# .. end-##_Define_the_llm
(llm,) = _update_globals(["llm_small"])  # docs-skiprow
# .. start-##_imports:
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
# .. end-##_Imports:
# .. start-##_TLS_Connection:
connection_config = TlsOracleDatabaseConnectionConfig(
    user="<db user>",  # Replace with your DB user
    password="<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    dsn="<db connection string>",  # e.g. "(description=(retry_count=2)..."
    # This is optional, but helpful to re-configure credentials when loading the AgentSpec config for this object
    id="oracle_datastore_connection_config",
)
# .. end-##_TLS_Connection
# .. start-##_mTLS_Connection:
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
# .. end-##_mTLS_Connection
connection_config = _env_cfg()  # docs-skiprow
with connection_config.get_connection() as connection:  # docs-skiprow
    connection.cursor().execute("DROP TABLE IF EXISTS products")  # docs-skiprow
# Datastore and Entity definitions
# .. start-##_Schema
table_definition = """CREATE TABLE products (
    ID NUMBER PRIMARY KEY,
    title VARCHAR2(255) NOT NULL,
    description VARCHAR2(255) NOT NULL,
    price NUMBER NOT NULL,
    category VARCHAR(255) DEFAULT NULL,
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
# .. end-##_Schema
# .. start-##_Create_Datastore_step_and_flow
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
        - Summarize potential inconstencies across descriptions of products in the same category.
          For example, identify typos and hightlight improvement opportunities
    Important:
        - Be helpful and concise in your messages

    Here are the product description:
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
# .. end-##_Create_Datastore_step_and_flow
# .. start-##_Execute_flow
conversation = assistant.start_conversation({"bind_variables": {"product_category": "Produce"}})
conversation.execute()
print(conversation.get_last_message().content)
# .. end-##_Execute_flow
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(assistant)
# .. end-##_Export_config_to_Agent_Spec
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
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_flow, components_registry=component_registry)
# .. end-##_Load_Agent_Spec_config
