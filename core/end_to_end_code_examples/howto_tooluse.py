# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# Code Example - How to Build Assistants with Tools
# -------------------------------------------------

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
# python howto_tooluse.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.




# %%[markdown]
## Imports for this guide

# %%
from typing import Annotated

from wayflowcore.agent import Agent
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.models.llmmodelfactory import LlmModel
from wayflowcore.property import BooleanProperty, StringProperty
from wayflowcore.steps import OutputMessageStep, PromptExecutionStep, ToolExecutionStep
from wayflowcore.tools import ClientTool, ServerTool, Tool, ToolRequest, ToolResult, tool

# %%[markdown]
## Configure your LLM

# %%
from wayflowcore.models.vllmmodel import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Defining some helper functions

# %%
def _read_and_clean_pdf_file(file_path: str, clean_pdf: bool = False):
    from langchain_community.document_loaders import PyPDFLoader

    loader = PyPDFLoader(file_path=file_path)
    page_content_list = []
    for page in loader.lazy_load():
        page_content_list.append(page.page_content)
    if clean_pdf:
        # we remove the extras "\n"
        all_content = []
        for page_content in page_content_list:
            for row in page_content.split("\n"):
                if not row.strip().endswith("."):
                    all_content.append(row)
                else:
                    all_content.append(row + "\n")
    else:
        all_content = page_content_list
    return "\n".join(page_content_list)


# The path to the pdf file to be summarized
PDF_FILE_PATH = "path/to/example_document.pdf"



# %%[markdown]
## Defining a tool using the tool decorator

# %%
### Option 1 - Using typing.Annotated
@tool("read_pdf")
def read_pdf_server_tool(
    file_path: Annotated[str, "Path to the pdf file"],
    clean_pdf: Annotated[bool, "Cleans and reformat the pdf pages"] = False,
) -> str:
    """Reads a PDF file given a filepath."""
    return _read_and_clean_pdf_file(file_path, clean_pdf)

### Option 2 - Using only the docstring
@tool("read_pdf", description_mode="only_docstring")
def read_pdf_server_tool(file_path: str, clean_pdf: bool = False) -> str:
    """Reads a PDF file given a filepath."""
    return _read_and_clean_pdf_file(file_path, clean_pdf)


# %%[markdown]
## Defining a tool using the ServerTool

# %%
### Option 1 - Using Properties
read_pdf_server_tool = ServerTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    input_descriptors=[
        StringProperty("file_path", description="Path to the pdf file"),
        BooleanProperty(
            "clean_pdf", description="Cleans and reformat the pdf pages", default_value=False
        ),
    ],
    output_descriptors=[StringProperty()],
    func=_read_and_clean_pdf_file,
)

### Option 2 - Using JSON Schema
read_pdf_server_tool = ServerTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the pdf file",
        },
        "clean_pdf": {
            "type": "boolean",
            "default": False,
            "description": "Cleans and reformat the pdf pages",
        },
    },
    func=_read_and_clean_pdf_file,
    output={"type": "string", "title": "tool_output"},
)

# %%[markdown]
## Defining a build flow helper function

# %%
def build_flow(llm: LlmModel, tool: Tool) -> Flow:
    pdf_read_step = ToolExecutionStep(
        name="pdf_read_step",
        tool=tool,
    )
    summarization_step = PromptExecutionStep(
        name="summarization_step",
        llm=llm,
        prompt_template="Please summarize the following PDF in 100 words or less. PDF:\n{{pdf_content}}",
        input_mapping={"pdf_content": ToolExecutionStep.TOOL_OUTPUT},
    )
    output_step = OutputMessageStep(
        name="output_step",
        message_template="Here is the summarized pdf:\n{{summarized_pdf}}",
        input_mapping={"summarized_pdf": PromptExecutionStep.OUTPUT},
    )
    return Flow(
        begin_step=pdf_read_step,
        control_flow_edges=[
            ControlFlowEdge(source_step=pdf_read_step, destination_step=summarization_step),
            ControlFlowEdge(source_step=summarization_step, destination_step=output_step),
            ControlFlowEdge(source_step=output_step, destination_step=None),
        ],
    )

# %%[markdown]
## Creating and running a flow with a server tool

# %%
assistant = build_flow(llm, read_pdf_server_tool)

inputs = {"file_path": PDF_FILE_PATH, "clean_pdf": False}
conversation = assistant.start_conversation(inputs=inputs)

status = conversation.execute()
if isinstance(status, FinishedStatus):
    flow_outputs = status.output_values
    print(f"---\nFlow outputs >>> {flow_outputs}\n---")
else:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")


# %%[markdown]
## Defining a build agent helper function

# %%
def build_agent(llm: LlmModel, tool: Tool) -> Agent:
    from textwrap import dedent

    custom_instruction = dedent(
        """
        You are helping to load and summarize a PDF file given a filepath.
        ## Context
        You will receive a filepath from the username which indicates the path to the
        PDF file we want to summarize
        ## Task
        You will follow the next instructions:
        1. Use the tool to load the PDF file (don't go to the next step unless the file content was received).
           If the user does not specify anything, do not clean the PDF prior to summarizing it.
        2. Summarize the given PDF content in 100 words or less.
        ## Output Format
        Return the summarized document as follows:
        ```
        Here is the summarized pdf:
        [summarized pdf]
        ```
        """
    ).strip()

    return Agent(
        llm=llm,
        tools=[tool],
        custom_instruction=custom_instruction,
        max_iterations=3,
    )

# %%[markdown]
## Creating and running an agent with a server tool

# %%
assistant = build_agent(llm, read_pdf_server_tool)

conversation = assistant.start_conversation()

conversation.append_user_message(
    f"Please summarize my PDF document (can be found at {PDF_FILE_PATH})"
)
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")


# %%[markdown]
## Defining a tool using the ClientTool

# %%
def _execute_read_pdf_request(tool_request: ToolRequest) -> str:
    args = tool_request.args
    if "file_path" not in args or "clean_pdf" not in args:
        print(f"Missing arguments in tool request, args were {args}")
        return "INVALID_REQUEST"
    return _read_and_clean_pdf_file(args["file_path"], args["clean_pdf"])


def execute_tool_from_tool_request(tool_request: ToolRequest) -> str:
    if tool_request.name == "read_pdf":
        return _execute_read_pdf_request(tool_request)
    else:
        raise ValueError(f"Unknown tool in tool request: {tool_request.name}")


### Option 1 - Using Properties
read_pdf_client_tool = ClientTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    input_descriptors=[
        StringProperty("file_path", description="Path to the pdf file"),
        BooleanProperty(
            "clean_pdf", description="Cleans and reformat the pdf pages", default_value=False
        ),
    ],
    output_descriptors=[StringProperty()],
)

### Option 2 - Using JSON Schema
read_pdf_client_tool = ClientTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the pdf file",
        },
        "clean_pdf": {
            "type": "boolean",
            "default": False,
            "description": "Cleans and reformat the pdf pages",
        },
    },
    output={"type": "string"},
)

# %%[markdown]
## Creating and running a flow with a client tool

# %%
assistant = build_flow(llm, read_pdf_client_tool)

inputs = {"file_path": PDF_FILE_PATH, "clean_pdf": False}
conversation = assistant.start_conversation(inputs=inputs)

status = conversation.execute()

failed = False
if isinstance(status, ToolRequestStatus):
    # Executing the request and sending it back to the assistant
    tool_request = status.tool_requests[0]
    tool_result = execute_tool_from_tool_request(tool_request)
    conversation.append_tool_result(
        ToolResult(content=tool_result, tool_request_id=tool_request.tool_request_id)
    )
else:
    failed = True
    print(f"Invalid execution status, expected ToolRequestStatus, received {type(status)}")

if not failed:
    # Continuing the conversation
    status = conversation.execute()

if not failed and isinstance(status, FinishedStatus):
    flow_outputs = status.output_values
    print(f"---\nFlow outputs >>> {flow_outputs}\n---")
elif not failed:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")
else:
    pass


# %%[markdown]
## Creating and running an agent with a client tool

# %%
assistant = build_agent(llm, read_pdf_client_tool)

conversation = assistant.start_conversation()
conversation.append_user_message(
    f"Please summarize my PDF document (can be found at {PDF_FILE_PATH})"
)

status = conversation.execute()

# Executing the request and sending it back to the assistant
if isinstance(status, ToolRequestStatus):
    tool_request = status.tool_requests[0]
    tool_result = execute_tool_from_tool_request(tool_request)
    conversation.append_tool_result(
        ToolResult(content=tool_result, tool_request_id=tool_request.tool_request_id)
    )
else:
    failed = True
    print(f"Invalid execution status, expected ToolRequestStatus, received {type(status)}")

if not failed:
    # Continuing the conversation
    status = conversation.execute()

if not failed and isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
elif not failed:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")
else:
    pass


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {"read_pdf": read_pdf_server_tool}
assistant: Agent = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_json(serialized_assistant)
