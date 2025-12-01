# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import os
import re
import stat
import sysconfig
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple, TypedDict, Union
from unittest.mock import patch

import pytest
from _pytest.fixtures import FixtureRequest
from dotenv import load_dotenv

from wayflowcore import Message, MessageType
from wayflowcore._threading import shutdown_threadpool
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.mcp import enable_mcp_without_auth
from wayflowcore.mcp.mcphelpers import _reset_mcp_contextvar
from wayflowcore.models import LlmModel, StreamChunkType
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.models.ociclientconfig import (
    OCIClientConfig,
    OCIClientConfigWithUserAuthentication,
    OCIUserAuthenticationConfig,
)
from wayflowcore.models.openaiapitype import OpenAIAPIType
from wayflowcore.steps import OutputMessageStep
from wayflowcore.tools import ToolRequest

if os.environ.get("DEBUG_LEVEL") == "info":
    logging.basicConfig(
        format="%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d:%H:%M:%S",
        level=logging.INFO,
    )
    logging.getLogger("wayflowcore").setLevel(logging.INFO)
else:
    logging.basicConfig(
        format="%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d:%H:%M:%S",
        level=logging.INFO,
    )
    logging.getLogger("wayflowcore").setLevel(logging.DEBUG)


llama_api_url = os.environ.get("LLAMA_API_URL")
if not llama_api_url:
    raise Exception("LLAMA_API_URL is not set in the environment")

oss_api_url = os.environ.get("OSS_API_URL")
if not oss_api_url:
    raise Exception("OSS_API_URL is not set in the environment")

llama70b_api_url = os.environ.get("LLAMA70B_API_URL")
if not llama70b_api_url:
    raise Exception("LLAMA70B_API_URL is not set in the environment")

ollama8bv31_api_url = os.environ.get("OLLAMA8BV32_API_URL")
if not ollama8bv31_api_url:
    raise Exception("OLLAMA8BV32_API_URL is not set in the environment")

oci_reasoning_model_name = os.environ.get("OCI_REASONING_MODEL")
if not oci_reasoning_model_name:
    raise Exception("OCI_REASONING_MODEL is not set in the environment")

gemma_api_url = os.environ.get("GEMMA_API_URL")
if not gemma_api_url:
    raise Exception("GEMMA_API_URL is not set in the environment")

e5large_api_url = os.environ.get("E5largev2_EMBEDDING_API_URL")
if not e5large_api_url:
    raise ValueError("E5largev2_EMBEDDING_API_URL is not set in the environment")

ollama_embedding_api_url = os.environ.get("OLLAMA_EMBEDDING_API_URL")
if not ollama_embedding_api_url:
    raise ValueError("OLLAMA_EMBEDDING_API_URL is not set in the environment")

compartment_id = os.environ.get("COMPARTMENT_ID")
if not compartment_id:
    raise Exception("compartment_id is not set in the environment")

oracle_http_proxy = os.environ.get("ORACLE_HTTP_PROXY")

import shutil
import tempfile

import pytest


@pytest.fixture(scope="session")
def session_tmp_path():
    """Session-scoped temp path"""
    dirpath = tempfile.mkdtemp()
    yield dirpath
    shutil.rmtree(dirpath)


def reset_http_proxy():
    for env_var in ["HTTP_PROXY", "http_proxy"]:
        if env_var in os.environ:
            del os.environ[env_var]


def pytest_sessionstart(session):
    # remove http proxy from the local environment to ensure successful OCI and VLLM models connection
    reset_http_proxy()
    load_dotenv()


INSTANCE_PRINCIPAL_ENDPOINT_BASE_URL = os.environ.get("INSTANCE_PRINCIPAL_ENDPOINT_BASE_URL")
if not INSTANCE_PRINCIPAL_ENDPOINT_BASE_URL:
    raise Exception("INSTANCE_PRINCIPAL_ENDPOINT_BASE_URL is not set in the environment")


DUMMY_OCI_USER_CONFIG_DICT = {
    "user": "ocid1.user.oc1..aaaaaaaa",
    "key_content": "key_content",
    "fingerprint": "aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa",
    "tenancy": "ocid1.tenancy.oc1..aaaaaaaa",
    "region": "us-chicago-1",
}


