# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
from abc import ABCMeta
from dataclasses import dataclass
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
)

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.componentwithio import ComponentWithInputsOutputs
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.property import Property
from wayflowcore.serialization.serializer import (
    SerializableObject,
    autodeserialize_any_from_dict,
    serialize_any_to_dict,
    serialize_to_dict,
)
from wayflowcore.tools import Tool

if TYPE_CHECKING:
    # to avoid circular dependencies
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._flowconversation import FlowConversation
    from wayflowcore.flow import Flow
    from wayflowcore.models.llmmodel import LlmModel
    from wayflowcore.serialization.context import DeserializationContext, SerializationContext

logger = logging.getLogger(__name__)


# How to write a custom step
# ==========================
#
# Do I really need a custom step?
# -------------------------------
#
# Most of the usual agentic logic can be achieved with supported steps and tools. Writing a custom step is only useful/needed
# when some logic is always the same, and we want the experience to be more standard in wayflowcore.
#
# Define the static configuration of the step
# -------------------------------------------
#
# This static configuration defines what are the arguments of the step. They are defined in the ``_get_step_specific_static_configuration_descriptors`` function.
# You need to specify the type of each argument by using item descriptors.
#
# For example, for the ``PromptExecutionStep``:
# ```python
# @classmethod
# def _get_step_specific_static_configuration_descriptors(cls) -> Dict[str, Any]:
#     return {
#         "prompt_template": str,
#         "llm": LlmModel,
#         "generation_config": Optional[LlmGenerationConfig],
#     }
# ```
#
# In some cases, the `input_descriptors`/`output_descriptors` of the step might influence its behavior. For example,
# the ``output_descriptors`` of the `PromptExecutionStep` defines whether the step does structured generation or not.
# In this case, set the `_input_descriptors_change_step_behavior`/`_output_descriptors_change_step_behavior` class attributes of the step to `True`, but
# they should NOT be part of the static config mentioned above.
#
#
#
# Initialisation function
# -----------------------
#
# 1. Should have all these arguments:
#
#    * ``input_descriptors``: for input descriptors overriding
#    * ``output_descriptors``: for output descriptors overriding
#    * ``input_mapping``: for input descriptors renaming
#    * ``output_mapping``: for output descriptors renaming
#    * ``__metadata_info__``: for metadata
#    * all the arguments mentioned in the static config above (with same names)
#
# 2. Calls the super constructor with the following:
#
#     ```
#     super().__init__(
#         llm=llm,  # any LLM that the step might use for proper LLM usage tracking
#         step_static_configuration=<STATIC_CONFIG>,  # mentioned in last section
#         input_mapping=input_mapping,
#         output_mapping=output_mapping,
#         input_descriptors=input_descriptors,
#         output_descriptors=output_descriptors,
#         __metadata_info__=__metadata_info__,
#     )
#     ```
#
# Static descriptor functions
# ---------------------------
#
# One should implement `_compute_step_specific_input_descriptors_from_static_config` and `_compute_step_specific_output_descriptors_from_static_config`.
# These two methods return the io descriptors that the step exposes, which depends on its static configuration. They should both have
# as arguments all the arguments of the static configuration of the step, plus additionally `input_descriptors`/`output_descriptors` if
# `_input_descriptors_change_step_behavior`/`_output_descriptors_change_step_behavior` are set to `True`.
#
# The names of `input_descriptors`/`output_descriptors` are the internal names of the step, before renaming with `input_mapping`/`output_mapping`.
#
# Example with the ``PromptExecutionStep``:
#
# ```python
#     def _compute_step_specific_input_descriptors_from_static_config(
#         cls,
#         prompt_template: str,
#         llm: LlmModel,
#         output_descriptors: Optional[List[Property]],
#         generation_config: Optional[LlmGenerationConfig],
#     ) -> List[Property]:
#         return TemplateRenderingStep._compute_step_specific_input_descriptors_from_static_config(
#             template=prompt_template
#         )
#
#     @classmethod
#     def _compute_step_specific_output_descriptors_from_static_config(
#         cls,
#         prompt_template: str,
#         llm: LlmModel,
#         output_descriptors: Optional[List[Property]],
#         generation_config: Optional[LlmGenerationConfig],
#     ) -> List[Property]:
#         if output_descriptors is not None and len(output_descriptors) > 0:
#             return output_descriptors
#
#         return [
#             StringProperty(
#                 name=PromptExecutionStep.OUTPUT,
#                 description="the generated text",
#             )
#         ]
# ```
#
# Static branches function
# ------------------------
#
# Some steps might have several exit branches depending on what happens during the execution of the step. The ``_compute_internal_branches_from_static_config``
# needs to be implemented to indicate what are the names of the possible branches. This function needs to have the same arguments as
# the static io descriptors methods described in the previous section.
#
# The default branch name, when these is only a single control flow, is ``Step.BRANCH_NEXT``.
#
# Example with the `PromptExecutionStep`:
#
# ```python
# @classmethod
# def _compute_internal_branches_from_static_config(
#     cls,
#     prompt_template: str,
#     llm: LlmModel,
#     output_descriptors: Optional[List[Property]],
#     generation_config: Optional[LlmGenerationConfig],
# ) -> List[Optional[str]]:
#     return [cls.BRANCH_NEXT]
# ```
#
# Implement might yield
# ---------------------
#
# This property `might_yield` says whether the step should be able to yield to the user or not.
#
#
# Implement the `_invoke()`
# -------------------------
#
# The logic of the step needs to be implemented in this function. All inputs are passed in the `inputs` argument, under
# the names and types listed in the `input_descriptors`.
# This function needs to return a `StepResult`, which has:
# - outputs of the `output_descriptors` in a dict.
# - the step result type. It can be ``PASSTHROUGH`` if the step is finished or ``YIELDING`` if the step is not done yet, and it should return to itself.
# - `next_branch` containing the name of the chosen branch, one of the branches returned by `_compute_internal_branches_from_static_config` with the static config or `get_branches()` on the step.
#
#
#
# Template
# --------
# ```python
# # Copyright © 2024, 2025 Oracle and/or its affiliates.
# #
# # Licensed under the Apache License, Version 2.0 (the "License");
# # you may not use this file except in compliance with the License.
# # You may obtain a copy of the License at
# #
# #     http://www.apache.org/licenses/LICENSE-2.0
# #
# # Unless required by applicable law or agreed to in writing, software
# # distributed under the License is distributed on an "AS IS" BASIS,
# # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# # See the License for the specific language governing permissions and
# # limitations under the License.
# import logging
# from typing import Any, Dict, List, Optional
#
# from wayflowcore._metadata import MetadataType
# from wayflowcore.conversation import Conversation
# from wayflowcore.property import Property
# from wayflowcore.stepbuilder.stepbuilder import StepBuilder
# from wayflowcore.steps.step import Step, StepExecutionStatus, StepResult
#
# logger = logging.getLogger(__name__)
#
#
# class SomeStep(Step):
#     """Step to ..."""
#
#     SOME_VAR_OUTPUT = "some_var_output"
#     """str: Output key for the var outputted by the step"""
#
#     def __init__(
#         self,
#         # <STATIC_CONFIG>
#         input_descriptors: Optional[List[Property]] = None,
#         output_descriptors: Optional[List[Property]] = None,
#         input_mapping: Optional[Dict[str, str]] = None,
#         output_mapping: Optional[Dict[str, str]] = None,
#         __metadata_info__: Optional[MetadataType] = None,
#     ):
#
#         super().__init__(
#             step_static_configuration=dict(
#                 # <STATIC_CONFIG>
#             ),
#             input_descriptors=input_descriptors,
#             output_descriptors=output_descriptors,
#             input_mapping=input_mapping,
#             output_mapping=output_mapping,
#             __metadata_info__=__metadata_info__,
#         )
#
#     @classmethod
#     def _get_step_specific_static_configuration_descriptors(cls) -> Dict[str, type]:
#         """
#         Returns a dictionary in which the keys are the names of the configuration items
#         and the values are a descriptor for the expected type
#         """
#         return {
#             # <STATIC_CONFIG>
#         }
#
#     @classmethod
#     def _compute_step_specific_input_descriptors_from_static_config(
#         cls,
#         # <STATIC_CONFIG>
#     ) -> List[Property]:
#         return []
#
#     @classmethod
#     def _compute_step_specific_output_descriptors_from_static_config(
#         cls,
#         # <STATIC_CONFIG>
#     ) -> List[Property]:
#         return []
#
#     @classmethod
#     def _compute_internal_branches_from_static_config(
#         cls,
#         # <STATIC_CONFIG>
#     ) -> List[Optional[str]]:
#         return [cls.BRANCH_NEXT]
#
#     @property
#     def might_yield(self) -> bool:
#         return False
#
#     # You either need to implement `_invoke_step` for CPU-bounded
#     # workloads (it will be ran in a worker thread)
#     # or `_invoke_step_async` for IO-bounded workloads (ran in the main event loop)
#
#     def _invoke_step(
#         self,
#         inputs: Dict[str, Any],
#         conversation: Conversation,
#         step_name: str,
#     ) -> StepResult:
#         return StepResult(
#             outputs={self.SOME_VAR_OUTPUT: ""},     # OUTPUTS following output_descriptors
#             # step_type=StepExecutionStatus.PASSTHROUGH,  # optional
#             # branch_name=cls.BRANCH_NEXT,  # optional, name of the next branch
#         )
#
# ```


