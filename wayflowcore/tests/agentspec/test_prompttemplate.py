# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import cast

from wayflowcore.agent import Agent
from wayflowcore.agentspec.agentspecexporter import AgentSpecExporter
from wayflowcore.agentspec.runtimeloader import AgentSpecLoader
from wayflowcore.executors.executionstatus import UserMessageRequestStatus
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.templates import PromptTemplate
from wayflowcore.templates.reacttemplates import (
    REACT_SYSTEM_TEMPLATE,
    ReactToolOutputParser,
    _ReactMergeToolRequestAndCallsTransform,
)
from wayflowcore.transforms import (
    CoalesceSystemMessagesTransform,
    RemoveEmptyNonUserMessageTransform,
)


def test_prompttemplate_can_be_exported_to_agentspec_then_imported(remotely_hosted_llm):
    agent_template = PromptTemplate(
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

    agent = Agent(llm=remotely_hosted_llm, agent_template=agent_template)

    serialized_assistant = AgentSpecExporter().to_yaml(agent)
    new_assistant = cast(Agent, AgentSpecLoader().load_yaml(serialized_assistant))

    new_agent_template = new_assistant.config.agent_template
    # Prompt template - Messages check
    assert len(new_agent_template.messages) == len(agent_template.messages)
    for message_, new_message_ in zip(agent_template.messages, new_agent_template.messages):
        assert new_message_.role == message_.role
        assert new_message_.contents == message_.contents

    # Prompt template - Native tool calling check
    assert new_agent_template.native_tool_calling == agent_template.native_tool_calling

    # Prompt template - Message transforms
    assert len(new_agent_template.post_rendering_transforms) == len(
        agent_template.post_rendering_transforms
    )
    for transform_, new_transform_ in zip(
        agent_template.post_rendering_transforms, new_agent_template.post_rendering_transforms
    ):
        assert type(transform_) == type(new_transform_)

    # Prompt template - Output parser
    assert type(new_agent_template.output_parser) == type(agent_template.output_parser)

    # Prompt template - Generation config
    assert agent_template.generation_config.stop == new_agent_template.generation_config.stop

    conversation = new_assistant.start_conversation()
    conversation.append_user_message("This is a test, simply output 'TEST'")
    status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)