@pytest.fixture
def dummy_oci_client_config_with_user_authentication():
    user_config = OCIUserAuthenticationConfig(
        DUMMY_OCI_USER_CONFIG_DICT["user"],
        DUMMY_OCI_USER_CONFIG_DICT["key_content"],
        DUMMY_OCI_USER_CONFIG_DICT["fingerprint"],
        DUMMY_OCI_USER_CONFIG_DICT["tenancy"],
        DUMMY_OCI_USER_CONFIG_DICT["region"],
    )
    return OCIClientConfigWithUserAuthentication(
        service_endpoint=COHERE_OCI_API_KEY_CONFIG["client_config"]["service_endpoint"],
        compartment_id=COHERE_OCI_API_KEY_CONFIG["client_config"]["compartment_id"],
        user_config=user_config,
    )


@pytest.fixture
def oci_user_authentication_config():
    oci_config_file_path = "~/.oci/config"
    if not Path(oci_config_file_path).expanduser().exists():
        pytest.skip("Skipping test because it requires a valid oci user config")

    import oci

    oci_config = oci.config.from_file(file_location=oci_config_file_path)
    key_file_path = oci_config.pop("key_file")
    oci_config["key_content"] = Path(key_file_path).expanduser().read_text()

    oci_user_auth_config = OCIUserAuthenticationConfig(
        user=oci_config["user"],
        key_content=oci_config["key_content"],
        fingerprint=oci_config["fingerprint"],
        tenancy=oci_config["tenancy"],
        region=oci_config["region"],
    )

    return OCIClientConfigWithUserAuthentication(
        service_endpoint=COHERE_OCI_API_KEY_CONFIG["client_config"]["service_endpoint"],
        compartment_id=COHERE_OCI_API_KEY_CONFIG["client_config"]["compartment_id"],
        user_config=oci_user_auth_config,
    )


VLLM_MODEL_CONFIG = {
    "model_type": "vllm",
    "host_port": llama_api_url,
    "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "generation_config": {"max_tokens": 512},
}

VLLM_OSS_CONFIG = {
    "model_type": "vllm",
    "host_port": oss_api_url,
    "model_id": "openai/gpt-oss-120b",
    "generation_config": {"max_tokens": 512},
    "api_type": OpenAIAPIType.RESPONSES,
}

VLLM_OSS_REASONING_CONFIG = {
    "model_type": "vllm",
    "host_port": oss_api_url,
    "model_id": "openai/gpt-oss-120b",
    "generation_config": {"max_tokens": 4096, "reasoning": {"effort": "high"}},
    "api_type": OpenAIAPIType.RESPONSES,
}

OPENAI_COMPATIBLE_MODEL_CONFIG = {
    "model_type": "openaicompatible",
    "base_url": llama_api_url,
    "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "generation_config": {"max_tokens": 512},
    "supports_structured_generation": True,
    "supports_tool_calling": True,
}

OPENAI_CONFIG = {
    "model_type": "openai",
    "model_id": "gpt-4o-mini",
    "proxy": oracle_http_proxy,
    "generation_config": {"max_tokens": 512},
}

OPENAI_RESPONSES_CONFIG = {
    "model_type": "openai",
    "model_id": "gpt-5-mini",
    "proxy": oracle_http_proxy,
    "generation_config": {"max_tokens": 512, "reasoning": {"effort": "minimal"}},
    "api_type": OpenAIAPIType.RESPONSES,
}

OPENAI_REASONING_RESPONSES_CONFIG = {
    "model_type": "openai",
    "model_id": "gpt-5",
    "proxy": oracle_http_proxy,
    "generation_config": {"max_tokens": 4096, "reasoning": {"effort": "high"}},
    "api_type": OpenAIAPIType.RESPONSES,
}

GEMMA_CONFIG = {
    "model_type": "vllm",
    "host_port": gemma_api_url,
    "model_id": "google/gemma-3-27b-it",
}


