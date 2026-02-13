# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import argparse
from typing import Annotated, AsyncGenerator, List, Literal, Optional, Tuple

import anyio
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken, AuthProvider, TokenVerifier
from fastmcp.server.auth.auth import ClientRegistrationOptions
from fastmcp.server.auth.providers.in_memory import InMemoryOAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.middleware import Middleware, MiddlewareContext
from mcp.types import EmbeddedResource, TextResourceContents
from pydantic import AnyUrl, BaseModel, Field

from wayflowcore.mcp.mcphelpers import mcp_streaming_tool

BASE_SCOPE_NAME = "base_tools"
PROTECTED_SCOPE_NAME = "protected_tools"


class JWTTestMiddleware(Middleware):
    def __init__(
        self,
        protected_tool_list: List[str],
        jwt_verifier: JWTVerifier,
    ) -> None:
        self.protected_tool_list = protected_tool_list
        self.jwt_verifier = jwt_verifier
        super().__init__()

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        mcp_request_context = context.fastmcp_context.request_context
        connection_request = mcp_request_context.request
        base_access_token_info: AccessToken = connection_request.user.access_token
        access_token = base_access_token_info.token
        tool_name: str = context.message.name

        if tool_name in self.protected_tool_list:
            # check for access
            verified_access_token_info = await self.jwt_verifier.verify_token(access_token)
            if not verified_access_token_info:
                raise ToolError(f"Access denied: Insufficient scopes to access tool {tool_name}")

        result = await call_next(context)
        return result


def _create_test_jwt_verifier_and_middleware(
    public_key: str,
) -> Tuple[TokenVerifier, List[Middleware]]:
    auth = JWTVerifier(
        public_key=public_key,
        issuer="https://test.example.com",
        audience="https://api.example.com",
        required_scopes=[BASE_SCOPE_NAME],
    )
    middleware = JWTTestMiddleware(
        protected_tool_list=["generate_random_string_protected"],
        jwt_verifier=JWTVerifier(
            public_key=public_key, required_scopes=[BASE_SCOPE_NAME, PROTECTED_SCOPE_NAME]
        ),
    )
    return auth, middleware


def _create_test_inmemory_oauth_provider(base_mcp_url: str) -> InMemoryOAuthProvider:
    return InMemoryOAuthProvider(
        base_url=base_mcp_url,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[BASE_SCOPE_NAME],
            client_secret_expiry_seconds=5,
            default_scopes=[],
        ),
        required_scopes=[BASE_SCOPE_NAME],
    )


class GenerateTupleOut(BaseModel, title="tool_output"):
    result: tuple[
        Annotated[int, Field(title="int_output")], Annotated[str, Field(title="str_output")]
    ]
    # /!\ this needs to be named `result`


class GenerateOptionalOut(BaseModel, title="tool_output"):
    # Optional output to validate anyOf handling in WayFlow
    result: Optional[str]


class GenerateUnionOut(BaseModel, title="tool_output"):
    # True union output (non-null) to validate anyOf handling in WayFlow
    result: str | int


