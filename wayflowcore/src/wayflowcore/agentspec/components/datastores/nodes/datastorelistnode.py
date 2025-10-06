# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, List, Optional

from pyagentspec.property import ListProperty, Property

from wayflowcore._utils._templating_helpers import get_variables_names_and_types_from_template
from wayflowcore.agentspec.components.datastores import PluginDatastore
from wayflowcore.agentspec.components.datastores.nodes.datastorecreatenode import (
    _wayflowcore_property_to_pyagentspec_property,
)
from wayflowcore.agentspec.components.node import ExtendedNode
from wayflowcore.steps.datastoresteps._utils import (
    compute_input_descriptors_from_where_dict,
    get_entity_as_dict_property,
)


class PluginDatastoreListNode(ExtendedNode):
    """Step that can list entities in a ``PluginDatastore``."""

    datastore: PluginDatastore
    """PluginDatastore this step operates on"""
    collection_name: str
    """Collection in the datastore manipulated by this step.
    Can be parametrized using jinja variables, and the resulting input
    descriptors will be inferred by the step."""
    where: Optional[Dict[str, Any]]
    """Filtering to be applied when retrieving entities. The dictionary is composed of
    property name and value pairs to filter by with exact matches.
    Only entities matching all conditions in the dictionary will be retrieved.
    For example, `{"name": "Fido", "breed": "Golden Retriever"}` will match
    all ``Golden Retriever`` dogs named ``Fido``."""
    limit: Optional[int]
    """Maximum number of entities to list. By default retrieves all entities."""
    unpack_single_entity_from_list: Optional[bool]
    """When limit is set to `1`, one may optionally decide to unpack the single entity
    in the list and only return a the dictionary representing the retrieved entity.
    This can be useful when, e.g., reading a single entity by its ID."""

    ENTITIES: str = "entities"
    """str: Output key for the entities listed by this step."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        input_properties = get_variables_names_and_types_from_template(
            getattr(self, "collection_name", "")
        )
        input_properties.extend(
            compute_input_descriptors_from_where_dict(getattr(self, "where", {}))
        )
        return [
            _wayflowcore_property_to_pyagentspec_property(property_)
            for property_ in input_properties
        ]

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        if getattr(self, "unpack_single_entity_from_list", False):
            return [
                _wayflowcore_property_to_pyagentspec_property(
                    get_entity_as_dict_property(self.ENTITIES)
                )
            ]
        else:
            return [
                ListProperty(
                    title=self.ENTITIES,
                    item_type=_wayflowcore_property_to_pyagentspec_property(
                        get_entity_as_dict_property()
                    ),
                )
            ]