OPENAI_REASONING_CONFIG = {
    "model_type": "openai",
    "model_id": "o3-mini",
    "proxy": oracle_http_proxy,
    "generation_config": {"max_tokens": 512},
}

COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG = {
    "model_type": "ocigenai",
    "model_id": "cohere.command-r-plus-08-2024",
    "client_config": {
        "service_endpoint": f"{INSTANCE_PRINCIPAL_ENDPOINT_BASE_URL}/cohere",
        "compartment_id": compartment_id,
        "auth_type": "INSTANCE_PRINCIPAL",
    },
    "generation_config": {"max_tokens": 512},
}

COHERE_OCI_API_KEY_CONFIG = {
    "model_type": "ocigenai",
    "model_id": "cohere.command-r-plus-08-2024",
    "client_config": {
        "service_endpoint": "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        "compartment_id": compartment_id,
        "auth_type": "API_KEY",
    },
    "generation_config": {"max_tokens": 512},
}

LLAMA_OCI_INSTANCE_PRINCIPAL_CONFIG = {
    "model_type": "ocigenai",
    "model_id": "meta.llama-3.3-70b-instruct",
    "client_config": {
        "service_endpoint": f"{INSTANCE_PRINCIPAL_ENDPOINT_BASE_URL}/llama",
        "compartment_id": compartment_id,
        "auth_type": "INSTANCE_PRINCIPAL",
    },
    "generation_config": {"max_tokens": 512},
}

LLAMA_OCI_API_KEY_CONFIG = {
    "model_type": "ocigenai",
    "model_id": "meta.llama-3.3-70b-instruct",
    "client_config": {
        "service_endpoint": "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        "compartment_id": compartment_id,
        "auth_type": "API_KEY",
    },
    "generation_config": {"max_tokens": 512},
}

LLAMA_4_OCI_API_KEY_CONFIG = {
    "model_type": "ocigenai",
    "model_id": "meta.llama-4-scout-17b-16e-instruct",
    "client_config": {
        "service_endpoint": "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        "compartment_id": compartment_id,
        "auth_type": "API_KEY",
    },
    "generation_config": {"max_tokens": 512},
}


GROK_OCI_API_KEY_CONFIG = {
    "model_type": "ocigenai",
    "model_id": "xai.grok-3-mini",
    "client_config": {
        "service_endpoint": "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        "compartment_id": compartment_id,
        "auth_type": "API_KEY",
    },
    "generation_config": {"max_tokens": 1024},
}

OCI_REASONING_MODEL_API_KEY_CONFIG = {
    "model_type": "ocigenai",
    "model_id": oci_reasoning_model_name,
    "client_config": {
        "service_endpoint": "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        "compartment_id": compartment_id,
        "auth_type": "API_KEY",
    },
    "generation_config": {"max_tokens": 2000},
}

OLLAMA_MODEL_CONFIG = {
    "model_type": "ollama",
    "host_port": ollama8bv31_api_url,  # example: 8.8.8.8:8000
    "model_id": "llama3.1",
    "generation_config": {"max_tokens": 512},
}

BIG_VLLM_CONFIG = {
    "model_type": "vllm",
    "host_port": llama70b_api_url,
    "model_id": "/storage/models/Llama-3.1-70B-Instruct",
    "generation_config": {"max_tokens": 512},
}

ALL_VLLM_CONFIGS = [VLLM_MODEL_CONFIG]

with_all_llm_configs = pytest.mark.parametrize(
    "llm_config",
    argvalues=ALL_VLLM_CONFIGS,
    ids=[config["model_type"] for config in ALL_VLLM_CONFIGS],
)


# some functions require internet connection and make requests to remote LLMs.
# the goal is to be able to skip tests that require them (which are probably long and expensive to run)
# to run some quick unit tests
SKIP_LLM_TESTS_ENV_VAR = "SKIP_LLM_TESTS"

