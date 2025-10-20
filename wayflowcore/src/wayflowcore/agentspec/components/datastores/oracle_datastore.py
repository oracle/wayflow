# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict, Optional

from pyagentspec import Component

from wayflowcore.agentspec.components.datastores.entity import PluginEntity
from wayflowcore.agentspec.components.datastores.relational_datastore import (
    PluginRelationalDatastore,
)


class PluginOracleDatabaseConnectionConfig(Component):
    """Base class used for configuring connections to Oracle Database."""


class PluginTlsOracleDatabaseConnectionConfig(PluginOracleDatabaseConnectionConfig):
    """TLS Connection Configuration to Oracle Database."""

    user: str
    """User used to connect to the database"""
    password: str
    """Password for the provided user"""
    dsn: str
    """Connection string for the database (e.g., created using `oracledb.make_dsn`)"""
    config_dir: Optional[str] = None
    """Configuration directory for the database connection. Set this if you are using an
        alias from your tnsnames.ora files as a DSN. Make sure that the specified DSN is
        appropriate for TLS connections (as the tnsnames.ora file in a downloaded wallet
        will only include DSN entries for mTLS connections)"""


class PluginMTlsOracleDatabaseConnectionConfig(PluginOracleDatabaseConnectionConfig):
    """Mutual-TLS Connection Configuration to Oracle Database."""

    config_dir: str
    """TNS Admin directory"""
    dsn: str
    """Connection string for the database, or entry in the tnsnames.ora file"""
    user: str
    """Connection string for the database"""
    password: str
    """Password for the provided user"""
    wallet_location: str
    """Location where the Oracle Database wallet is stored."""
    wallet_password: str
    """Password for the provided wallet."""


class PluginOracleDatabaseDatastore(PluginRelationalDatastore):
    """In-memory datastore for testing and development purposes."""

    # "schema" is a special field for Pydantic, so use the prefix "datastore_" to avoid clashes
    datastore_schema: Dict[str, PluginEntity]
    """Mapping of collection names to entity definitions used by this datastore."""
    connection_config: PluginOracleDatabaseConnectionConfig
    """Configuration of connection parameters"""
