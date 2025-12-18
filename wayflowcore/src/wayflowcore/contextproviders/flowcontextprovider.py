# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import dataclasses
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from wayflowcore._metadata import MetadataType
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.property import Property

from .contextprovider import ContextProvider

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.flow import Flow
    from wayflowcore.tools import Tool


logger = logging.getLogger(__name__)


class FlowContextProvider(ContextProvider):

    def __init__(
        self,
        flow: "Flow",
        flow_output_names: Optional[List[str]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        """Context provider that wraps and executes a flow.

        Parameters
        ----------
        flow:
            The ``Flow`` to be used as context. It must not require inputs and must not yield.
        flow_output_names:
            List of output names for the context provider, to be used in the calling flow's I/O system.
            This list must contain unique names.
            These names, if specified, must be a subset of the context flow's outputs.
            If not specified, defaults to all outputs from all steps of the provided flow
        name:
            The name of the context provider

        Examples
        --------
        >>> from wayflowcore.contextproviders import FlowContextProvider
        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.steps import OutputMessageStep
        >>> contextual_flow = Flow.from_steps([OutputMessageStep(
        ...     message_template="The current time is 2pm.",
        ...     output_mapping={OutputMessageStep.OUTPUT: "time_output_io"},
        ... )])
        >>> context_provider = FlowContextProvider(contextual_flow, flow_output_names=["time_output_io"])
        >>> flow = Flow.from_steps(
        ...     steps=[OutputMessageStep("Last time message: {{time_output_io}}")],
        ...     context_providers=[context_provider]
        ... )
        >>> conversation = flow.start_conversation()
        >>> execution_status = conversation.execute()
        >>> last_message = conversation.get_last_message()
        >>> # print(last_message.content)
        >>> # Last time message: The current time is 2pm.

        """
        from wayflowcore.executors._flowexecutor import FlowConversationExecutor

        if flow.might_yield:
            raise ValueError("The context flow must not yield")
        self.flow = flow
        if flow_output_names is not None:
            self._validate_flow_output_names(set(flow_output_names), flow)
        self.flow_output_names = flow_output_names or list(self.flow.output_descriptors_dict.keys())
        self._output_descriptions = [
            # NOTE: using the mapped name instead of the default name here as there might be dupes
            dataclasses.replace(value_description, name=mapped_name)
            for mapped_name, value_description in self.flow.output_descriptors_dict.items()
            if mapped_name in (self.flow_output_names)
        ]
        self._executor = FlowConversationExecutor()
        super().__init__(
            name=name, id=id, description=description, __metadata_info__=__metadata_info__
        )

    async def call_async(self, conversation: "Conversation") -> Any:
        from wayflowcore.tracing.span import ContextProviderExecutionSpan

        with ContextProviderExecutionSpan(context_provider=self) as span:
            conversation = self.flow.start_conversation(
                inputs={},
                messages=conversation.message_list,
            )
            status = await conversation.execute_async()
            if status._requires_yielding:
                raise ValueError("The context flow must not yield")
            if not isinstance(status, FinishedStatus):  # type narrowing for mypy
                raise ValueError(
                    "The final execution status of the context flow must be FinishedStatus"
                )
            extracted_outputs = self._extract_outputs(status)
            span.record_end_span_event(
                output=extracted_outputs,
            )
            return extracted_outputs

    def _extract_outputs(self, status: FinishedStatus) -> Any:
        # assumes unique names in output_descriptions
        output_names = {value_desc.name for value_desc in self.get_output_descriptors()}
        outputs = tuple(v for k, v in status.output_values.items() if k in output_names)
        if len(outputs) == 1:
            outputs = outputs[0]
        return outputs

    @classmethod
    def get_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        from wayflowcore.flow import Flow

        return {
            "flow": Flow,
            "flow_output_names": List[str],
        }

    def get_output_descriptors(self) -> List["Property"]:
        return self._output_descriptions

    @staticmethod
    def _validate_flow_output_names(flow_output_names: Set[str], flow: "Flow") -> None:
        names_of_flow_outputs = set(flow.output_descriptors_dict.keys())
        if not flow_output_names.issubset(names_of_flow_outputs):
            raise ValueError(
                "If flow_output_names is specified, it must be a subset of the context flow's outputs. "
                f"You specified {flow_output_names} but the flow returns {names_of_flow_outputs}"
            )

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        all_tools = {}

        if recursive:
            all_tools.update(
                self.flow._referenced_tools_dict(recursive=True, visited_set=visited_set)
            )

        return all_tools