LLM_MOCKED_METHODS = [
    "wayflowcore.models.ocigenaimodel.OCIGenAIModel._init_client_if_needed",
    "wayflowcore.models.ociclientconfig.OCIUserAuthenticationConfig.__init__",
    "wayflowcore.embeddingmodels.openaicompatiblemodel.OpenAICompatibleEmbeddingModel.embed",
    "wayflowcore.executors._ociagentexecutor._init_oci_agent_client",
]
LLM_MOCKED_METHODS_ASYNC = [
    "wayflowcore.models.openaicompatiblemodel.OpenAICompatibleModel._post",
]
LLM_MOCKED_ASYNC_METHODS = [
    "wayflowcore.models.openaicompatiblemodel.OpenAICompatibleModel._post_stream",
]


@pytest.fixture(autouse=True)
def skip_test_fixture():
    """
    Auto-used fixture that patches LLM methods so that if they are called,
    the test is skipped in a thread-safe way.
    """

    def skip_callable(*args, **kwargs):
        pytest.skip("LM called, skipping test")

    async def skip_callable_async(*args, **kwargs):
        pytest.skip("LM called, skipping test")

    async def skip_callable_stream(*args, **kwargs):
        pytest.skip("LM called, skipping test")
        yield

    patches = []
    if should_skip_llm_test():
        for method_name in LLM_MOCKED_METHODS:
            p = patch(method_name, side_effect=skip_callable)
            patches.append(p)
            p.start()
        for method_name in LLM_MOCKED_ASYNC_METHODS:
            p = patch(method_name, side_effect=skip_callable_stream)
            patches.append(p)
            p.start()
        for method_name in LLM_MOCKED_METHODS_ASYNC:
            p = patch(method_name, side_effect=skip_callable_async)
            patches.append(p)
            p.start()

    yield  # Test runs here

    for p in patches:
        p.stop()


@pytest.fixture
def test_with_llm_fixture():
    if should_skip_llm_test():
        pytest.skip("Skipping test requiring a LLM")


def should_skip_llm_test() -> bool:
    return SKIP_LLM_TESTS_ENV_VAR in os.environ


@pytest.fixture
def cleanup_env():
    yield
    from wayflowcore.executors._agentexecutor import _DISABLE_STREAMING

    if _DISABLE_STREAMING in os.environ:
        os.environ.pop(_DISABLE_STREAMING)


@pytest.fixture
def shutdown_threadpool_fixture():
    yield
    shutdown_threadpool()


def skip_callable(*args, **kwargs):
    pytest.skip("Skipping test because it requires an LLM")


def assert_str_equal_ignoring_white_space(str_1: str, str_2: str) -> None:
    white_space_regex = re.compile(r"\s")
    assert white_space_regex.sub("", str_1) == white_space_regex.sub("", str_2)


@pytest.fixture
def remotely_hosted_llm():
    return LlmModelFactory.from_config(VLLM_MODEL_CONFIG)


def mock_llm():
    return LlmModelFactory.from_config(
        {
            "model_type": "vllm",
            "host_port": "mock.com",
            "model_id": "super-smart",
        }
    )


ToolRequestT = TypedDict(
    "ToolRequestT",
    {"name": str, "args": Dict[str, Any], "tool_request_id": str},
    total=False,
)


def patch_streaming_llm(
    llm: LlmModel,
    text_output: Optional[str] = None,
    tool_requests: Optional[Sequence[Union[ToolRequest, ToolRequestT]]] = None,
):
    async def stream(*args, **kwargs):
        yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT), None
        yield StreamChunkType.TEXT_CHUNK, Message(content="", message_type=MessageType.AGENT), None
        yield StreamChunkType.END_CHUNK, Message(
            content=text_output or "",
            role="assistant",
            tool_requests=(
                [
                    (
                        t
                        if isinstance(t, ToolRequest)
                        else ToolRequest(
                            name=t.get("name"),
                            args=t.get("args", {}),
                        )
                    )
                    for t in tool_requests
                ]
                if tool_requests is not None
                else None
            ),
        ), None

    return patch.object(
        llm,
        "_stream_generate_impl",
        side_effect=stream,
    )


@pytest.fixture
def remote_gemma_llm():
    return LlmModelFactory.from_config(GEMMA_CONFIG)


@pytest.fixture
def grok_oci_llm():
    return LlmModelFactory.from_config(GROK_OCI_API_KEY_CONFIG)


