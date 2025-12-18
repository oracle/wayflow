# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import argparse
import os
from typing import Dict

from wayflowcore import Agent, Flow, Swarm
from wayflowcore.agentserver.server import OpenAIResponsesServer
from wayflowcore.datastore import Entity, OracleDatabaseDatastore, TlsOracleDatabaseConnectionConfig
from wayflowcore.mcp import MCPTool, SSETransport, enable_mcp_without_auth
from wayflowcore.models import VllmModel
from wayflowcore.property import IntegerProperty, StringProperty
from wayflowcore.steps.datastoresteps import DatastoreCreateStep

ORACLE_DB_CREATE_DDL = (
    """CREATE TABLE names ("ID" INTEGER, name VARCHAR(400) NOT NULL, PRIMARY KEY ("ID"))"""
)
ORACLE_DB_DELETE_DDL = "DROP TABLE IF EXISTS names cascade constraints"


def get_agents() -> Dict[str, Agent]:
    enable_mcp_without_auth()

    mcp_tool = MCPTool(
        name="find_bug",
        description="find a bug in a DB",
        input_descriptors=[StringProperty(name="query")],
        client_transport=SSETransport(url="http://fake"),
        _validate_server_exists=False,
    )

    llm = VllmModel(
        model_id="meta-llama/Meta-Llama-3.1-8B-Instruct", host_port=os.environ.get("LLAMA_API_URL")
    )

    db_schema = {
        "names": Entity(
            properties={
                "ID": IntegerProperty(),
                "name": StringProperty(),
            },
        ),
    }

    connection_config = TlsOracleDatabaseConnectionConfig(
        user=os.environ.get("ADB_DB_USER"),
        password=os.environ.get("ADB_DB_PASSWORD"),
        dsn=os.environ.get("ADB_DSN"),
        config_dir=os.environ.get("ADB_CONFIG_DIR", None),
    )
    datastore = OracleDatabaseDatastore(connection_config=connection_config, schema=db_schema)

    flow = Flow.from_steps(
        steps=[DatastoreCreateStep(datastore=datastore, collection_name="names")],
        name="datastore_tool",
        description="To create enttes on the datastore",
    )

    agent = Agent(
        tools=[mcp_tool],  # add datastore tools when supported
        flows=[flow],
        custom_instruction="Answer the questions from the user. You have knowledge about geography of Europe and can answer questions about it. Here are some cities you might need:"
        "Switzerland: capital is Bern, biggest city is Zurich"
        "France: capital is Paris, biggest city is Paris"
        "UK: capital is London, biggest city is London"
        "Spain: capital is Madrid, biggest city is Madrid",
        llm=llm,
        name="main_agent",
        description="The main agent that will answer the questions from the user",
    )
    second_agent = Agent(
        tools=[mcp_tool],  # add datastore tools when supported
        flows=[flow],
        custom_instruction="Some math expert agent",
        llm=llm,
        name="math_expert_agent",
        description="The math expert agent that will answer the questions from the user",
    )

    # we want to test swarm because a swarm has multiple sub agents,
    # and the swarm conversation contains direct references to these sub-components
    # so when deserializing, the fallback that uses the hack to not have to
    # deserialize entirely the component need to work in the case where
    # subagents also need to not be deserialized
    swarm = Swarm(
        first_agent=agent,
        relationships=[(agent, second_agent)],
        name="swarm_agent",
    )

    return {"datastore-assistant": agent, "datastore-swarm": swarm}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8000,
        help="Port to run the server on (default: choose an available port)",
    )
    args = parser.parse_args()

    app = OpenAIResponsesServer(agents=get_agents())
    app.run(port=args.port)


if __name__ == "__main__":
    main()
