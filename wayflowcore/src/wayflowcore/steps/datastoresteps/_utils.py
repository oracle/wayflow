# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, List, Optional

from wayflowcore._utils._templating_helpers import (
    get_variables_names_and_types_from_template,
    render_template,
)
from wayflowcore.datastore.datastore import Datastore
from wayflowcore.property import AnyProperty, DictProperty, Property, StringProperty


def compute_input_descriptors_from_where_dict(where: Optional[Dict[str, Any]]) -> List[Property]:
    input_properties: List[Property] = []
    if where is None:
        return input_properties
    for key, value in where.items():
        input_properties += get_variables_names_and_types_from_template(template=key)
        if isinstance(value, str):
            value_properties = get_variables_names_and_types_from_template(template=value)
        else:
            value_properties = []
        if len(value_properties) > 1:
            # This is so that it makes type casting at step execution easier, when users need
            # to redefine the input descriptors (e.g., because one of the values should be an
            # int). In any case we expect a multi-variable use-case to be very rare.
            raise ValueError(
                "Dictionary values in where dictionary can only contain one jinja variable at "
                "a time. Use a template rendering step to render complex values."
            )
        input_properties += value_properties
    return input_properties


def get_entity_as_dict_property(name: str = "") -> Property:
    return DictProperty(name=name, key_type=StringProperty(), value_type=AnyProperty())


def set_values_on_templated_where(
    templated_dict: Dict[str, Any], inputs: Dict[str, Any], input_descriptors: List[Property]
) -> Dict[str, Any]:
    dict_with_resolved_template = {}
    for k, v in templated_dict.items():
        if not isinstance(v, str):
            dict_with_resolved_template[render_template(k, inputs)] = v
            continue
        # There is at most one variable here because we verified it in the static config
        variables_in_template = get_variables_names_and_types_from_template(template=v)
        if len(variables_in_template) > 0:
            input_property_name = variables_in_template[0].name
            input_descriptor = next(
                desc for desc in input_descriptors if desc.name == input_property_name
            )
            if isinstance(input_descriptor, StringProperty):
                # There could be static stuff in the template alongisde the variable
                v = render_template(v, inputs)
            else:
                v = inputs[input_property_name]
        dict_with_resolved_template[render_template(k, inputs)] = v

    return dict_with_resolved_template


def is_parametrized(input: str) -> bool:
    return len(get_variables_names_and_types_from_template(input)) > 0


def validate_collection_name(collection_name: str, datastore: Datastore) -> None:
    if not is_parametrized(collection_name):
        if collection_name not in datastore.describe():
            raise ValueError(f"Entity type not available in datastore {collection_name}")


def check_no_reserved_names(properties: List[Property], reserved_names: List[str]) -> None:
    for p in properties:
        if p.name in reserved_names:
            raise ValueError(
                f"Name {p.name} is reserved in the step. Choose a different name instead."
            )
