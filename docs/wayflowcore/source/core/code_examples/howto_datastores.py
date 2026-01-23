# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: WayFlow Code Example - How to Connect to Your Data

# .. start-##_Imports
from textwrap import dedent

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.datastore import Entity, InMemoryDatastore
from wayflowcore.datastore.entity import nullable
from wayflowcore.flow import Flow
from wayflowcore.property import (
    AnyProperty,
    DictProperty,
    FloatProperty,
    IntegerProperty,
    ObjectProperty,
    StringProperty,
)
from wayflowcore.steps import InputMessageStep, OutputMessageStep, PromptExecutionStep
from wayflowcore.steps.datastoresteps import (
    DatastoreCreateStep,
    DatastoreDeleteStep,
    DatastoreListStep,
    DatastoreUpdateStep,
)
# .. end-##_Imports
# .. start-##_Define_the_llm
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
# .. end-##_Define_the_llm
(llm,) = _update_globals(["llm_small"])  # docs-skiprow
# .. start-##_Create_entities
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
# .. end-##_Create_entities
# .. start-##_Create_datastore
datastore = InMemoryDatastore(schema={"products": product})

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
        "description": "Vitamin C-filled citrus fruits",
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
    },
]

# Create supports both bulk-creation, as well as single element creation
datastore.create(collection_name="products", entities=dummy_data[:-1])
datastore.create(collection_name="products", entities=dummy_data[-1])
# .. end-##_Create_datastore
# .. start-##_Create_Datastore_step
datastore_list_step = DatastoreListStep(
    datastore,
    name="product_list_step",
    collection_name="products",
    where={"title": "{{user_requested_product}}"},
    limit=1,
    unpack_single_entity_from_list=True,
)

datastore_update_step = DatastoreUpdateStep(
    datastore,
    name="product_update_step",
    collection_name="products",
    where={"title": "{{user_requested_product}}"}
)
# .. end-##_Create_Datastore_step
# .. start-##_Create_flow
# We create the steps needed by our flow
USER_INPUT_STEP = "user_product_input_step"
USER_TASK_INPUT_STEP = "user_task_input_step"
LLM_REWRITE_STEP = "llm_rewrite_step"
USER_OUTPUT_STEP = "user_output_step"

user_input_message_template = dedent(
    """I am an inventory Assistant, designed to help you keep product descriptions up-to-date.
    What product would you like to update? Please provide its title.
    """
)

user_task_message_template = "How would you like to update the description? I will help you rewrite it according to your instructions"

rewrite_description_prompt_template = dedent(
    """You are an inventory assistant.

    Your task:
        - Based on the product details given below, rewrite the description according to the user's request
    Important:
        - Be helpful and concise in your messages
        - Only provide the new description as an output, and nothing else

    Here is the User's request:
    - {{ user_request }}

    Here is the product description:
    - {{ product }}
    """
)

user_input_step = InputMessageStep(
    name=USER_INPUT_STEP,
    message_template=user_input_message_template,
)

user_task_input_step = InputMessageStep(
    name=USER_TASK_INPUT_STEP,
    message_template=user_task_message_template,
)

llm_rewrite_step = PromptExecutionStep(
    name=LLM_REWRITE_STEP,
    prompt_template=rewrite_description_prompt_template,
    llm=llm,
    input_descriptors=[
        DictProperty("product", key_type=StringProperty(), value_type=AnyProperty())
    ],
    output_descriptors=[
        ObjectProperty(
            name=PromptExecutionStep.OUTPUT, properties={"description": StringProperty()}
        )
    ],
)

user_output_step = OutputMessageStep(
    name=USER_OUTPUT_STEP,
    message_template="The product has been updated with the following description: {{ answer['description'] }}",
)

assistant = Flow(
    begin_step=user_input_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=user_input_step, destination_step=user_task_input_step),
        ControlFlowEdge(source_step=user_task_input_step, destination_step=datastore_list_step),
        ControlFlowEdge(source_step=datastore_list_step, destination_step=llm_rewrite_step),
        ControlFlowEdge(source_step=llm_rewrite_step, destination_step=datastore_update_step),
        ControlFlowEdge(source_step=datastore_update_step, destination_step=user_output_step),
        ControlFlowEdge(source_step=user_output_step, destination_step=None),
    ],
    data_flow_edges=[
        # The first title given by the user is mapped to the datastore steps for listing and updating
        DataFlowEdge(
            user_input_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            datastore_list_step,
            "user_requested_product",
        ),
        DataFlowEdge(
            user_input_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            datastore_update_step,
            "user_requested_product",
        ),
        # The task and product detail are given to the LLM in the prompt execution step
        DataFlowEdge(
            user_task_input_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            llm_rewrite_step,
            "user_request",
        ),
        DataFlowEdge(datastore_list_step, DatastoreListStep.ENTITIES, llm_rewrite_step, "product"),
        # The generated update is applied on the datastore, and echoed back to the user
        DataFlowEdge(
            llm_rewrite_step,
            PromptExecutionStep.OUTPUT,
            datastore_update_step,
            DatastoreUpdateStep.UPDATE,
        ),
        DataFlowEdge(llm_rewrite_step, PromptExecutionStep.OUTPUT, user_output_step, "answer"),
    ],
)
# .. end-##_Create_flow
# .. start-##_Execute_flow
conversation = assistant.start_conversation()
conversation.execute()
conversation.append_user_message("Broccoli")

conversation.execute()
conversation.append_user_message(
    "Shoppers don't know what 'cruciferous' means, we should find a catchier description."
)

conversation.execute()
print(conversation.get_last_message().content)
# .. end-##_Execute_flow
# .. start-##_Import_agents
from wayflowcore.agent import Agent
# .. end-##_Import_agents
# .. start-##_Create_agent_flows
AGENT_PROMPT = dedent(
    """
    You are an inventory assistant. Your task is to help the user with their requests by using the available tools.
    If you are unsure about the action to take, or you don't have the right tool, simply tell the user so and follow their guidance.
    """
)

create_product_flow = Flow.from_steps(
    [DatastoreCreateStep(datastore, "products")],
    name="Create product",
    description="Creates a new product in the data source",
)
list_products_flow = Flow.from_steps(
    [DatastoreListStep(datastore, "products")],
    name="List all products",
    description="Lists all products in the data source.",
)
list_one_product_flow = Flow.from_steps(
    [datastore_list_step],
    name="List single product",
    description="Lists a single product in the data source by its title.",
)
update_product_flow = Flow.from_steps(
    [datastore_update_step],
    name="Update product",
    description="Updates a product in the data source by its title.",
)
delete_product_flow = Flow.from_steps(
    [DatastoreDeleteStep(datastore, "products", where={"title": "{{product_title}}"})],
    name="Delete product",
    description="Delete a product in the data source by its title.",
)
# .. end-##_Create_agent_flows
# .. start-##_Create_the_agent
agent = Agent(
    llm=llm,
    flows=[
        create_product_flow,
        list_products_flow,
        list_one_product_flow,
        update_product_flow,
        delete_product_flow,
    ],
    custom_instruction=AGENT_PROMPT,
)
# .. end-##_Create_the_agent
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_agent = AgentSpecExporter().to_json(agent)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_agent)
# .. end-##_Load_Agent_Spec_config
