.. _top-howtocheckpointing:

=========================================
How to Checkpoint and Resume Conversations
=========================================

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Agents <../tutorials/basic_agent>`
    - :doc:`Flows <../tutorials/basic_flow>`
    - :doc:`Serve Agents with WayFlow <howto_serve_agents>`

WayFlow can now checkpoint the runtime state of a conversation and restore it later by
conversation id. This is useful when you want to:

- resume after a crash or restart
- pause and continue a long-running workflow
- inspect prior checkpoints for debugging
- reload an earlier state and branch from it


Choose a checkpointer
=====================

WayFlow exposes a shared checkpointing subsystem in ``wayflowcore.checkpointing``.
You can use:

- ``InMemoryCheckpointer`` for tests and local experimentation
- ``PostgresCheckpointer`` for PostgreSQL-backed persistence
- ``OracleDatabaseCheckpointer`` for Oracle-backed persistence

All checkpointers share the same API for saving, loading, listing, and deleting checkpoints.


Start a checkpointed conversation
=================================

Attach a checkpointer when you start the conversation. ``conversation_id`` becomes the durable key
used to look up the conversation later.

.. literalinclude:: ../code_examples/howto_checkpointing.py
   :language: python
   :start-after: .. start-##_Start_a_checkpointed_conversation
   :end-before: .. end-##_Start_a_checkpointed_conversation

Once checkpointing is enabled, WayFlow saves the root conversation automatically at the configured
checkpoint boundaries. For nested execution lineage without checkpoint restore, pass
``root_conversation_id`` explicitly.


Resume the latest checkpoint
============================

To restore the latest saved state, call ``start_conversation()`` again with the same
``conversation_id``
and checkpointer.

.. literalinclude:: ../code_examples/howto_checkpointing.py
   :language: python
   :start-after: .. start-##_Resume_the_latest_checkpoint
   :end-before: .. end-##_Resume_the_latest_checkpoint

If no checkpoint exists for that id, WayFlow creates a new conversation instead.


Load a specific checkpoint
==========================

You can inspect checkpoint history and reload an older checkpoint for replay or time-travel
debugging.

.. literalinclude:: ../code_examples/howto_checkpointing.py
   :language: python
   :start-after: .. start-##_Load_a_specific_checkpoint
   :end-before: .. end-##_Load_a_specific_checkpoint

``list_checkpoints()`` returns ordered checkpoint metadata, including the checkpoint id,
creation timestamp, and save metadata recorded at the boundary.


Control checkpoint frequency
============================

Use ``CheckpointingInterval`` to decide how often WayFlow should persist state.

.. literalinclude:: ../code_examples/howto_checkpointing.py
   :language: python
   :start-after: .. start-##_Control_checkpoint_frequency
   :end-before: .. end-##_Control_checkpoint_frequency

The available options are:

- ``CONVERSATION_TURNS``: save after the outermost ``conversation.execute()`` call returns
- ``LLM_TURNS``: also save at internal turn boundaries after turns that used an LLM
- ``ALL_INTERNAL_TURNS``: also save at every internal agent/flow turn boundary

Saving more frequently improves restart fidelity, but it also increases write volume.


Use checkpointing with the OpenAI Responses server
==================================================

The OpenAI Responses server path now uses the shared checkpointing subsystem behind
``ServerStorageConfig``. That means the existing OpenAI-compatible features such as
``previous_response_id``, ``conversation``, ``get_response()``, ``delete_response()``,
and ``store=False`` all run through the same shared checkpoint model.

If you are serving agents, keep using :doc:`Serve Agents with WayFlow <howto_serve_agents>` to
configure the storage backend. The server will use the matching shared checkpointer internally.


Limitations
===========

- ``OciAgent`` checkpoint restore is not supported yet
- checkpoint restore loads the saved state first; it does not merge fresh ``inputs`` or ``messages``
- ``InMemoryCheckpointer`` is not persistent across processes


Next steps
==========

- :doc:`Serialize and Deserialize Conversations <howto_serialize_conversations>`
- :doc:`Serve Agents with WayFlow <howto_serve_agents>`
- :doc:`Build a Swarm of Agents <howto_swarm>`