def _deserialize_as(
    expected_cls: Type[Any],
    arg_prepared_value: Any,
    deserialization_context: "DeserializationContext",
) -> Any:
    if arg_prepared_value is None:
        return None

    if get_origin(expected_cls) is Union:
        types = get_args(expected_cls)
        internal_type = next(t for t in types if t is not None)
        return _deserialize_as(internal_type, arg_prepared_value, deserialization_context)
    elif get_origin(expected_cls) is list:
        internal_type = get_args(expected_cls)[0]
        return [
            _deserialize_as(internal_type, t, deserialization_context) for t in arg_prepared_value
        ]
    elif get_origin(expected_cls) is dict:
        if isinstance(arg_prepared_value, dict):
            internal_type = get_args(expected_cls)[0]
            return {
                k: _deserialize_as(internal_type, v, deserialization_context)
                for k, v in arg_prepared_value.items()
            }
        return autodeserialize_any_from_dict(arg_prepared_value, deserialization_context)
    elif issubclass(expected_cls, Enum):
        if "_component_type" in arg_prepared_value:
            return autodeserialize_any_from_dict(arg_prepared_value, deserialization_context)
        else:
            try:
                return expected_cls(arg_prepared_value)
            except Exception:
                raise ValueError(
                    f"Error during deserialization of enum. Found value {arg_prepared_value}."
                )
    else:
        return autodeserialize_any_from_dict(arg_prepared_value, deserialization_context)


