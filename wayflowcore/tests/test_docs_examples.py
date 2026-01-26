# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import copy
import glob
import os
import runpy
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from wayflowcore.datastore.inmemory import _INMEMORY_USER_WARNING
from wayflowcore.transforms.summarization import _SUMMARIZATION_WARNING_MESSAGE

from .a2a.conftest import a2a_server_fixture  # noqa
from .a2a.test_a2aagent import a2a_agent, connection_config_no_verify  # noqa
from .mcptools.conftest import sse_mcp_server_http  # noqa
from .mcptools.test_mcp_tools import MCP_USER_QUERY
from .test_ociagent import agent as oci_agent  # noqa
from .testhelpers.testhelpers import retry_test
from .utils import get_available_port

DOCS_DIR = Path(__file__).parents[2] / "docs" / "wayflowcore" / "source" / "core"
UTILS_DIR = Path(__file__).parent / "_utils"
EXAMPLE_DOCUMENT_PATH = DOCS_DIR / "_static" / "howto" / "example_document.md"

sys.path.insert(0, os.path.abspath(UTILS_DIR))


@pytest.fixture(scope="session")
def mock_server(session_tmp_path):
    "Start a mock server for testing howto_remote_tool_expired_token document."
    import threading
    import time

    import httpx
    import uvicorn
    from starlette.applications import Starlette
    from starlette.exceptions import HTTPException
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.status import HTTP_401_UNAUTHORIZED

    async def protected_endpoint(request: Request):
        user = request.query_params.get("user")
        if user is None:
            return JSONResponse({"detail": "Missing 'user' query parameter."}, status_code=400)

        authorization = request.headers.get("authorization")
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Missing or malformed Authorization header.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = authorization.split(" ")[1]
        if token == "valid-token":
            return JSONResponse({"response": f"Success! You are authenticated, {user}."})
        elif token == "expired-token":
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Token has expired.",
                headers={
                    "WWW-Authenticate": "Bearer error='invalid_token', error_description='The access token expired'"
                },
            )
        else:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid access token.",
                headers={"WWW-Authenticate": "Bearer error='invalid_token'"},
            )

    app = Starlette(debug=True, routes=[Route("/protected", protected_endpoint)])

    host = "localhost"
    port = get_available_port(session_tmp_path)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Check if the server is up
    url = f"http://{host}:{port}/protected?user=test"
    headers = {"Authorization": "Bearer valid-token"}

    with httpx.Client(timeout=0.2) as client:
        for _ in range(50):  # up to 5 seconds
            try:
                response = client.get(url, headers=headers)
                if response.status_code in {400, 200, 401}:
                    break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Mock server did not start in time")

    try:
        yield f"http://{host}:{port}/protected"
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)


def _read_dummy_pdf_file(file_path: str, clean_pdf: bool = False) -> str:
    """Dummy version of the Read and Clean PDF file function."""
    # For testing we use the md file that contains the same content as the PDF.
    with open(EXAMPLE_DOCUMENT_PATH) as f:
        data = f.read()
    return data


def get_all_code_examples_files() -> List[str]:
    return glob.glob(str(DOCS_DIR) + "/code_examples/**/*.py", recursive=True)


def make_update_globals(test_globs: Dict[str, Any], pytest_request):
    def _update_globals(varnames_to_update: List[str]) -> Tuple[Any, ...]:
        replacements = copy.copy(test_globs)
        if "oci_agent" in varnames_to_update:
            replacements["oci_agent"] = pytest_request.getfixturevalue("oci_agent")
        if "a2a_agent" in varnames_to_update:
            replacements["a2a_agent"] = pytest_request.getfixturevalue("a2a_agent")
        elif "sse_mcp_server" in varnames_to_update:
            replacements["sse_mcp_server"] = pytest_request.getfixturevalue("sse_mcp_server_http")

        return tuple(replacements[name] for name in varnames_to_update)

    return _update_globals


# We retry code example tests as some of them rely on LLMs, but we keep the retry number low.
# We should not increase the max attempts beyond 2 because flakiness of docs should be minimal.
# If you are considering raising this number, please make your documentation example more robust instead.
@retry_test(max_attempts=2)
@pytest.mark.filterwarnings(f"ignore:{_SUMMARIZATION_WARNING_MESSAGE}:UserWarning")
@pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")
@pytest.mark.filterwarnings("ignore:websockets.legacy is deprecated:DeprecationWarning")
@pytest.mark.filterwarnings("ignore:websockets.server.WebSocketServerProtocol:DeprecationWarning")
@pytest.mark.parametrize(
    "file_path", get_all_code_examples_files(), ids=get_all_code_examples_files()
)
def test_code_examples_in_docs_can_be_successfully_run(
    file_path: str,
    tmp_path: str,
    remotely_hosted_llm,
    remote_gemma_llm,
    big_llama,
    test_with_llm_fixture,
    request,
) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-12-03
    Average success time:  6.18 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    globs = {
        "llm_small": remotely_hosted_llm,
        "tmp_path": tmp_path,
        "read_dummy_pdf_file": _read_dummy_pdf_file,
        "mcp_user_query": MCP_USER_QUERY,
        "mcp_example_tool_name": "generate_random_string",
        "vision_llm": remote_gemma_llm,
        "llm_big": big_llama,
    }
    globs["_update_globals"] = make_update_globals(globs, request)
    with open(file_path) as f:
        if "# docs-title:" not in f.read():
            pytest.skip("Docs code example is not ready to be tested")

    if "expired_token" in file_path:
        globs["mock_server_url"] = request.getfixturevalue("mock_server")

    runpy.run_path(file_path, init_globals=globs)
