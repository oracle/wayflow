# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from wayflowcore.component import FrozenDataclassComponent
from wayflowcore.property import DictProperty, FloatProperty, ListProperty, Property
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject


class VariableWriteOperation(str, Enum):
    """Operations that can be performed when writing a variable."""

    OVERWRITE = "overwrite"
    """Operation that works on any type of variable to replace its value with the incoming value."""

    MERGE = "merge"
    """Operation that updates a ``Variable`` of type dict (resp. list), so that the variable will
    contain both the existing data stored in the variable along with the new values in the incoming
    dict (resp. list).
    """

    INSERT = "insert"
    """Operation that can be used to append a single element at the end of a list."""

    def __str__(self) -> str:
        return str.__str__(self)


@dataclass(frozen=True)
class Variable(FrozenDataclassComponent):
    """Variables store values that can be written and read throughout a flow.

    Variables simplify data management by providing a shared context or state for values
    needed in multiple parts of the flow, and can also be used to collect
    intermediate results for reuse at later stages.

    Parameters
    ----------
    name:
        Name of the variable
    type:
        Type of the variable
    description:
        Description of the variable
    default_value:
        Default value for the variable before any write operation is performed.

        .. note::

            Collections (lists or dictionaries) must have their default value
            set to a (possibly empty) instance of that collection to enable merge and insert operations.
    Examples
    --------
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

    """

    type: Property
    default_value: Any = None

    def __post_init__(self) -> None:
        if self.name == "":
            raise ValueError(f"Name of variable {self} should not be empty.")

        # TODO: validate the type of the default_value if it's not None
        if self.default_value is None:
            if isinstance(self.type, ListProperty):
                raise ValueError(
                    "The default value for a List variable should be an empty list '[]'."
                )
            elif isinstance(self.type, DictProperty):
                raise ValueError(
                    "The default value for a Dict variable should be an empty dict '{}'."
                )

    def _serialize_to_dict(self, serialization_context: SerializationContext) -> Dict[str, Any]:
        return {
            **self.to_dict(),
            "_component_type": Variable.__name__,
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> "SerializableObject":
        return cls.from_dict({k: v for k, v in input_dict.items() if k != "_component_type"})

    def to_property(self) -> Property:
        return self.type.copy(
            name=self.name,
            description=self.description,
            default_value=(
                self.default_value if self.default_value is not None else Property.empty_default
            ),
        )

    @classmethod
    def from_property(cls, property_: Property) -> "Variable":
        return cls(
            name=property_.name,
            type=property_,
            description=property_.description or None,
            default_value=(
                property_.default_value
                if property_.default_value != Property.empty_default
                else None
            ),
            __metadata_info__=property_.__metadata_info__,
        )

    def to_dict(self) -> Dict[str, Any]:
        from wayflowcore.serialization.serializer import serialize_to_dict

        return {
            "default_value": self.default_value,
            "description": self.description,
            "name": self.name,
            "type": serialize_to_dict(self.type),
        }

    @classmethod
    def from_dict(cls, args: Dict[str, Any]) -> "Variable":
        from wayflowcore.serialization.serializer import deserialize_from_dict

        property_dict = args.pop("type", None)
        if property_dict is None:
            property_dict = {}

        if "json_type" in property_dict:
            raise ValueError("Legacy property with `json_type` is deprecated.")

        property_ = deserialize_from_dict(Property, property_dict)

        default_value = args.get("default_value", None)
        if (
            default_value is not None
            and isinstance(default_value, int)
            and isinstance(property_, FloatProperty)
        ):
            default_value = float(default_value)

        return Variable(
            name=args["name"],
            description=args["description"],
            default_value=default_value,
            type=property_,
        )
