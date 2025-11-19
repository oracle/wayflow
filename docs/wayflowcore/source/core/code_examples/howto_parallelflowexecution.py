# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: WayFlow Code Example - How to Run Multiple Flows in Parallel

# .. start-##_Define_the_tools
from wayflowcore.property import DictProperty, ListProperty, StringProperty
from wayflowcore.tools.toolhelpers import DescriptionMode, tool


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[DictProperty(name="user_info", value_type=StringProperty())],
)
def get_user_information(username: str) -> dict[str, str]:
    """Retrieve information about a user"""
    return {
        "alice": {"name": "Alice", "email": "alice@email.com", "date_of_birth": "1980/05/01"},
        "bob": {"name": "Bob", "email": "bob@email.com", "date_of_birth": "1970/10/01"},
    }.get(username, {})


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[StringProperty(name="current_time")],
)
def get_current_time() -> str:
    """Return current time"""
    return "2025/10/01 10:30 PM"


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[
        ListProperty(name="user_purchases", item_type=DictProperty(value_type=StringProperty()))
    ],
)
def get_user_last_purchases(username: str) -> list[dict[str, str]]:
    """Retrieve the list of purchases made by a user"""
    return {
        "alice": [
            {"item_type": "videogame", "title": "Arkanoid", "date": "2000/10/10"},
            {"item_type": "videogame", "title": "Pacman", "date": "2002/09/09"},
        ],
        "bob": [
            {"item_type": "movie", "title": "Batman begins", "date": "2015/10/10"},
            {"item_type": "movie", "title": "The Dark Knight", "date": "2020/08/08"},
        ],
    }.get(username, [])


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[
        ListProperty(name="items_on_sale", item_type=DictProperty(value_type=StringProperty()))
    ],
)
def get_items_on_sale() -> list[dict[str, str]]:
    """Retrieve the list of items currently on sale"""
    return [
        {"item_type": "household", "title": "Broom"},
        {"item_type": "videogame", "title": "Metroid"},
        {"item_type": "movie", "title": "The Lord of the Rings"},
    ]


# .. end-##_Define_the_tools
# .. start-##_Create_the_flows_to_be_run_in_parallel
from wayflowcore.flow import Flow
from wayflowcore.steps import ParallelFlowExecutionStep, ToolExecutionStep

get_current_time_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_current_time_step", tool=get_current_time)]
)
get_user_information_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_user_information_step", tool=get_user_information)]
)
get_user_last_purchases_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_user_last_purchases_step", tool=get_user_last_purchases)]
)
get_items_on_sale_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_items_on_sale_steo", tool=get_items_on_sale)]
)

parallel_flow_step = ParallelFlowExecutionStep(
    name="parallel_flow_step",
    flows=[
        get_current_time_flow,
        get_user_information_flow,
        get_user_last_purchases_flow,
        get_items_on_sale_flow,
    ],
    max_workers=4,
)
# .. end-##_Create_the_flows_to_be_run_in_parallel
# .. start-##_Generate_the_marketing_message
from wayflowcore.models import VllmModel
from wayflowcore.steps import OutputMessageStep, PromptExecutionStep

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

prompt = """# Instructions

You are a marketing expert. You have to write a welcome message for a user.

The message must contain:
- A first sentence of greetings, including user's name, and personalized in case it's user's birthday
- A proposal containing something to buy

The purchase proposal must be:
- aligned with user's purchase history
- part of the list of items on sale

# User information

{{user_info}}

Note that the current time to check the birthday is: {{current_time}}

The list of items purchased by the user is:
{{user_purchases}}

# Items on sale

{{items_on_sale}}

Please write the welcome message for the user.
Do not give me the instructions to do it, I want only the final message to send.
"""

prompt_execution_step = PromptExecutionStep(
    name="prepare_marketing_message", prompt_template=prompt, llm=llm
)
output_message_step = OutputMessageStep(name="output_message_step", message_template="{{output}}")
# .. end-##_Generate_the_marketing_message
(prompt_execution_step.llm,) = _update_globals(["llm_small"])  # docs-skiprow # type: ignore
# .. start-##_Create_and_test_the_final_flow
from wayflowcore.flow import Flow

flow = Flow.from_steps([parallel_flow_step, prompt_execution_step, output_message_step])

conversation = flow.start_conversation(inputs={"username": "bob"})
status = conversation.execute()
print(conversation.get_last_message().content)

# Expected output:
# Happy Birthday, Bob! We hope your special day is filled with excitement and joy.
# As a token of appreciation for being an valued customer, we'd like to recommend our sale on "The Lord of the Rings",
# a movie that we think you'll love, given your interest in superhero classics like "Batman Begins" and "The Dark Knight".
# It's now available at a discounted price, so don't miss out on this amazing opportunity to add it to your collection.
# Browse our sale now and enjoy!
# .. end-##_Create_and_test_the_final_flow
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(flow)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    "get_user_information": get_user_information,
    "get_current_time": get_current_time,
    "get_user_last_purchases": get_user_last_purchases,
    "get_items_on_sale": get_items_on_sale,
}
flow = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_flow)
# .. end-##_Load_Agent_Spec_config
