# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.property import JsonSchemaParam, Property

from .tools import Tool


class ClientTool(Tool):
    """
    Contains the description of a tool, including its name, documentation and schema of its
    arguments. Instead of being run in the server, calling this tool will actually
    yield to the client for them to compute the result, and post it back to continue
    execution.

    Attributes
    ----------
    name:
        name of the tool
    description:
        description of the tool
    input_descriptors:
        list of properties describing the inputs of the tool.
    output_descriptors:
        list of properties describing the outputs of the tool.

        If there is a single output descriptor, the tool needs to just return the value.
        If there are several output descriptors, the tool needs to return a dict of all expected values.

        If no output descriptor is passed, or if a single output descriptor is passed without a name, the output will
        be automatically be named ``Tool.DEFAULT_TOOL_NAME``.

    Examples
    --------
    >>> from wayflowcore.tools import ClientTool
    >>> from wayflowcore.property import FloatProperty
    >>> addition_client_tool = ClientTool(
    ...    name="add_numbers",
    ...    description="Simply adds two numbers",
    ...    input_descriptors=[
    ...         FloatProperty(name="a", description="the first number", default_value=0),
    ...         FloatProperty(name="b", description="the second number"),
    ...    ],
    ... )

    """

    def __init__(
        self,
        name: str,
        description: str,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        parameters: Optional[Dict[str, JsonSchemaParam]] = None,
        output: Optional[JsonSchemaParam] = None,
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):

        super().__init__(
            name=name,
            description=description,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            parameters=parameters,
            output=output,
            id=id,
            __metadata_info__=__metadata_info__,
            requires_confirmation=False,
        )

    @property
    def might_yield(self) -> bool:
        """
        Indicates that the client tool might yield (it always does).
        """
        return True
