# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import List

from pyagentspec.property import Property

from wayflowcore._utils._templating_helpers import (
    get_non_str_variables_names_from_str_template,
    get_optional_variable_names_from_str,
    get_variable_names_from_str_template,
)


def get_placeholder_properties_from_string_with_jinja_loops(
    string_with_placeholders: str,
) -> List[Property]:
    all_found_var_names = get_variable_names_from_str_template(string_with_placeholders)
    found_non_str_var_names = get_non_str_variables_names_from_str_template(
        string_with_placeholders, all_found_var_names
    )
    found_optional_var_names = get_optional_variable_names_from_str(
        string_with_placeholders, all_found_var_names
    )
    return [
        Property(
            json_schema={
                "title": var_name,
                "type": "string",
                # 'description': '' # TODO description
                **({"default": ""} if var_name in found_optional_var_names else {}),
            }
        )
        for var_name in all_found_var_names
        if var_name not in found_non_str_var_names
    ] + [
        Property(
            json_schema={
                "title": var_name,
                # 'description': '' # TODO description
                **({"default": ""} if var_name in found_optional_var_names else {}),
            }
        )
        for var_name in found_non_str_var_names
        if var_name in all_found_var_names
    ]
