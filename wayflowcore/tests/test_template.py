# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from typing import List

import pytest

from wayflowcore._utils.formatting import parse_tool_call_using_json
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.outputparser import JsonToolOutputParser, PythonToolOutputParser, RegexOutputParser
from wayflowcore.property import IntegerProperty, ListProperty, Property, StringProperty
from wayflowcore.templates import (
    LLAMA_AGENT_TEMPLATE,
    NATIVE_AGENT_TEMPLATE,
    PYTHON_CALL_AGENT_TEMPLATE,
    REACT_AGENT_TEMPLATE,
    PromptTemplate,
)
from wayflowcore.templates.structuredgeneration import (
    adapt_prompt_template_for_json_structured_generation,
)
from wayflowcore.tools import ToolRequest, ToolResult, tool

logger = logging.getLogger(__name__)


def assert_inputs_are_correct(properties: List[Property], expected_properties: List[Property]):
    assert len(properties) == len(expected_properties)
    for prop_, expected_prop in zip(properties, expected_properties):
        assert type(prop_) == type(expected_prop)
        assert prop_.name == expected_prop.name


def assert_messages_are_correct(messages: List[Message], expected_messages: List[Message]):
    assert len(messages) == len(expected_messages), messages
    for message, expected_message in zip(messages, expected_messages):
        assert message.message_type == expected_message.message_type
        assert message.content == expected_message.content


@pytest.mark.parametrize("country", ["Switzerland", "France"])
def test_simple_string_template(country):
    template = PromptTemplate.from_string(template="What is the capital of {{country}}?")
    assert_inputs_are_correct(template.input_descriptors, [StringProperty("country")])
    prompt = template.format(inputs=dict(country=country))
    messages = prompt.messages
    assert len(messages) == 1
    message = messages[0]
    assert message.content == f"What is the capital of {country}?"
    assert message.message_type == MessageType.USER


@pytest.mark.parametrize("country", ["Switzerland", "France"])
@pytest.mark.parametrize("what", ["biggest city", "highest mountain"])
def test_simple_string_template_with_partial(country, what):
    template = PromptTemplate.from_string(template="What is the {{what}} of {{country}}?")
    assert_inputs_are_correct(
        template.input_descriptors, [StringProperty("what"), StringProperty("country")]
    )

    partial_template = template.with_partial(inputs=dict(country=country))
    assert_inputs_are_correct(partial_template.input_descriptors, [StringProperty("what")])

    prompt_content = partial_template.format(inputs=dict(what=what)).messages[0].content
    assert prompt_content == f"What is the {what} of {country}?"


@pytest.mark.parametrize(
    "messages",
    [
        [Message(content="What is the capital of {{country}}?")],
        [{"role": "user", "content": "What is the capital of {{country}}?"}],
    ],
)
def test_simple_chat_template(messages):
    template = PromptTemplate(messages=messages)
    assert_inputs_are_correct(template.input_descriptors, [StringProperty("country")])
    prompt = template.format(dict(country="Switzerland"))
    assert_messages_are_correct(
        prompt.messages,
        [Message(message_type=MessageType.USER, content="What is the capital of Switzerland?")],
    )