def create_server(
    host: str,
    port: int,
    uses_https: bool,
    auth_public_key: Optional[str],
    auth_type: Optional[Literal["oauth", "jwt"]],
    oauth_callback_port: Optional[str],
):
    """Create and configure the MCP server"""

    auth: Optional[AuthProvider] = None
    middlewares = []
    base_url = ("https" if uses_https else "http") + f"://{host}:{port}"
    if auth_type is None:
        pass
    elif auth_type == "jwt":
        auth, middleware_ = _create_test_jwt_verifier_and_middleware(auth_public_key)
        middlewares.append(middleware_)
    elif auth_type == "oauth":
        auth = _create_test_inmemory_oauth_provider(base_url)
    else:
        raise ValueError(f"MCP Auth type {auth_type} is not supported")

    server = FastMCP(
        name="Example MCP Server",
        instructions="A MCP Server.",
        auth=auth,
        middleware=middlewares,
    )

    @server.tool(
        description="Return the result of the fooza operation between numbers a and b. Do not use for anything else than computing a fooza operation."
    )
    def fooza_tool(a: int, b: int) -> int:
        return a * 2 + b * 3 - 1

    @server.tool(
        description="Return the result of the bwip operation between numbers a and b. Do not use for anything else than computing a bwip operation."
    )
    def bwip_tool(a: int, b: int) -> int:
        return a - b + 1

    @server.tool(
        description="Return the result of the zbuk operation between numbers a and b. Do not use for anything else than computing a zbuk operation."
    )
    def zbuk_tool(a: int, b: int) -> int:
        return a + b * 2

    @server.tool(
        description="Return the result of the ggwp operation between numbers a and b. Do not use for anything else than computing a ggwp operation."
    )
    def ggwp_tool(a: int, b: int) -> int:
        return a + b // 2

    @server.tool(description="Tool to return a random string")
    def generate_random_string() -> str:
        import random

        return f"random_string_{random.randint(100, 999)}"

    @server.tool(description="Tool to return a random string")
    def generate_random_string_protected() -> str:
        import random

        return f"random_string_{random.randint(100, 999)}"

    @server.tool(description="Tool that returns a complex type")
    def generate_complex_type() -> list[str]:
        return ["value1", "value2"]

    @server.tool(
        description="Tool that returns a dict",
        output_schema={
            "additionalProperties": {"type": "string"},
            "title": "tool_output",
            "type": "object",
        },
    )
    def generate_dict() -> dict[str, str]:
        return {"key": "value"}

    @server.tool(
        description="Tool that returns a list",
        output_schema={
            "properties": {
                "result": {"items": {"type": "string"}, "title": "Result", "type": "array"}
            },
            "required": ["result"],
            "title": "tool_output",
            "type": "object",
        },
    )
    def generate_list() -> list[str]:
        # to support complex output schemas, you must wrap the output
        # to match the given `output_schema`
        return {"result": ["value1", "value2"]}

    @server.tool(
        description="Tool that returns a tuple",
        output_schema={
            "properties": {
                "result": {
                    "maxItems": 2,
                    "minItems": 2,
                    "prefixItems": [
                        {"title": "str_output", "type": "string"},
                        {"title": "bool_output", "type": "boolean"},
                    ],
                    "title": "Result",
                    "type": "array",
                }
            },
            "required": ["result"],
            "title": "tool_output",
            "type": "object",
        },
    )
    def generate_tuple() -> tuple[str, bool]:
        return {"result": ("value", True)}

    @server.tool(
        description="Tool that returns an optional string",
        output_schema=GenerateOptionalOut.model_json_schema(),
    )
    def generate_optional() -> Optional[str]:
        # Deterministic value for testing
        return {"result": "maybe"}

    @server.tool(
        description="Tool that returns a union value",
        output_schema=GenerateUnionOut.model_json_schema(),
    )
    def generate_union() -> str | int:
        # Deterministic value for testing
        return {"result": "maybe"}

    @server.tool(description="Tool that consumes a list and a dict")
    def consumes_list_and_dict(vals: list[str], props: dict[str, str]) -> str:
        return f"vals={vals!r}, props={props!r}"

    @server.tool(description="Returns the resource associated with a user")
    def get_resource(user: str):  # on purpose not put the type to check we handle
        return EmbeddedResource(
            resource=TextResourceContents(
                text=f"{user}_response",
                uri=AnyUrl("users://{user}/profile"),
                mimeType="text/plain",
            ),
            type="resource",
        )

    async def streaming_tool() -> AsyncGenerator[str, None]:
        contents = [f"This is the sentence N°{i}" for i in range(5)]
        for chunk in contents:
            yield chunk  # streamed chunks
            await anyio.sleep(0.2)

        yield ". ".join(contents)  # final result

    server.tool(description="Streaming tool")(
        mcp_streaming_tool(streaming_tool, context_cls=Context)
    )

    @server.tool(description="Streaming tool")
    @mcp_streaming_tool
    async def streaming_tool_with_ctx(ctx: Context) -> AsyncGenerator[str, None]:
        ctx.info("Hello")
        contents = [f"This is the sentence N°{i}" for i in range(5)]
        for chunk in contents:
            yield chunk  # streamed chunks
            await anyio.sleep(0.2)

        yield ". ".join(contents)  # final result

    @server.tool(
        description="Streaming tool",
        output_schema=GenerateTupleOut.model_json_schema(),
    )
    @mcp_streaming_tool
    async def streaming_tool_tuple(ctx: Context) -> AsyncGenerator[tuple[int, str], None]:
        contents = [f"This is the sentence N°{i}" for i in range(5)]
        for idx, chunk in enumerate(contents):
            yield (idx, chunk)  # streamed chunks
            await anyio.sleep(0.2)

        yield {"result": (5, ". ".join(contents))}  # final result

    return server


def main(
    host: str,
    port: int,
    mode: Literal["sse", "streamable-http"],
    ssl_keyfile: str | None,
    ssl_certfile: str | None,
    ssl_ca_certs: str | None,
    ssl_cert_reqs: int,
    auth_public_key: str | None,
    auth_type: Optional[str],
    oauth_callback_port: Optional[str],
):
    uses_https = all((ssl_keyfile, ssl_certfile, ssl_ca_certs))
    server = create_server(
        host=host,
        port=port,
        uses_https=uses_https,
        auth_public_key=auth_public_key,
        auth_type=auth_type,
        oauth_callback_port=oauth_callback_port,
    )
    import logging

    server.run(
        transport=mode,
        show_banner=False,
        host=host,
        port=port,
        uvicorn_config=dict(
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            ssl_ca_certs=ssl_ca_certs,
            ssl_cert_reqs=ssl_cert_reqs,
            log_level=logging.DEBUG,
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process host, port, and mode.")

    parser.add_argument(
        "--host", type=str, help='The host address (e.g., "localhost" or "127.0.0.1")'
    )
    parser.add_argument("--port", type=int, help="The port number (e.g., 8080)")
    parser.add_argument(
        "--mode", type=str, choices=["sse", "streamable-http"], help="The mode for the application"
    )
    parser.add_argument(
        "--ssl_keyfile", type=str, help="Path to the server private key file (PEM format)."
    )
    parser.add_argument(
        "--ssl_certfile", type=str, help="Path to the server certificate chain file (PEM format)."
    )
    parser.add_argument(
        "--ssl_ca_certs", type=str, help="Path to the trusted CA certificate file (PEM format)."
    )
    parser.add_argument(
        "--ssl_cert_reqs", type=int, help="Server certificate verify mode (0=None or 2=Required)."
    )
    parser.add_argument("--auth_public_key", type=str, help="Public key for the MCP auth.")
    parser.add_argument("--auth_type", type=str, help="Type of auth.")
    parser.add_argument(
        "--oauth_callback_port", type=int, help="Callback port for when using Oauth."
    )

    args = parser.parse_args()

    main(
        host=args.host,
        port=args.port,
        mode=args.mode,
        ssl_keyfile=args.ssl_keyfile,
        ssl_certfile=args.ssl_certfile,
        ssl_ca_certs=args.ssl_ca_certs,
        ssl_cert_reqs=args.ssl_cert_reqs,
        auth_public_key=args.auth_public_key,
        auth_type=args.auth_type,
        oauth_callback_port=args.oauth_callback_port,
    )
