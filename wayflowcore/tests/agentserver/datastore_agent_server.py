# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import argparse
import os

from wayflowcore import Agent
from wayflowcore.agentserver.server import OpenAIResponsesServer
from wayflowcore.datastore import OracleDatabaseDatastore, TlsOracleDatabaseConnectionConfig
from wayflowcore.mcp import MCPTool, SSETransport, enable_mcp_without_auth
from wayflowcore.models import VllmModel
from wayflowcore.property import StringProperty

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

connection_config = TlsOracleDatabaseConnectionConfig(
    user=os.environ.get("ADB_DB_USER"),
    password=os.environ.get("ADB_DB_PASSWORD"),
    dsn=os.environ.get("ADB_DSN"),
    config_dir=os.environ.get("ADB_CONFIG_DIR", None),
)
datastore = OracleDatabaseDatastore(connection_config=connection_config, schema={})


agent = Agent(
    tools=[mcp_tool],  # add datastore tools when supported
    custom_instruction="Answer the questions from the user. You have knowledge about geography of Europe and can answer questions about it. Here are some cities you might need:"
    "Switzerland: capital is Bern, biggest city is Zurich"
    "France: capital is Paris, biggest city is Paris"
    "UK: capital is London, biggest city is London"
    "Spain: capital is Madrid, biggest city is Madrid",
    llm=llm,
)


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

    app = OpenAIResponsesServer(agents={"datastore-assistant": agent})
    app.run(port=args.port)


if __name__ == "__main__":
    main()
