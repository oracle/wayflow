# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import argparse
import os

from wayflowcore import Agent, tool
from wayflowcore.agentserver.server import OpenAIResponsesServer
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

mcp_agent = Agent(
    tools=[mcp_tool],
    custom_instruction="Answer the questions from the user. You have knowledge about geography of Europe and can answer questions about it. Here are some cities you might need:"
    "Switzerland: capital is Bern, biggest city is Zurich"
    "France: capital is Paris, biggest city is Paris"
    "UK: capital is London, biggest city is London"
    "Spain: capital is Madrid, biggest city is Madrid\n\n"
    "Additional information: {{instructions}}",
    llm=llm,
    input_descriptors=[StringProperty(name="instructions", default_value="none")],
)


@tool(description_mode="only_docstring", requires_confirmation=True)
def search_hr_database(query: str) -> str:
    """Function that searches the HR database for employee benefits."""
    return '{"John Smith": {"benefits": "Unlimited PTO", "salary": "$1,000"}, "Mary Jones": {"benefits": "25 days", "salary": "$10,000"}}'


tool_confirmation_agent = Agent(
    tools=[search_hr_database],
    custom_instruction="Answer the questions from the user.",
    llm=llm,
)

vision_llm = VllmModel(
    model_id="/storage/models/Llama-3.3-70B-Instruct",
    host_port=os.environ.get("LLAMA70BV33_API_URL"),
)

image_agent = Agent(
    custom_instruction="Answer the questions from the user about the given image.",
    llm=vision_llm,
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

    app = OpenAIResponsesServer(
        agents={
            "mcp-assistant": mcp_agent,
            "tool-confirmation-assistant": tool_confirmation_agent,
            "image-assistant": image_agent,
        },
    )
    app.run(port=args.port, api_key="SOME_FAKE_SECRET")


if __name__ == "__main__":
    main()
