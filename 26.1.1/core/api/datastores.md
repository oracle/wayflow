<a id="datastores"></a>

# Datastores

Datastores connect Agents and Flows to data modelled by entity definitions.
To see how you can use a datastore in a Flow or Agent, see [Datastore task steps](flows.md#datastoresteps).

## Entity

Entities define the data model of datastores.

<a id="id2"></a>

### *class* wayflowcore.datastore.Entity(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>, properties=<factory>)

An `Entity` defines the properties of an object in a collection
manipulated by a datastore.

Entities can be used to model relational entities, where their
properties are the columns of the tables, as well as any
other kind of entity. For example, a text file on OCI Object Storage
can be represented as an entity with properties file name and content.

* **Parameters:**
  * **name** (`str`) – 

    Optional name of the entities described by this object.

    #### NOTE
    In a datastore, the relevant name is the one provided as the
    dictionary key of the `schema` parameter for the corresponding
    `Entity`.
  * **description** (`str`) – 

    Optional description of the entity type.

    #### IMPORTANT
    It can be helpful to put a description in the following cases:
    * to help users know what this entity is about, and simplify the usage of a `Step` using it
    * to help a LLM if it needs to generate values for this entity (e.g. in `DatastoreCreateStep`)
    * to help an agent when tools are generated from the Datastore operations,
      to automatically provide a comprehensive docstring for that tool
  * **default_value** (`Any`) – Optional default value.
  * **properties** (`Dict`[`str`, [`Property`](flows.md#wayflowcore.property.Property)]) – 

    Mapping of property names and their types. Defaults to no properties.

    #### IMPORTANT
    If a property is not required (but doesn’t have a default value conforming to its type),
    use the `nullable` helper function to create a new property that can be set to None.
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

### Examples

```pycon
>>> from wayflowcore.datastore import Entity, nullable
>>> from wayflowcore.property import StringProperty, IntegerProperty
```

You can define an entity representing documents with metadata as follows:

```pycon
>>> documents = Entity(
...     description="Documents in object store, including category metadata",
...     properties={
...         "id": IntegerProperty(),
...         # By default, documents are created empty
...         "content": StringProperty(default_value=""),
...         # Category is empty by default
...         "category": nullable(StringProperty()),
...     }
... )
```

#### get_entity_defaults()

Construct a dictionary of default values for properties that
have them.

This method can be helpful to supplement default values in an
entity object. Note that datastores already provide this
functionality on creation of an object.

* **Returns:**
  A dictionary mapping each property name in the dictionary to its
  default value (if it has one, otherwise it will not be part of
  this dictionary)
* **Return type:**
  dict[str, Any]

<a id="nullable-helper-function"></a>

### *class* wayflowcore.datastore.nullable(property)

Makes a property nullable.

* **Parameters:**
  **property** ([*Property*](flows.md#wayflowcore.property.Property)) – Property that can be null. If a default value is set on this
  property the resulting nullable property will have the same
  default value. If no default value is set, the default of the
  resulting property is `None`.
* **Returns:**
  A new property descriptor that is equivalent to the original one,
  but that can also be `None`.
* **Return type:**
  [UnionProperty](flows.md#wayflowcore.property.UnionProperty)

## Base class

<a id="datastore"></a>

### *class* wayflowcore.datastore.Datastore

Store and perform basic manipulations on collections of entities
of various types.

Provides an interface for listing, creating, deleting and updating
collections. It also provides a way of describing the entities in
this datastore.

#### *abstract* create(collection_name, entities)

Create new entities of the specified type.

* **Parameters:**
  * **collection_name** (`str`) – Name of the collection to create the new entities in.
  * **entities** (`Union`[`Dict`[`str`, `Any`], `List`[`Dict`[`str`, `Any`]]]) – 

    One or more entities to create. Creating multiple entities
    at once may be beneficial for performance compared to
    executing multiple calls to create.

    #### IMPORTANT
    When bulk-creating entities, all entities must contain the same set of properties.
    For example, if the `Entity` “employees” has `properties` “name” (required) and
    “salary” (optional), either all entities to create define only the name, or all
    define both name and salary. Some entities defining the salary and others relying on
    its default value is not supported.)
* **Returns:**
  The newly created entities, including any defaults not provided
  in the original entity. If the input entities were multiples,
  they will be returned as a list. Otherwise, a single dictionary
  with the newly created entity will be returned.
* **Return type:**
  list[dict] or dict

#### *abstract* delete(collection_name, where)

Delete entities based on the specified criteria.

* **Parameters:**
  * **collection_name** (`str`) – Name of the collection in which entities will be deleted.
  * **where** (`Dict`[`str`, `Any`]) – Filter criteria for the entities to delete.
    The dictionary is composed of property name and value pairs
    to filter by with exact matches. Only entities matching all
    conditions in the dictionary will be deleted. For example,
    `{"name": "Fido", "breed": "Golden Retriever"}` will match
    all `Golden Retriever` dogs named `Fido`.
* **Return type:**
  `None`

#### *abstract* describe()

Get the descriptions of the schema associated with this
`Datastore`.

* **Returns:**
  The description of the schema for the `Datastore`.
* **Return type:**
  dict[str, [Entity](#wayflowcore.datastore.Entity)]

#### *abstract* list(collection_name, where=None, limit=None)

Retrieve a list of entities in a collection based on the
given criteria.

* **Parameters:**
  * **collection_name** (`str`) – Name of the collection to list.
  * **where** (`Optional`[`Dict`[`str`, `Any`]]) – Filter criteria for the collection to list.
    The dictionary is composed of property name and value pairs
    to filter by with exact matches. Only entities matching all
    conditions in the dictionary will be listed. For example,
    `{"name": "Fido", "breed": "Golden Retriever"}` will match
    all `Golden Retriever` dogs named `Fido`.
  * **limit** (`Optional`[`int`]) – Maximum number of entities to retrieve, by default `None`
    (retrieve all entities).
* **Returns:**
  A list of entities matching the specified criteria.
* **Return type:**
  list[dict]

#### *abstract* update(collection_name, where, update)

Update existing entities that match the provided conditions.

* **Parameters:**
  * **collection_name** (`str`) – Name of the collection to be updated.
  * **where** (`Dict`[`str`, `Any`]) – Filter criteria for the collection to update.
    The dictionary is composed of property name and value pairs
    to filter by with exact matches. Only entities matching all
    conditions in the dictionary will be updated. For example,
    `{"name": "Fido", "breed": "Golden Retriever"}` will match
    all `Golden Retriever` dogs named `Fido`.
  * **update** (`Dict`[`str`, `Any`]) – The update to apply to the matching entities in the collection.
* **Returns:**
  The updated entities, including any defaults or values not set in the update.
* **Return type:**
  list[dict]

## In memory

<a id="inmemorydatastore"></a>

### *class* wayflowcore.datastore.InMemoryDatastore(schema, id=None, name=None, description=None)

In-memory datastore for testing and development purposes.

This datastore implements basic functionalities of datastores, with
the following properties:

* All schema objects manipulated by the datastore must be fully defined
  using the `Entity` property. These entities are not persisted
  across instances of `InMemoryDatastore` or Python processes;
* The underlying data cannot be shared across instances of this `Datastore`.

#### IMPORTANT
This `Datastore` is meant only for testing and development
purposes. Switch to a production-grade datastore (e.g.,
`OracleDatabaseDatastore`) before deploying an assistant.

#### NOTE
When this `Datastore` is serialized, only its configuration
will be serialized, without any of the stored data.

Initialize an `InMemoryDatastore`.

* **Parameters:**
  * **schema** (`Dict`[`str`, [`Entity`](#wayflowcore.datastore.Entity)]) – Mapping of collection names to entity definitions used by this
    datastore.
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)

### Example

```pycon
>>> from wayflowcore.datastore import Entity
>>> from wayflowcore.datastore.inmemory import InMemoryDatastore
>>> from wayflowcore.property import StringProperty, IntegerProperty
```

You can define one or more entities for your datastore and initialize it

```pycon
>>> document = Entity(
...     properties={ "id": IntegerProperty(), "content": StringProperty(default_value="") }
... )
>>> datastore = InMemoryDatastore({"documents": document})
```

The `InMemoryDatastore` can create, list, update and delete entities.
Creation can happen for single entities as well as multiples:

```pycon
>>> datastore.create("documents", {"id": 1, "content": "The quick brown fox jumps over the lazy dog"})
{'content': 'The quick brown fox jumps over the lazy dog', 'id': 1}
>>> bulk_insert_docs = [
...     {"id": 2, "content": "The rat the cat the dog bit chased escaped."},
...     {"id": 3, "content": "More people have been to Russia than I have."}
... ]
>>> datastore.create("documents", bulk_insert_docs)
[{'content': 'The rat the cat the dog bit chased escaped.', 'id': 2}, {'content': 'More people have been to Russia than I have.', 'id': 3}]
```

Use `where` parameters to filter results when listing entities. When no matches are found, an empty list is returned
Note that if multiple properties are set in the `where` dictionary, all of the values must match:

```pycon
>>> datastore.list("documents", where={"id": 3})
[{'content': 'More people have been to Russia than I have.', 'id': 3}]
>>> datastore.list("documents", where={"id": 1, "content": "Not the content of document 1"})
[]
```

Use the limit parameter to reduce the size of the result set:

```pycon
>>> datastore.list("documents", limit=1)
[{'content': 'The quick brown fox jumps over the lazy dog', 'id': 1}]
```

The same where parameter can be used to determine which entities should be updated or deleted:

```pycon
>>> datastore.update("documents", where={"id": 1}, update={"content": "Will, will Will will Will Will's will?"})
[{'content': "Will, will Will will Will Will's will?", 'id': 1}]
>>> datastore.delete("documents", where={"id": 3})
```

<!-- We exclude these members because they are already included in the base class -->

## Relational Datastore

### *class* wayflowcore.datastore._relational.RelationalDatastore(schema, engine)

A relational data store that supports querying data using
SQL-like queries.

This class extends the Datastore class and adds support for querying
data using SQL-like queries.

Initialize a `RelationalDatastore`

* **Parameters:**
  * **schema** (`Dict`[`str`, [`Entity`](#wayflowcore.datastore.Entity)]) – Mapping of entity names to entities manipulated in this
    Datastore
  * **engine** (`Engine`) – SQLAlchemy engine used to connect to the relational database

#### create(collection_name, entities)

Create new entities of the specified type.

* **Parameters:**
  * **collection_name** (`str`) – Name of the collection to create the new entities in.
  * **entities** (`Union`[`Dict`[`str`, `Any`], `List`[`Dict`[`str`, `Any`]]]) – 

    One or more entities to create. Creating multiple entities
    at once may be beneficial for performance compared to
    executing multiple calls to create.

    #### IMPORTANT
    When bulk-creating entities, all entities must contain the same set of properties.
    For example, if the `Entity` “employees” has `properties` “name” (required) and
    “salary” (optional), either all entities to create define only the name, or all
    define both name and salary. Some entities defining the salary and others relying on
    its default value is not supported.)
* **Returns:**
  The newly created entities, including any defaults not provided
  in the original entity. If the input entities were multiples,
  they will be returned as a list. Otherwise, a single dictionary
  with the newly created entity will be returned.
* **Return type:**
  list[dict] or dict

#### delete(collection_name, where)

Delete entities based on the specified criteria.

* **Parameters:**
  * **collection_name** (`str`) – Name of the collection in which entities will be deleted.
  * **where** (`Dict`[`str`, `Any`]) – Filter criteria for the entities to delete.
    The dictionary is composed of property name and value pairs
    to filter by with exact matches. Only entities matching all
    conditions in the dictionary will be deleted. For example,
    `{"name": "Fido", "breed": "Golden Retriever"}` will match
    all `Golden Retriever` dogs named `Fido`.
* **Return type:**
  `None`

#### describe()

Get the descriptions of the schema associated with this
`Datastore`.

* **Returns:**
  The description of the schema for the `Datastore`.
* **Return type:**
  dict[str, [Entity](#wayflowcore.datastore.Entity)]

#### list(collection_name, where=None, limit=None)

Retrieve a list of entities in a collection based on the
given criteria.

* **Parameters:**
  * **collection_name** (`str`) – Name of the collection to list.
  * **where** (`Optional`[`Dict`[`str`, `Any`]]) – Filter criteria for the collection to list.
    The dictionary is composed of property name and value pairs
    to filter by with exact matches. Only entities matching all
    conditions in the dictionary will be listed. For example,
    `{"name": "Fido", "breed": "Golden Retriever"}` will match
    all `Golden Retriever` dogs named `Fido`.
  * **limit** (`Optional`[`int`]) – Maximum number of entities to retrieve, by default `None`
    (retrieve all entities).
* **Returns:**
  A list of entities matching the specified criteria.
* **Return type:**
  list[dict]

#### query(query, bind=None)

Execute a query against the stored data.

This method can be useful to join data or use advanced
filtering options not provided in `Datastore.list`.

* **Parameters:**
  * **query** (*str*) – The query to execute, possibly parametrized with bind variables.
    The syntax for bind variables is `:variable_name`, where
    `variable_name` must be a key in the `bind` parameter of this method
  * **bind** (*dict* *[**str* *,* *Any* *]*) – Bind variables for the query.
* **Return type:**
  `List`[`Dict`[`str`, `Any`]]
* **Returns:**
  * *The result of the query execution as a list of dictionaries*
  * *mapping column names in the select statement to their values.*
  *  *.. note::* – If the select clause contains something other than column names,
    the literal values written in the column name are used as keys
    of the dictionary, e.g.:
    ``sql
    SELECT COUNT(DISTINCT ID), MAX(salary) FROM employees
    ``
    will return a list with a single element, a dictionary with
    keys “COUNT(DISTINCT ID)” and “MAX(salary)”

#### update(collection_name, where, update)

Update existing entities that match the provided conditions.

* **Parameters:**
  * **collection_name** (`str`) – Name of the collection to be updated.
  * **where** (`Dict`[`str`, `Any`]) – Filter criteria for the collection to update.
    The dictionary is composed of property name and value pairs
    to filter by with exact matches. Only entities matching all
    conditions in the dictionary will be updated. For example,
    `{"name": "Fido", "breed": "Golden Retriever"}` will match
    all `Golden Retriever` dogs named `Fido`.
  * **update** (`Dict`[`str`, `Any`]) – The update to apply to the matching entities in the collection.
* **Returns:**
  The updated entities, including any defaults or values not set in the update.
* **Return type:**
  list[dict]

## Oracle Database

#### IMPORTANT
The Oracle Database Datastore requires additional optional dependencies, which can be installed
with the `[datastore]` installation option.

#### NOTE
By default (when using the OracleDatabaseConnectionConfig classes as-is), the python-oracledb
client will use a thin connection to the database. If you want to use a thick connection
(leveraging Oracle Instant Client), invoke oracledb.init_instant_client() before initializing
any connection to the database. More information about thick and thin connection can be found in the
[python-oracledb documentation](https://python-oracledb.readthedocs.io/en/latest/api_manual/module.html#oracledb.init_oracle_client).

<a id="oracledatabaseconnectionconfig"></a>

### *class* wayflowcore.datastore.OracleDatabaseConnectionConfig(\*, id=<factory>, \_\_metadata_info_\_=<factory>, name='', description=None)

Base class used for configuring connections to Oracle Database.

* **Parameters:**
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)

#### get_connection()

Create a connection object from the configuration

* **Returns:**
  A python-oracledb connection object
* **Return type:**
  Any

<a id="oracledatabasetlsconnectionconfig"></a>

### *class* wayflowcore.datastore.TlsOracleDatabaseConnectionConfig(user, password, dsn, config_dir=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>, name='', description=None)

TLS Connection Configuration to Oracle Database.

* **Parameters:**
  * **user** (`str`) – User used to connect to the database
  * **password** (`str`) – Password for the provided user
  * **dsn** (`str`) – Connection string for the database (e.g., created using oracledb.make_dsn)
  * **config_dir** (`Optional`[`str`]) – Configuration directory for the database connection. Set this if you are using an
    alias from your tnsnames.ora files as a DSN. Make sure that the specified DSN is
    appropriate for TLS connections (as the tnsnames.ora file in a downloaded wallet
    will only include DSN entries for mTLS connections).
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)

#### config_dir *: `Optional`[`str`]* *= None*

#### dsn *: `str`*

#### password *: `str`*

#### user *: `str`*

<a id="oracledatabasemtlsconnectionconfig"></a>

### *class* wayflowcore.datastore.MTlsOracleDatabaseConnectionConfig(config_dir, dsn, user, password, wallet_location, wallet_password, \*, id=<factory>, \_\_metadata_info_\_=<factory>, name='', description=None)

Mutual-TLS Connection Configuration to Oracle Database.

* **Parameters:**
  * **config_dir** (`str`) – TNS Admin directory
  * **dsn** (`str`) – connection string for the database, or entry in the tnsnames.ora file
  * **user** (`str`) – connection string for the database
  * **password** (`str`) – password for the provided user
  * **wallet_location** (`str`) – location where the Oracle Database wallet is stored
  * **wallet_password** (`str`) – password for the provided wallet
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)

#### config_dir *: `str`*

#### dsn *: `str`*

#### password *: `str`*

#### user *: `str`*

#### wallet_location *: `str`*

#### wallet_password *: `str`*

<a id="oracledatabasedatastore"></a>

### *class* wayflowcore.datastore.OracleDatabaseDatastore(schema, connection_config)

Datastore that uses Oracle Database as the storage mechanism.

#### IMPORTANT
This `Datastore` can only be used to connect to existing
database schemas, with tables of interest already defined in the
database.

Initialize an Oracle Database Datastore.

* **Parameters:**
  * **schema** (`Dict`[`str`, [`Entity`](#wayflowcore.datastore.Entity)]) – Mapping of collection names to entity definitions used by
    this datastore.
  * **connection_config** ([`OracleDatabaseConnectionConfig`](#wayflowcore.datastore.OracleDatabaseConnectionConfig)) – Configuration of connection parameters

#### query(query, bind=None)

Execute a query against the stored data.

This method can be useful to join data or use advanced
filtering options not provided in `Datastore.list`.

* **Parameters:**
  * **query** (*str*) – The query to execute, possibly parametrized with bind variables.
    The syntax for bind variables is `:variable_name`, where
    `variable_name` must be a key in the `bind` parameter of this method
  * **bind** (*dict* *[**str* *,* *Any* *]*) – Bind variables for the query.
* **Return type:**
  `List`[`Dict`[`str`, `Any`]]
* **Returns:**
  * *The result of the query execution as a list of dictionaries*
  * *mapping column names in the select statement to their values.*
  *  *.. note::* – If the select clause contains something other than column names,
    the literal values written in the column name are used as keys
    of the dictionary, e.g.:
    ``sql
    SELECT COUNT(DISTINCT ID), MAX(salary) FROM employees
    ``
    will return a list with a single element, a dictionary with
    keys “COUNT(DISTINCT ID)” and “MAX(salary)”

## Postgres Database

#### IMPORTANT
The Postgres Database Datastore requires additional optional dependencies, which can be installed
with the `[datastore]` installation option.

<a id="postgresdatabaseconnectionconfig"></a>

### *class* wayflowcore.datastore.PostgresDatabaseConnectionConfig(\*, id=<factory>, \_\_metadata_info_\_=<factory>, name='', description=None)

Abstract class for a PostgreSQL connection.

* **Parameters:**
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)

#### *abstract* get_connection()

* **Return type:**
  `Engine`

<a id="postgresdatabasetlsconnectionconfig"></a>

### *class* wayflowcore.datastore.TlsPostgresDatabaseConnectionConfig(\*, id=<factory>, \_\_metadata_info_\_=<factory>, name='', description=None, user, password, url='localhost:5432', sslmode='require', sslcert=None, sslkey=None, sslrootcert=None, sslcrl=None)

Configuration for a PostgreSQL connection with TLS/SSL support.

* **Parameters:**
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **user** (*str*)
  * **password** (*str*)
  * **url** (*str*)
  * **sslmode** (*Literal* *[* *'disable'* *,*  *'allow'* *,*  *'prefer'* *,*  *'require'* *,*  *'verify-ca'* *,*  *'verify-full'* *]*)
  * **sslcert** (*str* *|* *None*)
  * **sslkey** (*str* *|* *None*)
  * **sslrootcert** (*str* *|* *None*)
  * **sslcrl** (*str* *|* *None*)

#### get_connection()

* **Return type:**
  `Engine`

#### get_sqlalchemy_url()

Builds a SQLAlchemy connection URL.

* **Return type:**
  `str`

#### password *: `str`*

Password of the postgres database

#### sslcert *: `Optional`[`str`]* *= None*

Path of the client SSL certificate, replacing the default ~/.postgresql/postgresql.crt.
Ignored if an SSL connection is not made.

#### sslcrl *: `Optional`[`str`]* *= None*

Path of the SSL server certificate revocation list (CRL). Certificates listed will be rejected
while attempting to authenticate the server’s certificate.

#### sslkey *: `Optional`[`str`]* *= None*

Path of the file containing the secret key used for the client certificate, replacing the default
~/.postgresql/postgresql.key. Ignored if an SSL connection is not made.

#### sslmode *: `Literal`[`'disable'`, `'allow'`, `'prefer'`, `'require'`, `'verify-ca'`, `'verify-full'`]* *= 'require'*

SSL mode for the PostgreSQL connection.

#### sslrootcert *: `Optional`[`str`]* *= None*

Path of the file containing SSL certificate authority (CA) certificate(s). Used to verify server identity.

#### url *: `str`* *= 'localhost:5432'*

URL to access the postgres database

#### user *: `str`*

User of the postgres database

<a id="postgresdatabasedatastore"></a>

### *class* wayflowcore.datastore.PostgresDatabaseDatastore(schema, connection_config)

Datastore that uses Postgres Database as the storage mechanism.

#### IMPORTANT
This `Datastore` can only be used to connect to existing
database schemas, with tables of interest already defined in the
database.

Initialize an Postgres Database Datastore.

* **Parameters:**
  * **schema** (`Dict`[`str`, [`Entity`](#wayflowcore.datastore.Entity)]) – Mapping of collection names to entity definitions used by
    this datastore.
  * **connection_config** ([`PostgresDatabaseConnectionConfig`](#wayflowcore.datastore.PostgresDatabaseConnectionConfig)) – Configuration of connection parameters

#### query(query, bind=None)

Execute a query against the stored data.

This method can be useful to join data or use advanced
filtering options not provided in `Datastore.list`.

* **Parameters:**
  * **query** (*str*) – The query to execute, possibly parametrized with bind variables.
    The syntax for bind variables is `:variable_name`, where
    `variable_name` must be a key in the `bind` parameter of this method
  * **bind** (*dict* *[**str* *,* *Any* *]*) – Bind variables for the query.
* **Return type:**
  `List`[`Dict`[`str`, `Any`]]
* **Returns:**
  * *The result of the query execution as a list of dictionaries*
  * *mapping column names in the select statement to their values.*
  *  *.. note::* – If the select clause contains something other than column names,
    the literal values written in the column name are used as keys
    of the dictionary, e.g.:
    ``sql
    SELECT COUNT(DISTINCT ID), MAX(salary) FROM employees
    ``
    will return a list with a single element, a dictionary with
    keys “COUNT(DISTINCT ID)” and “MAX(salary)”
