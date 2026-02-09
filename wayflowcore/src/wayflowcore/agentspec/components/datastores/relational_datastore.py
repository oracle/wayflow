# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore.agentspec.components.datastores.datastore import PluginDatastore


class PluginRelationalDatastore(PluginDatastore, abstract=True):
    """A relational data store that supports querying data using SQL-like queries.

    This class extends the PluginDatastore class and adds support for querying
    data using SQL-like queries.
    """
