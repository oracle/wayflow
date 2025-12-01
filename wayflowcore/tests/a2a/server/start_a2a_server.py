# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import argparse
import os
from typing import Annotated

from server import A2AServer

from wayflowcore.agent import Agent
from wayflowcore.models import VllmModel
from wayflowcore.tools import tool

llm = VllmModel(
    model_id="meta-llama/Meta-Llama-3.1-8B-Instruct",
    host_port=os.getenv("LLAMA_API_URL"),
)


def get_agent_with_server_tool():
    @tool
    def multiply(
        a: Annotated[int, "first required integer"],
        b: Annotated[int, "second required integer"],
    ) -> int:
        "Return the result of multiplication between number a and b."
        print(f"{a}, {b}")
        return a * b

    @tool
    def add(
        a: Annotated[int, "first required integer"],
        b: Annotated[int, "second required integer"],
    ) -> int:
        "Return the result of addition between number a and b."
        print(f"{a}, {b}")
        return a + b

    agent = Agent(
        llm=llm,
        name="agent",
        custom_instruction="You are a Math agent that can do multiplication and addition by using the equipped tool.",
        tools=[multiply, add],
        can_finish_conversation=True,
    )
    return agent


def create_server(host: str, port: int):
    """Create and configure the A2A server"""
    agent = get_agent_with_server_tool()
    server = A2AServer(agent=agent)
    return server


def main(host: str, port: int):
    server = create_server(host=host, port=port)
    print(f"Starting A2A server on http://{host}:{port}")
    server.serve(host=host, port=port)
    print("A2A server has stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start an A2A server for testing.")
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help='The host address (e.g., "localhost" or "127.0.0.1")',
    )
    parser.add_argument("--port", type=int, default=8000, help="The port number (e.g., 8000)")
    args = parser.parse_args()
    main(host=args.host, port=args.port)
