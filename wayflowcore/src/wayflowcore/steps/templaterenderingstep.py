# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore._utils._templating_helpers import (
    check_template_validity,
    get_variables_names_and_types_from_template,
    render_template,
)
from wayflowcore.property import Property, StringProperty
from wayflowcore.steps.step import Step, StepResult

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


class TemplateRenderingStep(Step):
    OUTPUT = "output"
    """str: Output key for the rendered template."""

    def __init__(
        self,
        template: str,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Step to render a template given some inputs.

        Note
        ----

        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        **Input descriptors**

        By default, when ``input_descriptors`` is set to ``None``, the input_descriptors will be automatically inferred
        from the ``template``, with one input descriptor per variable in the template,
        trying to detect the type of the variable based on how it is used in the template.
        See below for concrete examples on how descriptors are extracted from text prompts.

        If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
        in particular using the new type instead of the detected one.
        If some of them are missing, an error will be thrown at instantiation of the step.

        If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
        they won't be used during the execution of the step.

        **Output descriptors**

        This step has one output descriptor, ``TemplateRenderingStep.OUTPUT``, of type ``StringProperty()``, that
        is the text rendered by the step.

        Parameters
        ----------
        template:
            jinja template to format. Any jinja variable appearing in this template will be a required input of
            this step. See the example section for concrete examples with WayFlow, or check the reference of
            jinja2 at https://jinja.palletsprojects.com/en/stable/templates.
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
        We provide here some basic examples to work with templates in WayFlow. Any wayflowcore step that takes
        jinja2 templates will automatically detect jinja2 variables and add them as the step inputs.

        **1) Simple variable in a template**

        To add a variable to a template, you just need to wrap its named between double brackets:

        >>> from wayflowcore.steps import TemplateRenderingStep
        >>> TemplateRenderingStep.format_template(
        ...     template="What is the capital of {{country}}?",
        ...     inputs={'country': 'Switzerland'},
        ... )
        'What is the capital of Switzerland?'

        With simple brackets, the variable will be of type string. The variable will be a required
        input of the step.


        **2) More complex variable in a template**

        In many cases, we want to format list of objects inside a template. To do this, we can use the for loop syntax
        of jinja2:

        >>> TemplateRenderingStep.format_template(
        ...     template=(
        ...         "What is the largest capital between "
        ...         "{% for country in countries %}"
        ...         "{{country}}{{ ' and ' if not loop.last }}"
        ...         "{% endfor %}?"
        ...     ),
        ...     inputs={'countries': ['Switzerland', 'France']},
        ... )
        'What is the largest capital between Switzerland and France?'

        Here, the detected variable will be `countries` and its type will be any. You can also loop with list of dicts
        or objects (see more at https://jinja.palletsprojects.com/en/stable/templates/#for).
        The variable will be a required input of the step.


        **3) Optional variables in a template**

        Sometimes, you might want to change the template depending on whether a value exist or not (for example,
        to include feedback when you generate with an LLM, but you don't have any feedback at first). In this case,
        you can use the if jinja syntax as follows:

        >>> TemplateRenderingStep.format_template(
        ...     template="{% if visited %}Welcome back{% else %}Welcome{% endif %}",
        ...     inputs={'visited': None},
        ... )
        'Welcome'
        >>> TemplateRenderingStep.format_template(
        ...     template="{% if visited %}Welcome back{% else %}Welcome{% endif %}",
        ...     inputs={'visited': 'something'},
        ... )
        'Welcome back'

        In this case, the detected variable is of type any and optional and will default to None
        if needed in the step.
        """
        super().__init__(
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(template=template),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )
        self.template = template
        check_template_validity(self.template)

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {
            "template": str,
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        template: str,
    ) -> List[Property]:
        return get_variables_names_and_types_from_template(template)

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        template: str,
    ) -> List[Property]:
        return [
            StringProperty(
                name=TemplateRenderingStep.OUTPUT,
                description="the formatted template",
            )
        ]

    @classmethod
    def format_template(cls, template: str, inputs: Dict[str, Any]) -> str:
        return render_template(template=template, inputs=inputs)

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        return StepResult(
            outputs={
                TemplateRenderingStep.OUTPUT: TemplateRenderingStep.format_template(
                    template=self.template, inputs=inputs
                )
            },
        )
