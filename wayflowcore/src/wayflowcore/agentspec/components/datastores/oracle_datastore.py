# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict, Optional

from pyagentspec import Component
from pyagentspec.sensitive_field import SensitiveField
from pydantic import SerializeAsAny

from wayflowcore.agentspec.components.datastores.entity import PluginEntity
from wayflowcore.agentspec.components.datastores.relational_datastore import (
    PluginRelationalDatastore,
)


class PluginOracleDatabaseConnectionConfig(Component, abstract=True):
    """Base class used for configuring connections to Oracle Database."""


class PluginTlsOracleDatabaseConnectionConfig(PluginOracleDatabaseConnectionConfig):
    """TLS Connection Configuration to Oracle Database."""

    user: SensitiveField[str]
    """User used to connect to the database"""
    password: SensitiveField[str]
    """Password for the provided user"""
    dsn: SensitiveField[str]
    """Connection string for the database (e.g., created using `oracledb.make_dsn`)"""
    config_dir: SensitiveField[Optional[str]] = None
    """Configuration directory for the database connection. Set this if you are using an
        alias from your tnsnames.ora files as a DSN. Make sure that the specified DSN is
        appropriate for TLS connections (as the tnsnames.ora file in a downloaded wallet
        will only include DSN entries for mTLS connections)"""


class PluginMTlsOracleDatabaseConnectionConfig(PluginOracleDatabaseConnectionConfig):
    """Mutual-TLS Connection Configuration to Oracle Database."""

    config_dir: SensitiveField[str]
    """TNS Admin directory"""
    dsn: SensitiveField[str]
    """Connection string for the database, or entry in the tnsnames.ora file"""
    user: SensitiveField[str]
    """Connection string for the database"""
    password: SensitiveField[str]
    """Password for the provided user"""
    wallet_location: SensitiveField[str]
    """Location where the Oracle Database wallet is stored."""
    wallet_password: SensitiveField[str]
    """Password for the provided wallet."""


class PluginOracleDatabaseDatastore(PluginRelationalDatastore):
    """Datastore that uses Oracle Database as the storage mechanism."""

    # "schema" is a special field for Pydantic, so use the prefix "datastore_" to avoid clashes
    datastore_schema: Dict[str, PluginEntity]
    """Mapping of collection names to entity definitions used by this datastore."""
    connection_config: SerializeAsAny[PluginOracleDatabaseConnectionConfig]
    """Configuration of connection parameters"""
