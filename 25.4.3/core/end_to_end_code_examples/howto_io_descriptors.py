# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# WayFlow Code Example - How to change input and output descriptors of Components
# -------------------------------------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==25.4" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_io_descriptors.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.




# %%[markdown]
## Auto IO detection

# %%
from wayflowcore.steps import InputMessageStep

step = InputMessageStep(
    message_template="You're trying to connect to {{service}}. Please enter your username:"
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  StringProperty(name="service", description=""service" input variable for the template")
print("Output descriptors: ", *step.output_descriptors)
# Output descriptors:  StringProperty(name="user_provided_input", description="the input value provided by the user")

# %%[markdown]
## Specify input descriptor:

# %%
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

# %%[markdown]
## Default any descriptor

# %%
step = InputMessageStep(
    message_template="Here are some snacks: {% for snack in snacks %}{{snack}}{% endfor %}. Which one is your favorite?",
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  AnyProperty(name="snacks", description=""snacks" input variable for the template")

# %%[markdown]
## List descriptor

# %%
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

# %%[markdown]
## Rename a descriptor

# %%
step = InputMessageStep(
    message_template="Hi {{unclear_var_name}}. How are you doing?",
    input_descriptors=[StringProperty(name="username")],
    input_mapping={"unclear_var_name": "username"},
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  StringProperty(name="username")

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(step)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

new_step = AgentSpecLoader().load_json(config)

