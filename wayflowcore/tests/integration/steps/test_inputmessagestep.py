# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import pytest

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.flow import Flow
from wayflowcore.steps.inputmessagestep import InputMessageStep
from wayflowcore.steps.outputmessagestep import OutputMessageStep


def test_input_step_without_message() -> None:
    question = InputMessageStep(name="first_question", message_template=None)
    assert len(question.input_descriptors) == 0

    flow = Flow(
        begin_step=question,
        control_flow_edges=[ControlFlowEdge(question, None)],
    )
    conversation = flow.start_conversation()
    status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)
    assert len(conversation.message_list) == 0

    conversation.append_user_message("Louis")
    status = flow.execute(conversation)
    assert conversation.get_last_message().content == "Louis"
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {question.USER_PROVIDED_INPUT: "Louis"}


def test_input_step_raises_when_no_new_user_message_is_appended() -> None:
    first_question = InputMessageStep(message_template="What is your name?")
    second_question = InputMessageStep(
        message_template="Hi {{name}}. What do you want to do today?"
    )
    final_message = OutputMessageStep(message_template="Ok! I will help you do {{task}}!")
    flow = Flow(
        begin_step=first_question,
        steps={
            "first_question": first_question,
            "second_question": second_question,
            "final_message": final_message,
        },
        control_flow_edges=[
            ControlFlowEdge(first_question, second_question),
            ControlFlowEdge(second_question, final_message),
            ControlFlowEdge(final_message, None),
        ],
        data_flow_edges=[
            DataFlowEdge(
                first_question, InputMessageStep.USER_PROVIDED_INPUT, second_question, "name"
            ),
            DataFlowEdge(
                second_question, InputMessageStep.USER_PROVIDED_INPUT, final_message, "task"
            ),
        ],
    )
    conversation = flow.start_conversation()
    status = flow.execute(conversation)
    assert conversation.get_last_message().content == "What is your name?"
    assert isinstance(status, UserMessageRequestStatus)
    conversation.append_user_message("Louis")
    status = flow.execute(conversation)
    assert conversation.get_last_message().content == "Hi Louis. What do you want to do today?"
    assert isinstance(status, UserMessageRequestStatus)
    with pytest.raises(ValueError):
        # mistakenly re-executing without having appended a new user message
        flow.execute(conversation)
