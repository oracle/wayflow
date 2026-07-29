.. _checkpointing:

Checkpointing
=============

Checkpointing APIs persist and restore conversation state across process restarts,
debugging sessions, and server requests.

Core types
----------

.. autoclass:: wayflowcore.checkpointing.ConversationCheckpoint

.. autoclass:: wayflowcore.checkpointing.CheckpointingInterval

.. autoclass:: wayflowcore.checkpointing.Checkpointer
   :members: load_latest, load, save, save_async, list_checkpoints, delete

Storage configuration
---------------------

.. autoclass:: wayflowcore.checkpointing.StorageConfig
   :members: to_schema

Datastore-backed checkpointers
------------------------------

.. autoclass:: wayflowcore.checkpointing.DatastoreCheckpointer

.. autoclass:: wayflowcore.checkpointing.InMemoryCheckpointer

.. autoclass:: wayflowcore.checkpointing.PostgresCheckpointer

.. autoclass:: wayflowcore.checkpointing.OracleDatabaseCheckpointer
