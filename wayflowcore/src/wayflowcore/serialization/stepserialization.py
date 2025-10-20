# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Type,
    Union,
    get_args,
    get_origin,
)

from ..models import LlmModel
from ..stepdescription import StepDescription
from ..tools import Tool
from .context import DeserializationContext, SerializationContext
from .serializer import autodeserialize_any_from_dict, deserialize_from_dict, serialize_any_to_dict

if TYPE_CHECKING:
    from wayflowcore.steps.step import Step

logger = logging.getLogger(__name__)


def serialize_step_to_dict(
    step: "Step", serialization_context: SerializationContext
) -> Dict[str, Any]:
    """
    Converts a step to a nested dict of standard types such that it can be easily serialized with
    either JSON or YAML

    Parameters
    ----------
    step:
      The Step that is intended to be serialized
    """
    from wayflowcore.serialization.serializer import serialize_to_dict
    from wayflowcore.steps.step import Step

    serialization_dict: Dict[str, Any] = {
        "_component_type": Step.__name__,
        "step_cls": step.__class__.__name__,
        "step_args": {},
        "input_mapping": step.input_mapping,
        "output_mapping": step.output_mapping,
        "input_descriptors": [
            serialize_to_dict(property_, serialization_context)
            for property_ in step.input_descriptors
        ],
        "output_descriptors": [
            serialize_to_dict(property_, serialization_context)
            for property_ in step.output_descriptors
        ],
        "__metadata_info__": step.__metadata_info__,
        "id": step.id,
        "name": step.name,
    }

    step_config = {
        **step._get_common_static_configuration_descriptors(),
        **step._get_step_specific_static_configuration_descriptors(),
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
        if not hasattr(step, config_name):
            raise ValueError(
                f"The step {step.__class__.__name__} cannot be serialized because it has a step "
                f"config named {config_name} but is missing the attribute of the same name."
            )
        serialization_dict["step_args"][config_name] = serialize_any_to_dict(
            getattr(step, config_name), serialization_context
        )

    return serialization_dict


def deserialize_step_from_dict(
    step_as_dict: Dict[str, Any], deserialization_context: DeserializationContext
) -> "Step":
    from wayflowcore.property import Property
    from wayflowcore.serialization.serializer import deserialize_from_dict
    from wayflowcore.steps.step import _StepRegistry

    step_cls_name = step_as_dict["step_cls"]
    if step_cls_name not in _StepRegistry._REGISTRY:
        raise ValueError(
            f"Step `{step_cls_name}` unknown and not registered. Registered steps: {list(_StepRegistry._REGISTRY.keys())}"
        )
    step_cls = _StepRegistry._REGISTRY[step_cls_name]

    step_config = step_cls.get_static_configuration_descriptors()

    step_args_dict = step_as_dict.get("step_args", {})

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

    if "input_mapping" in step_as_dict:
        step_arguments["input_mapping"] = step_as_dict["input_mapping"]
    if "output_mapping" in step_as_dict:
        step_arguments["output_mapping"] = step_as_dict["output_mapping"]
    if "__metadata_info__" in step_as_dict:
        step_arguments["__metadata_info__"] = step_as_dict["__metadata_info__"]
    if "input_descriptors" in step_as_dict:
        step_arguments["input_descriptors"] = [
            deserialize_from_dict(Property, property_, deserialization_context)
            for property_ in step_as_dict["input_descriptors"]
        ]
    if "output_descriptors" in step_as_dict:
        step_arguments["output_descriptors"] = [
            deserialize_from_dict(Property, property_, deserialization_context)
            for property_ in step_as_dict["output_descriptors"]
        ]
    step = step_cls(**step_arguments)

    if "id" in step_as_dict:
        step.id = step_as_dict["id"]

    if "name" in step_as_dict:
        step.name = step_as_dict["name"]

    return step


def _deserialize_as(
    expected_cls: Type[Any],
    arg_prepared_value: Any,
    deserialization_context: DeserializationContext,
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
    elif expected_cls == Tool:
        return deserialize_from_dict(Tool, arg_prepared_value, deserialization_context)
    elif expected_cls == StepDescription:
        return deserialize_from_dict(StepDescription, arg_prepared_value, deserialization_context)
    elif expected_cls == LlmModel:
        return deserialize_from_dict(LlmModel, arg_prepared_value, deserialization_context)
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


def _handle_transitions_updates(
    step: "Step",
    step_name: str,
    old_transitions: Union[Sequence[Optional[str]], Dict[str, Optional[str]]],
    additional_transitions: Dict[str, Optional[str]],
) -> Dict[str, Optional[str]]:
    """
    Based on the previously gathered `additional_transitions` (during step building), we now modify the `transitions`
    dict to include these additional transitions, and fill potentially missing branches that are now mandatory
    (to avoid crashing on old configs)
    """
    if isinstance(old_transitions, Mapping):
        if not isinstance(old_transitions, dict):
            raise ValueError("Internal error")

        if len(additional_transitions) > 0:
            old_transitions.update(additional_transitions)
        return old_transitions

    from wayflowcore.steps import BranchingStep, ChoiceSelectionStep, RetryStep
    from wayflowcore.steps.step import Step

    transitions_dict = additional_transitions

    step_cls = step.__class__

    if step_cls in [BranchingStep, ChoiceSelectionStep, RetryStep]:
        if step_cls == BranchingStep:
            if BranchingStep.BRANCH_DEFAULT not in transitions_dict:
                transitions_dict[BranchingStep.BRANCH_DEFAULT] = None

        elif step_cls == ChoiceSelectionStep:
            if ChoiceSelectionStep.BRANCH_DEFAULT not in transitions_dict:
                transitions_dict[ChoiceSelectionStep.BRANCH_DEFAULT] = None

        elif step_cls == RetryStep:
            if RetryStep.BRANCH_NEXT not in transitions_dict:
                transitions_dict[RetryStep.BRANCH_NEXT] = None
            if RetryStep.BRANCH_FAILURE not in transitions_dict:
                transitions_dict[RetryStep.BRANCH_FAILURE] = None

        branches = step.get_branches()
        for old_transition in old_transitions:
            if old_transition in branches:
                transitions_dict[str(old_transition)] = old_transition

    else:
        if len(old_transitions) > 1 and step_name in old_transitions:
            old_transitions = [s for s in old_transitions if s != step_name]
        if len(old_transitions) == 1:
            transitions_dict = {Step.BRANCH_NEXT: old_transitions[0]}
        else:
            ValueError(
                f"Found several potential next steps and transitions is a list: {old_transitions}"
            )

    return transitions_dict
