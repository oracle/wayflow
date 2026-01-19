# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import os
import subprocess
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple, Union

import httpx
import pytest
import yaml

from wayflowcore.datastore import OracleDatabaseConnectionConfig, TlsOracleDatabaseConnectionConfig
from wayflowcore.datastore.oracle import _execute_query_on_oracle_db
from wayflowcore.datastore.postgres import (
    PostgresDatabaseConnectionConfig,
    _execute_query_on_postgres_db,
)

from ..datastores.conftest import (
    all_oracle_tls_connection_config_env_variables_are_specified,
    all_postgres_connection_config_env_variables_are_specified,
    get_postgres_connection_config,
)
from ..utils import LogTee, _terminate_process_tree, get_available_port
from .datastore_agent_server import ORACLE_DB_CREATE_DDL, ORACLE_DB_DELETE_DDL


def _wait_for_http_ready(url: str, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(url, timeout=5.0)
            if resp.status_code < 500:
                return
        except httpx.RequestError:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for server readiness at {url}")


def start_server(
    agent_configs: List[str],
    agent_ids: List[str],
    tool_registry: Optional[str],
    server_storage: str,
    host: str,
    port: int,
    connection_config_file: Optional[str] = None,
    setup_datastore: bool = True,
    timeout: float = 25,
) -> Tuple[subprocess.Popen, str, LogTee]:
    cmd = [
        "wayflow",
        "serve",
        "--port",
        str(port),
        "--host",
        host,
        "--server-storage",
        server_storage,
        "--setup-datastore",
        "yes" if setup_datastore else "no",
    ]
    for single_config_agent in agent_configs:
        cmd.extend(["--agent-config", single_config_agent])
    for single_agent_id in agent_ids:
        cmd.extend(["--agent-id", single_agent_id])

    if tool_registry:
        cmd.extend(["--tool-registry", tool_registry])

    if connection_config_file:
        cmd.extend(["--datastore-connection-config", connection_config_file])

    url = f"http://{host}:{port}"
    print(f"Starting server at {url} with: {' '.join(cmd)}")

    return _run_server(url=url, cmd=cmd, timeout=timeout)


def _run_server(
    url: str,
    cmd: List[str],
    timeout: float,
):
    process: Optional[Any] = None
    try:

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # line-buffered
            start_new_session=True,
        )

        # Tee logs to CI and keep a ring buffer
        if process.stdout is None:
            raise RuntimeError("Failed to capture server stdout")
        tee = LogTee(process.stdout, prefix="[uvicorn] ")
        tee.start()

        # Poll for readiness or early exit
        start = time.time()
        while time.time() - start < timeout:
            rc = process.poll()
            if rc is not None:
                raise RuntimeError(f"Uvicorn exited early with code {rc}.\nLogs:\n{tee.dump()}")

            if _check_server_is_up(url):
                print("Server is up.", flush=True)
                return process, url, tee
            time.sleep(0.2)

        # Timed out
        raise RuntimeError(
            f"Uvicorn server did not start in time ({timeout}s).\nLogs so far:\n{tee.dump()}"
        )
    except Exception as e:
        if process:
            _terminate_process_tree(process, timeout=5.0)
        raise e


def _delete_table(
    datastore_config_obj: Union[PostgresDatabaseConnectionConfig, OracleDatabaseConnectionConfig],
) -> None:
    delete_table_query = "DROP TABLE IF EXISTS conversations;"
    if isinstance(datastore_config_obj, OracleDatabaseConnectionConfig):
        _execute_query_on_oracle_db(
            connection_config=datastore_config_obj, query=delete_table_query
        )
    elif isinstance(datastore_config_obj, PostgresDatabaseConnectionConfig):
        _execute_query_on_postgres_db(
            connection_config=datastore_config_obj, query=delete_table_query
        )
    else:
        raise ValueError(
            f"Should be either an OracleDatabaseConnectionConfig or a PostgresDatabaseConnectionConfig but was {datastore_config_obj}"
        )


def _get_api_key_headers():
    return {"authorization": f"Bearer SOME_FAKE_SECRET"}


def _check_server_is_up(base_url: str) -> bool:
    url = f"{base_url}/v1/models"
    try:
        resp = httpx.get(url, timeout=5.0, headers=_get_api_key_headers())
        return resp.status_code == 200
    except httpx.RequestError:
        return False