def _handle_backward_compatibility_for_branches(
    step_cls: Type["Step"],
    step_arguments: Dict[str, Any],
) -> Dict[str, Optional[str]]:
    """
    We previously had next step names in the step config. Now, these old deprecated parameters need to be specified
    in the transitions dict of the flow.
    To still enable loading old configurations (that specify these arguments in the step config), we catch them here,
    remove them from the config but save them as `additional_transitions` that will affect the `transitions` dict later.
    We save these additional transitions in the deserialization context, so that it can be accessed by the flow
    serializer function later.
    """
    compatibility_dict: Dict[str, Optional[str]] = {}

    from wayflowcore.steps import BranchingStep, ChoiceSelectionStep, FlowExecutionStep, RetryStep
    from wayflowcore.steps.step import Step

    def remove_branch_argument_from_config(arg_name: str, branch_name: str) -> None:
        if arg_name in step_arguments:
            logger.warning(
                f"`{arg_name}` is deprecated. Please use instead `{branch_name}` in `transitions`"
            )
            value = step_arguments.pop(arg_name)
            if value is not None:
                compatibility_dict[branch_name] = value

    if step_cls == RetryStep:
        remove_branch_argument_from_config(
            arg_name="success_next_step", branch_name=Step.BRANCH_NEXT
        )
        remove_branch_argument_from_config(
            arg_name="failure_next_step", branch_name=RetryStep.BRANCH_FAILURE
        )

    elif step_cls == ChoiceSelectionStep:
        remove_branch_argument_from_config(
            arg_name="default_next_step", branch_name=ChoiceSelectionStep.BRANCH_DEFAULT
        )

    elif step_cls == BranchingStep:
        if "step_name_mapping" in step_arguments:
            logger.warning(
                "`step_name_mapping` is deprecated for `ChoiceSelectionStep`. Please use `branch_name_mapping` instead"
            )
            step_arguments["branch_name_mapping"] = step_arguments.pop("step_name_mapping") or {}

        remove_branch_argument_from_config(
            arg_name="default_next_step", branch_name=BranchingStep.BRANCH_DEFAULT
        )

    elif step_cls == FlowExecutionStep:
        if "outer_step_transitions" in step_arguments:
            compatibility_dict.update(step_arguments.pop("outer_step_transitions") or {})

    return compatibility_dict


