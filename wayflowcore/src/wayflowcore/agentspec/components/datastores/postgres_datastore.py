# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict, Literal, Optional

from pyagentspec import Component
from pyagentspec.sensitive_field import SensitiveField

from wayflowcore.agentspec.components.datastores.entity import PluginEntity
from wayflowcore.agentspec.components.datastores.relational_datastore import (
    PluginRelationalDatastore,
)


class PluginPostgresDatabaseConnectionConfig(Component):
    """Base class used for configuring connections to Postgres Database."""


class PluginTlsPostgresDatabaseConnectionConfig(PluginPostgresDatabaseConnectionConfig):
    """TLS Connection Configuration to Postgres Database."""

    user: SensitiveField[str]
    """User of the postgres database"""
    password: SensitiveField[str]
    """Password of the postgres database"""
    url: SensitiveField[str] = "localhost:5432"
    """URL to access the postgres database"""
    sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = (
        "require"
    )
    """SSL mode for the PostgreSQL connection."""
    sslcert: SensitiveField[Optional[str]] = None
    """Path of the client SSL certificate, replacing the default `~/.postgresql/postgresql.crt`.
    Ignored if an SSL connection is not made."""
    sslkey: SensitiveField[Optional[str]] = None
    """Path of the file containing the secret key used for the client certificate, replacing the default
    `~/.postgresql/postgresql.key`. Ignored if an SSL connection is not made."""
    sslrootcert: SensitiveField[Optional[str]] = None
    """Path of the file containing SSL certificate authority (CA) certificate(s). Used to verify server identity."""
    sslcrl: SensitiveField[Optional[str]] = None
    """Path of the SSL server certificate revocation list (CRL). Certificates listed will be rejected
    while attempting to authenticate the server's certificate."""


class PluginPostgresDatabaseDatastore(PluginRelationalDatastore):
    """Datastore that uses Postgres Database as the storage mechanism."""

    # "schema" is a special field for Pydantic, so use the prefix "datastore_" to avoid clashes
    datastore_schema: Dict[str, PluginEntity]
    """Mapping of collection names to entity definitions used by this datastore."""
    connection_config: PluginPostgresDatabaseConnectionConfig
    """Configuration of connection parameters"""
