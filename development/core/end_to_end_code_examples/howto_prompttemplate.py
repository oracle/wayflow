# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Use Advanced Prompting Techniques
# -------------------------------------------------------

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
# python howto_prompttemplate.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Configure your LLM

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)

# %%[markdown]
## Basic text prompt with Regex parsing

# %%
import re

from wayflowcore.outputparser import JsonOutputParser, RegexOutputParser, RegexPattern
from wayflowcore.templates import PromptTemplate

prompt_template = PromptTemplate.from_string(
    template="What is the result of 100+(454-3). Think step by step and then give your answer between <result>...</result> delimiters",
    output_parser=RegexOutputParser(
        regex_pattern=RegexPattern(pattern=r"<result>(.*)</result>", flags=re.DOTALL)
    ),
)
prompt = prompt_template.format()  # no inputs needed since the template has no variable
result = llm.generate(prompt).message.content
print(result)
# 551

# %%[markdown]
## Prompt with chat history

# %%
from wayflowcore.messagelist import Message, MessageType

messages = [
    Message(content="What is the capital of Switzerland?", message_type=MessageType.USER),
    Message(content="The capital of Switzerland is Bern?", message_type=MessageType.AGENT),
    Message(content="Really? I thought it was Zurich?", message_type=MessageType.USER),
]

# %%[markdown]
### As inlined messages

# %%
prompt_template = PromptTemplate(
    messages=[
        {"role": "system", "content": "You are a helpful assistant. Answer the user questions"},
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
    ]
)

prompt = prompt_template.format(inputs={PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME: messages})
print(prompt.messages)
# [
#   Message(content='You are a helpful assistant. Answer the user questions', message_type=MessageType.SYSTEM),
#   Message(content='What is the capital of Switzerland?', message_type=MessageType.USER),
#   Message(content='The capital of Switzerland is Bern?', message_type=MessageType.AGENT),
#   Message(content='Really? I thought it was Zurich?', message_type=MessageType.USER)
# ]
result = llm.generate(prompt).message.content
print(result)
# While Zurich is a major city in Switzerland and home to many international organizations, the capital is indeed Bern (also known as Berne).

# %%[markdown]
### In the system prompt

# %%
prompt_text = """You are a helpful assistant. Answer the user questions.
For context, the conversation was:
{% for msg in __CHAT_HISTORY__ %}
{{ msg.message_type.value }} >> {{msg.content}}
{%- endfor %}

Just answer the user question.
"""
prompt_template = PromptTemplate(messages=[{"role": "system", "content": prompt_text}])

prompt = prompt_template.format(inputs={PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME: messages})
print(prompt.messages)
# [Message(content="""You are a helpful assistant. Answer the user questions.
# For context, the conversation was:
#
# USER >> What is the capital of Switzerland?
# AGENT >> The capital of Switzerland is Bern?
# USER >> Really? I thought it was Zurich?
#
# Just answer the user question.""", message_type=MessageType.SYSTEM]
result = llm.generate(prompt).message.content
print(result)
# While Zurich is a major city and financial hub in Switzerland, the capital is indeed Bern.

# %%[markdown]
### With message transform

# %%
from typing import List
from wayflowcore.transforms import MessageTransform

class OnlyLastChatMessageTransform(MessageTransform):
    def __call__(self, messages: List[Message]) -> List[Message]:
        if len(messages) == 0:
            return []
        return [messages[-1]]

prompt_template = PromptTemplate(
    messages=[
        {"role": "system", "content": "You are a helpful assistant. Answer the user questions"},
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
    ],
    pre_rendering_transforms=[OnlyLastChatMessageTransform()],
)
prompt = prompt_template.format(inputs={PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME: messages})
print(prompt.messages)
# [
#   Message(content='You are a helpful assistant. Answer the user questions', message_type=MessageType.SYSTEM),
#   Message(content='Really? I thought it was Zurich?', message_type=MessageType.USER)
# ]

# %%[markdown]
## Configure how to use tools in templates

# %%
from typing import Annotated
from wayflowcore.tools import tool

@tool
def some_tool(param1: Annotated[str, "name of the user"]) -> Annotated[str, "tool_output"]:
    """Performs some action"""
    return "some_tool_output"

# %%[markdown]
### With native tool calling

# %%
template = PromptTemplate(
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
    ],
)
template = template.with_tools([some_tool])
prompt = template.format(
    inputs={PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME: [Message("call the some_output tool")]}
)
print(prompt.tools)
# [ServerTool()]
response = llm.generate(prompt).message
print(response)
# Message(content='', message_type=<MessageType.TOOL_REQUEST, tool_requests=[ToolRequest(name='some_output', args={'param1': 'call the some_output tool'}, tool_request_id='chatcmpl-tool-ae924a4829324411add8760d3ae265bd')])

# %%[markdown]
### With custom tool calling

