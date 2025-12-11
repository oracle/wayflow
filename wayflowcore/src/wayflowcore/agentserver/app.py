# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict, Literal, TypeAlias, Union

from wayflowcore.agentserver import ServerStorageConfig
from wayflowcore.agentserver.server import A2AServer, OpenAIResponsesServer
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.datastore import Datastore

ServerApiType: TypeAlias = Literal["openai-responses", "a2a"]


def create_server_app(
    api: ServerApiType,
    agents: Dict[str, ConversationalComponent],
    storage: Datastore,
    storage_config: ServerStorageConfig,
) -> Union[OpenAIResponsesServer, A2AServer]:
    if api == "openai-responses":
        return OpenAIResponsesServer(
            agents=agents,
            storage=storage,
            storage_config=storage_config,
        )
    elif api == "a2a":
        server = A2AServer(
            storage_config=storage_config,
        )
        agent = list(agents.values())[0]
        server.serve_agent(agent=agent)
        return server

    raise NotImplementedError(f"API `{api}` is not supported yet.")