def register_wayflow_server_fixture(
    name: str,
    host: str,
    server_storage: str,
    agent_configs: List[str],
    agent_ids: Optional[str] = None,
    tool_registry: Optional[str] = None,
    connection_config_callable: Optional[
        Callable[[], Union[PostgresDatabaseConnectionConfig, OracleDatabaseConnectionConfig]]
    ] = None,
):
    def _fixture(request):
        llama_endpoint = os.environ.get("LLAMA_API_URL")
        new_agent_files = []
        for agent_config in agent_configs:
            agent_config_content = Path(agent_config).read_text()
            agent_config_content_with_url = agent_config_content.replace(
                "LLAMA_API_URL", llama_endpoint
            )
            with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
                f.write(agent_config_content_with_url)
                new_agent_files.append(f.name)

        start_kwargs = {
            "host": host,
            "port": get_available_port(request.getfixturevalue("session_tmp_path")),
            "server_storage": server_storage,
            "agent_configs": new_agent_files,
            "agent_ids": agent_ids,
            "tool_registry": str(tool_registry),
        }

        connection_config = connection_config_callable() if connection_config_callable else None
        if connection_config is not None:
            config_content = {
                "type": connection_config.__class__.__name__,
                **asdict(connection_config),
            }
            with tempfile.NamedTemporaryFile(delete=False, mode="w") as config_file:
                yaml.dump(config_content, config_file)
            _delete_table(connection_config)
            start_kwargs["connection_config_file"] = str(config_file.name)

        process, url, tee = start_server(**start_kwargs)
        try:
            yield url
        finally:
            _terminate_process_tree(process, timeout=5.0)
            tee.stop()

            for new_agent_file in new_agent_files:
                os.remove(new_agent_file)

            if connection_config is not None:
                os.remove(config_file.name)  # type: ignore

                _delete_table(connection_config)

    _fixture = pytest.mark.xdist_group("requires-server-port")(_fixture)
    return pytest.fixture(scope="session", name=name)(_fixture)


TEST_DIR = Path(__file__).resolve().parent

HR_AGENT_PARAMS = dict(
    agent_configs=[
        TEST_DIR / "hr_agent.json",
        TEST_DIR / "simple_flow.json",
    ],
    tool_registry=TEST_DIR / "agent_registry.py",
    agent_ids=["hr-assistant", "simple-flow"],
)


wayflow_server_http_inmemory = register_wayflow_server_fixture(
    name="wayflow_server_http_inmemory",
    host="127.0.0.1",
    **HR_AGENT_PARAMS,
    server_storage="in-memory",
)


def get_oracle_connection_config():
    return TlsOracleDatabaseConnectionConfig(
        user=os.environ["ADB_DB_USER"],
        password=os.environ["ADB_DB_PASSWORD"],
        dsn=os.environ["ADB_DSN"],
        config_dir=os.environ.get("ADB_CONFIG_DIR", None),
    )


wayflow_server_http_postgres = register_wayflow_server_fixture(
    name="wayflow_server_http_postgres",
    **HR_AGENT_PARAMS,
    host="127.0.0.1",
    server_storage="postgres-db",
    connection_config_callable=get_postgres_connection_config,
)

wayflow_server_http_oracle = register_wayflow_server_fixture(
    name="wayflow_server_http_oracle",
    **HR_AGENT_PARAMS,
    host="127.0.0.1",
    server_storage="oracle-db",
    connection_config_callable=get_oracle_connection_config,
)


@pytest.fixture(scope="session")
@pytest.mark.xdist_group("requires-server-port")
def multi_agent_inmemory_server(session_tmp_path):
    available_port = get_available_port(session_tmp_path)
    print(f"Starting a multi-agent server on port {available_port}")
    cmd = ["python", str(TEST_DIR / "multi_agent_server.py"), "--port", str(available_port)]
    url = f"http://127.0.0.1:{available_port}"

    process, url, tee = _run_server(url, cmd, timeout=20)
    try:
        yield url
    finally:
        _terminate_process_tree(process, timeout=5.0)
        tee.stop()


@pytest.fixture(scope="session")
def oracle_db_with_names():
    if not all_oracle_tls_connection_config_env_variables_are_specified():
        pytest.skip("Oracle DB not configured")
    connection_config = get_oracle_connection_config()
    try:
        _execute_query_on_oracle_db(connection_config, ORACLE_DB_DELETE_DDL)
        _execute_query_on_oracle_db(connection_config, ORACLE_DB_CREATE_DDL)
        yield
    finally:
        _execute_query_on_oracle_db(connection_config, ORACLE_DB_DELETE_DDL)


@pytest.fixture(scope="session")
@pytest.mark.xdist_group("requires-server-port")
def datastore_agent_inmemory_server(oracle_db_with_names, session_tmp_path):
    available_port = get_available_port(session_tmp_path)
    print(f"Starting datastore agent server on port {available_port}")
    cmd = ["python", str(TEST_DIR / "datastore_agent_server.py"), "--port", str(available_port)]
    url = f"http://127.0.0.1:{available_port}"

    process, url, tee = _run_server(url, cmd, timeout=20)
    try:
        yield url
    finally:
        _terminate_process_tree(process, timeout=5.0)
        tee.stop()


def get_all_server_fixtures_name():
    server_fixtures_names = ["wayflow_server_http_inmemory"]
    if all_postgres_connection_config_env_variables_are_specified():
        server_fixtures_names.append("wayflow_server_http_postgres")
    if all_oracle_tls_connection_config_env_variables_are_specified():
        server_fixtures_names.append("wayflow_server_http_oracle")
    return server_fixtures_names
