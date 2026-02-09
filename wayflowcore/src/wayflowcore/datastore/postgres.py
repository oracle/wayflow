# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional, cast

from wayflowcore._utils.lazy_loader import LazyLoader
from wayflowcore.datastore.entity import Entity
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject, serialize_to_dict
from wayflowcore.warnings import SecurityWarning

from ..component import DataclassComponent
from ._relational import RelationalDatastore

if TYPE_CHECKING:
    # Important: do not move these imports out of the TYPE_CHECKING
    # block so long as sqlalchemy is an optional dependencies.
    # Otherwise, importing the module when they are not installed would lead to an import error.
    import sqlalchemy
else:
    sqlalchemy = LazyLoader("sqlalchemy")


@dataclass(kw_only=True)
class PostgresDatabaseConnectionConfig(DataclassComponent, ABC):
    """Abstract class for a PostgreSQL connection."""

    @abstractmethod
    def get_connection(self) -> "sqlalchemy.Engine":
        raise NotImplementedError()

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        warnings.warn(
            f"{self.__class__.__name__} is a security sensitive configuration object, "
            "and cannot be serialized.",
            SecurityWarning,
        )
        return {}

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        raise TypeError(
            f"{cls.__name__} is a security sensitive configuration object, and "
            "cannot be deserialized."
        )


@dataclass(kw_only=True)
class TlsPostgresDatabaseConnectionConfig(PostgresDatabaseConnectionConfig):
    """Configuration for a PostgreSQL connection with TLS/SSL support."""

    user: str
    """User of the postgres database"""

    password: str
    """Password of the postgres database"""

    url: str = "localhost:5432"
    """URL to access the postgres database"""

    sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = (
        "require"
    )
    """SSL mode for the PostgreSQL connection."""

    sslcert: Optional[str] = None
    """Path of the client SSL certificate, replacing the default `~/.postgresql/postgresql.crt`.
    Ignored if an SSL connection is not made."""

    sslkey: Optional[str] = None
    """Path of the file containing the secret key used for the client certificate, replacing the default
    `~/.postgresql/postgresql.key`. Ignored if an SSL connection is not made."""

    sslrootcert: Optional[str] = None
    """Path of the file containing SSL certificate authority (CA) certificate(s). Used to verify server identity."""

    sslcrl: Optional[str] = None
    """Path of the SSL server certificate revocation list (CRL). Certificates listed will be rejected
    while attempting to authenticate the server's certificate."""

    def get_sqlalchemy_url(self) -> str:
        """Builds a SQLAlchemy connection URL."""
        return (
            f"postgresql+psycopg2://{str(self.user)}:{str(self.password)}@"
            f"{self._remove_trailing_http(self.url)}/postgres"
        )

    def _remove_trailing_http(self, url: str) -> str:
        return url.rstrip("http://").rstrip("https://")

    def get_connection(self) -> "sqlalchemy.Engine":
        from sqlalchemy import create_engine

        connect_args: Dict[str, Any] = {"sslmode": self.sslmode}

        # Only apply SSL-related parameters when SSL is not disabled
        if self.sslmode != "disable":
            if self.sslcert is not None:
                connect_args["sslcert"] = self.sslcert
            if self.sslkey is not None:
                connect_args["sslkey"] = str(self.sslkey)
            if self.sslrootcert is not None:
                connect_args["sslrootcert"] = self.sslrootcert
            if self.sslcrl is not None:
                connect_args["sslcrl"] = self.sslcrl

        return create_engine(self.get_sqlalchemy_url(), connect_args=connect_args)


class PostgresDatabaseDatastore(RelationalDatastore, SerializableObject):
    """Datastore that uses Postgres Database as the storage mechanism.

    .. important::

        This ``Datastore`` can only be used to connect to existing
        database schemas, with tables of interest already defined in the
        database.

    """

    def __init__(
        self,
        schema: Dict[str, Entity],
        connection_config: PostgresDatabaseConnectionConfig,
    ):
        """Initialize an Postgres Database Datastore.

        Parameters
        ----------
        schema :
            Mapping of collection names to entity definitions used by
            this datastore.
        connection_config :
            Configuration of connection parameters
        """
        self.connection_config = connection_config
        engine = connection_config.get_connection()
        super().__init__(schema, engine)
        SerializableObject.__init__(self)

    def _serialize_to_dict(self, serialization_context: SerializationContext) -> Dict[str, Any]:
        return {
            "schema": {
                name: serialize_to_dict(entity, serialization_context)
                for name, entity in self.schema.items()
            },
            "connection_config": serialize_to_dict(self.connection_config, serialization_context),
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> "PostgresDatabaseDatastore":
        from wayflowcore.serialization.serializer import autodeserialize_from_dict

        schema = {
            name: cast(Entity, autodeserialize_from_dict(entity, deserialization_context))
            for name, entity in input_dict["schema"].items()
        }

        connection_config = cast(
            PostgresDatabaseConnectionConfig,
            autodeserialize_from_dict(input_dict["connection_config"], deserialization_context),
        )

        return PostgresDatabaseDatastore(schema, connection_config)


def _execute_query_on_postgres_db(
    connection_config: PostgresDatabaseConnectionConfig, query: str
) -> None:
    from sqlalchemy import text

    with connection_config.get_connection().begin() as conn:
        conn.execute(text(query))