@pytest.mark.parametrize(
    "messages",
    [
        [
            Message(
                content="You are a helpful assistant named {{name}}",
                message_type=MessageType.SYSTEM,
            ),
            Message(content="What is the weather {{date}}?", message_type=MessageType.USER),
            Message(
                message_type=MessageType.TOOL_REQUEST,
                tool_requests=[ToolRequest(name="get_weather", args={}, tool_request_id="id1")],
            ),
            Message(
                message_type=MessageType.TOOL_RESULT,
                tool_result=ToolResult(tool_request_id="id1", content="sunny"),
            ),
            Message(message_type=MessageType.AGENT, content="The weather is sunny {{date}}"),
        ],
        [
            {"role": "system", "content": "You are a helpful assistant named {{name}}"},
            {"role": "user", "content": "What is the weather {{date}}?"},
            {
                "role": "assistant",
                "tool_requests": [{"name": "get_weather", "args": {}, "tool_request_id": "id1"}],
            },
            {"role": "user", "tool_result": {"tool_request_id": "id1", "content": "sunny"}},
            {"role": "assistant", "content": "The weather is sunny {{date}}"},
        ],
    ],
)
def test_template_with_system_and_agent_messages(messages):
    template = PromptTemplate(messages=messages)
    assert_inputs_are_correct(
        template.input_descriptors, [StringProperty("name"), StringProperty("date")]
    )
    prompt = template.format(dict(name="Jerry", date="today"))

    assert_messages_are_correct(
        prompt.messages,
        [
            Message(
                content="You are a helpful assistant named Jerry", message_type=MessageType.SYSTEM
            ),
            Message(content="What is the weather today?", message_type=MessageType.USER),
            Message(
                message_type=MessageType.TOOL_REQUEST,
                tool_requests=[ToolRequest(name="get_weather", args={}, tool_request_id="id1")],
            ),
            Message(
                message_type=MessageType.TOOL_RESULT,
                tool_result=ToolResult(tool_request_id="id1", content="sunny"),
            ),
            Message(message_type=MessageType.AGENT, content="The weather is sunny today"),
        ],
    )


@pytest.mark.parametrize(
    "chat_history",
    [
        [
            Message(content="What is the weather today?", message_type=MessageType.USER),
        ],
        [
            Message(content="What is the weather today?", message_type=MessageType.USER),
            Message(
                message_type=MessageType.TOOL_REQUEST,
                tool_requests=[ToolRequest(name="get_weather", args={}, tool_request_id="id1")],
            ),
            Message(
                message_type=MessageType.TOOL_RESULT,
                tool_result=ToolResult(tool_request_id="id1", content="sunny"),
            ),
        ],
    ],
)
def test_template_with_chat_history(chat_history):
    template = PromptTemplate(
        messages=[
            Message(
                content="You are a helpful assistant named {{name}}",
                message_type=MessageType.SYSTEM,
            ),
            PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
        ],
    )
    assert_inputs_are_correct(
        template.input_descriptors, [StringProperty("name"), ListProperty("__CHAT_HISTORY__")]
    )
    prompt = template.format(dict(name="Jerry", __CHAT_HISTORY__=chat_history))
    assert_messages_are_correct(
        prompt.messages,
        [
            Message(
                content="You are a helpful assistant named Jerry", message_type=MessageType.SYSTEM
            ),
            *chat_history,
        ],
    )


def test_template_with_chat_history_placeholder_but_no_chat_history_passed_raises():
    template = PromptTemplate(messages=[PromptTemplate.CHAT_HISTORY_PLACEHOLDER])
    with pytest.raises(ValueError, match="Should pass the chat_history as input"):
        template.format(inputs=dict())


def test_template_without_chat_history_placeholder_but_no_chat_history_passed_raises():
    template = PromptTemplate(
        messages=[
            Message(message_type=MessageType.SYSTEM, content="Chat history: {{__CHAT_HISTORY__}}")
        ],
    )
    with pytest.raises(ValueError, match="Should pass the chat_history as input"):
        template.format(inputs=dict())


SYSTEM_MESSAGE = Message(message_type=MessageType.SYSTEM, content="You are a helpful assistant")
USER_MESSAGE = Message(message_type=MessageType.USER, content="What is the capital of Switzerland?")
TOOL_REQUEST_MESSAGE = Message(
    message_type=MessageType.TOOL_REQUEST,
    content="I should call some_tool",
    tool_requests=[ToolRequest(name="some_tool", args={}, tool_request_id="id1")],
)
TOOL_RESULT = Message(
    message_type=MessageType.TOOL_RESULT,
    tool_result=ToolResult(tool_request_id="id1", content="some_output"),
)
AGENT_MESSAGE = Message(
    message_type=MessageType.AGENT, content="The capital of Switzerland is Bern"
)
TOOL_REQUEST_MESSAGE_PARALLEL = Message(
    message_type=MessageType.TOOL_REQUEST,
    tool_requests=[
        ToolRequest(name="some_tool", args={}, tool_request_id="id1"),
        ToolRequest(
            name="some_other_tool", args={"some_param": "some_value"}, tool_request_id="id2"
        ),
    ],
)
TOOL_RESULT_2 = Message(
    message_type=MessageType.TOOL_RESULT,
    tool_result=ToolResult(tool_request_id="id2", content="some_other_output"),
)