@contextmanager
def patched_vllm_llm(llm: LlmModel, txt: str):
    async def iterator():
        yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT), None
        yield StreamChunkType.TEXT_CHUNK, Message(content=txt, message_type=MessageType.AGENT), None
        yield StreamChunkType.END_CHUNK, llm.agent_template.output_parser.parse_output(
            Message(content=txt, message_type=MessageType.AGENT)
        ), None

    with patch.object(
        llm, "_post", return_value={"choices": [{"message": {"content": txt}}]}
    ), patch.object(
        llm,
        "_post_stream",
        return_value=iterator(),
    ):
        yield


# requires an OPEN_AI API key to use this fixture
@pytest.fixture
def gpt_llm():
    if not "OPENAI_TESTS" in os.environ:
        pytest.skip("Requires an OPENAI API key")
    return LlmModelFactory.from_config(OPENAI_CONFIG)


@pytest.fixture
def gpt_reasoning_llm():
    if not "OPENAI_TESTS" in os.environ:
        pytest.skip("Requires an OPENAI API key")
    return LlmModelFactory.from_config(OPENAI_REASONING_CONFIG)


@pytest.fixture
def cohere_llm():
    if not ("OCI_GENAI_API_KEY_CONFIG" in os.environ and "OCI_GENAI_API_KEY_PEM" in os.environ):
        pytest.skip("OCI GENAI models not configured")
    return LlmModelFactory.from_config(COHERE_OCI_API_KEY_CONFIG)


@pytest.fixture
def llama_oci_llm():
    if not ("OCI_GENAI_API_KEY_CONFIG" in os.environ and "OCI_GENAI_API_KEY_PEM" in os.environ):
        pytest.skip("OCI GENAI models not configured")
    return LlmModelFactory.from_config(LLAMA_OCI_API_KEY_CONFIG)


@pytest.fixture
def oci_agent_client_config():
    if not (
        "OCI_GENAI_API_KEY_CONFIG" in os.environ
        and "OCI_GENAI_API_KEY_PEM" in os.environ
        and "OCI_GENAI_SERVICE_ENDPOINT" in os.environ
    ):
        pytest.skip("OCI Agent client config not configured")
    oci_genai_service_endpoint = os.environ.get("OCI_GENAI_SERVICE_ENDPOINT")
    return OCIClientConfig.from_dict(
        {
            "service_endpoint": oci_genai_service_endpoint,
            "compartment_id": "",
            "auth_type": "API_KEY",
        }
    )


@pytest.fixture
def oci_reasoning_model() -> LlmModel:
    if not ("OCI_GENAI_API_KEY_CONFIG" in os.environ and "OCI_GENAI_API_KEY_PEM" in os.environ):
        pytest.skip("OCI GENAI models not configured")
    return LlmModelFactory.from_config(OCI_REASONING_MODEL_API_KEY_CONFIG)


@pytest.fixture
def big_llama():
    return LlmModelFactory.from_config(BIG_VLLM_CONFIG)


def get_single_step_flow():
    return create_single_step_flow(OutputMessageStep("Any message"))


