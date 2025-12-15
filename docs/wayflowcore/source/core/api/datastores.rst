.. _datastores:

Datastores
==========

Datastores connect Agents and Flows to data modelled by entity definitions.
To see how you can use a datastore in a Flow or Agent, see :ref:`Datastore task steps <datastoresteps>`.

Entity
------

Entities define the data model of datastores.

.. _entity:
.. autoclass:: wayflowcore.datastore.Entity

.. _nullable_helper_function:
.. autoclass:: wayflowcore.datastore.nullable

Base class
----------

.. _datastore:
.. autoclass:: wayflowcore.datastore.Datastore

In memory
---------

.. _inmemorydatastore:
.. autoclass:: wayflowcore.datastore.InMemoryDatastore
    :exclude-members: list, create, update, delete, describe

    ..
        We exclude these members because they are already included in the base class

Relational Datastore
--------------------

.. autoclass:: wayflowcore.datastore._relational.RelationalDatastore

Oracle Database
---------------

.. important::
    The Oracle Database Datastore requires additional optional dependencies, which can be installed
    with the ``[datastore]`` installation option.

.. note::
    By default (when using the `OracleDatabaseConnectionConfig` classes as-is), the `python-oracledb`
    client will use a thin connection to the database. If you want to use a thick connection
    (leveraging Oracle Instant Client), invoke `oracledb.init_instant_client()` before initializing
    any connection to the database. More information about thick and thin connection can be found in the
    `python-oracledb documentation <https://python-oracledb.readthedocs.io/en/latest/api_manual/module.html#oracledb.init_oracle_client>`_.

.. _oracledatabaseconnectionconfig:
.. autoclass:: wayflowcore.datastore.OracleDatabaseConnectionConfig

.. _oracledatabasetlsconnectionconfig:
.. autoclass:: wayflowcore.datastore.TlsOracleDatabaseConnectionConfig

.. _oracledatabasemtlsconnectionconfig:
.. autoclass:: wayflowcore.datastore.MTlsOracleDatabaseConnectionConfig

.. _oracledatabasedatastore:
.. autoclass:: wayflowcore.datastore.OracleDatabaseDatastore

    .. automethod:: query


Postgres Database
-----------------

.. important::
    The Postgres Database Datastore requires additional optional dependencies, which can be installed
    with the ``[datastore]`` installation option.

.. _postgresdatabaseconnectionconfig:
.. autoclass:: wayflowcore.datastore.PostgresDatabaseConnectionConfig

.. _postgresdatabasetlsconnectionconfig:
.. autoclass:: wayflowcore.datastore.TlsPostgresDatabaseConnectionConfig

.. _postgresdatabasedatastore:
.. autoclass:: wayflowcore.datastore.PostgresDatabaseDatastore

    .. automethod:: query