class StepExecutionStatus(str, Enum):
    """
    Enumeration for the type of an assistant step.
    This mainly influences whether to stop and go back to the invoker (yielding step)
    for example to ask user input, or to just continue to the next step (passthrough step).
    """

    PASSTHROUGH = "PASSTHROUGH"
    YIELDING = "YIELDING"
    INTERRUPTED = "INTERRUPTED"


_BRANCH_SELF = "__self__"
_BRANCH_NEXT = "next"


@dataclass
class StepResult:
    """
    Output information collected from the execution of a ``Step``.

    Parameters
    ----------
    outputs:
        Dictionary of outputs collected from the executed ``Step``.
    branch_name:
        Name of the control flow branch the step is taking.
    step_type:
        Whether we want to be able to go back to this step (``StepExecutionStatus.YIELDING``) or simply continue with the next step (``StepExecutionStatus.PASSTHROUGH``).
    """

    outputs: Dict[str, Any]
    branch_name: str = _BRANCH_NEXT
    step_type: StepExecutionStatus = StepExecutionStatus.PASSTHROUGH


class _StepRegistry(ABCMeta):
    """
    Registry pattern implementation for assistant steps.
    """

    # See https://charlesreid1.github.io/python-patterns-the-registry.html for more info

    _REGISTRY: Dict[str, Type["Step"]] = {}

    def __new__(mcs, *args: Any, **kwargs: Any) -> Type[Any]:
        new_cls = super().__new__(mcs, *args, **kwargs)

        if new_cls.__name__ in mcs._REGISTRY:
            raise ValueError(
                f"Found two subtypes of `Step` with the same name '{new_cls.__name__}'. "
                "This is not allowed because it will break the registry pattern needed by several WayFlow "
                "functionalities. Please update the name of the subclasses you implemented."
            )

        mcs._REGISTRY[new_cls.__name__] = new_cls  # type: ignore
        return new_cls


