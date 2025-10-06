# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import inspect
from typing import Callable, Type

import pytest

import wayflowcore.steps  # keep it to make sure to import all steps
from wayflowcore.steps import __all__ as all_public_steps
from wayflowcore.steps.step import Step, _StepRegistry


def get_function_params(func: Callable):
    """
    Returns a Dict[str, inspect.Parameter] linking parameter names to their type and optional default value
    """
    args = dict(inspect.signature(func).parameters)

    for x in ["return", "self"]:
        if x in args:
            del args[x]
    return args


def check_function_call_be_called_with_args(func_args, args):
    """
    Checks that a func can be called with some arguments and it will not crash, meaning that:
    - required values are passed
    - if some additional values are passed, the function has **kwargs
    """
    func_arg_keys = set(func_args.keys())
    args_names = set(args.keys())

    if func_arg_keys == args_names:
        return True

    if "kwargs" not in func_args:
        return False

    func_arg_keys.remove("kwargs")

    if "args" in func_arg_keys:
        func_arg_keys.remove("args")

    return func_arg_keys.issubset(args_names)


def defaults_are_equal(arg1, arg2):
    if isinstance(arg1, (list, tuple)) and isinstance(arg2, (list, tuple)):
        return sorted(arg1) == sorted(arg2)
    if isinstance(arg1, dict) and isinstance(arg2, dict):
        return all(arg1[k] == arg2[k] for k in arg1.keys())
    return arg1 == arg2


STEPS_TO_SKIP = {
    Step.__name__,  # base class, doesn't have the functions implemented
}


@pytest.mark.parametrize(
    "step_class",
    argvalues=_StepRegistry._REGISTRY.values(),
    ids=_StepRegistry._REGISTRY.keys(),
)
def test_signature_of_all_methods_correspond(step_class: Type[Step]):
    if (
        step_class.__name__ not in all_public_steps or step_class.__name__ in STEPS_TO_SKIP
    ):  # not internal steps
        pytest.skip("Internal step, no need to check")

    # initialization arguments
    args_init = get_function_params(step_class.__init__)
    for required_arg_name in [
        "input_mapping",
        "output_mapping",
        "__metadata_info__",
        "input_descriptors",
        "output_descriptors",
        "name",
    ]:
        assert required_arg_name in args_init
        args_init.pop(required_arg_name)

    # we will skip private argument
    for arg_name in list(args_init.keys()):
        if arg_name[0] == "_":
            args_init.pop(arg_name)

    static_config = step_class._get_step_specific_static_configuration_descriptors()

    static_config_with_io_descriptors_if_needed = {k: v for k, v in static_config.items()}
    if step_class._input_descriptors_change_step_behavior:
        static_config_with_io_descriptors_if_needed["input_descriptors"] = None
    if step_class._output_descriptors_change_step_behavior:
        static_config_with_io_descriptors_if_needed["output_descriptors"] = None

    # wayflowcore-only args
    # we deprecated this argument, replacing it with llm.
    # We should not throw an error if missing from static configs
    for core_arg_name in ["llms"]:
        if core_arg_name in args_init:
            args_init.pop(core_arg_name)

    args_static_input = get_function_params(
        step_class._compute_step_specific_input_descriptors_from_static_config
    )
    args_static_output = get_function_params(
        step_class._compute_step_specific_output_descriptors_from_static_config
    )
    args_static_next_step = get_function_params(
        step_class._compute_internal_branches_from_static_config
    )

    # check equality
    assert set(args_init.keys()) == set(
        static_config.keys()
    ), f"Step should have same arguments for initialization and in the static configuration"

    # check builder functions can be called with the static configuration
    assert check_function_call_be_called_with_args(
        args_static_input, static_config_with_io_descriptors_if_needed
    ), "Step should have same arguments for initialization and computing the step inputs"
    assert check_function_call_be_called_with_args(
        args_static_output, static_config_with_io_descriptors_if_needed
    ), "Step should have same arguments for initialization and computing the step outputs"
    assert check_function_call_be_called_with_args(
        args_static_next_step, static_config_with_io_descriptors_if_needed
    ), "Step should have same arguments for initialization and computing the next steps"