def _assert_config_are_equal(config1: Dict[str, Any], config2: Dict[str, Any]):
    """
    Asserts that two configs are equal, modulo object ids used in $ref fields and _referenced_objects.
    """

    # To track which (id1, id2) pairs we already compared for cycle avoidance
    compared_ids: Set[Tuple[str, str]] = set()

    def eq(obj1, obj2, refs1, refs2):
        # Fast path for exact value equality
        if obj1 is obj2:
            return True

        # $ref handling
        if (
            isinstance(obj1, dict)
            and isinstance(obj2, dict)
            and set(obj1.keys()) == {"$ref"}
            and set(obj2.keys()) == {"$ref"}
        ):
            ref1 = obj1["$ref"]
            ref2 = obj2["$ref"]
            pair = (ref1, ref2)
            if pair in compared_ids:
                return True  # already checked this pair
            compared_ids.add(pair)

            if ref1 not in refs1 or ref2 not in refs2:
                raise AssertionError(f"Missing $ref: {ref1} or {ref2}")
            # Recursively compare referenced objects
            if not eq(refs1[ref1], refs2[ref2], refs1, refs2):
                raise AssertionError(f"Referenced object mismatch for refs {ref1} and {ref2}")
            return True

        # Dict: compare keys and values
        if isinstance(obj1, dict) and isinstance(obj2, dict):
            # All keys should be the same
            if set(obj1.keys()) != set(obj2.keys()):
                raise AssertionError(
                    f"Dict keys mismatch: {set(obj1.keys())} != {set(obj2.keys())}"
                )
            # Compare each field
            for k in obj1:
                if (
                    # references are unique per config and cannot be checked directly.
                    # We verify them when they are used in the config.
                    k != "_referenced_objects"
                    and k != "id"
                    and not eq(obj1[k], obj2[k], refs1, refs2)
                ):
                    raise AssertionError(f"Dict field '{k}' mismatch")
            return True

        # List: element-wise compare
        if isinstance(obj1, list) and isinstance(obj2, list):
            if len(obj1) != len(obj2):
                raise AssertionError("List length mismatch")
            for v1, v2 in zip(obj1, obj2):
                if not eq(v1, v2, refs1, refs2):
                    raise AssertionError("List element mismatch")
            return True

        # Otherwise, compare directly
        if obj1 != obj2:
            raise AssertionError(f"Value mismatch: {obj1!r} != {obj2!r}")
        return True

    # top-level _referenced_objects extract
    try:
        refs1 = config1["_referenced_objects"]
        refs2 = config2["_referenced_objects"]
    except KeyError:
        raise AssertionError("Both configs must have a '_referenced_objects' field")

    # Compare the full objects, not just the referenced ones.
    eq(config1, config2, refs1, refs2)


@pytest.fixture
def requires_langchain():
    try:
        pass
    except ImportError:
        pytest.skip("Skipping test because requires langchain")


class TestError(Exception):
    """TestError

    The base exception from which all exceptions raised by test
    will inherit.
    """


class TestOSError(OSError, TestError):
    """Exception raised for I/O related error."""


def check_file_permissions(path):
    """Check that the permissions on a file are rw only for the user,
    and rwx user-only for directories.
    """

    if os.path.isdir(path):
        st_mode = os.stat(path).st_mode
        # Owner has rwx access
        assert st_mode & stat.S_IRWXU
        # everyone else has no access
        assert not (st_mode & (stat.S_IRWXG | stat.S_IRWXO))
    elif os.path.exists(path):
        st_mode = os.stat(path).st_mode
        # Owner has rw access
        assert st_mode & (stat.S_IRUSR | stat.S_IWUSR)
        # everyone else has no access and user does not have x access
        assert not (st_mode & (stat.S_IRWXG | stat.S_IRWXO))


def get_directory_allowlist_write(tmp_path: str, session_tmp_path: str) -> List[Union[str, Path]]:
    std_paths = sysconfig.get_paths()
    return [
        std_paths.get("purelib"),  # Allow packages to r/w their pycache
        std_paths.get("platlib"),
        tmp_path,
        session_tmp_path,
        "/dev/null",
    ]


def get_directory_allowlist_read(tmp_path: str, session_tmp_path: str) -> List[Union[str, Path]]:
    allowed_paths = get_directory_allowlist_write(tmp_path, session_tmp_path) + [
        Path(os.path.dirname(__file__)) / "configs",
        Path(os.path.dirname(__file__)) / "agentspec" / "configs",
        Path(os.path.dirname(__file__)) / "datastores" / "entities.json",
        Path("~/.oci/config").expanduser(),
        # Used in docstring tests
        Path(os.path.dirname(__file__)).parent / "src" / "wayflowcore",
        Path("~/.pdbrc").expanduser(),
        Path(os.path.dirname(__file__)) / ".pdbrc",
        Path(os.path.dirname(__file__)).parent / ".pdbrc",
        Path(os.path.dirname(__file__)).parent.parent / ".pdbrc",
        Path(os.path.dirname(__file__)).parent.parent.parent / ".pdbrc",
        # Used in docs test
        Path(os.path.dirname(__file__)).parents[1] / "docs" / "wayflowcore" / "source" / "core",
        # Used by OCI package to get OS information / read configurations
        Path("/System/Library/CoreServices/SystemVersion.plist"),
        Path("/usr/share/zoneinfo/UTC"),
    ]
    # Dynamically add the wallet location from the environment variable
    wallet_location = os.getenv("ADB_WALLET_DIR")
    if wallet_location:
        allowed_paths.append(os.path.abspath(wallet_location))
    return allowed_paths