class Step(ComponentWithInputsOutputs, SerializableObject, metaclass=_StepRegistry):
    """
    Assistant steps are what get executed by the flow.
    They can have custom logic in the ``.invoke()`` method.
    They can act based on input values passed to them, or messages in the messages list.
    The messages list should be used to reflect the conversation with the user, i.e.
    only things that make sense to show to the user or that were provided by the user.
    They should indicate what is the next step upon return.
    """

    BRANCH_SELF = _BRANCH_SELF
    """str: Name of the branch taken by a step that will come back to itself."""
    BRANCH_NEXT = _BRANCH_NEXT
    """str: Name of the branch taken by steps that do not have flow control and just have one transition"""

    # DO NOT IMPLEMENT EQUALITY, WayFlow RELIES ON STEP OBJECT EQUALITY

    _input_descriptors_change_step_behavior: ClassVar[bool] = False
    _output_descriptors_change_step_behavior: ClassVar[bool] = False

    def __init__(
        self,
        step_static_configuration: Dict[str, Any],
        llm: Optional["LlmModel"] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        """
        Parameters
        ----------
        llm:
            Model that is used when executing the step.
        name:
            Name of the step.

        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
        input_descriptors:
            List of input descriptors of the step. They will compose the input dictionary that will be passed at ``.invoke()`` time.
        output_descriptors:
            List of output descriptors of the step. The executor will assume that what is returned by ``.invoke()`` contains a value for all these descriptors.
        """

        if input_mapping or output_mapping:
            logger.debug(
                "Input parameters `input_mapping` and `output_mapping` are used to rename io descriptors of step. "
                "Make sure the user-provided descriptors use the new names."
            )
        self.input_mapping: Dict[str, str] = input_mapping or {}
        self.reversed_input_mapping = {
            new_name: old_name for old_name, new_name in self.input_mapping.items()
        }
        self.output_mapping: Dict[str, str] = output_mapping or {}
        self.reversed_output_mapping = {
            new_name: old_name for old_name, new_name in self.output_mapping.items()
        }

        self._step_static_configuration = step_static_configuration
        self._validate_no_io_descriptors_in_internal_static_config()
        self.llm = llm

        # ensure the static config values are attributes of the step
        for static_arg_name, static_arg in step_static_configuration.items():
            setattr(self, static_arg_name, static_arg)

        (
            self.input_descriptors,
            self._internal_input_descriptors,
            self.output_descriptors,
            self._internal_output_descriptors,
        ) = self._resolve_io_descriptors(input_descriptors, output_descriptors)

        ComponentWithInputsOutputs.__init__(
            self,
            name=IdGenerator.get_or_generate_name(
                name, prefix=f"step_{self.__class__.__name__}_", length=8
            ),
            description="",
            input_descriptors=self.input_descriptors,
            output_descriptors=self.output_descriptors,
            __metadata_info__=__metadata_info__,
        )

    def _resolve_io_descriptors(
        self,
        input_descriptors: Optional[List[Property]],
        output_descriptors: Optional[List[Property]],
    ) -> Tuple[List[Property], List[Property], List[Property], List[Property]]:
        step_static_config_with_io_descriptors_if_needed = (
            self._compute_step_specific_methods_arguments(
                static_configuration=self._step_static_configuration,
                input_descriptors=input_descriptors,
                output_descriptors=output_descriptors,
                input_mapping=self.input_mapping,
                output_mapping=self.output_mapping,
            )
        )

        # handle inputs
        internal_input_descriptors = (
            self._compute_step_specific_input_descriptors_from_static_config(
                **step_static_config_with_io_descriptors_if_needed
            )
        )
        for internal_name, new_name in self.input_mapping.items():
            internal_input_names = {prop_.name for prop_ in internal_input_descriptors}
            if internal_name not in internal_input_names:
                raise ValueError(
                    f"Unknown internal input name: {internal_name}.\nAvailable internal input descriptors: {internal_input_names}"
                )

        external_default_input_descriptors = self._rename_properties_from_mapping(
            properties=internal_input_descriptors, mapping=self.input_mapping
        )
        external_input_descriptors = ComponentWithInputsOutputs._resolve_input_descriptors(
            input_descriptors,
            external_default_input_descriptors,
        )

        # handle outputs
        internal_output_descriptors = (
            self._compute_step_specific_output_descriptors_from_static_config(
                **step_static_config_with_io_descriptors_if_needed
            )
        )
        for internal_name, new_name in self.output_mapping.items():
            internal_output_names = {prop_.name for prop_ in internal_output_descriptors}
            if internal_name not in internal_output_names:
                raise ValueError(
                    f"Unknown internal output name: {internal_name}.\nAvailable internal output descriptors: {internal_output_names}"
                )

        external_default_output_descriptors = self._rename_properties_from_mapping(
            properties=internal_output_descriptors, mapping=self.output_mapping
        )
        external_output_descriptors = ComponentWithInputsOutputs._resolve_output_descriptors(
            output_descriptors,
            external_default_output_descriptors,
        )

        return (
            external_input_descriptors,
            internal_input_descriptors,
            external_output_descriptors,
            internal_output_descriptors,
        )

    def _validate_no_io_descriptors_in_internal_static_config(self) -> None:
        if "input_descriptors" in self._step_static_configuration:
            raise ValueError(
                "`input_descriptors` should not appear in the static config. If they have an impact on the "
                "way the step works, please set the attribute `cls._input_descriptors_change_step_behavior` to `True`"
            )
        if "output_descriptors" in self._step_static_configuration:
            raise ValueError(
                "`output_descriptors` should not appear in the static config. If they have an impact on the "
                "way the step works, please set the attribute `cls._output_descriptors_change_step_behavior` to `True`"
            )

    @staticmethod
    def _rename_properties_from_mapping(
        properties: List[Property],
        mapping: Dict[str, str],
    ) -> List[Property]:
        return ComponentWithInputsOutputs._remove_properties_with_duplicate_names(
            [
                (
                    property_.copy(name=mapping[property_.name])
                    if property_.name in mapping
                    else property_
                )
                for property_ in properties
            ]
        )

    @property
    def llms(self) -> List["LlmModel"]:
        return [self.llm] if self.llm is not None else []

    @classmethod
    def get_static_configuration_descriptors(cls) -> Dict[str, type]:
        return {
            **cls._get_common_static_configuration_descriptors(),
            **cls._get_step_specific_static_configuration_descriptors(),
        }

    @classmethod
    def _get_step_specific_static_configuration_descriptors(cls) -> Dict[str, Any]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        raise NotImplementedError()

    @classmethod
    def _get_common_static_configuration_descriptors(
        cls,
    ) -> Dict[str, Any]:
        """
        Returns a dictionary in which the keys are the names of the configuration items common to all steps
        and the values are a descriptor for the expected type
        """

        return {
            "input_descriptors": List[Property],
            "output_descriptors": List[Property],
            "input_mapping": Dict[str, Any],
            "output_mapping": Dict[str, Any],
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls, *args: Any, **kwargs: Any
    ) -> List[Property]:
        """
        Returns a list of input values, based on the static configuration item
        """
        raise NotImplementedError()

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls, *args: Any, **kwargs: Any
    ) -> List[Property]:
        """
        Returns a list of output values, based on the static configuration item
        """
        raise NotImplementedError()

    @classmethod
    def _compute_input_descriptors_from_static_config(
        cls,
        input_mapping: Optional[Dict[str, str]],
        output_mapping: Dict[str, str],
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        **kwargs: Any,
    ) -> List[Property]:
        """
        Returns a list of input values, based on the static configuration item
        """
        static_method_parameters = cls._compute_step_specific_methods_arguments(
            static_configuration=kwargs,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            input_mapping=input_mapping,
            output_mapping=output_mapping,
        )
        internal_input_descriptors = (
            cls._compute_step_specific_input_descriptors_from_static_config(
                **static_method_parameters
            )
        )
        if input_mapping is not None:
            internal_input_descriptors = cls._rename_properties_from_mapping(
                internal_input_descriptors, input_mapping
            )
        return ComponentWithInputsOutputs._resolve_input_descriptors(
            input_descriptors,
            internal_input_descriptors,
        )

    @classmethod
    def _compute_output_descriptors_from_static_config(
        cls,
        input_mapping: Optional[Dict[str, str]],
        output_mapping: Dict[str, str],
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        **kwargs: Any,
    ) -> List[Property]:
        """
        Returns a list of output values, based on the static configuration item
        """
        static_method_parameters = cls._compute_step_specific_methods_arguments(
            static_configuration=kwargs,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            input_mapping=input_mapping,
            output_mapping=output_mapping,
        )
        internal_output_descriptors = (
            cls._compute_step_specific_output_descriptors_from_static_config(
                **static_method_parameters
            )
        )
        if output_mapping is not None:
            internal_output_descriptors = cls._rename_properties_from_mapping(
                internal_output_descriptors, output_mapping
            )
        return ComponentWithInputsOutputs._resolve_input_descriptors(
            output_descriptors,
            internal_output_descriptors,
        )

    @classmethod
    def _compute_step_specific_methods_arguments(
        cls,
        static_configuration: Dict[str, Any],
        input_mapping: Optional[Dict[str, Any]],
        output_mapping: Optional[Dict[str, Any]],
        input_descriptors: Optional[List[Property]],
        output_descriptors: Optional[List[Property]],
    ) -> Dict[str, Any]:
        new_arguments = {**static_configuration}

        if cls._input_descriptors_change_step_behavior:
            new_arguments["input_descriptors"] = (
                cls._rename_properties_from_mapping(
                    input_descriptors, {v: k for k, v in input_mapping.items()}
                )
                if input_mapping is not None and input_descriptors is not None
                else input_descriptors
            )

        if cls._output_descriptors_change_step_behavior:
            new_arguments["output_descriptors"] = (
                cls._rename_properties_from_mapping(
                    output_descriptors, {v: k for k, v in output_mapping.items()}
                )
                if output_mapping is not None and output_descriptors is not None
                else output_descriptors
            )

        return new_arguments

    @classmethod
    def _compute_branches_from_static_config(
        cls,
        input_mapping: Optional[Dict[str, str]],
        output_mapping: Dict[str, str],
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """
        Returns a list of names of next steps if known from the config, or if just the
        number of next steps is known, a list of similar size containing None values
        """
        static_method_parameters = cls._compute_step_specific_methods_arguments(
            static_configuration=kwargs,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            input_mapping=input_mapping,
            output_mapping=output_mapping,
        )
        return cls._compute_internal_branches_from_static_config(**static_method_parameters)

    @classmethod
    def _compute_internal_branches_from_static_config(cls, *args: Any, **kwargs: Any) -> List[str]:
        """
        Returns a list of names of next steps if known from the config, or if just the
        number of next steps is known, a list of similar size containing None values
        """
        return [cls.BRANCH_NEXT]

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        serialization_dict: Dict[str, Any] = {
            "_component_type": Step.__name__,
            "step_cls": self.__class__.__name__,
            "step_args": {},
            "input_mapping": self.input_mapping,
            "output_mapping": self.output_mapping,
            "input_descriptors": [
                serialize_to_dict(property_, serialization_context)
                for property_ in self.input_descriptors
            ],
            "output_descriptors": [
                serialize_to_dict(property_, serialization_context)
                for property_ in self.output_descriptors
            ],
            "__metadata_info__": self.__metadata_info__,
            "id": self.id,
            "name": self.name,
        }

        step_config = {
            **self._get_common_static_configuration_descriptors(),
            **self._get_step_specific_static_configuration_descriptors(),
        }
        for config_name, config_type_descriptor in step_config.items():
            if config_name in {
                "input_mapping",
                "output_mapping",
                "input_descriptors",
                "output_descriptors",
            }:
                # serialized at the root of the config
                continue
            if not hasattr(self, config_name):
                raise ValueError(
                    f"The step {self.__class__.__name__} cannot be serialized because it has a step "
                    f"config named {config_name} but is missing the attribute of the same name."
                )
            serialization_dict["step_args"][config_name] = serialize_any_to_dict(
                getattr(self, config_name), serialization_context
            )

        return serialization_dict

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        from wayflowcore.property import Property
        from wayflowcore.serialization.serializer import deserialize_from_dict
        from wayflowcore.steps.step import _StepRegistry

        step_cls_name = input_dict["step_cls"]
        if step_cls_name not in _StepRegistry._REGISTRY:
            raise ValueError(
                f"Step `{step_cls_name}` unknown and not registered. Registered steps: {list(_StepRegistry._REGISTRY.keys())}"
            )
        step_cls = _StepRegistry._REGISTRY[step_cls_name]

        step_config = step_cls.get_static_configuration_descriptors()

        step_args_dict = input_dict.get("step_args", {})

        # 1. we remove old arguments and save the compatibility transition dict
        compatibility_dict = _handle_backward_compatibility_for_branches(step_cls, step_args_dict)

        # 2. we handle the deprecated `llms` argument for backward compatibility
        if "llms" in step_args_dict:
            logger.warning(
                f"The `llms` argument of {step_cls_name} is deprecated. Use the `llm` argument instead."
            )
            llms = step_args_dict.pop("llms")
            step_args_dict["llm"] = llms[0] if llms else None

        # 3. load parameters. They might also use this backward compatibility logic
        step_arguments = {}
        for arg_name, arg_prepared_value in step_args_dict.items():
            expected_value_cls = step_config[arg_name]
            step_arguments[arg_name] = _deserialize_as(
                expected_value_cls, arg_prepared_value, deserialization_context
            )

        # 4. once parameters are deserialized (they can also contain old arguments), we can register this
        # compatibility dict to the deserialization context so that it can be caught by the flow serializing function
        deserialization_context._register_additional_transitions(compatibility_dict)

        if "input_mapping" in input_dict:
            step_arguments["input_mapping"] = input_dict["input_mapping"]
        if "output_mapping" in input_dict:
            step_arguments["output_mapping"] = input_dict["output_mapping"]
        if "__metadata_info__" in input_dict:
            step_arguments["__metadata_info__"] = input_dict["__metadata_info__"]
        if "input_descriptors" in input_dict:
            step_arguments["input_descriptors"] = [
                deserialize_from_dict(Property, property_, deserialization_context)
                for property_ in input_dict["input_descriptors"]
            ]
        if "output_descriptors" in input_dict:
            step_arguments["output_descriptors"] = [
                deserialize_from_dict(Property, property_, deserialization_context)
                for property_ in input_dict["output_descriptors"]
            ]
        step = step_cls(**step_arguments)

        if "id" in input_dict:
            step.id = input_dict["id"]

        if "name" in input_dict:
            step.name = input_dict["name"]

        return step

    @property
    def might_yield(self) -> bool:
        """
        Indicates if the step might yield back to the user.
        Might be the step directly, or one of the steps it calls.
        """
        # only a few steps can yield, so make the default assumed case to be
        # not yielding
        return False

    def sub_flows(self) -> Optional[List["Flow"]]:
        """
        Returns the sub-flows this step uses, if it does.
        """
        return None

    def sub_flow(self) -> Optional["Flow"]:
        """
        Returns the first sub-flow this step uses, if it does.
        """
        sub_flows = self.sub_flows()
        return sub_flows[0] if sub_flows is not None and len(sub_flows) > 0 else None

    @property
    def supports_dict_io_with_non_str_keys(self) -> bool:
        """
        Indicates if the step can accept/return dictionaries with
        keys that are not strings as IO.
        """
        return False

    def _has_async_implemented(self) -> bool:
        return "_invoke_step_async" in self.__class__.__dict__

    async def invoke_async(
        self, inputs: Dict[str, Any], conversation: "Conversation"
    ) -> StepResult:
        from wayflowcore.executors._flowconversation import FlowConversation
        from wayflowcore.tracing.span import StepInvocationSpan

        if not isinstance(conversation, FlowConversation):
            raise ValueError(
                f"the provided conversation to a flow must be of type FlowConversation but was {type(conversation).__name__}"
            )
        with StepInvocationSpan(
            step=self, inputs=inputs, name=f"StepInvocation[{self.name}]"
        ) as span:
            internal_inputs = self.remap_inputs(inputs)
            if self._has_async_implemented():
                step_result = await self._invoke_step_async(
                    inputs=internal_inputs, conversation=conversation
                )
            else:
                step_result = self._invoke_step(inputs=internal_inputs, conversation=conversation)
            step_result.outputs = self.remap_outputs(step_result.outputs)
            span.record_end_span_event(step_result=step_result)
        return step_result

    def invoke(self, inputs: Dict[str, Any], conversation: "Conversation") -> StepResult:
        return run_async_in_sync(
            self.invoke_async, inputs, conversation, method_name="invoke_async"
        )

    def _invoke_step(self, inputs: Dict[str, Any], conversation: "FlowConversation") -> StepResult:
        """
        Invokes the step with the given inputs and conversation context.

        This method is intended to be overridden by subclasses to implement custom logic.
        The method should act based on the provided inputs and conversation context, and
        returns a ``StepResult`` indicating the next step in the conversation.
        """
        raise NotImplementedError()

    async def _invoke_step_async(
        self, inputs: Dict[str, Any], conversation: "FlowConversation"
    ) -> StepResult:
        """
        Invokes the step with the given inputs and conversation context.

        This method is intended to be overridden by subclasses to implement custom logic.
        The method should act based on the provided inputs and conversation context, and
        returns a ``StepResult`` indicating the next step in the conversation.
        """
        raise NotImplementedError()

    def get_branches(self) -> List[str]:
        """Returns the names of the control flow output branches of this step"""
        expected_parameters_names = list(
            self._get_step_specific_static_configuration_descriptors().keys()
        )
        if self._input_descriptors_change_step_behavior:
            expected_parameters_names.append("input_descriptors")
        if self._output_descriptors_change_step_behavior:
            expected_parameters_names.append("output_descriptors")
        expected_parameters_names.extend(["input_mapping", "output_mapping"])
        parameters = {
            param_name: getattr(self, param_name) for param_name in expected_parameters_names
        }
        return self._compute_branches_from_static_config(**parameters)

    def remap_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if self.input_mapping is None or len(self.input_mapping) == 0:
            return inputs

        input_with_internal_names = {}
        for input_descriptor in self._internal_input_descriptors:
            internal_name = input_descriptor.name
            external_name = self.input_mapping.get(internal_name, internal_name)
            if external_name in inputs:
                input_with_internal_names[internal_name] = inputs[external_name]
        return input_with_internal_names

    def remap_outputs(self, outputs: Dict[str, Any]) -> Dict[str, type]:
        if self.output_mapping is None or len(self.output_mapping) == 0:
            return outputs

        output_with_external_names = {}
        for output_descriptor in self.output_descriptors:
            external_name = output_descriptor.name
            internal_name = self.reversed_output_mapping.get(external_name, external_name)
            if internal_name in outputs:
                output_with_external_names[external_name] = outputs[internal_name]

        if (
            "__execution_status__" in outputs
        ):  # Workaround: If output mapping is specified, this key is removed from the Step Outputs.
            output_with_external_names["__execution_status__"] = outputs["__execution_status__"]
        return output_with_external_names

    def _referenced_tools(self, recursive: bool = True) -> List["Tool"]:
        """
        Returns a list of all tools that are present in this component's configuration, including tools
        nested in subcomponents
        """
        visited_set: Set[str] = set()
        all_tools_dict = self._referenced_tools_dict(recursive=recursive, visited_set=visited_set)
        return list(all_tools_dict.values())

    def _referenced_tools_dict(
        self, recursive: bool = True, visited_set: Optional[Set[str]] = None
    ) -> Dict[str, "Tool"]:
        """
        Returns a dictionary of all tools that are present in this component's configuration, including tools
        nested in subcomponents, with the keys being the tool IDs, and the values being the tools.
        """
        visited_set = set() if visited_set is None else visited_set

        if self.id in visited_set:
            # we are already visited, no need to return anything
            return {}

        # Mark ourself as visited to avoid repeated visits
        visited_set.add(self.id)

        return self._referenced_tools_dict_inner(recursive=recursive, visited_set=visited_set)

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        """
        Returns a dictionary of all tools that are present in this component's configuration, including tools
        nested in subcomponents, with the keys being the tool IDs, and the values being the tools.
        """
        return {}
