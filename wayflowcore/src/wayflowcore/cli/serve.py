# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

import argparse
import importlib
import sys
import warnings
from dataclasses import fields
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple, Union, cast

import yaml

from wayflowcore.agentserver import ServerStorageConfig
from wayflowcore.agentserver._storagehelpers import (
    _prepare_oracle_datastore,
    _prepare_postgres_datastore,
)
from wayflowcore.agentserver.app import create_server_app
from wayflowcore.agentspec import AgentSpecLoader
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.datastore import (
    Datastore,
    InMemoryDatastore,
    OracleDatabaseConnectionConfig,
    OracleDatabaseDatastore,
)
from wayflowcore.datastore.oracle import (
    MTlsOracleDatabaseConnectionConfig,
    TlsOracleDatabaseConnectionConfig,
)
from wayflowcore.datastore.postgres import (
    PostgresDatabaseConnectionConfig,
    PostgresDatabaseDatastore,
    TlsPostgresDatabaseConnectionConfig,
)
from wayflowcore.tools import ServerTool

__all__ = ["add_parser", "serve"]

ApiType = Literal["openai-responses"]
PersistenceType = Literal["in-memory", "oracle-db", "postgres-db"]


class _CollectListAction(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None,
    ) -> None:
        existing = getattr(namespace, self.dest, None)
        collected = list(existing) if isinstance(existing, list) else []
        if isinstance(values, list):
            collected.extend(values)
        elif isinstance(values, str):
            collected.append(values)
        setattr(namespace, self.dest, collected)


def add_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "serve",
        help="Run a WayFlow agent in a FastAPI server.",
        description="Launch a WayFlow server hosting agents with the selected API protocol.",
    )
    _configure_parser(parser)
    return parser


def _configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--api",
        choices=["openai-responses"],
        default="openai-responses",
        help="Protocol to expose (default: openai-responses).",
    )
    parser.add_argument(
        "--agent-config",
        nargs="+",
        action=_CollectListAction,
        default=None,
        help="Path to the agent specification file (default: agent.json).",
    )
    parser.add_argument(
        "--agent-id",
        nargs="+",
        action=_CollectListAction,
        default=None,
        help="Identifier used by clients to select the hosted agent (default: my-agent).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port to bind the server to (default: 3000).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind to (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--tool-registry",
        help="Optional path to a Python module exposing a `tool_registry` dictionary for agent server tools.",
    )
    parser.add_argument(
        "--server-storage",
        choices=["in-memory", "oracle-db", "postgres-db"],
        default="in-memory",
        help="Persistence backend for conversations (default: in-memory).",
    )
    parser.add_argument(
        "--server-storage-config",
        help="Optional YAML file overriding ServerStorageConfig defaults.",
    )
    parser.add_argument(
        "--datastore-connection-config",
        help="YAML file containing the type of connection to use and its configuration.\n"
        "For example: `type: TlsPostgresDatabaseConnectionConfig\nuser: my_user\npassword: my_password\nurl:localhost:7777`",
    )
    parser.add_argument(
        "--setup-datastore",
        choices=["no", "yes"],
        default="no",
        help="Whether to create or reset datastore tables when supported (default: no). It will NOT delete any existing table, you should do it first.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Optional api key to add an authentication layer to the server. This API_KEY will be required on requests as a bearer token in the headers: "
        "{'authorization': 'Bearer SOME_FAKE_SECRET'}",
    )
    parser.set_defaults(handler=_run_serve)


