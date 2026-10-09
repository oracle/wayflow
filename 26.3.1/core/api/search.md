<a id="search-api"></a>

# Search

This section documents the APIs for the core Search, Vector, and related configuration/data classes.

## Search Configuration

<a id="search-config"></a>

### *class* wayflowcore.search.config.SearchConfig(retriever, name=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Configuration for a search pipeline.

A search pipeline defines how to retrieve and process entities for search.

* **Parameters:**
  * **retriever** ([`VectorRetrieverConfig`](#wayflowcore.search.config.VectorRetrieverConfig)) – Retriever configuration for the search pipeline.
  * **name** (`Optional`[`str`]) – Name of the search pipeline.
    If None, a name is inferred and assigned during instantiating a `Datastore`.
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### name *: `Optional`[`str`]* *= None*

#### retriever *: [`VectorRetrieverConfig`](#wayflowcore.search.config.VectorRetrieverConfig)*

<a id="vector-config"></a>

### *class* wayflowcore.search.config.VectorConfig(model=None, collection_name=None, vector_property=None, serializer=None, name=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Configuration for how to generate and store embeddings/vectors for a collection of entities in a `Datastore`.

* **Parameters:**
  * **model** (`Optional`[[`EmbeddingModel`](embeddingmodels.md#wayflowcore.embeddingmodels.embeddingmodel.EmbeddingModel)]) – Embedding model to use for encoding queries.
    If there is no embedding model given, then the embedding model needs to be given in `VectorRetrieverConfig`.
  * **collection_name** (`Optional`[`str`]) – Name of the collection for which the VectorConfig belongs to.
    If no collection_name is given, the VectorConfig is usable for any collection.
  * **vector_property** (`Optional`[`str`]) – The document field/property name where generated vectors are stored.
    If None, the vector column will be inferred during search.
  * **serializer** (`Optional`[[`SerializerConfig`](#wayflowcore.search.config.SerializerConfig)]) – Serializer to concatenate or preprocess text before embedding, by default None.
    If None, a default Serializer will be used depending on the `VectorGenerator` class.
    It will be ignored if used for OracleDatabaseDatastore,
    because embeddings can only be generated for InMemoryDatastore.
  * **name** (`Optional`[`str`]) – Identifier for this vector configuration. If None, a name is inferred during instantiating a `Datastore`.
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### collection_name *: `Optional`[`str`]* *= None*

#### model *: `Optional`[[`EmbeddingModel`](embeddingmodels.md#wayflowcore.embeddingmodels.embeddingmodel.EmbeddingModel)]* *= None*

#### name *: `Optional`[`str`]* *= None*

#### serializer *: `Optional`[SerializerConfig]* *= None*

#### vector_property *: `Optional`[`str`]* *= None*

<a id="retriever-config"></a>

### *class* wayflowcore.search.config.RetrieverConfig

Base configuration for search retrievers.

Defines the interface for retriever configurations that can be used
in search pipelines.

#### *abstract* get_index_config()

Get configuration parameters for the index.

* **Returns:**
  Configuration parameters for the index.
* **Return type:**
  dict[str, Any]

<a id="vector-retriever-config"></a>

### *class* wayflowcore.search.config.VectorRetrieverConfig(vectors=None, model=None, collection_name=None, distance_metric=SimilarityMetric.COSINE, index_params=<factory>, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Configuration for vector-based retrievers.

Uses semantic embeddings to find similar entities.

* **Parameters:**
  * **vectors** (`Union`[`str`, [`VectorConfig`](#wayflowcore.search.config.VectorConfig), `None`]) – Name of the vector config present in the datastore or the VectorConfig itself to use, by default None.
    If None, the vector column will be inferred during search.
  * **model** (`Optional`[[`EmbeddingModel`](embeddingmodels.md#wayflowcore.embeddingmodels.embeddingmodel.EmbeddingModel)]) – Embedding model to use for encoding queries. By default, it uses the embedding model from VectorConfig.
    If there is no embedding model given in the VectorConfig, then the embedding model needs to be given.
  * **collection_name** (`Optional`[`str`]) – Name of the collection to retrieve from. If None, applies to all collections.
  * **distance_metric** ([`SimilarityMetric`](#wayflowcore.search.metrics.SimilarityMetric)) – 

    Distance metric to use, by default cosine_distance (SimilarityMetric.COSINE).

    Metrics currently supported:
    : - l2_distance (SimilarityMetric.EUCLIDEAN)
      - cosine_distance (SimilarityMetric.COSINE)
      - inner_product (SimilarityMetric.DOT)
  * **\*\*index_params** (`Dict`[`str`, `Any`]) – Additional parameters for the index configuration.
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### collection_name *: `Optional`[`str`]* *= None*

#### distance_metric *: [`SimilarityMetric`](#wayflowcore.search.metrics.SimilarityMetric)* *= 'cosine_distance'*

#### get_index_config()

Get configuration parameters for the vector index.

* **Returns:**
  Configuration parameters for the vector index.
* **Return type:**
  dict[str, Any]

#### index_params *: `Dict`[`str`, `Any`]*

#### model *: `Optional`[[`EmbeddingModel`](embeddingmodels.md#wayflowcore.embeddingmodels.embeddingmodel.EmbeddingModel)]* *= None*

#### vectors *: `Union`[`str`, VectorConfig, `None`]* *= None*

<a id="serializer-config"></a>

### *class* wayflowcore.search.config.SerializerConfig

Base configuration for serializing entity properties into a single string.

Use this for generating input text for embedding models or
any string-based search/pruning steps.

#### *abstract* serialize(entity)

Serialize entity to string by concatenating property values. Must be implemented by subclasses

* **Parameters:**
  **entity** (`Dict`[`str`, `Any`]) – Entity to serialize.
* **Returns:**
  Serialized string representation.
* **Return type:**
  str

<a id="concat-serializer-config"></a>

### *class* wayflowcore.search.config.ConcatSerializerConfig(separator='\\\\n', pre_processors=None, post_processors=None, include_property_names=True, skip_hidden_properties=True, property_name_format='{key}: {value}', columns_to_exclude=None)

Serializer that concatenates property values with optional pre- and post-processing steps.

* **Parameters:**
  * **separator** (*str*) – String used to separate concatenated property values. Default is ‘n’.
  * **pre_processors** (*Optional* *[**List* *[**Callable* *[* *[**str* *]* *,* *str* *]* *]* *]*) – List of callables to apply sequentially to each property value before formatting. Default is None.
  * **post_processors** (*Optional* *[**List* *[**Callable* *[* *[**str* *]* *,* *str* *]* *]* *]*) – List of callables to apply sequentially to the entire result after concatenation. Default is None.
  * **include_property_names** (*bool*) – Whether to include property names in the formatted output. Default is True.
  * **skip_hidden_properties** (*bool*) – If True, skip properties whose names begin with an underscore. Default is True.
  * **property_name_format** (*str*) – String format applied when including property names, with placeholders for property key and value. Default is ‘{key}: {value}’.
  * **columns_to_exclude** (*List* *[**str* *]*) – Columns to exclude while performing serialization. Default is None.

#### columns_to_exclude *: `Optional`[`List`[`str`]]* *= None*

#### include_property_names *: `bool`* *= True*

#### post_processors *: `Optional`[`List`[`Callable`[[`str`], `str`]]]* *= None*

#### pre_processors *: `Optional`[`List`[`Callable`[[`str`], `str`]]]* *= None*

#### property_name_format *: `str`* *= '{key}: {value}'*

#### separator *: `str`* *= '\\n'*

#### serialize(entity)

Serialize entity to string by concatenating property values.

* **Parameters:**
  **entity** (`Dict`[`str`, `Any`]) – Entity to serialize.
* **Returns:**
  Serialized string representation.
* **Return type:**
  str

#### skip_hidden_properties *: `bool`* *= True*

## Similarity Metrics

<a id="similarity-metric"></a>

### *class* wayflowcore.search.metrics.SimilarityMetric(value)

Enumeration of similarity metrics.

COSINE: Cosine similarity
EUCLIDEAN: Euclidean distance
DOT: Dot product similarity

#### COSINE *= 'cosine_distance'*

#### DOT *= 'inner_product'*

#### EUCLIDEAN *= 'l2_distance'*

## Search Toolbox

<a id="search-tool-box"></a>

### *class* wayflowcore.search.toolbox.SearchToolBox(datastore, collection_names=None, search_configs=None, k=3, requires_confirmation=None, id=None, name=None, description=None, \_\_metadata_info_\_=None)

ToolBox implementation for In-Memory and Oracle Database Datastore search tools.

All generated search tools are named with the prefix “[search]()” followed by the collection
name and the search config name if given (for example, “search_users_config2”).

Initialize with datastore reference and search parameters.

* **Parameters:**
  * **datastore** ([`Datastore`](datastores.md#wayflowcore.datastore.Datastore)) – The datastore instance to create search tools from.
  * **collection_names** (`Optional`[`List`[`str`]]) – Which collection names to expose tools for; None => all.
  * **search_configs** (`Optional`[`List`[`str`]]) – Search Configs to make tools for.
    If a search config is linked to a collection name, that search config will be used for the collection.
    If two search configs are given for a collection name, both of them are made into tools.
    If a search config is not linked to any collection, all collections in `collection_names` get this search config.
    If no search config is given for a collection, a default search configuration is inferred for that collection.
  * **k** (`int`) – Number of results to return for search tools.
  * **requires_confirmation** (`Optional`[`bool`]) – Flag to ask for user confirmation whenever executing any of this toolbox’s tools, yields `ToolExecutionConfirmationStatus` if True or if the `Tool` from the `ToolBox` requires confirmation.
  * **id** (*str*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

## Vector Generator

<a id="id1"></a>

### *class* wayflowcore.search.vectorgenerator.VectorGenerator

Abstract base class for generating embeddings from entities.

#### *abstract* generate_vectors(entities)

Generate vectors for a list of entities.

* **Parameters:**
  **entities** (`List`[`Dict`[`str`, `Any`]]) – List of entities to generate vectors for.
* **Returns:**
  List of vectors, one per entity.
* **Return type:**
  List[List[float]]

<a id="simple-vector-generator"></a>

### *class* wayflowcore.search.vectorgenerator.SimpleVectorGenerator(vector_config, embedding_model)

Vector generator for simple vector generation.
No chunking is supported with this one.

Initialize the vector generator.

* **Parameters:**
  * **vector_config** ([`VectorConfig`](#wayflowcore.search.config.VectorConfig)) – Configuration for vector generation.
  * **embedding_model** ([`EmbeddingModel`](embeddingmodels.md#wayflowcore.embeddingmodels.embeddingmodel.EmbeddingModel)) – Model to use for generating embeddings.

#### generate_vectors(entities)

Generate vectors for a list of entities.

* **Parameters:**
  **entities** (`List`[`Dict`[`str`, `Any`]]) – List of entities to generate vectors for.
* **Returns:**
  List of vectors, one per entity.
* **Return type:**
  List[List[float]]

## Vector Indexes

<a id="vector-index"></a>

### *class* wayflowcore.search.vectorindex.VectorIndex

Abstract base class for vector indices.

#### *abstract* search(query_vector, k, metric=SimilarityMetric.COSINE, where=None, columns_to_exclude=None)

Search for k nearest neighbors with additional filtering and exclusion options.

* **Return type:**
  `List`[`Dict`[`str`, `Any`]]
* **Parameters:**
  * **query_vector** (*List* *[**float* *]*)
  * **k** (*int*)
  * **metric** ([*SimilarityMetric*](#wayflowcore.search.metrics.SimilarityMetric))
  * **where** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **columns_to_exclude** (*List* *[**str* *]*  *|* *None*)

<a id="oracle-vector-index"></a>

### *class* wayflowcore.search.vectorindex.OracleDatabaseVectorIndex(engine, vector_property, table)

Base class for OracleDB vector indices. Acts as an interface between the Vector Index on OracleDB and Wayflow

Initialize the object for the vector index built in Oracle Database.

* **Parameters:**
  * **engine** (`Engine`) – SQLAlchemy Engine to use for connection.
  * **vector_property** (`str`) – The column name for which the Vector Index is configured.
  * **table** (`Table`) – Database table object for the table / collection present in Oracle Database

#### search(query_vector, k, metric=SimilarityMetric.COSINE, where=None, columns_to_exclude=None)

Search for k nearest neighbors using approximate search in Oracle Database Vector Index.
This method works even if there is no Vector Index configured in the Oracle Database.
It is recommended to configure an Index on Oracle Database for faster and cheaper approximate search.

* **Parameters:**
  * **query_vector** (`List`[`float`]) – Query vector.
  * **k** (`int`) – Number of results to return.
  * **metric** ([`SimilarityMetric`](#wayflowcore.search.metrics.SimilarityMetric)) – 

    Distance metric to use to get neighbours.
    It is recommended to use the same distance metric as the one used for configuring the Vector Index
    in Oracle Database. If there is a mismatch, it will be ignored by the Oracle Database.

    Metrics currently supported:
    : - l2_distance (SimilarityMetric.EUCLIDEAN)
      - cosine_distance (SimilarityMetric.COSINE)
      - inner_product (SimilarityMetric.DOT)
  * **where** (`Optional`[`Dict`[`str`, `Any`]]) – Filter out results by specific row/column entries.
  * **columns_to_exclude** (`Optional`[`List`[`str`]]) – Columns to exclude while returning the final results.
* **Returns:**
  List of matching items.
* **Return type:**
  list of dict

<a id="inmemory-vector-index"></a>

### *class* wayflowcore.search.vectorindex.BaseInMemoryVectorIndex(dimension, metric=SimilarityMetric.COSINE)

Base class for in-memory vector indices with common functionality.

Initialize the vector index.

* **Parameters:**
  * **dimension** (`int`) – Dimension of the vectors.
  * **metric** ([`SimilarityMetric`](#wayflowcore.search.metrics.SimilarityMetric)) – Distance metric to use (SimilarityMetric.COSINE, SimilarityMetric.EUCLIDEAN, SimilarityMetric.DOT).
    Must be one of the SimilarityMetric enum values.
    Default: SimilarityMetric.COSINE.

#### *abstract* build(data, vector_field=None)

Build index from data. Must be implemented by subclasses.

* **Parameters:**
  * **data** (`List`[`Dict`[`str`, `Any`]]) – List of items to index (entities).
  * **vector_field** (`Optional`[`str`]) – Field name containing vectors (required for entities).
* **Return type:**
  `None`

#### *property* entities *: List[Dict[str, Any]]*

Entities getter for accessing items.

#### search(query_vector, k, metric=None, where=None, columns_to_exclude=None)

Search for k nearest neighbors using efficient batched computation.

* **Parameters:**
  * **query_vector** (`List`[`float`]) – Query vector.
  * **k** (`int`) – Number of results to return.
  * **metric** (`Optional`[[`SimilarityMetric`](#wayflowcore.search.metrics.SimilarityMetric)]) – Distance metric to use for search (will temporarily override the instance metric for this search call).
  * **where** (`Optional`[`Dict`[`str`, `Any`]]) – Filter out results by specific row/column entries.
  * **columns_to_exclude** (`Optional`[`List`[`str`]]) – Columns to exclude while returning the final results.
* **Returns:**
  **results** – List of matching items with scores.
* **Return type:**
  List[Dict[str, Any]]

<a id="entity-vector-index"></a>

### *class* wayflowcore.search.vectorindex.EntityVectorIndex(dimension, metric=SimilarityMetric.COSINE)

Vector index for entity-based indexing.

Initialize the vector index.

* **Parameters:**
  * **dimension** (`int`) – Dimension of the vectors.
  * **metric** ([`SimilarityMetric`](#wayflowcore.search.metrics.SimilarityMetric)) – Distance metric to use (SimilarityMetric.COSINE, SimilarityMetric.EUCLIDEAN, SimilarityMetric.DOT).
    Must be one of the SimilarityMetric enum values.
    Default: SimilarityMetric.COSINE.

#### build(data, vector_field=None)

Build index from entities with vectors.

* **Parameters:**
  * **data** (`List`[`Dict`[`str`, `Any`]]) – List of entities containing vectors.
  * **vector_field** (`Optional`[`str`]) – Name of the field containing vectors (required).
* **Raises:**
  **ValueError** – If vector_field is not provided.
* **Return type:**
  `None`
