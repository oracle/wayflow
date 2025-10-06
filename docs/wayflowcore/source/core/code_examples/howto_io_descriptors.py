# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: WayFlow Code Example - How to change input and output descriptors of Components


# .. start-##_Auto_IO_detection
from wayflowcore.steps import InputMessageStep

step = InputMessageStep(
    message_template="You're trying to connect to {{service}}. Please enter your username:"
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  StringProperty(name="service", description=""service" input variable for the template")
print("Output descriptors: ", *step.output_descriptors)
# Output descriptors:  StringProperty(name="user_provided_input", description="the input value provided by the user")
# .. end-##_Auto_IO_detection
# .. start-##_Specify_input_descriptor:
from wayflowcore.property import StringProperty
from wayflowcore.steps import InputMessageStep

step = InputMessageStep(
    message_template="You're trying to connect to {{service}}. Please enter your username:",
    input_descriptors=[
        StringProperty(
            name="service",
            description="service to which the user wants to connect to",
            default_value="OCI",
        )
    ],
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  StringProperty(name="service", description="service to which the user wants to connect to", default_value="OCI")
# .. end-##_Specify_input_descriptor
# .. start-##_Default_any_descriptor
step = InputMessageStep(
    message_template="Here are some snacks: {% for snack in snacks %}{{snack}}{% endfor %}. Which one is your favorite?",
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  AnyProperty(name="snacks", description=""snacks" input variable for the template")
# .. end-##_Default_any_descriptor
# .. start-##_List_descriptor
from wayflowcore.property import ListProperty

step = InputMessageStep(
    message_template="Here are some snacks: {% for snack in snacks %}{{snack}}{% endfor %}. Which one is your favorite?",
    input_descriptors=[
        ListProperty(
            name="snacks",
            description="list of snacks",
            item_type=StringProperty(),
        )
    ],
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  ListProperty(name="snacks", item=StringProperty(), description="list of snacks")
# .. end-##_List_descriptor
# .. start-##_Rename_a_descriptor
step = InputMessageStep(
    message_template="Hi {{unclear_var_name}}. How are you doing?",
    input_descriptors=[StringProperty(name="username")],
    input_mapping={"unclear_var_name": "username"},
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  StringProperty(name="username")
# .. end-##_Rename_a_descriptor
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(step)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

new_step = AgentSpecLoader().load_json(config)
# .. end-##_Load_Agent_Spec_config

from wayflowcore.serialization import serialize  # docs-skiprow
assert serialize(step) == serialize(new_step)  # docs-skiprow