def _run_serve(args: argparse.Namespace) -> None:
    try:
        raw_agent_config = args.agent_config or ["agent.json"]
        agent_config_paths = [Path(config).expanduser() for config in raw_agent_config]
        missing = [path for path in agent_config_paths if not path.is_file()]
        if missing:
            missing_str = ", ".join(str(path) for path in missing)
            raise FileNotFoundError(f"Agent config file not found: {missing_str}")

        agent_ids = args.agent_id or ["my-agent"]

        if len(agent_config_paths) != len(agent_ids):
            raise ValueError(
                "You must specify the same number of --agent-config and --agent-id values."
            )

        tool_registry_path = None
        if args.tool_registry is not None:
            tool_registry_path = Path(args.tool_registry).expanduser()
            if not tool_registry_path.is_file():
                raise FileNotFoundError(f"Tool registry file not found: {tool_registry_path}")

        storage_config = _load_server_storage_config(args.server_storage_config)

        datastore_config_obj = None
        storage_type: PersistenceType = args.server_storage
        api: ApiType = args.api
        if storage_type in {"oracle-db", "postgres-db"}:
            config_path = args.datastore_connection_config
            if not config_path:
                config_path = _prompt_for_config_path(storage_type)
            datastore_config_obj = _load_datastore_connection_config(
                Path(config_path).expanduser(),
                storage_type=storage_type,
            )
        elif args.datastore_connection_config:
            warnings.warn(
                "Warning: --datastore-connection-config is ignored for in-memory storage."
            )

        serve(
            api=api,
            agent_configs=agent_config_paths,
            agent_ids=agent_ids,
            port=args.port,
            host=args.host,
            tool_registry=tool_registry_path,
            server_storage=storage_type,
            storage_config=storage_config,
            datastore_connection_config=datastore_config_obj,
            setup_datastore=args.setup_datastore == "yes",
            api_key=args.api_key,
        )
    except KeyboardInterrupt:
        print("Received keyboard interrupt, exiting ...")
        raise
    except (FileNotFoundError, ValueError, TypeError, NotImplementedError, yaml.YAMLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def serve(
    api: ApiType,
    agent_configs: List[Path],
    agent_ids: List[str],
    port: int,
    host: str,
    tool_registry: Optional[Path],
    server_storage: PersistenceType,
    storage_config: Optional[ServerStorageConfig],
    datastore_connection_config: Optional[Any],
    setup_datastore: bool = False,
    api_key: Optional[str] = None,
) -> None:

    agents: dict[str, ConversationalComponent] = {}
    if len(agent_configs) != len(agent_ids):
        raise ValueError("You specified different numbers of agents and configs")

    for single_agent_config, single_agent_id in zip(agent_configs, agent_ids):
        assistant = _load_agent(
            file_path=str(single_agent_config),
            tool_registry=tool_registry,
        )
        agents[single_agent_id] = assistant

    storage, resolved_storage_config = _get_persistence_arguments(
        persistence=server_storage,
        storage_config=storage_config,
        datastore_connection_config=datastore_connection_config,
        setup_datastore=setup_datastore,
    )

    app = create_server_app(
        api=api,
        agents=agents,
        storage=storage,
        storage_config=resolved_storage_config,
    )
    app.run(
        port=port,
        host=host,
        api_key=api_key,
    )


def _load_agent(file_path: str, tool_registry: Optional[Path] = None) -> ConversationalComponent:
    tool_registry_mapping: Dict[str, ServerTool | Callable[..., Any]] = {}
    if tool_registry is not None:
        tool_registry_mapping = _load_registry(tool_registry)
    agent_spec_loader = AgentSpecLoader(tool_registry=tool_registry_mapping)

    with open(file_path, "r", encoding="utf-8") as f:
        serialized_agent = f.read()

    agent = agent_spec_loader.load_json(serialized_agent)
    return cast(ConversationalComponent, agent)


def _load_registry(file_path: Path) -> dict[str, ServerTool | Callable[..., Any]]:
    module_name = file_path.stem
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    registry_package = importlib.util.module_from_spec(spec)  # type: ignore
    if spec.loader is None:  # type: ignore
        raise ImportError(f"Could not load module from {file_path}")
    spec.loader.exec_module(registry_package)  # type: ignore

    if not hasattr(registry_package, "tool_registry"):
        raise ValueError("The tool registry file does not have any variable named `tool_registry`.")
    registry = registry_package.tool_registry

    if not isinstance(registry, dict) or not all(
        isinstance(tool, ServerTool) or callable(tool) for tool in registry.values()
    ):
        raise ValueError(f"All values of the registry should be tools: {registry}")

    return cast(dict[str, ServerTool | Callable[..., Any]], registry)


def _get_persistence_arguments(
    persistence: PersistenceType,
    storage_config: Optional[ServerStorageConfig] = None,
    datastore_connection_config: Optional[Any] = None,
    setup_datastore: bool = False,
) -> Tuple[Datastore, ServerStorageConfig]:
    storage_config = storage_config or ServerStorageConfig()
    storage_schema = storage_config.to_schema()
    storage: Datastore
    match persistence:
        case "postgres-db":
            if datastore_connection_config is None:
                raise ValueError(
                    "Postgres persistence requires a datastore connection configuration."
                )
            if not isinstance(
                datastore_connection_config,
                TlsPostgresDatabaseConnectionConfig,
            ):
                raise TypeError(
                    "datastore_connection_config must be a PostgresDatabaseConnectionConfig instance."
                )
            if setup_datastore:
                _prepare_postgres_datastore(datastore_connection_config, storage_config)
            storage = PostgresDatabaseDatastore(
                schema=storage_schema,
                connection_config=datastore_connection_config,
            )
            return storage, storage_config
        case "in-memory":
            return InMemoryDatastore(schema=storage_schema), storage_config
        case "oracle-db":
            if datastore_connection_config is None:
                raise ValueError(
                    "Oracle persistence requires a datastore connection configuration."
                )
            if not isinstance(
                datastore_connection_config,
                (TlsOracleDatabaseConnectionConfig, MTlsOracleDatabaseConnectionConfig),
            ):
                raise TypeError(
                    "datastore_connection_config must be an OracleDatabaseConnectionConfig instance."
                )
            if setup_datastore:
                _prepare_oracle_datastore(datastore_connection_config, storage_config)
            storage = OracleDatabaseDatastore(
                schema=storage_schema,
                connection_config=datastore_connection_config,
            )
            return storage, storage_config
        case _:
            raise NotImplementedError(f"Persistence layer not implemented: {persistence}")


def _prompt_for_config_path(storage_type: PersistenceType) -> str:
    prompt = (
        f"Enter path to the datastore connection configuration required for `{storage_type}` "
        "(press Ctrl-D to cancel): "
    )
    try:
        response = input(prompt)
    except EOFError as exc:
        raise SystemExit("Datastore connection configuration is required.") from exc

    trimmed = response.strip()
    if not trimmed:
        raise SystemExit("Datastore connection configuration is required.")
    return trimmed


def _load_yaml_dict(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in YAML file: {path}")
    return loaded


def _load_server_storage_config(path_str: Optional[str]) -> Optional[ServerStorageConfig]:
    if path_str is None:
        return None
    config_path = Path(path_str).expanduser()
    data = _load_yaml_dict(config_path)
    allowed_fields = {
        field.name for field in fields(ServerStorageConfig) if field.name != "datastore"
    }
    unknown_fields = set(data) - allowed_fields
    if unknown_fields:
        unknown_str = ", ".join(sorted(unknown_fields))
        raise ValueError(f"Unknown ServerStorageConfig fields: {unknown_str}")
    filtered = {key: data[key] for key in allowed_fields if key in data}
    return ServerStorageConfig(**filtered)


def _load_datastore_connection_config(
    path: Path,
    storage_type: PersistenceType,
) -> OracleDatabaseConnectionConfig | PostgresDatabaseConnectionConfig:
    data = _load_yaml_dict(path)
    raw_type = data.pop("type", None)
    if raw_type is None:
        raise ValueError(
            "The connection config should have a `type` field equal to the name of the connection config object to use."
        )
    raw_type = str(raw_type)

    if storage_type == "postgres-db":
        if raw_type == "TlsPostgresDatabaseConnectionConfig":
            return TlsPostgresDatabaseConnectionConfig(**data)
        else:
            raise ValueError(
                f"For postgres storage type `{raw_type}`, the connection config type should be `TlsPostgresDatabaseConnectionConfig` but got `{raw_type}`"
            )

    if storage_type == "oracle-db":
        if raw_type == "TlsOracleDatabaseConnectionConfig":
            return TlsOracleDatabaseConnectionConfig(**data)
        else:
            raise ValueError(
                f"For oracle db storage type `{raw_type}`, the connection config type should be either `TlsOracleDatabaseConnectionConfig` or `MTlsOracleDatabaseConnectionConfig` but got `{raw_type}`"
            )

    raise ValueError(f"Unexpected storage type `{storage_type}` for datastore configuration.")