# %%
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.templates.reacttemplates import (
    REACT_SYSTEM_TEMPLATE,
    ReactToolOutputParser,
    _ReactMergeToolRequestAndCallsTransform,
)
from wayflowcore.transforms import (
    CoalesceSystemMessagesTransform,
    RemoveEmptyNonUserMessageTransform,
)

REACT_CHAT_TEMPLATE = PromptTemplate(
    messages=[
        {"role": "system", "content": REACT_SYSTEM_TEMPLATE},
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
    ],
    native_tool_calling=False,
    post_rendering_transforms=[
        _ReactMergeToolRequestAndCallsTransform(),
        CoalesceSystemMessagesTransform(),
        RemoveEmptyNonUserMessageTransform(),
    ],
    output_parser=ReactToolOutputParser(),
    generation_config=LlmGenerationConfig(stop=["## Observation"]),
)
template = REACT_CHAT_TEMPLATE.with_tools([some_tool])
prompt = template.format(
    inputs={PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME: [Message("call the some_output tool")]}
)
print(prompt.tools)
# [ServerTool()]
response = llm.generate(prompt).message
print(response)
# Message(content='', message_type=MessageType.TOOL_REQUEST, tool_requests=[ToolRequest(name='some_tool', args={'param1': 'call the some_output tool'}, tool_request_id='chatcmpl-tool-69c7e27e55474501be0dfc2509e5d4f2')]

# %%[markdown]
## Configure how to use structured generation in templates

# %%
from wayflowcore.property import ObjectProperty, StringProperty

output = ObjectProperty(
    name="output",
    description="information about a person",
    properties={
        "name": StringProperty(description="name of the person"),
        "age": StringProperty(description="age of the person"),
    },
)

# %%[markdown]
### With native structured generation

# %%
template = PromptTemplate.from_string(
    template="Extract information about a person. The person is 65 years old, named Johnny",
    response_format=output,
)
prompt = template.format()
print(prompt.response_format)
# ObjectProperty(...)
response = llm.generate(prompt).message
print(response)
# Message(content='{"name": "Johnny", "age": "65"}', message_type=MessageType.AGENT)

# %%[markdown]
### With custom structured generation

# %%
text_template = """Extract information about a person. The person is 65 years old, named Johnny.
Just return a json document that respects this JSON Schema:
{{__RESPONSE_FORMAT__.to_json_schema() | tojson }}

Reminder: only output the required json document, no need to repeat the title of the description, just the properties are required!
"""

template = PromptTemplate(
    messages=[{"role": "user", "content": text_template}],
    native_structured_generation=False,
    output_parser=JsonOutputParser(),
    response_format=output,
)
prompt = template.format()
# ^no input needed since __RESPONSE_FORMAT__ is filled with `response_format`
print(prompt.response_format)
# None  # it is not passed separately, but will be taken care of by the output parser
print(prompt.messages)
# [Message(content="""Extract information about a person. The person is 65 years old, named Johnny.
# Just return a json document that respects this JSON Schema:
# {"type": "object", "properties": {"name": {"type": "string", "description": "name of the person"}, "age": {"type": "string", "description": "age of the person"}}, "title": "output", "description": "information about a person"}
#
# Reminder: only output the required json document, no need to repeat the title of the description, just the properties are required!""", message_type=MessageType.USER)]
response = llm.generate(prompt).message
print(response)
# Message(content='{"name": "Johnny", "age": "65"}', message_type=MessageType.AGENT)

# %%[markdown]
### With additional output parser

# %%
prompt_template = PromptTemplate.from_string(
    template="What is the result of 100+(454-3). Think step by step and then give your answer between <result>...</result> delimiters",
    output_parser=RegexOutputParser(
        regex_pattern={
            "thoughts": RegexPattern(pattern=r"(.*)<result>", flags=re.DOTALL),
            "result": RegexPattern(pattern=r"<result>(.*)</result>", flags=re.DOTALL),
        }
    ),
    response_format=ObjectProperty(
        properties={
            "thoughts": StringProperty(description="step by step thinking of the LLM"),
            "result": StringProperty(description="result of the computation"),
        }
    ),
)
prompt = prompt_template.format()  # no inputs needed since the template has no variable
result = llm.generate(prompt).message.content
print(result)
# {"thoughts": "To solve the expression step by step:\n\n1. Evaluate the expression inside the parentheses: 454 - 3 = 451\n2. Add the result to 100: 100 + 451 = 551\n\nSo, the final result is:\n\n", "result": "551"}

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agent import Agent
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec.components.template import prompttemplate_serialization_plugin, prompttemplate_deserialization_plugin
assistant = Agent(llm=llm, agent_template=prompt_template)
serialized_assistant = AgentSpecExporter(plugins=[prompttemplate_serialization_plugin]).to_json(assistant)

# %%[markdown]
## Load Agent Spec config

# %%
new_agent: Agent = AgentSpecLoader(plugins=[prompttemplate_deserialization_plugin]).load_json(serialized_assistant)