ALL_MESSAGES = [SYSTEM_MESSAGE, USER_MESSAGE, TOOL_REQUEST_MESSAGE, TOOL_RESULT, AGENT_MESSAGE]


@pytest.mark.parametrize(
    "chat_history_format,expected_messages",
    [
        (lambda x: x, ALL_MESSAGES),
        (
            lambda x: [m for m in x if m.message_type in {MessageType.SYSTEM, MessageType.AGENT}],
            [SYSTEM_MESSAGE, AGENT_MESSAGE],
        ),
    ],
)
def test_template_as_message_and_chat_history_format(chat_history_format, expected_messages):
    template = PromptTemplate(
        messages=ALL_MESSAGES,
        post_rendering_transforms=[chat_history_format],
    )
    prompt = template.format(inputs=dict())
    assert_messages_are_correct(prompt.messages, expected_messages)


SYSTEM_MESSAGE_WITH_CHAT_HISTORY = Message(
    message_type=MessageType.SYSTEM, content="{{__CHAT_HISTORY__}}"
)


def test_template_in_message_and_chat_history_format():
    template = PromptTemplate(
        messages=[
            Message(
                content="{% for m in __CHAT_HISTORY__ %}{{m.content}}{% endfor %}",
                message_type=MessageType.SYSTEM,
            )
        ],
    )
    prompt = template.format(
        inputs=dict(__CHAT_HISTORY__=[Message(content="hello", message_type=MessageType.USER)])
    )
    assert_messages_are_correct(
        prompt.messages, [Message(message_type=MessageType.SYSTEM, content="hello")]
    )


def test_variables_in_chat_history_are_not_rendered():
    template = PromptTemplate(
        messages=[
            Message(
                content="You are a helpful assistant named {{name}}",
                message_type=MessageType.SYSTEM,
            ),
            PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
        ]
    )
    prompt = template.format(
        dict(name="Jerry", __CHAT_HISTORY__=[Message(content="Your name is really {{name}}?")])
    )
    assert_messages_are_correct(
        prompt.messages,
        [
            Message(
                content="You are a helpful assistant named Jerry", message_type=MessageType.SYSTEM
            ),
            Message(content="Your name is really {{name}}?"),
        ],
    )


def test_chat_template_with_partial():
    template = PromptTemplate(
        messages=[
            Message(
                content="You are a helpful assistant named {{agent_name}}. The user is named {{user_name}}.",
                message_type=MessageType.SYSTEM,
            ),
            PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
        ]
    )
    assert_inputs_are_correct(
        template.input_descriptors,
        [
            StringProperty("agent_name"),
            StringProperty("user_name"),
            ListProperty("__CHAT_HISTORY__"),
        ],
    )
    agent_template = template.with_partial(inputs=dict(agent_name="Jerry"))
    assert_inputs_are_correct(
        agent_template.input_descriptors,
        [StringProperty("user_name"), ListProperty("__CHAT_HISTORY__")],
    )

    prompt = agent_template.format(
        dict(user_name="Safia", __CHAT_HISTORY__=[Message(content="What is the weather today?")])
    )
    assert_messages_are_correct(
        prompt.messages,
        [
            Message(
                content="You are a helpful assistant named Jerry. The user is named Safia.",
                message_type=MessageType.SYSTEM,
            ),
            Message(content="What is the weather today?"),
        ],
    )


