# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from fasta2a.schema import Artifact, Message, Task, TaskState, TaskStatus
from fasta2a.storage import Storage
from typing_extensions import TypeVar

from wayflowcore.conversation import Conversation
from wayflowcore.datastore import Datastore, InMemoryDatastore
from wayflowcore.datastore._relational import RelationalDatastore
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.serialization.context import DeserializationContext
from wayflowcore.tools import Tool

from ..serverstorageconfig import ServerStorageConfig

ContextT = TypeVar("ContextT", default=Any)
"""The shape of the context stored in the storage (is not used in our case but is added to be compatible with fasta2a's Storage class"""


class A2AStorage(Storage[ContextT]):  # type: ignore[misc]

    def __init__(self, storage_config: ServerStorageConfig):
        self.storage_config = storage_config
        if storage_config.datastore is None:
            self.datastore: Datastore = InMemoryDatastore(schema=self.storage_config.to_schema())
        else:
            self.datastore = storage_config.datastore

    async def load_task(self, task_id: str, history_length: Optional[int] = None) -> Optional[Task]:
        """Load a task from the storage, if the task is not found, return None"""
        retrieved_results = self.datastore.list(
            collection_name=self.storage_config.table_name,
            where={self.storage_config.turn_id_column_name: task_id},
            limit=1,
        )

        if len(retrieved_results) == 0:
            return None

        # Create task from the retrieved result
        retrieved_result = retrieved_results[0]
        extra_data = json.loads(retrieved_result[self.storage_config.extra_metadata_column_name])

        task_kwargs = {
            "id": task_id,
            "context_id": retrieved_result[self.storage_config.conversation_id_column_name],
            "status": extra_data["status"],
            "kind": "task",
        }

        if "history" in extra_data:
            task_kwargs["history"] = extra_data["history"]
            if history_length:
                task_kwargs["history"] = task_kwargs["history"][:history_length]

        if "artifacts" in extra_data:
            task_kwargs["artifacts"] = extra_data["artifacts"]

        return Task(**task_kwargs)

    async def submit_task(self, context_id: str, message: Message) -> Task:
        """Create the new current task in the storage"""
        # Generate a unique task ID
        task_id = str(uuid.uuid4())

        # Add IDs to the message for A2A protocol
        message["task_id"] = task_id
        message["context_id"] = context_id

        task_status = TaskStatus(
            state="submitted",
            timestamp=str(datetime.now().isoformat()),
        )

        task = Task(
            id=task_id,
            context_id=context_id,
            kind="task",
            status=task_status,
            history=[message],
        )

        self.datastore.create(
            collection_name=self.storage_config.table_name,
            entities=[
                {
                    self.storage_config.agent_id_column_name: "agent",  # we don't need this field for A2A -> assign a random value, it might be useful in the future
                    self.storage_config.conversation_id_column_name: context_id,
                    self.storage_config.turn_id_column_name: task_id,
                    self.storage_config.is_last_turn_column_name: 0,  # it is not processed yet -> will be set to true once it is processed
                    self.storage_config.created_at_column_name: int(time.time()),
                    self.storage_config.conversation_turn_state_column_name: "",  # the corresponding conversation has not been created yet
                    self.storage_config.extra_metadata_column_name: json.dumps(
                        {
                            "status": task_status,
                            "history": [message],
                        }
                    ),
                }
            ],
        )

        return task

    async def update_task(
        self,
        task_id: str,
        state: TaskState,
        new_artifacts: Optional[List[Artifact]] = None,
        new_messages: Optional[List[Message]] = None,
    ) -> Task:
        """Update the current task"""
        task = await self.load_task(task_id=task_id)
        if not task:
            raise ValueError(f"Cannot update task '{task_id}': task not found.")

        task["status"] = TaskStatus(
            state=state,
            timestamp=datetime.now().isoformat(),
        )

        if new_messages:
            if "history" not in task:
                task["history"] = []
            # Add IDs to messages for consistency
            for message in new_messages:
                message["task_id"] = task_id
                message["context_id"] = task["context_id"]
                task["history"].append(message)

        if new_artifacts:
            if "artifacts" not in task:
                task["artifacts"] = []
            task["artifacts"].extend(new_artifacts)

        extra_data = {
            "status": task["status"],
        }

        if "history" in task:
            extra_data["history"] = task["history"]
        if "artifacts" in task:
            extra_data["artifacts"] = task["artifacts"]

        self.datastore.update(
            collection_name=self.storage_config.table_name,
            where={self.storage_config.turn_id_column_name: task_id},
            update={self.storage_config.extra_metadata_column_name: json.dumps(extra_data)},
        )

        return task

    async def load_latest_task(self, context_id: str) -> Optional[Dict[str, Any]]:
        "Load the latest processed task if existing else return None"
        retrieved_results = self.datastore.list(
            collection_name=self.storage_config.table_name,
            where={
                self.storage_config.conversation_id_column_name: context_id,
                self.storage_config.is_last_turn_column_name: 1,
            },
        )

        if len(retrieved_results) == 0:
            return None
        elif len(retrieved_results) == 1:
            return retrieved_results[0]
        else:
            raise ValueError("Internal error")

    async def load_context_conversation(
        self, context_id: str, tools_dict: Dict[str, Tool]
    ) -> Optional[Conversation]:
        """Load the conversation of the latest processed task in the context"""
        latest_task = await self.load_latest_task(context_id=context_id)
        if not latest_task:
            return None

        serialized_conv = latest_task[self.storage_config.conversation_turn_state_column_name]

        deserialization_context = DeserializationContext()
        for tool in tools_dict.values():
            deserialization_context.registered_tools[tool.name] = tool

        conv = cast(Conversation, autodeserialize(serialized_conv, deserialization_context))
        return conv

    async def load_task_conversation(
        self, task_id: str, tools_dict: Dict[str, Tool]
    ) -> Optional[Conversation]:
        """Load task's corresponding Wayflow conversation"""
        serialized_conv = self.datastore.list(
            collection_name=self.storage_config.table_name,
            where={self.storage_config.turn_id_column_name: task_id},
        )[0][self.storage_config.conversation_turn_state_column_name]

        if len(serialized_conv) == 0:
            return None

        deserialization_context = DeserializationContext()
        for tool in tools_dict.values():
            deserialization_context.registered_tools[tool.name] = tool

        conv = cast(Conversation, autodeserialize(serialized_conv, deserialization_context))
        return conv

    async def update_task_conversation(
        self, context_id: str, task_id: str, conv: Conversation
    ) -> None:
        """
        1. Set previous last turn to False
        2. Update task's corresponding Wayflow conversation + set is_last_turn = True
        """
        updates_old = {self.storage_config.is_last_turn_column_name: 0}
        updates_old_where = {
            self.storage_config.conversation_id_column_name: context_id,
            self.storage_config.is_last_turn_column_name: 1,
        }

        serialized_conv = serialize(conv)
        updates_new = {
            self.storage_config.conversation_turn_state_column_name: serialized_conv,
            self.storage_config.is_last_turn_column_name: 1,
        }
        updates_new_where = {
            self.storage_config.conversation_id_column_name: context_id,
            self.storage_config.turn_id_column_name: task_id,
        }

        if isinstance(self.datastore, RelationalDatastore):
            # for relational datastores, we prefer making a single
            # transaction, to avoid corrupting the state of the DB
            # if the process crashes between the updates

            data_table = self.datastore.data_tables[self.storage_config.table_name]
            sql_update_stmt_1 = data_table._update_query(
                where=updates_old_where,
                update=updates_old,
            )

            sql_update_stmt_2 = data_table._update_query(
                where=updates_new_where,
                update=updates_new,
            )

            with data_table.engine.connect() as connection:
                connection.execute(sql_update_stmt_1)
                connection.execute(sql_update_stmt_2)
                connection.commit()
        else:
            self.datastore.update(
                collection_name=self.storage_config.table_name,
                where=updates_old_where,
                update=updates_old,
            )

            self.datastore.update(
                collection_name=self.storage_config.table_name,
                where=updates_new_where,
                update=updates_new,
            )

    async def update_context(self, context_id: str, context: Any) -> None:
        raise NotImplementedError()

    async def load_context(self, context_id: str) -> Any:
        raise NotImplementedError()
