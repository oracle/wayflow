# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Annotated, Any, AsyncIterable, Dict, List, Optional, Union

from wayflowcore._metadata import MetadataType
from wayflowcore.executors._flowconversation import FlowConversation
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import StreamChunkType, TaggedMessageChunkTypeWithTokenUsage
from wayflowcore.models.llmmodel import LlmCompletion, LlmModel, Prompt
from wayflowcore.property import Property
from wayflowcore.steps.step import Step, StepResult
from wayflowcore.tools import ServerTool, Tool, tool


def create_dummy_server_tool() -> ServerTool:
    # TODO: This tool used to return None, but None-annotated return values break the
    # inspection of the signature done by the tool execution step
    @tool
    def dummy_tool(x: Annotated[str, "dummy input"]) -> str:
        """a dummy tool"""
        return ""

    if not isinstance(dummy_tool, ServerTool):
        raise TypeError("Internal error, please contact wayflowcore developers.")

    return dummy_tool


class DummyModel(LlmModel):

    def __init__(self, fails_if_not_set: bool = True):
        model_id = "dummy"
        super().__init__(
            model_id=model_id,
            generation_config=None,
            __metadata_info__=None,
            supports_structured_generation=True,
            supports_tool_calling=True,
        )
        self.output: Optional[
            Union[
                str,
                List[str],
                Dict[Optional[str], str],
                Message,
                Dict[Optional[str], Message],
            ]
        ] = None
        self.fails_if_not_set = fails_if_not_set

    def _find_next_output(
        self, prompt: List[Message], tools: Optional[List[Tool]], use_tools: bool
    ) -> Union[Message, str]:
        output: Union[str, Message] = ""
        if self.output is None:
            if self.fails_if_not_set:
                raise ValueError(
                    f"Did you forget to set the output of the Dummy model? (called with {prompt}) If not, then set `fails_if_not_set` to False."
                )
            output = "..."
        elif isinstance(self.output, list):
            if len(self.output) == 0:
                raise ValueError(
                    f"Did you forget to set the output of the Dummy model? (called with {prompt}) No further element in list."
                )
            output = self.output.pop(0)
            if len(self.output) == 0:
                self.output = None
        elif isinstance(self.output, dict):
            if len(prompt) == 0:
                output = self.output[None]
            else:
                key = prompt[-1].content
                if key not in self.output:
                    raise ValueError(
                        f"Dummy model wrongly configured, missing key {key} in dummy dict: {self.output}"
                    )
                output = self.output[key]
        else:
            output = self.output
        return output

    def set_next_output(
        self,
        output: Union[
            str, List[str], Dict[Optional[str], str], Message, Dict[Optional[str], Message]
        ],
    ) -> None:
        self.output = output

    async def _generate_impl(self, prompt: Prompt) -> LlmCompletion:
        res = self._find_next_output(
            prompt=prompt.messages,
            tools=prompt.tools,
            use_tools=True,
        )
        if isinstance(res, Message):
            completion = LlmCompletion(res, None)
        else:
            completion = LlmCompletion(Message(content=res, message_type=MessageType.AGENT), None)
        completion.message = prompt.parse_output(completion.message)
        return completion

    async def _stream_generate_impl(
        self,
        prompt: Prompt,
    ) -> AsyncIterable[TaggedMessageChunkTypeWithTokenUsage]:
        final_message = (await self._generate_impl(prompt=prompt)).message
        yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT), None
        yield StreamChunkType.TEXT_CHUNK, final_message, None
        yield StreamChunkType.END_CHUNK, final_message, None

    @property
    def config(self) -> Dict[str, Any]:
        raise NotImplementedError("Dummy models are not supported for serialization")


def generate_usual_sequence_of_chunk(
    final_message: Message,
) -> List[TaggedMessageChunkTypeWithTokenUsage]:
    # initial message is just for message type
    initial_start = final_message.copy(contents=None)
    initial_start.tool_requests = None

    # text content contains the text
    text_message = final_message.copy()
    text_message.tool_requests = None

    return [
        (
            StreamChunkType.START_CHUNK,
            initial_start,
            None,
        ),
        (
            StreamChunkType.TEXT_CHUNK,
            text_message,
            None,
        ),
        (
            StreamChunkType.END_CHUNK,
            final_message,
            None,
        ),
    ]


class DoNothingStep(Step):
    def __init__(
        self,
        llm: Optional[LlmModel] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        super().__init__(
            llm=llm,
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(llm=llm),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            __metadata_info__=__metadata_info__,
        )

    # override
    @property
    def might_yield(self) -> bool:
        return False

    def _invoke_step(
        self,
        inputs: Dict[str, str],
        conversation: FlowConversation,
    ) -> StepResult:
        return StepResult(
            outputs={},
        )

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, Any]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {"llm": Optional[LlmModel]}

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls, llm: Optional[LlmModel] = None
    ) -> List[Property]:
        return []

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls, llm: Optional[LlmModel] = None
    ) -> List[Property]:
        return []

    @classmethod
    def _compute_internal_branches_from_static_config(
        cls, llm: Optional[LlmModel] = None
    ) -> List[str]:
        # We always have a single next step, but we don't know which just based on config
        # it is set in the flow transitions
        return [cls.BRANCH_NEXT]


class SleepStep(Step):
    def __init__(
        self,
        llm: Optional[LlmModel] = None,
        sleep_time: float = 1.0,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        self.sleep_time = sleep_time
        super().__init__(
            llm=llm,
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration={},
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            __metadata_info__=__metadata_info__,
        )

    # override
    @property
    def might_yield(self) -> bool:
        return False

    def _invoke_step(
        self,
        inputs: Dict[str, str],
        conversation: FlowConversation,
    ) -> StepResult:
        import time

        time.sleep(self.sleep_time)

        return StepResult(
            outputs={},
        )

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {
            "llm": LlmModel,
            "sleep_time": float,
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls, llm: Optional[LlmModel] = None, sleep_time: float = 1.0
    ) -> List[Property]:
        return []

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls, llm: Optional[LlmModel] = None, sleep_time: float = 1.0
    ) -> List[Property]:
        return []

    @classmethod
    def _compute_internal_branches_from_static_config(
        cls, llm: Optional[LlmModel] = None, sleep_time: float = 1.0
    ) -> List[str]:
        # We always have a single next step, but we don't know which just based on config
        # it is set in the flow transitions
        return [cls.BRANCH_NEXT]
