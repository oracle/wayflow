# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore.tools import ClientTool, ServerTool

GET_LOCATION_CLIENT_TOOL = ClientTool(
    name="get_location",
    description="Search the location of a given company",
    parameters={
        "company_name": {
            "type": "string",
            "description": "Name of the company to search the location for",
            "default": "Oracle",
        },
    },
)

DUMMY_SERVER_TOOL = ServerTool(
    name="simple_function",
    description="This is a simple function",
    func=lambda: print("This is a simple function"),
    input_descriptors=[],
)
