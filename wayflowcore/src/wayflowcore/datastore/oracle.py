# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
import warnings
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.lazy_loader import LazyLoader
from wayflowcore.component import DataclassComponent
from wayflowcore.datastore.entity import Entity
from wayflowcore.exceptions import DatastoreError
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.search import (
    OracleDatabaseVectorIndex,
    SearchConfig,
    VectorConfig,
    VectorRetrieverConfig,
)
from wayflowcore.search.metrics import SimilarityMetric
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

logger = logging.getLogger(__name__)


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
        self,
        schema: Dict[str, Entity],
        connection_config: OracleDatabaseConnectionConfig,
        search_configs: Optional[List["SearchConfig"]] = None,
        vector_configs: Optional[List["VectorConfig"]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        id: Optional[str] = None,
        __metadata_info__: Optional["MetadataType"] = None,
    ):
        """Initialize an Oracle Database Datastore.

        Search config resolution priority:
            1. Explicit collection match (config.collection_name == requested)
            2. Universal config (config.collection_name is None/empty)

        Vector Config resolution Priority:
            1. VectorRetrieverConfig has a vectors attribute defined
            2. One of vector_configs' collection name matches with input collection_name
            3. Vector column is inferred from Schema

        Parameters
        ----------
        schema :
            Mapping of collection names to entity definitions used by
            this datastore.
        connection_config :
            Configuration of connection parameters
        search_configs :
            List of search configurations for vector search capabilities.
            By default, it's set as None.
            If no search config is given, the datastore will not support Search functionality.
        vector_configs :
            List of vector configurations for vector generation and storage.
            By default, it's set as None.
            If None, a vector config will be inferred for each vector property found in the schema.
        name :
            Name of the datastore
        description :
            Description of the datastore
        id :
            ID of the datastore
        """
        self.connection_config = connection_config
        engine = sqlalchemy.create_engine(
            "oracle+oracledb://", creator=connection_config.get_connection
        )

        for vector_config in vector_configs or []:
            if vector_config.serializer:
                logger.warning(
                    "Received SerializerConfig in "
                    "VectorConfig passed during initialization of OracleDatabaseDatastore."
                    "SerializerConfig will be ignored and not be used in the OracleDatabaseDatastore."
                )

        self.engine = engine
        super().__init__(
            schema=schema,
            engine=engine,
            search_configs=search_configs,
            vector_configs=vector_configs,
            id=id,
            name=IdGenerator.get_or_generate_name(name, prefix="oracle_datastore", length=8),
            description=description,
            __metadata_info__=__metadata_info__,
        )

        SerializableObject.__init__(self, None)

    def _serialize_to_dict(self, serialization_context: SerializationContext) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "schema": {
                name: serialize_to_dict(entity, serialization_context)
                for name, entity in self.schema.items()
            },
            "connection_config": serialize_to_dict(self.connection_config, serialization_context),
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }

        # Include search_configs and vector_configs in serialization if they exist
        if self.search_configs is not None:
            result["search_configs"] = [
                serialize_to_dict(config, serialization_context) for config in self.search_configs
            ]

        if self.vector_configs is not None:
            result["vector_configs"] = [
                serialize_to_dict(config, serialization_context) for config in self.vector_configs
            ]

        return result

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> "OracleDatabaseDatastore":
        from wayflowcore.serialization.serializer import (
            autodeserialize_any_from_dict,
            autodeserialize_from_dict,
        )

        schema = {
            name: cast(Entity, autodeserialize_from_dict(entity, deserialization_context))
            for name, entity in input_dict["schema"].items()
        }

        connection_config = cast(
            OracleDatabaseConnectionConfig,
            autodeserialize_from_dict(input_dict["connection_config"], deserialization_context),
        )

        id = input_dict["id"]
        name = input_dict["name"]
        description = input_dict["description"]

        search_configs: Optional[List[SearchConfig]] = None
        if "search_configs" in input_dict:
            search_configs = [
                autodeserialize_any_from_dict(config, deserialization_context)
                for config in input_dict["search_configs"]
            ]

        vector_configs: Optional[List[VectorConfig]] = None
        if "vector_configs" in input_dict:
            vector_configs = [
                autodeserialize_any_from_dict(config, deserialization_context)
                for config in input_dict["vector_configs"]
            ]

        return OracleDatabaseDatastore(
            schema, connection_config, id, name, description, search_configs, vector_configs
        )

    def _handle_vector_property_name_not_found(self, collection_name: str) -> str:
        raise ValueError(f"No Vector Property found for Table {collection_name}")

    def _search_backend(
        self,
        collection_name: str,
        query_embedding: List[float],
        k: int,
        metric: SimilarityMetric,
        where: Optional[Dict[str, Any]],
        columns_to_exclude: Optional[List[str]],
        vector_config: Optional[VectorConfig],
    ) -> List[Dict[str, Any]]:
        """
        Backend execution for Oracle vector search: instantiate database vector index and search.
        """

        vector_property = None

        if vector_config:
            vector_property = vector_config.vector_property

        if vector_property is None:
            vector_property = self._get_first_vector_property_name(collection_name)

        index = OracleDatabaseVectorIndex(
            self.engine, vector_property, table=self.data_tables[collection_name].sqlalchemy_table
        )
        results = index.search(query_embedding, k, metric, where, columns_to_exclude)

        return results

    def _find_vector_config_from_name(
        self, vector_config_name: Optional[str], collection_name: Optional[str] = None
    ) -> Optional[VectorConfig]:
        if vector_config_name in self._vector_config_map:
            vector_config = self._vector_config_map[vector_config_name]
            return vector_config
        return None

    def _handle_no_matching_vector_config(
        self, collection_name: str, retriever: VectorRetrieverConfig
    ) -> None:
        warnings.warn(
            f"No vector config found for collection {collection_name}. Inferring Vector Property from schema",
            UserWarning,
        )
        return None


def _execute_query_on_oracle_db(
    connection_config: OracleDatabaseConnectionConfig, query: str
) -> None:
    with connection_config.get_connection() as conn:
        conn.cursor().execute(query)