@tool(description_mode="only_docstring")
def some_tool() -> str:
    """Some tool"""
    return ""


def test_tools_are_properly_rendered_natively():
    prompt_messages = [
        Message(
            content="You are a helpful assistant named {{agent_name}}.",
            message_type=MessageType.SYSTEM,
        ),
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
    ]

    all_tools = [some_tool]

    # prompt with tools directly
    template = PromptTemplate(messages=prompt_messages, tools=all_tools, native_tool_calling=True)
    prompt = template.format(inputs=dict(__CHAT_HISTORY__=[], agent_name="Jerry"))
    assert prompt.tools == all_tools

    # prompt with tools added later
    template = PromptTemplate(messages=prompt_messages, native_tool_calling=True).with_tools(
        all_tools
    )
    prompt = template.format(inputs=dict(__CHAT_HISTORY__=[], agent_name="Jerry"))
    assert prompt.tools == all_tools


def test_template_non_native_tool_calling_needs_tool_template_and_raises_if_not_passed():
    with pytest.warns(Warning, match="There is no tool placeholder"):
        template = PromptTemplate(
            messages=[Message(content="", message_type=MessageType.SYSTEM)],
            tools=[some_tool],
            native_tool_calling=False,
            output_parser=PythonToolOutputParser(),
        )


@pytest.mark.parametrize(
    "tool_template, expected_content",
    [
        (
            "[{% for tool in __TOOLS__%}{{tool.to_openai_format() | tojson}}{{',' if not loop.last}}{% endfor %}]",
            'You are a helpful assistant with tools: [{"type": "function", "function": {"name": "some_tool", "description": "Some tool", "parameters": {}}}]',
        ),
        (
            '{% for tool in __TOOLS__%}{{tool.name}}{{"-" if not loop.last}}{% endfor %}',
            "You are a helpful assistant with tools: some_tool",
        ),
    ],
)
def test_template_non_native_tool_calling_formats_tools(tool_template, expected_content):
    template = PromptTemplate(
        messages=[
            Message(
                content=f"You are a helpful assistant with tools: {tool_template}",
                message_type=MessageType.SYSTEM,
            )
        ],
        tools=[some_tool],
        native_tool_calling=False,
        output_parser=PythonToolOutputParser(),
    )
    prompt = template.format(inputs={})
    assert prompt.tools is None
    assert_messages_are_correct(
        prompt.messages, [Message(message_type=MessageType.SYSTEM, content=expected_content)]
    )


TEXT_PROPERTY = StringProperty(name="text")


def test_template_with_native_structured_generation():
    template = PromptTemplate(
        messages=[Message("Please generate something")],
        response_format=TEXT_PROPERTY,
        native_structured_generation=True,
    )
    prompt = template.format()
    assert prompt.response_format == TEXT_PROPERTY


def test_template_with_non_native_structured_generation_without_parser():
    with pytest.raises(
        ValueError, match="Template was configured to non-native structured generation"
    ):
        template = PromptTemplate(
            messages=[Message("Please generate something: {{__RESPONSE_FORMAT__}}")],
            response_format=TEXT_PROPERTY,
            native_structured_generation=False,
        )


def test_template_with_non_native_structured_generation_without_placeholder_works():
    template = PromptTemplate(
        messages=[Message("Please generate something that is similar to this.")],
        response_format=TEXT_PROPERTY,
        native_structured_generation=False,
        output_parser=RegexOutputParser(".*"),
    )


