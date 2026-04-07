# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os
import subprocess
import sys


def _run_python_and_get_cost_map_env(env: dict[str, str]) -> str:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; "
                "import wayflowcore; "
                "print(os.environ.get('LITELLM_LOCAL_MODEL_COST_MAP', '<unset>'))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return completed.stdout.strip()


def test_wayflowcore_import_sets_local_litellm_cost_map_by_default() -> None:
    env = os.environ.copy()
    env.pop("LITELLM_LOCAL_MODEL_COST_MAP", None)

    assert _run_python_and_get_cost_map_env(env) == "True"


def test_wayflowcore_import_respects_explicit_litellm_cost_map_override() -> None:
    env = os.environ.copy()
    env["LITELLM_LOCAL_MODEL_COST_MAP"] = "False"

    assert _run_python_and_get_cost_map_env(env) == "False"