def check_allowed_filewrite(
    path: Union[str, Path], tmp_path: str, session_tmp_path: str, mode: str
) -> None:
    path = os.path.abspath(path)
    if mode == "r" or mode == "rb":
        assert any(
            [
                Path(dir) in Path(path).parents or Path(dir) == Path(path)
                for dir in get_directory_allowlist_read(
                    tmp_path=tmp_path, session_tmp_path=session_tmp_path
                )
            ]
        ), f"Reading outside of allowed directories! {path}"
    else:
        assert any(
            [
                Path(dir) in Path(path).parents or Path(dir) == Path(path)
                for dir in get_directory_allowlist_write(
                    tmp_path=tmp_path, session_tmp_path=session_tmp_path
                )
            ]
        ), f"Writing outside of allowed directories! {path}"


@contextmanager
def limit_filewrites(
    monkeypatch: Any, tmp_path: str, session_tmp_path: str, allowed_access_enabled: bool = True
) -> Iterator[bool]:
    import builtins

    _open = builtins.open

    def patched_open(name, *args, **kwargs):
        if not allowed_access_enabled:
            raise IOError("File is being accessed when it shouldn't have")
        # Sometimes, a process might write in a local path named with a number
        # For instance:
        # /proc/stat/8274921/ <--- correct
        # /proc/stat/8103810/ <--- correct
        # 8                   <--- incorrect
        # /proc/stat/6183016/ <--- correct
        # not sure why this happens, but it will fail test_selection in test_cache_writes
        if not isinstance(name, int):
            # Mode can be either in *args or **kwargs, if it's not, the default is "r"
            mode = "w" if "w" in args else "r"
            mode = kwargs.get("mode", mode)
            check_allowed_filewrite(
                name, tmp_path=tmp_path, session_tmp_path=session_tmp_path, mode=mode
            )
        return _open(name, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(builtins, "open", patched_open)
        yield True


@pytest.fixture(scope="function", autouse=True)
def guard_filewrites(
    request: FixtureRequest, monkeypatch: Any, tmp_path: str, session_tmp_path: str
) -> Iterator[bool]:
    """Fixture which raises an exception if the filesystem is accessed
    outside of a limited set of allowed directories (pycache, automlx
    cache dir, ...)
    """
    if request.node.get_closest_marker("skip_guard_filewrites"):
        yield True
    else:
        with limit_filewrites(
            monkeypatch,
            tmp_path=tmp_path,
            session_tmp_path=session_tmp_path,
            allowed_access_enabled=True,
        ) as x:
            yield x


@pytest.fixture(scope="function")
def guard_all_filewrites(monkeypatch: Any, tmp_path: str, session_tmp_path: str) -> Iterator[bool]:
    """Fixture which raises an exception if the filesystem is accessed."""
    with limit_filewrites(
        monkeypatch,
        tmp_path=tmp_path,
        session_tmp_path=session_tmp_path,
        allowed_access_enabled=False,
    ) as x:
        yield x


@pytest.fixture
def with_mcp_enabled():
    try:
        enable_mcp_without_auth()
        yield
    finally:
        _reset_mcp_contextvar()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# This hook is called after whole test run finished, right before returning the exit status to the system.
# see https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_sessionfinish
# This check is added  so that in case there is a thread is still open,
# logs will show it and we will be able to investigate.
def pytest_sessionfinish(session, exitstatus):
    threads = [t for t in threading.enumerate() if t is not threading.main_thread()]
    if threads:
        text = "Non-main threads still running at end of tests\n" + "\n".join(
            f"{t.name}: {t.daemon}, {t.is_alive()}" for t in threads
        )
        raise ValueError(text)
