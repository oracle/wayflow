# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# WayFlow Code Example - How to Use Asynchronous APIs
# ---------------------------------------------------

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
# python howto_async.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.



# %%[markdown]
## Define the llm

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)


# %%[markdown]
## Single async generation

# %%
import anyio

prompt = "Who is the CEO of Oracle?"
# Run one async generation (non-blocking to the event loop)
anyio.run(llm.generate_async, prompt)


# %%[markdown]
## Async Agent execution

# %%
from wayflowcore.agent import Agent

agent = Agent(
    llm=llm,
    custom_instruction="You are a helpful assistant.",
)
conv = agent.start_conversation()
conv.append_user_message("Who is the CEO of Oracle?")
anyio.run(conv.execute_async)


# %%[markdown]
## Async Flow execution

# %%
from wayflowcore.flow import Flow
from wayflowcore.steps import PromptExecutionStep

step = PromptExecutionStep(
    llm=llm,
    prompt_template="Who is the CEO of Oracle?",
)
flow = Flow.from_steps(steps=[step])
flow_conv = flow.start_conversation()
anyio.run(flow_conv.execute_async)


# %%[markdown]
## Define tools async vs sync

# %%
from wayflowcore.tools.toolhelpers import DescriptionMode, tool

# For CPU-bound tasks, async does not help. WayFlow runs synchronous tools
# in worker threads to avoid blocking the event loop.
@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
def heavy_work() -> str:
    """Performs heavy CPU-bound work."""
    # WORK
    return ""

# For I/O-bound tasks, async is optimal. Asynchronous tools are directly used
# inside WayFlow's asynchronous stack to maximize efficiency.
@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
async def remote_call() -> str:
    """Performs remote API calls (I/O-bound)."""
    # CALLS
    return ""


# %%[markdown]
## Agent with async tools

# %%
from wayflowcore.agent import Agent

agent_with_tools = Agent(
    llm=llm,
    custom_instruction="You are a helpful assistant, answering the user request about {{query}}",
    tools=[heavy_work, remote_call],
)

async def run_agent_async(query: str, result_list: list[str]) -> str:
    conversation = agent_with_tools.start_conversation(
        inputs={'query': query}
    )
    status = await conversation.execute_async()
    result_list.append(conversation.get_last_message().content)


# %%[markdown]
## Run agents concurrently

# %%
async def run_agents_concurrently(query: str, n: int) -> list[str]:
    solutions: list[str] = []
    async with anyio.create_task_group() as tg:
        for _ in range(n):
            tg.start_soon(run_agent_async, query, solutions)
    return solutions

# Spawn 10 agents concurrently
anyio.run(run_agents_concurrently, "who is the CEO of Oracle?", 10)


# %%[markdown]
## Synchronous usage

# %%
# You can still use the synchronous API in a synchronous context.
sync_conv = agent.start_conversation()
sync_status = sync_conv.execute()

# Using synchronous APIs in an asynchronous context can block the event loop
# and lead to poor performance. WayFlow will emit a warning and indicate the
# appropriate asynchronous API to call instead (e.g., use execute_async).


# %%[markdown]
## Export Config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(agent_with_tools)

# %%[markdown]
## Load Agent Spec Config

# %%
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    heavy_work.name: heavy_work,
    remote_call.name: remote_call,
}
new_agent = AgentSpecLoader(tool_registry=tool_registry).load_json(config)
