# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
import pytest

from wayflowcore import Step
from wayflowcore.flowhelpers import run_step_and_return_outputs
from wayflowcore.property import IntegerProperty
from wayflowcore.steps.step import StepResult


class StepWithAllMethodsButInvokeMixin:
    def _compute_step_specific_input_descriptors_from_static_config(self):
        return []

    def _compute_step_specific_output_descriptors_from_static_config(self):
        return [IntegerProperty(name="output")]

    def _get_step_specific_static_configuration_descriptors(self):
        return {}


def test_step_raises_when_no_implemented_invoke():

    class MyCustomStepWithoutInvoke(StepWithAllMethodsButInvokeMixin, Step):
        pass

    step = MyCustomStepWithoutInvoke(step_static_configuration={})
    with pytest.raises(NotImplementedError):
        run_step_and_return_outputs(step)


def test_step_works_when_implemented_invoke():

    class MyCustomStepWithInvoke(StepWithAllMethodsButInvokeMixin, Step):
        def _invoke_step(self, inputs, conversation):
            return StepResult(outputs={"output": 1})

    step = MyCustomStepWithInvoke(step_static_configuration={})
    assert run_step_and_return_outputs(step) == {"output": 1}


def test_step_works_when_implemented_invoke_async():

    class MyCustomStepWithInvokeAsync(StepWithAllMethodsButInvokeMixin, Step):
        async def _invoke_step_async(self, inputs, conversation):
            return StepResult(outputs={"output": 1})

    step = MyCustomStepWithInvokeAsync(step_static_configuration={})
    assert run_step_and_return_outputs(step) == {"output": 1}