@pytest.mark.parametrize(
    "template,expected_content",
    [
        (
            "{{__RESPONSE_FORMAT__.to_json_schema() | tojson}}",
            'Please generate something: {"type": "string", "title": "text"}',
        ),
        ("{{__RESPONSE_FORMAT__.to_json_schema()['title']}}", "Please generate something: text"),
        (
            "{{__RESPONSE_FORMAT__.to_json_schema()['title'] | tojson}}",
            'Please generate something: "text"',
        ),
    ],
)
def test_template_with_non_native_structured_generation(template, expected_content):
    template = PromptTemplate(
        messages=[Message(f"Please generate something: {template}")],
        response_format=TEXT_PROPERTY,
        output_parser=RegexOutputParser(".*"),
        native_structured_generation=False,
    )
    prompt = template.format(inputs={})
    assert prompt.response_format is None
    assert_messages_are_correct(prompt.messages, [Message(expected_content)])


def test_native_chat_template():
    messages = [USER_MESSAGE, TOOL_REQUEST_MESSAGE, TOOL_RESULT, AGENT_MESSAGE]
    prompt = NATIVE_AGENT_TEMPLATE.with_tools([some_tool]).format(
        inputs={
            NATIVE_AGENT_TEMPLATE.CHAT_HISTORY_PLACEHOLDER_NAME: messages,
            "custom_instruction": "Your name is Jerry",
            "__PLAN__": None,
        }
    )
    assert prompt.tools == [some_tool]
    assert prompt.response_format is None
    assert_messages_are_correct(
        prompt.messages,
        [Message(message_type=MessageType.SYSTEM, content="Your name is Jerry")] + messages,
    )


def test_llama_chat_template():
    messages = [
        USER_MESSAGE,
        TOOL_REQUEST_MESSAGE_PARALLEL,
        TOOL_RESULT,
        TOOL_RESULT_2,
        AGENT_MESSAGE,
    ]
    prompt = LLAMA_AGENT_TEMPLATE.with_tools([some_tool]).format(
        inputs={
            LLAMA_AGENT_TEMPLATE.CHAT_HISTORY_PLACEHOLDER_NAME: messages,
            "custom_instruction": "Your name is Jerry",
            "__PLAN__": None,
        }
    )
    assert prompt.tools is None
    assert prompt.response_format is None
    assert_messages_are_correct(
        prompt.messages,
        [
            Message(
                content='Environment: ipython\nCutting Knowledge Date: December 2023\n\nYou are a helpful assistant with tool calling capabilities. Only reply with a tool call if the function exists in the library provided by the user. If it doesn\'t exist, just reply directly in natural language. When you receive a tool call response, use the output to format an answer to the original user question.\n\nYou have access to the following functions. To call a function, please respond with JSON for a function call.\nRespond in the format {"name": function name, "parameters": dictionary of argument name and its value}.\nDo not use variables.\n\n[{"type": "function", "function": {"name": "some_tool", "description": "Some tool", "parameters": {}}}]\n\nAdditional instructions:\nYour name is Jerry',
                message_type=MessageType.SYSTEM,
            ),
            Message(content="What is the capital of Switzerland?", message_type=MessageType.USER),
            Message(
                content='[{"name": "some_tool", "parameters": {}}, {"name": "some_other_tool", "parameters": {"some_param": "some_value"}}]',
                message_type=MessageType.AGENT,
            ),
            Message(
                content='<tool_response>"some_output"</tool_response>\n<tool_response>"some_other_output"</tool_response>',
                message_type=MessageType.USER,
            ),
            Message(content="The capital of Switzerland is Bern", message_type=MessageType.AGENT),
        ],
    )


