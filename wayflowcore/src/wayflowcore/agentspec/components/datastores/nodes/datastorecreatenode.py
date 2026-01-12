# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List, cast

from pyagentspec.datastores import Datastore
from pyagentspec.property import Property

from wayflowcore._utils._templating_helpers import get_variables_names_and_types_from_template
from wayflowcore.agentspec.components.node import ExtendedNode
from wayflowcore.property import Property as RuntimeProperty
from wayflowcore.steps.datastoresteps._utils import get_entity_as_dict_property


def _wayflowcore_property_to_pyagentspec_property(runtime_property: RuntimeProperty) -> Property:
    return Property(json_schema=cast(Dict[str, Any], runtime_property.to_json_schema()))


class PluginDatastoreCreateNode(ExtendedNode):
    """Node that can create a new entity in a ``Datastore``."""

    datastore: Datastore
    """Datastore this step operates on"""
    collection_name: str
    """Collection in the datastore manipulated by this step.
    Can be parametrized using jinja variables, and the resulting input
    descriptors will be inferred by the step."""

    ENTITY: str = "entity"
    """str: Input key for the entity to be created."""

    CREATED_ENTITY: str = "created_entity"
    """str: Output key for the newly created entity."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        input_properties = get_variables_names_and_types_from_template(
            getattr(self, "collection_name", "")
        )
        input_properties.append(get_entity_as_dict_property(self.ENTITY))
        return [
            _wayflowcore_property_to_pyagentspec_property(property_)
            for property_ in input_properties
        ]

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        return [
            _wayflowcore_property_to_pyagentspec_property(
                get_entity_as_dict_property(self.CREATED_ENTITY)
            )
        ]
