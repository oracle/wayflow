.. _top-howtocheckpointing:

==========================================
How to Checkpoint and Resume Conversations
==========================================

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Agents <../tutorials/basic_agent>`
    - :doc:`Flows <../tutorials/basic_flow>`
    - :doc:`Serve Agents with WayFlow <howto_serve_agents>`

Checkpointing lets WayFlow save a conversation while it runs and load it again later using the
same ``conversation_id``. Use it when you want to:

- continue after a process restart
- pause a long-running workflow and come back to it later
- inspect earlier checkpoints while debugging
- retry from an older checkpoint with different code or inputs


Choose a checkpointer
=====================

The checkpointer is the object that reads and writes checkpoints. WayFlow includes:

- ``InMemoryCheckpointer`` for tests and local experimentation
- ``PostgresCheckpointer`` for PostgreSQL-backed persistence
- ``OracleDatabaseCheckpointer`` for Oracle-backed persistence

All checkpointers use the same methods for loading, listing, and deleting checkpoints.
WayFlow saves checkpoints automatically during conversation execution.


Start a checkpointed conversation
=================================

Attach a checkpointer when you start the conversation. The ``conversation_id`` is the name WayFlow
uses to find that conversation again.

.. literalinclude:: ../code_examples/howto_checkpointing.py
   :language: python
   :start-after: .. start-##_Start_a_checkpointed_conversation
   :end-before: .. end-##_Start_a_checkpointed_conversation

Once checkpointing is enabled, WayFlow saves the top-level conversation automatically at the
configured checkpoints. If an Agent or Flow starts child conversations internally, WayFlow keeps
them attached to the same saved conversation. Application code only needs to pass the public
``conversation_id`` shown above.

For checkpointing, there are three useful identifiers:

- ``conversation_id``: the durable conversation id used to resume and list checkpoints
- ``checkpoint_id``: the exact saved snapshot to reload
- ``conversation.id``: the id of one concrete ``Conversation`` within that conversation thread

Each nested conversation gets its own ``conversation.id`` while inheriting the conversation thread's
``conversation_id``. Application code only supplies ``conversation_id``; child identities are
created and restored internally.

.. warning::

   Checkpoints contain the serialized conversation, including messages and intermediate state.
   Treat checkpoint storage like other persisted user conversation data: protect access, choose an
   appropriate retention policy, and avoid storing it in places meant only for test data.


Resume the latest checkpoint
============================

To resume a conversation, call ``start_conversation()`` again with the same ``conversation_id`` and
checkpointer.

.. literalinclude:: ../code_examples/howto_checkpointing.py
   :language: python
   :start-after: .. start-##_Resume_the_latest_checkpoint
   :end-before: .. end-##_Resume_the_latest_checkpoint

If the checkpointer has no saved state for that id, WayFlow starts a new conversation.


Load a specific checkpoint
==========================

You can also load an older checkpoint. This is useful when you want to replay part of a run or
compare what happens after changing a prompt, tool, or step.

.. literalinclude:: ../code_examples/howto_checkpointing.py
   :language: python
   :start-after: .. start-##_Load_a_specific_checkpoint
   :end-before: .. end-##_Load_a_specific_checkpoint

``list_checkpoints()`` returns checkpoints ordered from oldest to newest, with the checkpoint id,
creation time, and metadata recorded when the checkpoint was saved. That means ``checkpoints[-1]``
is the newest checkpoint and ``checkpoints[-2]`` is the one before it.


Control checkpoint frequency
============================

Use ``CheckpointingInterval`` to choose how often WayFlow should save state.

.. literalinclude:: ../code_examples/howto_checkpointing.py
   :language: python
   :start-after: .. start-##_Control_checkpoint_frequency
   :end-before: .. end-##_Control_checkpoint_frequency

The available options are:

- ``CONVERSATION_TURNS``: save after the main ``conversation.execute()`` call returns
- ``LLM_TURNS``: also save after internal turns that used an LLM
- ``ALL_INTERNAL_TURNS``: also save after each internal Agent or Flow turn

Saving more often gives WayFlow a more recent place to resume from, but it also writes more rows to
the checkpoint store.

WayFlow resumes from the last checkpoint it saved. It does not resume from the middle of a tool
call, LLM request, or step. If a crash happens after that checkpoint, code that ran after the
checkpoint may run again. Tools and steps with side effects should therefore be safe to retry. For
example, if a step writes to another service, sends a notification, or charges a payment method,
use your own idempotency key or tracking table so the side effect is not repeated.

When multiple processes share a relational checkpoint store, use a single writer per
``conversation_id``. WayFlow updates the "latest checkpoint" marker in one transaction for normal
writes, but the table does not enforce uniqueness for that marker. If two writers save the same
conversation at the same time, the store can end up with more than one checkpoint marked as latest.
In that case, loading by ``conversation_id`` raises an error instead of choosing one at random.
When recovering that history, load a specific ``checkpoint_id``.


Use checkpointing with the OpenAI Responses server
==================================================

The OpenAI Responses server uses the same checkpointing storage behind ``ServerStorageConfig``.
Existing OpenAI-compatible features such as ``previous_response_id``, ``conversation``,
``get_response()``, ``delete_response()``, and ``store=False`` continue to work through that shared
storage path.

If you are serving agents, configure storage the same way as in
:doc:`Serve Agents with WayFlow <howto_serve_agents>`. The server creates and uses the matching
checkpointer internally.


Next steps
==========

- :doc:`Serialize and Deserialize Conversations <howto_serialize_conversations>`
- :doc:`Serve Agents with WayFlow <howto_serve_agents>`
- :doc:`Build a Swarm of Agents <howto_swarm>`
