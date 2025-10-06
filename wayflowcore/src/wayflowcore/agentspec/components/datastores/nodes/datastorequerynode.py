# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import List

from pyagentspec.property import Property

from wayflowcore.agentspec.components.datastores.nodes.datastorecreatenode import (
    _wayflowcore_property_to_pyagentspec_property,
)
from wayflowcore.agentspec.components.datastores.relational_datastore import (
    PluginRelationalDatastore,
)
from wayflowcore.agentspec.components.node import ExtendedNode
from wayflowcore.property import AnyProperty, DictProperty, ListProperty, StringProperty


class PluginDatastoreQueryNode(ExtendedNode):
    """Step to execute a parameterized SQL query on a relational ``PluginDatastore``
    (``PluginOracleDatabaseDatastore``), that supports SQL queries (the specific
    SQL dialect depends on the database backing the datastore).

    This step enables safe, flexible querying of datastores using
    parameterized SQL.  Queries must use bind variables (e.g., `:customer_id`).
    String templating within queries is forbidden for security reasons;
    any such usage raises an error.
    """

    datastore: PluginRelationalDatastore
    """The ``PluginDatastore`` to execute the query against"""
    query: str
    """SQL query string using bind variables (e.g., ``SELECT * FROM table WHERE id = :val``).
    String templating/interpolation is forbidden and will raise an exception."""

    RESULT: str = "result"
    """str: Output key for the query result (list of dictionaries, one per row)."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        # Accept all bind variables as a single dictionary input to prevent potential
        # issues with regex identifying the bind variable names
        return [
            _wayflowcore_property_to_pyagentspec_property(
                DictProperty(
                    name="bind_variables",
                    key_type=StringProperty(),
                    value_type=AnyProperty(),
                )
            )
        ]

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        return [
            _wayflowcore_property_to_pyagentspec_property(
                ListProperty(
                    name=self.RESULT,
                    item_type=DictProperty(
                        key_type=StringProperty(),
                        value_type=AnyProperty(),
                    ),
                )
            )
        ]
