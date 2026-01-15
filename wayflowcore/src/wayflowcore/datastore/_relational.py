# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import warnings
from abc import ABC
from logging import getLogger
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    overload,
)

from wayflowcore._metadata import MetadataType

from wayflowcore._utils.lazy_loader import LazyLoader
from wayflowcore.component import Component
from wayflowcore.datastore._datatable import Datatable
from wayflowcore.datastore._utils import check_collection_name
from wayflowcore.datastore.datastore import Datastore
from wayflowcore.datastore.entity import Entity, EntityAsDictT
from wayflowcore.exceptions import (
    DatastoreConstraintViolationError,
    DatastoreEntityError,
    DatastoreError,
    DatastoreTypeError,
)
from wayflowcore.property import (
    BooleanProperty,
    FloatProperty,
    IntegerProperty,
    NullProperty,
    Property,
    StringProperty,
    UnionProperty,
    VectorProperty,
)
from wayflowcore.search import SearchConfig, VectorConfig

if TYPE_CHECKING:
    # Important: do not move these imports out of the TYPE_CHECKING
    # block so long as sqlalchemy is an optional dependency.
    # Otherwise, importing the module when it is not installed would lead to an import error.
    import sqlalchemy

    SqlachemyStatementT = TypeVar(
        "SqlachemyStatementT", sqlalchemy.Select[Any], sqlalchemy.Update, sqlalchemy.Delete
    )
else:
    sqlalchemy = LazyLoader("sqlalchemy")

logger = getLogger(__name__)


def get_nullable_sub_property(property_: UnionProperty) -> Property:
    """Extract the actual property wrapped by the ``nullable`` helper
    function.

    Parameters
    ----------
    property_ : UnionProperty
        Nullable property, e.g., created by the ``nullable`` helper
        function

    Returns
    -------
    Property
        The property wrapped in the union property to create a nullable
        property

    Raises
    ------
    DataStoreTypeError
        If the input ``UnionProperty`` is not a valid nullable
    """
    has_two_anyof, first_is_null, second_is_null = False, False, False
    has_two_anyof = len(property_.any_of) == 2
    if has_two_anyof:
        first_is_null = isinstance(property_.any_of[0], NullProperty)
        second_is_null = isinstance(property_.any_of[1], NullProperty)
    if not (has_two_anyof and (first_is_null ^ second_is_null)):
        raise DatastoreTypeError(
            f"Property {property_.name} is not valid. Union types should only be unions of "
            "NullProperty and another type of property. Use the `nullable` helper to achieve this."
        )

    the_actual_sub_property = int(first_is_null)  # or int(not second_is_null)
    return property_.any_of[the_actual_sub_property]


def to_sqlalchemy_type(property_: Property) -> Any:
    """Convert a property to its SQLAlchemy equivalent.

    Parameters
    ----------
    property_ : Property
        Property to be converted. Note that it will only work on
        individual property types, without taking into account possible
        inheritance

    Returns
    -------
    The SQLAlchemy object representing the type

    Raises
    ------
    DataStoreTypeError
        If the input property type is not one of the supported types for this conversion
    """
    from sqlalchemy.dialects import oracle

    if isinstance(property_, UnionProperty):
        property_ = get_nullable_sub_property(property_)
    type_map = {
        FloatProperty: sqlalchemy.Numeric,
        IntegerProperty: sqlalchemy.Integer,
        StringProperty: (sqlalchemy.Text, sqlalchemy.String),
        BooleanProperty: sqlalchemy.Boolean,
        VectorProperty: oracle.vector.VECTOR,
    }
    wayflowcore_type = type(property_)
    if wayflowcore_type not in type_map:
        raise DatastoreTypeError(
            f"{wayflowcore_type} is not supported as a column type for the Datastore. "
            f"Supported property types are {list(type_map.keys())}"
        )
    return type_map[wayflowcore_type]


def _case_insensitive(identifier: str) -> str:
    return identifier.lower()


def _case_insensitive_entity_dict(entity_as_dict: EntityAsDictT) -> EntityAsDictT:
    return {_case_insensitive(identifier): value for identifier, value in entity_as_dict.items()}


def _results_to_dict(results: Sequence["sqlalchemy.Row[Any]"]) -> List[Dict[str, Any]]:
    # NOTE: This is not a protected attribute, but rather a poor naming convention
    # in sqlalchemy (should be mapping_). From the docs:
    # > all `Row` methods and library-level attributes are intended to be underscored to
    # > avoid name conflicts
    # NOTE 2: we need to cast the keys to str to ensure these are JSON-serializable
    return [{str(k): v for k, v in dict(result._mapping).items()} for result in results]


