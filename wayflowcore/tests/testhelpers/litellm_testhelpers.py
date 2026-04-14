# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
"""Shared LiteLLM test helpers for Gemini-related tests."""

import configparser
import gc
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

ADC_CREDENTIALS_PATH = Path.home() / ".config/gcloud/application_default_credentials.json"
"""Default Google ADC file path used by Vertex-auth tests."""

GCLOUD_CONFIG_DIR = Path.home() / ".config/gcloud"
"""Default Google Cloud SDK config directory used by ADC-backed tests."""

VERTEX_ADC_LOCATION = "us-central1"
"""Vertex region used by ADC-backed Gemini tests in this workspace."""


# Vertex credential discovery accepts either an inline JSON payload or a path to
# a JSON file because tests in CI and local development use both forms.
def _get_non_empty_env_var(*env_var_names: str) -> str | None:
    """Return the first non-empty environment variable from the provided names."""
    for env_var_name in env_var_names:
        env_var_value = os.getenv(env_var_name)
        if isinstance(env_var_value, str) and env_var_value.strip():
            return env_var_value.strip()
    return None


def _get_project_id_from_json_value(json_value: object) -> str | None:
    """Extract a Google Cloud project id from a decoded JSON object when present."""
    if not isinstance(json_value, dict):
        return None
    for field_name in ("project_id", "quota_project_id"):
        project_id = json_value.get(field_name)
        if isinstance(project_id, str) and project_id.strip():
            return project_id.strip()
    return None


def _get_project_id_from_json_file(path: Path) -> str | None:
    """Extract a Google Cloud project id from a JSON file when present."""
    try:
        with open(path, "r") as file:
            return _get_project_id_from_json_value(json.load(file))
    except (OSError, json.JSONDecodeError):
        return None


def _load_json_value_from_string_or_file(value: str) -> object | None:
    """Decode JSON from an inline string or from a JSON file path."""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    try:
        with open(Path(value).expanduser(), "r") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return None


def get_vertex_credentials_dict() -> dict[str, Any] | None:
    """Return ``VERTEX_CREDENTIALS`` as a decoded credentials dictionary when configured."""
    vertex_credentials = _get_non_empty_env_var("VERTEX_CREDENTIALS")
    if vertex_credentials is None:
        return None

    json_value = _load_json_value_from_string_or_file(vertex_credentials)
    if isinstance(json_value, dict):
        return dict(json_value)
    return None


def _get_vertex_project_id_from_service_account_credentials() -> str | None:
    """Read the project id from the configured Vertex service-account payload, when present."""
    return _get_project_id_from_json_value(get_vertex_credentials_dict())


def _get_vertex_project_id_from_gcloud_config() -> str | None:
    """Read the configured gcloud project id from the local SDK config when present."""
    configurations_dir = GCLOUD_CONFIG_DIR / "configurations"
    active_config_path = GCLOUD_CONFIG_DIR / "active_config"

    config_names: list[str] = []
    try:
        active_config_name = active_config_path.read_text().strip()
    except OSError:
        active_config_name = ""

    if active_config_name:
        config_names.append(active_config_name)
    if "default" not in config_names:
        config_names.append("default")

    for config_name in config_names:
        config_path = configurations_dir / f"config_{config_name}"
        if not config_path.exists():
            continue

        parser = configparser.ConfigParser()
        try:
            parser.read(config_path)
        except configparser.Error:
            continue

        project_id = parser.get("core", "project", fallback="").strip()
        if project_id:
            return project_id

    return None


def _get_vertex_project_id_from_local_gcloud_json_files() -> str | None:
    """Read a project id from local Cloud SDK JSON files when there is a single clear match."""
    discovered_project_ids: set[str] = set()

    for candidate_path in GCLOUD_CONFIG_DIR.glob("*.json"):
        if candidate_path == ADC_CREDENTIALS_PATH:
            continue
        project_id = _get_project_id_from_json_file(candidate_path)
        if project_id is not None:
            discovered_project_ids.add(project_id)

    if len(discovered_project_ids) == 1:
        return next(iter(discovered_project_ids))

    return None


def _get_vertex_project_id_from_adc() -> str | None:
    """Discover the project id associated with local ADC without depending on VERTEX_CREDENTIALS."""
    # Prefer explicit environment configuration first, then fall back to local
    # gcloud state, and only ask google.auth as a last resort.
    project_id = _get_non_empty_env_var(
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_PROJECT_ID",
        "GCLOUD_PROJECT",
        "VERTEX_PROJECT_ID",
    )
    if project_id is not None:
        return project_id

    project_id = _get_vertex_project_id_from_gcloud_config()
    if project_id is not None:
        return project_id

    project_id = _get_vertex_project_id_from_local_gcloud_json_files()
    if project_id is not None:
        return project_id

    project_id = _get_project_id_from_json_file(ADC_CREDENTIALS_PATH)
    if project_id is not None:
        return project_id

    try:
        import google.auth

        credentials, project_id = google.auth.default()
    except Exception:
        return None

    if isinstance(project_id, str) and project_id.strip():
        return project_id.strip()

    quota_project_id = getattr(credentials, "quota_project_id", None)
    if isinstance(quota_project_id, str) and quota_project_id.strip():
        return quota_project_id.strip()

    return None


VERTEX_CREDENTIALS_PROJECT_ID = _get_vertex_project_id_from_service_account_credentials()
"""Project id discovered from ``VERTEX_CREDENTIALS``, when configured."""


VERTEX_ADC_PROJECT_ID = _get_vertex_project_id_from_adc()
"""Project id paired with the local ADC-backed Vertex tests, when discoverable."""


def _cleanup_litellm_threads(*, threads_before: set[int]) -> None:
    """Shutdown lingering LiteLLM/httpx thread-pool workers created during tests."""
    # LiteLLM/httpx can leave private ThreadPoolExecutor workers around after a
    # request. We compare thread snapshots so we only tear down executors that
    # were spawned during the current test run.
    threads_after = {
        thread.ident
        for thread in threading.enumerate()
        if thread is not threading.main_thread() and thread.ident is not None
    }
    spawned_thread_idents = threads_after - threads_before

    if not spawned_thread_idents:
        return

    for executor in [obj for obj in gc.get_objects() if isinstance(obj, ThreadPoolExecutor)]:
        for thread in getattr(executor, "_threads", set()):
            if thread.ident in spawned_thread_idents and thread.name.startswith(
                "ThreadPoolExecutor-"
            ):
                executor.shutdown(wait=True, cancel_futures=True)
                break


@pytest.fixture(scope="session")
def litellm_thread_cleanup():
    """Disable LiteLLM background logging and cleanup spawned thread-pool workers."""
    import litellm

    threads_before = {thread.ident for thread in threading.enumerate() if thread.ident is not None}
    litellm.disable_streaming_logging = True
    litellm.turn_off_message_logging = True
    yield
    _cleanup_litellm_threads(threads_before=threads_before)


@pytest.fixture(autouse=True, scope="session")
def litellm_anyio_cleanup() -> None:
    """Keep LiteLLM logging disabled without bootstrapping an async session fixture."""
    import litellm

    litellm.disable_streaming_logging = True
    litellm.turn_off_message_logging = True
