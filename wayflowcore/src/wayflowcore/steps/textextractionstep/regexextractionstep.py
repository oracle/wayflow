# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from wayflowcore._metadata import MetadataType
from wayflowcore.outputparser import RegexPattern
from wayflowcore.property import ListProperty, Property, StringProperty
from wayflowcore.steps.step import Step, StepResult

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation

logger = logging.getLogger(__name__)


class RegexExtractionStep(Step):
    TEXT = "text"
    """str: Input key for the raw text to be parsed with regex."""
    OUTPUT = "output"
    """str: Output key for the result from the regex parsing."""

    def __init__(
        self,
        regex_pattern: Union[str, RegexPattern],
        return_first_match_only: bool = True,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Step to extract information from a raw text using a regular expression (regex). The step returns the first matched text in the regex.

        Note
        ----

        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        **Input descriptors**

        This step has a single input descriptor:

        * ``RegexExtractionStep.TEXT``: ``StringProperty()``, text on which to use the regex pattern

        **Output descriptors**

        This step has a single output descriptor:

        * ``RegexExtractionStep.OUTPUT``: ``StringProperty()`` / ``ListProperty(StringProperty())``, the matched text / list of texts if ``return_first_match_only`` is ``True``

        Parameters
        ----------
        regex_pattern:
            Regex pattern to match the output(s).
        return_first_match_only:
            Whether to return a single match (if several matches are found) or all the matches as a list.
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
        >>> from wayflowcore.steps import RegexExtractionStep

        To match some part of the llm output, you might use some regex like:

        >>> step = RegexExtractionStep(
        ...     regex_pattern=r"Thought: (.*)\\nAction:",
        ... ) # doctest: +SKIP

        to extract from a Thought: ... Action: ... REACT pattern. It will return only the first match.

        To match all emails present in the text, use for example:

        >>> step = RegexExtractionStep(
        ...     regex_pattern=r"\\b\\w+@\\w+\\.\\w+",
        ...     return_first_match_only=False,
        ... ) # doctest: +SKIP

        and it will return a list of all emails matched in the text.

        """

        super().__init__(
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(
                regex_pattern=regex_pattern, return_first_match_only=return_first_match_only
            ),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )
        self.regex_pattern = regex_pattern
        self.return_first_match_only = return_first_match_only

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, Any]:
        return {
            "regex_pattern": Union[RegexPattern, str],
            "return_first_match_only": bool,
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        regex_pattern: Union[str, RegexPattern],
        return_first_match_only: bool,
    ) -> List[Property]:
        return [
            StringProperty(
                name=RegexExtractionStep.TEXT,
                description=f"raw text to extract information from",
            )
        ]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        regex_pattern: Union[str, RegexPattern],
        return_first_match_only: bool,
    ) -> List[Property]:
        if return_first_match_only:
            output_descriptor: Property = StringProperty(
                name=RegexExtractionStep.OUTPUT,
                description=f'the first extracted value using the regex "{regex_pattern}" from the raw input',
                default_value="",
            )
        else:
            output_descriptor = ListProperty(
                name=RegexExtractionStep.OUTPUT,
                description=f'the list of extracted value using the regex "{regex_pattern}" from the raw input',
                default_value=[],
            )
        return [output_descriptor]

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        raw_txt: str = inputs[self.TEXT]

        regex_pattern = RegexPattern.from_str(self.regex_pattern, flags=None)

        matches = re.findall(
            pattern=regex_pattern.pattern, string=raw_txt, flags=regex_pattern.flags or 0
        )
        matches = [m for m in matches if m != ""]
        logger.debug(
            f'Found {len(matches)} matches when running "{self.regex_pattern}" on "{raw_txt}": "{matches}"'
        )
        return_first = regex_pattern.match == "first"

        if len(matches) == 0:
            logger.warning(f"The RegexExtractionStep found 0 match.")
            if self.return_first_match_only:
                return StepResult(outputs={})
            else:
                return StepResult(outputs={self.OUTPUT: []})
        else:
            if self.return_first_match_only:
                if len(matches) > 1:
                    logger.warning(
                        f"The RegexExtractionStep found more than one match. Only the first one "
                        f"will be returned as output.\nFound a total of {len(matches)} matches:\n"
                        + "\n-----------\n".join(matches)
                    )
                return StepResult(outputs={self.OUTPUT: matches[0 if return_first else -1]})
            else:
                return StepResult(outputs={self.OUTPUT: matches})