class _RelationalDatatable(Datatable):
    """Class to manage access to an *existing* database table."""

    def __init__(
        self,
        entity_description: Entity,
        sqlalchemy_table: "sqlalchemy.Table",
        engine: "sqlalchemy.Engine",
    ):
        """
        Initializes the ``DatabaseDatatable``.

        Parameters
        ----------
        entity_description:
            Entity description associated with the database table.
        sqlalchemy_table:
            SQLAlchemy representation of the table
        engine:
            SQLAlchemy engine to use for database connections.
        """
        self.entity_description = entity_description
        self._defined_property_names = set([p for p in self.entity_description.properties])
        self.engine = engine
        self.sqlalchemy_table = sqlalchemy_table
        self._sqlalchemy_columns_in_entity = [
            column
            for column in self.sqlalchemy_table.c
            if column.name in self._defined_property_names
        ]
        super().__init__()

    def _check_all_columns_in_entity(self, where: Dict[str, Any]) -> None:
        filtered_properties = set(where.keys())
        if not (filtered_properties <= self._defined_property_names):
            raise DatastoreTypeError(
                f"Requested to filter on properties {filtered_properties}, but entity "
                f"{self.entity_description.name} only contains {self._defined_property_names}. "
                "This may be a mistake in the definition of the where clause or the entity, but it "
                "may also be an intentional omission, to prevent the assistant from accessing some "
                "of the entity's properties."
            )

    def _apply_where_clause(
        self, query: "SqlachemyStatementT", where: Optional[Dict[str, Any]]
    ) -> "SqlachemyStatementT":
        if where is not None:
            self._check_all_columns_in_entity(where)
            where = _case_insensitive_entity_dict(where)
            for column, value in where.items():
                query = query.where(self.sqlalchemy_table.c[column] == value)
        return query

    def _get_columns_with_case_sensitive_aliases(self) -> List["sqlalchemy.Label[Any]"]:
        columns = []
        for property_ in self.entity_description.properties:
            case_insensitive_property_name = _case_insensitive(property_)
            column = self.sqlalchemy_table.columns[case_insensitive_property_name]
            column_with_alias = column.label(sqlalchemy.quoted_name(property_, quote=True))
            columns.append(column_with_alias)
        return columns

    def _get_columns_with_case_sensitive_aliases_without_vectors(
        self,
    ) -> List["sqlalchemy.Label[Any]"]:
        columns = []
        for property_, property_type in self.entity_description.properties.items():
            if isinstance(property_type, VectorProperty):  # Do not return Vectors
                continue
            case_insensitive_property_name = _case_insensitive(property_)
            column = self.sqlalchemy_table.columns[case_insensitive_property_name]
            column_with_alias = column.label(sqlalchemy.quoted_name(property_, quote=True))
            columns.append(column_with_alias)
        return columns

    def list(
        self, where: Optional[Dict[str, Any]] = None, limit: Optional[int] = None
    ) -> List[EntityAsDictT]:
        query = sqlalchemy.select(*self._get_columns_with_case_sensitive_aliases())
        query = self._apply_where_clause(query, where).limit(limit=limit)
        with self.engine.connect() as conn:
            results = conn.execute(query).fetchall()
            return _results_to_dict(results)

    @overload
    def create(self, entities: EntityAsDictT) -> EntityAsDictT: ...

    @overload
    def create(self, entities: List[EntityAsDictT]) -> List[EntityAsDictT]: ...

    def create(
        self, entities: Union[EntityAsDictT, List[EntityAsDictT]]
    ) -> Union[EntityAsDictT, List[EntityAsDictT]]:
        """
        Adds new rows to the Database table
        It also returns the added rows without including any VectorProperty columns in the returned values.
        """
        return_single_element = False
        if not isinstance(entities, list):
            entities = [entities]
            return_single_element = True

        with self.engine.connect() as connection:
            try:
                result = connection.execute(
                    *self._create_query(entities),
                ).fetchall()
                if len(result) == 0:
                    raise DatastoreEntityError("Failed to create entity")
            except sqlalchemy.exc.IntegrityError as e:
                raise DatastoreConstraintViolationError(
                    "Entity violates integrity constraint"
                ) from e
            except sqlalchemy.exc.StatementError as e:
                raise DatastoreEntityError(str(e)) from e
            except sqlalchemy.exc.CompileError as e:
                if str(e).startswith("Unconsumed column names:"):
                    invalid_field = str(e).split(": ")[-1]
                    raise DatastoreEntityError(
                        f"Invalid field: {invalid_field} not in data representation"
                    ) from e
                raise

            connection.commit()
            result_as_dict = _results_to_dict(result)
        return result_as_dict[0] if return_single_element else result_as_dict

    def _create_query(
        self, entities: List[EntityAsDictT]
    ) -> Tuple["sqlalchemy.Executable", List[Dict[str, Any]]]:
        entities = [_case_insensitive_entity_dict(entity) for entity in entities]

        return (
            self.sqlalchemy_table.insert().returning(
                *self._get_columns_with_case_sensitive_aliases_without_vectors()
            ),
            entities,
        )

    def _update_query(self, where: Dict[str, Any], update: EntityAsDictT) -> "sqlalchemy.Update":
        """
        Update a Database table and corresponding Database table based on entities.
        It also returns the updated rows without inlcuding any VectorProperty columns in the returned values.
        """
        query = sqlalchemy.update(self.sqlalchemy_table)
        query = self._apply_where_clause(query, where)
        return query.values(**_case_insensitive_entity_dict(update)).returning(
            *self._get_columns_with_case_sensitive_aliases_without_vectors()
        )

    def update(self, where: Dict[str, Any], update: EntityAsDictT) -> List[EntityAsDictT]:
        query = self._update_query(where, update)
        with self.engine.connect() as connection:
            try:
                result = connection.execute(query).fetchall()
            except sqlalchemy.exc.IntegrityError as e:
                raise DatastoreConstraintViolationError(
                    "Update violates integrity constraint"
                ) from e
            except sqlalchemy.exc.StatementError as e:
                raise DatastoreEntityError(str(e)) from e
            except sqlalchemy.exc.CompileError as e:
                if str(e).startswith("Unconsumed column names:"):
                    invalid_field = str(e).split(": ")[-1]
                    raise DatastoreEntityError(
                        f"Invalid field: {invalid_field} not in data representation"
                    ) from e
                raise
            if len(result) == 0:
                logger.warning("Update operation with filter %s did not change any rows", where)
            else:
                logger.info("Updated %i entities", len(result))
            connection.commit()
            # NOTE: This is not a protected attribute, but rather a poor naming convention
            # in sqlalchemy (should be mapping_). From the docs:
            # > all `Row` methods and library-level attributes are intended to be underscored to
            # > avoid name conflicts
            result_as_dict = _results_to_dict(result)
        return result_as_dict

    def delete(self, where: Dict[str, Any]) -> None:
        query = sqlalchemy.delete(self.sqlalchemy_table)
        query = self._apply_where_clause(query, where)
        with self.engine.connect() as connection:
            result = connection.execute(query)
            if result.rowcount == 0:
                logger.warning("Delete operation with filter %s did not delete any rows", where)
            else:
                logger.info("Deleted %i entities", result.rowcount)
            connection.commit()


