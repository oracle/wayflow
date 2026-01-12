# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import warnings
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from wayflowcore._utils.lazy_loader import LazyLoader
from wayflowcore.component import DataclassComponent
from wayflowcore.datastore.entity import Entity
from wayflowcore.exceptions import DatastoreError
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject, serialize_to_dict
from wayflowcore.warnings import SecurityWarning

from ._relational import RelationalDatastore

if TYPE_CHECKING:
    # Important: do not move these imports out of the TYPE_CHECKING
    # block so long as sqlalchemy and oracledb are optional dependencies.
    # Otherwise, importing the module when they are not installed would lead to an import error.
    import oracledb
    import sqlalchemy
else:
    oracledb = LazyLoader("oracledb")
    sqlalchemy = LazyLoader("sqlalchemy")


@dataclass
class OracleDatabaseConnectionConfig(DataclassComponent):
    """Base class used for configuring connections to Oracle Database."""

    def get_connection(self) -> Any:
        """Create a connection object from the configuration

        Returns
        -------
        Any
            A `python-oracledb` connection object
        """
        try:
            connection_config = asdict(self)
            # pop metadata object attributes
            connection_config.pop("id")
            connection_config.pop("name")
            connection_config.pop("description")
            connection_config.pop("__metadata_info__")
            return oracledb.connect(**connection_config)
        except oracledb.DatabaseError as e:
            raise DatastoreError(
                "Connection to the database failed. Check the root exception for more details."
            ) from e

    def _serialize_to_dict(self, serialization_context: SerializationContext) -> Dict[str, Any]:
        warnings.warn(
            "OracleDatabaseConnectionConfig is a security sensitive configuration object, "
            "and cannot be serialized.",
            SecurityWarning,
        )
        return {}

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> "OracleDatabaseConnectionConfig":
        raise TypeError(
            "OracleDatabaseConnectionConfig is a security sensitive configuration object, and "
            "cannot be deserialized."
        )


@dataclass
class TlsOracleDatabaseConnectionConfig(OracleDatabaseConnectionConfig, DataclassComponent):
    """TLS Connection Configuration to Oracle Database.

    Parameters
    ----------
    user:
        User used to connect to the database
    password:
        Password for the provided user
    dsn:
        Connection string for the database (e.g., created using `oracledb.make_dsn`)
    config_dir:
        Configuration directory for the database connection. Set this if you are using an
        alias from your tnsnames.ora files as a DSN. Make sure that the specified DSN is
        appropriate for TLS connections (as the tnsnames.ora file in a downloaded wallet
        will only include DSN entries for mTLS connections).
    """

    user: str
    password: str
    dsn: str
    config_dir: Optional[str] = None


@dataclass
class MTlsOracleDatabaseConnectionConfig(OracleDatabaseConnectionConfig, DataclassComponent):
    """Mutual-TLS Connection Configuration to Oracle Database.

    Parameters
    ----------
    config_dir
        TNS Admin directory
    dsn
        connection string for the database, or entry in the tnsnames.ora file
    user
        connection string for the database
    password
        password for the provided user
    wallet_location
        location where the Oracle Database wallet is stored
    wallet_password
        password for the provided wallet
    """

    config_dir: Optional[str]
    dsn: str
    user: str
    password: str
    wallet_location: str
    wallet_password: str


class OracleDatabaseDatastore(RelationalDatastore, SerializableObject):
    """Datastore that uses Oracle Database as the storage mechanism.

    .. important::

        This ``Datastore`` can only be used to connect to existing
        database schemas, with tables of interest already defined in the
        database.

    """

    def __init__(
        self, schema: Dict[str, Entity], connection_config: OracleDatabaseConnectionConfig
    ):
        """Initialize an Oracle Database Datastore.

        Parameters
        ----------
        schema :
            Mapping of collection names to entity definitions used by
            this datastore.
        connection_config :
            Configuration of connection parameters
        """
        self.connection_config = connection_config
        engine = sqlalchemy.create_engine(
            "oracle+oracledb://", creator=connection_config.get_connection
        )
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
    ) -> "OracleDatabaseDatastore":
        from wayflowcore.serialization.serializer import autodeserialize_from_dict

        schema = {
            name: cast(Entity, autodeserialize_from_dict(entity, deserialization_context))
            for name, entity in input_dict["schema"].items()
        }

        connection_config = cast(
            OracleDatabaseConnectionConfig,
            autodeserialize_from_dict(input_dict["connection_config"], deserialization_context),
        )

        return OracleDatabaseDatastore(schema, connection_config)


def _execute_query_on_oracle_db(
    connection_config: OracleDatabaseConnectionConfig, query: str
) -> None:
    with connection_config.get_connection() as conn:
        conn.cursor().execute(query)
