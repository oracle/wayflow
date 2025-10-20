# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List

from pyagentspec.property import Property

from wayflowcore._utils._templating_helpers import get_variables_names_and_types_from_template
from wayflowcore.agentspec.components.datastores.datastore import PluginDatastore
from wayflowcore.agentspec.components.datastores.nodes.datastorecreatenode import (
    _wayflowcore_property_to_pyagentspec_property,
)
from wayflowcore.agentspec.components.node import ExtendedNode
from wayflowcore.property import ListProperty
from wayflowcore.steps.datastoresteps._utils import (
    compute_input_descriptors_from_where_dict,
    get_entity_as_dict_property,
)


class PluginDatastoreUpdateNode(ExtendedNode):
    """Step that can update entities in a ``PluginDatastore``."""

    datastore: PluginDatastore
    """PluginDatastore this step operates on"""
    collection_name: str
    """Collection in the datastore manipulated by this step.
    Can be parametrized using jinja variables, and the resulting input
    descriptors will be inferred by the step."""
    where: Dict[str, Any]
    """Filtering to be applied when updating entities. The dictionary is composed of
    property name and value pairs to filter by with exact matches.
    Only entities matching all conditions in the dictionary will be updated.
    For example, `{"name": "Fido", "breed": "Golden Retriever"}` will match
    all ``Golden Retriever`` dogs with name ``Fido``."""

    ENTITIES: str = "entities"
    """str: Output key for the entities listed by this step."""

    UPDATE: str = "update"
    """str: Input key for the dictionary of the updates to be made."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        input_properties = get_variables_names_and_types_from_template(
            getattr(self, "collection_name", "")
        )
        input_properties.extend(
            compute_input_descriptors_from_where_dict(getattr(self, "where", {}))
        )
        input_properties.append(get_entity_as_dict_property(self.UPDATE))
        return [
            _wayflowcore_property_to_pyagentspec_property(property_)
            for property_ in input_properties
        ]

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        return [
            _wayflowcore_property_to_pyagentspec_property(
                ListProperty(name=self.ENTITIES, item_type=get_entity_as_dict_property())
            )
        ]
