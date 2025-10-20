# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: WayFlow Code Example - How to Use Agents in Flows

# .. start-##_Define_the_llm
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
# .. end-##_Define_the_llm
(llm,) = _update_globals(["llm_small"])  # docs-skiprow # type: ignore
# .. start-##_Define_the_tools
import httpx
from wayflowcore.tools.toolhelpers import DescriptionMode, tool

@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
def get_wikipedia_page_content(topic: str) -> str:
    """Looks for information and sources on internet about a given topic."""
    url = "https://en.wikipedia.org/w/api.php"

    response = httpx.get(
        url, params={"action": "query", "format": "json", "list": "search", "srsearch": topic}
    )
    # extract page id
    data = response.json()
    search_results = data["query"]["search"]
    if not search_results:
        return "No results found."

    page_id = search_results[0]["pageid"]

    response = httpx.get(
        url,
        params={
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": True,
            "pageids": page_id,
        },
    )

    # extract page content
    page_data = response.json()
    return str(page_data["query"]["pages"][str(page_id)]["extract"])


@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
def proofread(text: str) -> str:
    """Checks and correct grammar mistakes"""
    return text
# .. end-##_Define_the_tools
# .. start-##_Define_the_agent
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.property import StringProperty

output = StringProperty(
    name="article",
    description="article to submit to the editor. Needs to be cited with sources and proofread",
    default_value="",
)

writing_agent = Agent(
    llm=llm,
    tools=[get_wikipedia_page_content, proofread],
    custom_instruction="""Your task is to write an article about the subject given by the user. You need to:
1. find some information about the topic with sources.
2. write an article
3. proofread the article
4. repeat steps 1-2-3 until the article looks good

The article needs to be around 100 words, always need cite sources and should be written in a professional tone.""",
    output_descriptors=[output],
)
# .. end-##_Define_the_agent
# .. start-##_Define_the_agent_step
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep

agent_step = AgentExecutionStep(
    name="agent_step",
    agent=writing_agent,
    caller_input_mode=CallerInputMode.NEVER,
    output_descriptors=[output],
)
# .. end-##_Define_the_agent_step
# .. start-##_Define_the_Flow
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import InputMessageStep, OutputMessageStep

email_template = """Dear ...,

Here is the article I told you about:
{{article}}

Best
"""

user_step = InputMessageStep(name="user_step", message_template="")
send_email_step = OutputMessageStep(name="send_email_step", message_template=email_template)

flow = Flow(
    begin_step=user_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=user_step, destination_step=agent_step),
        ControlFlowEdge(source_step=agent_step, destination_step=send_email_step),
        ControlFlowEdge(source_step=send_email_step, destination_step=None),
    ],
    data_flow_edges=[DataFlowEdge(agent_step, "article", send_email_step, "article")],
)
# .. end-##_Define_the_Flow
# .. start-##_Execute_the_flow
conversation = flow.start_conversation()
conversation.execute()

conversation.append_user_message("Oracle DB")
conversation.execute()

print(conversation.get_last_message())
# .. end-##_Execute_the_flow
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(flow)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    "get_wikipedia_page_content": get_wikipedia_page_content,
    "proofread": proofread,
}

flow = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_flow)
# .. end-##_Load_Agent_Spec_config
