# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import jq
from json_repair import repair_json

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.json_correction import edit_json
from wayflowcore.models.llmmodel import LlmModel
from wayflowcore.property import Property, StringProperty, string_to_property
from wayflowcore.steps.step import Step, StepResult

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation

logger = logging.getLogger(__name__)


def extract_potential_json_strings(text: str) -> List[str]:
    """Extract any potential JSON strings from an LLM's markdown output."""
    # First split on the backticks to get the regions that may contain JSON.
    regions = text.split("```")

    # Now, for each region, if we can parse it as JSON, do so and extract the requested values.
    strip_json_identifier = r"^\s*\[?\s*(?:json|JSON)\s*]?\s*\:?\s*([\s\S]+?)\s*$"

    potential_json_strs = []
    for txt in regions:
        # Remove any leading "json" identifiers, possibly in square brackets and with colon.
        m = re.search(strip_json_identifier, txt)
        txt = m.groups()[0] if m is not None else txt
        txt = txt.strip()

        if len(txt) > 0:
            repaired_json = repair_json(txt, return_objects=False)
            if repaired_json != '""':
                potential_json_strs.append(str(repaired_json))
    return potential_json_strs


class ExtractValueFromJsonStep(Step):
    TEXT = "text"
    """str: Input key for the raw json text to be parsed."""

    def __init__(
        self,
        output_values: Dict[Union[str, Property], str],
        llm: Optional[LlmModel] = None,
        retry: bool = False,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Step to extract information from a raw json text. It will first remove any ``````` or `````json`` delimiters, then load the json,
        and outputs all extracted values for which a jq expression was given.

        Note
        ----

        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        **Input descriptors**

        This step has a single input descriptor:

        * ``ExtractValueFromJsonStep.TEXT``: ``StringProperty()``, text to extract the values from.

        **Output descriptors**

        This step can have several output descriptors, one per key in the ``output_values`` mapping. The type will be ``AnyProperty()``.


        Parameters
        ----------
        output_values:
            The keys are either output names of this step or complete ``Property``. The values are the jq formulas to extract them from the json detected
        llm:
            LLM to correct the json with. By default, no LLM-based correction is applied.
        retry:
            If true, and there was a problem parsing the json, this step will try again to fix it. Defaults to False.
        input_descriptors:
            Input descriptors of the step. ``None`` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.

        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically using its static
            configuration in a best effort manner.

        name:
            Name of the step.

        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.

        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.

        Examples
        --------
        >>> from wayflowcore.steps import ExtractValueFromJsonStep
        >>> from wayflowcore.flowhelpers import create_single_step_flow

        To match some part of the llm output, you might use some regex like:

        >>> step = ExtractValueFromJsonStep(
        ...     output_values={
        ...         'thought': '.thought',
        ...         'name': '.action.function_name',
        ...     },
        ... )
        >>> assistant = create_single_step_flow(step, 'step')
        >>> conversation = assistant.start_conversation(inputs={ExtractValueFromJsonStep.TEXT: '{"thought":"I should call a tool", "action": {"function_name":"some_tool", "function_args": {}}}'})
        >>> status = conversation.execute()
        >>> status.output_values['name'] == "some_tool"
        True
        >>> status.output_values['thought'] == "I should call a tool"
        True

        """

        super().__init__(
            llm=llm,
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(
                output_values=output_values,
                llm=llm,
                retry=retry,
            ),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )
        self.retry = retry and self.llm is not None
        self.jq_processors = {
            (output_descr.name if isinstance(output_descr, Property) else output_descr): jq.compile(
                output_query
            )
            for output_descr, output_query in output_values.items()
        }
        self.output_values = output_values

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        # TODO: support keys being Property
        return {
            "output_values": Dict[str, str],
            "llm": Optional[LlmModel],  # type: ignore
            "retry": bool,
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        output_values: Dict[Union[str, Property], str],
        llm: Optional[LlmModel],
        retry: bool,
    ) -> List[Property]:
        return [
            StringProperty(
                name=cls.TEXT,
                description=f"raw text to extract information from",
            )
        ]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        output_values: Dict[Union[str, Property], str],
        llm: Optional[LlmModel],
        retry: bool,
    ) -> List[Property]:
        return [string_to_property(v) for v in output_values.keys()]

    def _extract_potential_json_blobs_from_string(self, raw_txt: str) -> List[str]:
        # find potential json blobs in raw text string
        blobs = []

        # First split on the backticks to get the regions that may contain JSON.
        regions = raw_txt.split("```")
        strip_json_identifier = r"^\s*\[?\s*(?:json|JSON)\s*]?\s*\:?\s*([\s\S]+?)\s*$"
        for txt in regions:
            # Remove any leading "json" identifiers, possibly in square brackets and with colon.
            m = re.search(strip_json_identifier, txt)
            txt = m.groups()[0] if m is not None else txt

            if len(txt) == 0:
                continue

            blobs.append(txt)
        return blobs

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        # We will have some thoughts and values from the LLM, separated by ```
        # Example:
        # The thought is: ```
        # {
        #     "v1": "some value",
        # }
        # ```
        # The action will therefore be:
        # ```
        # {
        #     "v2": "some other value"
        # }
        # ```
        raw_txt: str = inputs[self.TEXT]

        found_values = {}

        for txt in extract_potential_json_strings(raw_txt):

            if txt.strip() == "":
                continue

            logger.debug("Extracting from <%s>", txt)
            # Try to parse the section as JSON
            # Note that this will run over all blocks, including model thoughts (see example below), however :
            # 1. It is unlikely that random model thoughts will be valid JSON
            # 2. We only take values supplied in JQ templates and do not overwrite existing values
            for output_name, output_jq_processor in self.jq_processors.items():
                if output_name not in found_values:
                    # In case of hallucinations, we may see the same value multiple times, just take the first one.

                    # Example:
                    # Prompt asks for the weather in Zurich, the LLM hallucinates related questions + answers.

                    # What is the weather in Zurich?
                    # ```
                    # {
                    # "weather": "sunny"
                    # }
                    # ```
                    # What is the weather in Montreal?
                    # ```
                    # {
                    # "weather": "snowy"
                    # }
                    # ```
                    try:
                        new_value = output_jq_processor.input_text(txt).first()
                        if new_value is not None:
                            found_values[output_name] = new_value
                            logger.debug(f'Set value of "{output_name}" to: {new_value}')
                    except Exception as e:
                        logger.debug(f"Couldn't parse value as JSON: {e}")
                        if self.retry and self.llm is not None:
                            txt = edit_json(
                                txt,
                                str(e),
                                list(self.jq_processors.keys()),
                                conversation,
                                self.llm,
                            )

        return StepResult(
            outputs=found_values,
        )