class RelationalDatastore(Datastore, ABC):
    """A relational data store that supports querying data using
    SQL-like queries.

    This class extends the Datastore class and adds support for querying
    data using SQL-like queries.
    """

    def __init__(
        self,
        schema: Dict[str, Entity],
        engine: "sqlalchemy.Engine",
        search_configs: Optional[List["SearchConfig"]] = None,
        vector_configs: Optional[List["VectorConfig"]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        id: Optional[str] = None,
        __metadata_info__: Optional["MetadataType"] = None,
    ):
        """Initialize a ``RelationalDatastore``

        Parameters
        ----------
        schema :
            Mapping of entity names to entities manipulated in this
            Datastore
        engine :
            SQLAlchemy engine used to connect to the relational database
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
        self.engine = engine
        self.schema = schema
        normalized_entity_names = {
            _case_insensitive(entity_name): entity_name for entity_name in self.schema
        }
        if len(normalized_entity_names) != len(self.schema):
            raise DatastoreError(
                "Schema contains duplicate names after normalization of identifiers. "
                "These are indistinguishable at the database level and should be disambiguated."
            )
        self.data_tables = self._create_data_tables_from_entities()
        super().__init__(
            schema=schema,
            search_configs=search_configs,
            vector_configs=vector_configs,
            id=id,
            name=name,
            description=description,
        )

    def _create_data_tables_from_entities(self) -> Dict[str, _RelationalDatatable]:
        metadata = sqlalchemy.MetaData()

        # SQLAlchemy does not support some features of Oracle DB (e.g., JSON columns)
        # However, since the user might not care about the specific JSON columns when creating the
        # datastores, we first filter out the warnings, and then handle each column in the datastore
        # schema individually below
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter(action="always", category=sqlalchemy.exc.SAWarning)

            # We only reflect tables explicitly specified in the datastore schema to avoid issues
            # with un-supported column types (see above) on tables the user doesn't care about,
            # and any concurrent operations (like drop tables) happening on other schema elements
            metadata.reflect(
                bind=self.engine, only=[_case_insensitive(table_name) for table_name in self.schema]
            )
            for warning in w or []:
                logger.warning("Suppressed warning during database inspection: %s", warning.message)

        tables_by_case_insensitive = {
            _case_insensitive(tbl_name): tbl for tbl_name, tbl in metadata.tables.items()
        }

        data_tables: Dict[str, _RelationalDatatable] = {}

        for entity_name, entity in self.schema.items():
            lookup_table_name = _case_insensitive(entity_name)
            tbl = tables_by_case_insensitive.get(lookup_table_name)
            if tbl is None:
                raise DatastoreTypeError(
                    f"Entity {entity_name} does not exist in the relational datastore."
                )

            cols_by_case_insensitive = {_case_insensitive(col.name): col for col in tbl.columns}

            for property_name, prop in entity.properties.items():
                lookup_col_name = _case_insensitive(property_name)
                col = cols_by_case_insensitive.get(lookup_col_name)
                if col is None:
                    raise DatastoreTypeError(
                        f"Property {property_name} for entity {entity_name} does not exist in the datastore"
                    )
                self._validate_property_against_table(prop, col)

            data_tables[entity_name] = _RelationalDatatable(entity, tbl, self.engine)

        return data_tables

    def _validate_property_against_table(
        self, property_: Property, sqlalchemy_column: "sqlalchemy.Column[Any]"
    ) -> None:
        sqlachemy_type = to_sqlalchemy_type(property_)
        if not isinstance(sqlalchemy_column.type, sqlachemy_type):
            raise DatastoreTypeError(
                "Mismatching types found in property definition and database. "
                f"Got {property_}, found {sqlalchemy_column.type} in database."
            )

    def list(
        self,
        collection_name: str,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[EntityAsDictT]:
        check_collection_name(self.schema, collection_name)
        return self.data_tables[collection_name].list(where, limit)

    @overload
    def create(self, collection_name: str, entities: EntityAsDictT) -> EntityAsDictT: ...

    @overload
    def create(
        self, collection_name: str, entities: List[EntityAsDictT]
    ) -> List[EntityAsDictT]: ...

    def create(
        self, collection_name: str, entities: Union[EntityAsDictT, List[EntityAsDictT]]
    ) -> Union[EntityAsDictT, List[EntityAsDictT]]:
        check_collection_name(self.schema, collection_name)
        return self.data_tables[collection_name].create(entities)

    def update(
        self, collection_name: str, where: Dict[str, Any], update: EntityAsDictT
    ) -> List[EntityAsDictT]:
        check_collection_name(self.schema, collection_name)
        return self.data_tables[collection_name].update(where, update)

    def delete(self, collection_name: str, where: Dict[str, Any]) -> None:
        check_collection_name(self.schema, collection_name)
        return self.data_tables[collection_name].delete(where)

    def describe(self) -> Dict[str, Entity]:
        return self.schema

    def query(self, query: str, bind: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a query against the stored data.

        This method can be useful to join data or use advanced
        filtering options not provided in ``Datastore.list``.

        Parameters
        ----------
        query : str
            The query to execute, possibly parametrized with bind variables.
            The syntax for bind variables is ``:variable_name``, where
            ``variable_name`` must be a key in the ``bind`` parameter of this method
        bind : dict[str, Any]
            Bind variables for the query.

        Returns
        -------
        The result of the query execution as a list of dictionaries
        mapping column names in the select statement to their values.

        .. note::
            If the select clause contains something other than column names,
            the literal values written in the column name are used as keys
            of the dictionary, e.g.:
            ```sql
            SELECT COUNT(DISTINCT ID), MAX(salary) FROM employees
            ```
            will return a list with a single element, a dictionary with
            keys `"COUNT(DISTINCT ID)"` and `"MAX(salary)"`
        """
        with self.engine.connect() as connection:
            try:
                cursor = connection.execute(sqlalchemy.text(query), bind)
            except sqlalchemy.exc.DatabaseError as e:
                raise DatastoreError(
                    "SQL query execution failed. See stacktrace to find out more "
                    "(note: bind variables should be provided with the :varname syntax)"
                ) from e
            return _results_to_dict(cursor.fetchall())
