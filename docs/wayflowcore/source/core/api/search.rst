.. _search_api:

Search
======

This section documents the APIs for the core Search, Vector, and related configuration/data classes.

Search Configuration
--------------------

.. _search_config:
.. autoclass:: wayflowcore.search.config.SearchConfig

.. _vector_config:
.. autoclass:: wayflowcore.search.config.VectorConfig

.. _retriever_config:
.. autoclass:: wayflowcore.search.config.RetrieverConfig

.. _vector_retriever_config:
.. autoclass:: wayflowcore.search.config.VectorRetrieverConfig

.. _serializer_config:
.. autoclass:: wayflowcore.search.config.SerializerConfig

.. _concat_serializer_config:
.. autoclass:: wayflowcore.search.config.ConcatSerializerConfig

Similarity Metrics
------------------

.. _similarity_metric:
.. autoclass:: wayflowcore.search.metrics.SimilarityMetric

Search Toolbox
--------------

.. _search_tool_box:
.. autoclass:: wayflowcore.search.toolbox.SearchToolBox

Vector Generator
----------------

.. _vector_generator:
.. autoclass:: wayflowcore.search.vectorgenerator.VectorGenerator

.. _simple_vector_generator:
.. autoclass:: wayflowcore.search.vectorgenerator.SimpleVectorGenerator

Vector Indexes
--------------

.. _vector_index:
.. autoclass:: wayflowcore.search.vectorindex.VectorIndex

.. _oracle_vector_index:
.. autoclass:: wayflowcore.search.vectorindex.OracleDatabaseVectorIndex

.. _inmemory_vector_index:
.. autoclass:: wayflowcore.search.vectorindex.BaseInMemoryVectorIndex

.. _entity_vector_index:
.. autoclass:: wayflowcore.search.vectorindex.EntityVectorIndex