def test_bfcl_chat_template():
    messages = [USER_MESSAGE, TOOL_REQUEST_MESSAGE, TOOL_RESULT, AGENT_MESSAGE]
    prompt = PYTHON_CALL_AGENT_TEMPLATE.with_tools([some_tool]).format(
        inputs={
            PYTHON_CALL_AGENT_TEMPLATE.CHAT_HISTORY_PLACEHOLDER_NAME: messages,
            "custom_instruction": "Your name is Jerry",
            "__PLAN__": None,
        }
    )
    assert prompt.tools is None
    assert prompt.response_format is None
    assert_messages_are_correct(
        prompt.messages,
        [
            Message(
                content='You are an expert in composing functions. You are given a question and a set of possible functions.\nBased on the question, you will need to make one or more function/tool calls to achieve the purpose.\nIf none of the functions can be used, point it out. If the given question lacks the parameters required by the function, also point it out.\nYou should only return the function calls in your response.\n\nIf you decide to invoke any of the function(s), you MUST put it in the format of [func_name1(params_name1=params_value1, params_name2=params_value2...), func_name2(params)]\nYou SHOULD NOT include any other text in the response.\n\nAt each turn, you should try your best to complete the tasks requested by the user within the current turn. Continue to output functions to call until you have fulfilled the user\'s request to the best of your ability. Once you have no more functions to call, the system will consider the current turn complete and proceed to the next turn or task.\n\nHere is a list of functions in JSON format that you can invoke.\n[{"name": "some_tool", "description": "Some tool"}]\n\nAdditional instructions:\nYour name is Jerry',
                message_type=MessageType.SYSTEM,
            ),
            Message(content="What is the capital of Switzerland?", message_type=MessageType.USER),
            Message(
                content="[some_tool()]",
                message_type=MessageType.AGENT,
            ),
            Message(
                content='<tool_response>"some_output"</tool_response>',
                message_type=MessageType.USER,
            ),
            Message(content="The capital of Switzerland is Bern", message_type=MessageType.AGENT),
        ],
    )


def test_react_chat_template():
    messages = [USER_MESSAGE, TOOL_REQUEST_MESSAGE, TOOL_RESULT, AGENT_MESSAGE]
    prompt = REACT_AGENT_TEMPLATE.with_tools([some_tool]).format(
        inputs={
            REACT_AGENT_TEMPLATE.CHAT_HISTORY_PLACEHOLDER_NAME: messages,
            "custom_instruction": "Your name is Jerry",
            "__PLAN__": None,
        }
    )
    assert prompt.tools is None
    assert prompt.response_format is None
    assert_messages_are_correct(
        prompt.messages,
        [
            Message(
                content='Focus your actions on solving the user request. Be proactive, act on obvious actions and suggest options when the user hasn\'t specified anything yet. You can either answer with some text, or a tool call format containing 3 sections: Thought, Action and Observation. Here is the format:\n\n## Thought: explain what you plan to do and why\n## Action:\n```json\n{\n    "name": $TOOL_NAME,\n    "parameters": $INPUTS\n}\n```\n## Observation: the output of the action\n\nThe first thought section describes the step by step reasoning about what you should do and why.\nThe second action section contains a well formatted json describing which tool to call and with what arguments. $INPUTS is a dictionnary containing the function arguments.\nThe third observation section contains the result of the tool. This is not visible by the user, so you might need to repeat its content to the user.\n\n\nIf tool calls appear in the chat, they are formatted with the above template. They are part of the conversation. Here is an example:\n\nUser: What is the weather in Zurich today?\nAgent: ## Thought: we need to call a tool to get the current weather\n## Action:\n```json\n{\n    "name": "get_weather",\n    "parameters": {\n        "location": "Zurich"\n    }\n}\n```\nUser: ## Observation: sunny\nAgent: The weather is sunny today in Zurich!\n...\n\nHere is a list of functions in JSON format that you can invoke.\n[{"name": "some_tool", "description": "Some tool"}]\n\nAdditional instructions:\nYour name is Jerry\n\nReminder: always answer the user request with plain text or specify a tool call using the format above. Only use tools when necessary.\nRemember that a tool call with thought, action and observation is NOT VISIBLE by the user, so if it contains information that the user needs to know, then make sure to repeat the information as a message.',
                message_type=MessageType.SYSTEM,
            ),
            Message(content="What is the capital of Switzerland?", message_type=MessageType.USER),
            Message(
                content='Thoughts: I should call some_tool\nAction:\n```json\n{\n    "name": "some_tool",\n    "parameters": {}\n}\n```',
                message_type=MessageType.AGENT,
            ),
            Message(
                content="Observation: some_output",
                message_type=MessageType.USER,
            ),
            Message(content="The capital of Switzerland is Bern", message_type=MessageType.AGENT),
        ],
    )


