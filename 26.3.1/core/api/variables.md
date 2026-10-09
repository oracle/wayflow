# Variables

This page presents all APIs and classes related to variables in WayFlow.

<a id="variable"></a>

### *class* wayflowcore.variable.Variable(type, default_value=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>, name='', description=None)

Variables store values that can be written and read throughout a flow.

Variables simplify data management by providing a shared context or state for values
needed in multiple parts of the flow, and can also be used to collect
intermediate results for reuse at later stages.

* **Parameters:**
  * **name** (`str`) – Name of the variable
  * **type** ([`Property`](flows.md#wayflowcore.property.Property)) – Type of the variable
  * **description** (`Optional`[`str`]) – Description of the variable
  * **default_value** (`Optional`[`Any`]) – 

    Default value for the variable before any write operation is performed.

    #### NOTE
    Collections (lists or dictionaries) must have their default value
    set to a (possibly empty) instance of that collection to enable merge and insert operations.
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

### Examples

```pycon
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.dataconnection import DataFlowEdge
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.property import FloatProperty
>>> from wayflowcore.steps import OutputMessageStep, VariableStep, ToolExecutionStep
>>> from wayflowcore.variable import Variable, VariableWriteOperation
>>> from wayflowcore.tools import tool
>>> float_variable = Variable(
...     name="float_variable",
...     type=FloatProperty(),
...     description="a float variable",
...     default_value=5.0,
... )
>>> var_step_1 = VariableStep(read_variables=[float_variable])
>>> @tool(description_mode="only_docstring")
... def triple_number(x: float) -> float:
...     "Tool that triples a number"
...     return x * 3
>>> triple_step = ToolExecutionStep(tool=triple_number)
>>> var_step_2 = VariableStep(
...     write_variables=[float_variable],
...     read_variables=[float_variable],
...     write_operations=VariableWriteOperation.OVERWRITE,
... )
>>> output_step = OutputMessageStep("The variable is {{ variable }}")
>>> flow = Flow(
...     begin_step=var_step_1,
...     control_flow_edges=[
...         ControlFlowEdge(var_step_1, triple_step),
...         ControlFlowEdge(triple_step, var_step_2),
...         ControlFlowEdge(var_step_2, output_step),
...         ControlFlowEdge(output_step, None),
...     ],
...     data_flow_edges=[
...         DataFlowEdge(var_step_1, float_variable.name, triple_step, "x"),
...         DataFlowEdge(
...             triple_step, ToolExecutionStep.TOOL_OUTPUT, var_step_2, float_variable.name
...         ),
...         DataFlowEdge(var_step_2, float_variable.name, output_step, "variable"),
...     ],
...     variables=[float_variable],
... )
>>> conversation = flow.start_conversation()
>>> status = conversation.execute()
>>> conversation.get_last_message().content
'The variable is 15.0'
```

#### default_value *: `Any`* *= None*

#### *classmethod* from_dict(args)

* **Return type:**
  [`Variable`](#wayflowcore.variable.Variable)
* **Parameters:**
  **args** (*Dict* *[**str* *,* *Any* *]*)

#### *classmethod* from_property(property_)

* **Return type:**
  [`Variable`](#wayflowcore.variable.Variable)
* **Parameters:**
  **property_** ([*Property*](flows.md#wayflowcore.property.Property))

#### to_dict()

* **Return type:**
  `Dict`[`str`, `Any`]

#### to_property()

* **Return type:**
  [`Property`](flows.md#wayflowcore.property.Property)

#### type *: [`Property`](flows.md#wayflowcore.property.Property)*

<a id="variablewriteoperation"></a>

### *class* wayflowcore.variable.VariableWriteOperation(value)

Operations that can be performed when writing a variable.

#### INSERT *= 'insert'*

Operation that can be used to append a single element at the end of a list.

#### MERGE *= 'merge'*

Operation that updates a `Variable` of type dict (resp. list), so that the variable will
contain both the existing data stored in the variable along with the new values in the incoming
dict (resp. list).

#### OVERWRITE *= 'overwrite'*

Operation that works on any type of variable to replace its value with the incoming value.

### *class* wayflowcore.steps.variablesteps.variablestep.VariableStep(write_variables=None, read_variables=None, write_operations=None, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to perform a write and read operations on one or more variables.
These variables are stored in a key-value store distinct from the I/O system.
If both read and write is instructed for a variable, the step will perform write first, and read the updated value afterward.

A step has input and output descriptors, describing what values the step requires to run and what values it produces.

If both read and write is instructed for a variable, the step will perform write first, and read the updated value afterward.

**Input descriptors**

This step has an input descriptor for each variable in `write_variables` as follows:

* `variable.name`:  type will be resolved depending on the variable types and the type of variable write operation. The value to write in the variable store.

**Output descriptors**

This step has an output descriptor for each variable in read_variables as follows:

* `variable.name`: `variable type`, the value read from the variable store.

* **Parameters:**
  * **write_variables** (`Optional`[`List`[[`Variable`](#wayflowcore.variable.Variable)]]) – list of `Variable``s to write to. Leave it as default (``None`) or empty (`[]`) if you don’t have a write operation in this step.
  * **read_variables** (`Optional`[`List`[[`Variable`](#wayflowcore.variable.Variable)]]) – list of `Variable``s to read from. Leave it as default (``None`) or empty (`[]`) if you don’t have a read operation in this step.
  * **write_operations** (`Union`[[`VariableWriteOperation`](#wayflowcore.variable.VariableWriteOperation), `Dict`[`str`, [`VariableWriteOperation`](#wayflowcore.variable.VariableWriteOperation)], `None`]) – 

    The type of operation to perform on `write_variables`. The keys are the name of the write variables.

    If `write_variables` is `None` or an empty list, the value of this variable should also be left as default, be `None`, or an empty dictionary (`{}`).

    If you have one or more variables in `write_variables`, then this step will have write operations involved. You can set a single operation for all of the variables or use a dictionary to specify the operation for each variable separately. If you use a dictionary, you should specify the operation for all the variables in write_variables. Missing an operation for any variable in write_variables leads to a ValueError.

    #### NOTE
    `VariableWriteOperation.OVERWRITE` (or `'overwrite'`) works on any type of variable to replace its value with the incoming value.
    `VariableWriteOperation.MERGE` (or `'merge'`) updates a `Variable` of type dict (resp. list),
    so that the variable will contain both the existing data stored in the variable along with the new values in the incoming dict (resp. list).
    If the operation is `MERGE` but the variable’s value is `None`, it will throw an error,
    as a default value should have been provided when constructing the `Variable`.
    The `VariableWriteOperation.INSERT` (or `'insert'`) operation can be used to append a single element at the end of a list.
  * **input_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.dataconnection import DataFlowEdge
>>> from wayflowcore.steps import OutputMessageStep, VariableStep
>>> from wayflowcore.variable import Variable, VariableWriteOperation
>>> from wayflowcore.property import ListProperty, FloatProperty
>>> variable = Variable(
...     name="variable",
...     type=ListProperty(item_type=FloatProperty()),
...     description="list of floats variable",
...     default_value=[1.0],
... )
>>>
>>> variable_step = VariableStep(
...     write_variables=[variable],
...     read_variables=[variable],
...     write_operations=VariableWriteOperation.MERGE,
... )
>>>
>>> output_step = OutputMessageStep("The variable is {{ value }}.")
>>> flow = Flow(
...     begin_step=variable_step,
...     control_flow_edges=[
...         ControlFlowEdge(variable_step, output_step),
...         ControlFlowEdge(output_step, None),
...     ],
...     data_flow_edges=[
...         DataFlowEdge(variable_step, variable.name, output_step, "value"),
...     ],
...     variables=[variable],
... )
>>>
>>> conv = flow.start_conversation(inputs={variable.name: [2.0, 3.0, 4.0]})
>>> status = conv.execute()
>>> last_message = conv.get_last_message()
>>> last_message.content
'The variable is [1.0, 2.0, 3.0, 4.0].'
```

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

### *class* wayflowcore.steps.variablesteps.variablereadstep.VariableReadStep(variable, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to perform a read on a Variable.
This step has no input, and a single output “value”.
These variables are stored in a key-value store distinct from the I/O system.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

This step has no input descriptor.

**Output descriptors**

This step has a single output descriptor:

* `VariableReadStep.VALUE`: `variable type`, the value read from the variable store.

* **Parameters:**
  * **variable** ([`Variable`](#wayflowcore.variable.Variable)) – `Variable` to read from.
    If the variable refers to a non-existent `Variable` (not passed into the flow), the flow constructor will throw an error.
    An exception is raised if the read returns a `None` value.
  * **input_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.dataconnection import DataFlowEdge
>>> from wayflowcore.steps import VariableReadStep, OutputMessageStep
>>> from wayflowcore.variable import Variable
>>> from wayflowcore.property import ListProperty, FloatProperty
>>>
>>> float_variable = Variable(
...     name="float_variable",
...     type=ListProperty(item_type=FloatProperty()),
...     description="list of floats variable",
...     default_value=[1.0, 2.0, 3.0, 4.0],
... )
>>>
>>> read_step = VariableReadStep(variable=float_variable)
>>> output_step = OutputMessageStep("The variable is {{ variable }}")
>>>
>>> flow = Flow(
...     begin_step=read_step,
...     control_flow_edges=[
...         ControlFlowEdge(read_step, output_step),
...         ControlFlowEdge(output_step, None),
...     ],
...     data_flow_edges=[
...         DataFlowEdge(read_step, VariableReadStep.VALUE, output_step, "variable"),
...     ],
...     variables=[float_variable],
... )
>>> conv = flow.start_conversation()
>>> status = conv.execute()
>>> last_message = conv.get_last_message()
>>> last_message.content
'The variable is [1.0, 2.0, 3.0, 4.0]'
```

#### VALUE *= 'value'*

Output key for the read value from the `VariableReadStep`.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

### *class* wayflowcore.steps.variablesteps.variablewritestep.VariableWriteStep(variable, operation=VariableWriteOperation.OVERWRITE, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to perform a write on a Variable.
This step has no output and a single input, called “value”.
These variables are stored in a key-value store distinct from the I/O system.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

This step has a single input descriptor:

* `VariableWriteStep.VALUE`: `??`, the value to write in the variable store. Type will be resolved depending on the variable type and the type of variable write operation.

**Output descriptors**

This step has no output descriptor.

* **Parameters:**
  * **variable** ([`Variable`](#wayflowcore.variable.Variable)) – `Variable` to write to.
    If the variable refers to a non-existent Variable (not passed into the flow), the flow construction will throw an error.
  * **operation** ([`VariableWriteOperation`](#wayflowcore.variable.VariableWriteOperation)) – 

    The type of write operation to perform.

    #### NOTE
    `VariableWriteOperation.OVERWRITE` (or `'overwrite'`) works on any type of variable to replace its value with the incoming value.
    `VariableWriteOperation.MERGE` (or `'merge'`) updates a `Variable` of type dict (resp. list),
    so that the variable will contain both the existing data stored in the variable along with the new values in the incoming dict (resp. list).
    If the operation is `MERGE` but the variable’s value is `None`, it will throw an error,
    as a default value should have been provided when constructing the `Variable`.
    The `VariableWriteOperation.INSERT` (or `'insert'`) operation can be used to append a single element at the end of a list.
  * **input_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.steps import VariableWriteStep
>>> from wayflowcore.variable import Variable
>>> from wayflowcore.property import ListProperty, FloatProperty
>>>
>>> VARIABLE_IO = "$variable"
>>> # ^ how the variable value is stored in the I/O dict
>>>
>>> float_variable = Variable(
...     name="float_variable",
...     type=ListProperty(item_type=FloatProperty()),
...     description="list of floats variable",
...     default_value=[],
... )
>>>
>>> write_step = VariableWriteStep(
...     variable=float_variable,
...     input_mapping={VariableWriteStep.VALUE: VARIABLE_IO}
... )
>>>
>>> flow = Flow(
...     begin_step=write_step,
...     control_flow_edges=[
...         ControlFlowEdge(write_step, None),
...     ],
...     variables=[float_variable],
... )
>>> conv = flow.start_conversation(inputs={VARIABLE_IO: [1.0, 2.0, 3.0, 4.0]})
>>> status = conv.execute()
>>> new_variable_value = conv._get_variable_value(float_variable)
>>> # In practice, the value can be accessed with a VariableReadStep in the flow
>>> new_variable_value
[1.0, 2.0, 3.0, 4.0]
```

#### VALUE *= 'value'*

Input key for the value to write for the `VariableWriteStep`.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*
