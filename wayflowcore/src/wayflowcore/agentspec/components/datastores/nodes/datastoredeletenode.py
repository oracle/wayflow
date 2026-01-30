# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List

from pyagentspec.datastores import Datastore
from pyagentspec.property import Property

from wayflowcore._utils._templating_helpers import get_variables_names_and_types_from_template
from wayflowcore.agentspec.components.datastores.nodes.datastorecreatenode import (
    _wayflowcore_property_to_pyagentspec_property,
)
from wayflowcore.agentspec.components.node import ExtendedNode
from wayflowcore.steps.datastoresteps._utils import compute_input_descriptors_from_where_dict


class PluginDatastoreDeleteNode(ExtendedNode):
    """Step that can delete entities in a ``Datastore``."""

    datastore: Datastore
    """Datastore this node operates on"""
    collection_name: str
    """Collection in the datastore manipulated by this node.
    Can be parametrized using jinja variables, and the resulting input
    descriptors will be inferred by the node."""
    where: Dict[str, Any]
    """Filtering to be applied when deleting entities. The dictionary is composed of
    property name and value pairs to filter by with exact matches.
    Only entities matching all conditions in the dictionary will be deleted.
    For example, `{"name": "Fido", "breed": "Golden Retriever"}` will match
    all ``Golden Retriever`` dogs named ``Fido``."""

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
        return self.outputs or []