@pytest.mark.parametrize(
    "custom_instruction,plan,expected_messages",
    [
        (None, None, [USER_MESSAGE]),
        (
            None,
            "plan3",
            [
                USER_MESSAGE,
                Message(
                    content="The current plan you should follow is the following: \nplan3",
                    message_type=MessageType.SYSTEM,
                ),
            ],
        ),
        (
            "your are an assistant",
            None,
            [
                Message(
                    content="Additional instructions:\nyour are an assistant",
                    message_type=MessageType.SYSTEM,
                ),
                USER_MESSAGE,
            ],
        ),
    ],
)
def test_react_chat_template_without_tools(custom_instruction, plan, expected_messages):
    prompt = REACT_AGENT_TEMPLATE.format(
        inputs={
            REACT_AGENT_TEMPLATE.CHAT_HISTORY_PLACEHOLDER_NAME: [USER_MESSAGE],
            "custom_instruction": custom_instruction,
            "__PLAN__": plan,
        }
    )
    assert prompt.tools is None
    assert prompt.response_format is None
    assert_messages_are_correct(prompt.messages, expected_messages)


def test_parse_tool_call_using_json_raises_warning_on_non_dict_parameters(
    caplog: pytest.LogCaptureFixture,
):
    """
    Part of the fixes.
    """
    logger.propagate = True  # necessary so that the caplog handler can capture logging messages
    caplog.set_level(
        logging.WARNING
    )  # setting pytest to capture log messages of level WARNING or above

    template_with_json_parser = PromptTemplate(
        messages=[{"role": "user", "content": "dummy. Tools: {{__TOOLS__}}"}],
        native_tool_calling=False,
        output_parser=JsonToolOutputParser(),
    )
    prompt = template_with_json_parser.format()

    failing_raw_text = '{"name": "talk_to_user", "parameters": "Please confirm, if you meant for me to compute 2*2 or with different numbers."}'
    prompt.parse_output(Message(content=failing_raw_text, message_type=MessageType.AGENT))
    _ = parse_tool_call_using_json(failing_raw_text)
    assert "Couldn't parse tool request" in caplog.text


def test_json_structured_generation_helper_function():
    template = PromptTemplate(
        messages=[
            Message("{{instruction}}", message_type=MessageType.SYSTEM),
            Message("{{user_question}}", message_type=MessageType.USER),
        ],
        response_format=IntegerProperty(name="Sum"),
        tools=[some_tool],
    )

    template = template.with_partial(
        {"instruction": "You are a calculator with 20 years of experience."}
    )

    template = adapt_prompt_template_for_json_structured_generation(template)
    assert template.output_parser is not None
    assert len(template.messages) > 2

    prompt = template.format({"user_question": "How do I bake a NY cheesecake?"})

    # Check that it correctly preserves partial values and other configs
    assert prompt.messages[1].content == "You are a calculator with 20 years of experience."
    assert len(prompt.tools) == 1


def test_json_structured_generation_helper_function_errors():
    template = PromptTemplate(
        messages=[
            Message("{{instruction}}", message_type=MessageType.SYSTEM),
            Message("{{user_question}}", message_type=MessageType.USER),
        ],
        tools=[some_tool],
    )
    with pytest.raises(ValueError, match="Prompt template is missing a response format.*"):
        adapt_prompt_template_for_json_structured_generation(template)

    template = PromptTemplate(
        messages=[
            Message(
                "Output a single number between brackets, e.g., [3]",
                message_type=MessageType.SYSTEM,
            ),
        ],
        tools=[some_tool],
        output_parser=RegexOutputParser(r"[.*]"),
    )
    with pytest.raises(
        ValueError,
        match="Prompt template is already configured to use non-native structured generation.",
    ):
        adapt_prompt_template_for_json_structured_generation(template)
