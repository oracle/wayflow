# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""HTTP examples for the WayFlow Code Executor server."""

import time

import httpx

BASE_URL = "http://127.0.0.1:8765"

# .. start-##_Get_capabilities
response = httpx.get(f"{BASE_URL}/v1/code-executor")
response.raise_for_status()
print(response.json())
# .. end-##_Get_capabilities

# .. start-##_Run_script
response = httpx.post(
    f"{BASE_URL}/v1/executions",
    json={
        "language_id": "python",
        "input": [
            {
                "type": "script",
                "source_code": "print('hello from the Code Executor server')",
            }
        ],
        "wait": True,
    },
)
response.raise_for_status()
script_response = response.json()
print(script_response["output"])
# .. end-##_Run_script

# .. start-##_Run_function
response = httpx.post(
    f"{BASE_URL}/v1/executions",
    json={
        "language_id": "python",
        "input": [
            {
                "type": "function",
                "source_code": "def multiply(a, b):\n    return a * b",
                "function_name": "multiply",
                "arguments": {"a": 6, "b": 7},
            }
        ],
        "wait": True,
    },
)
response.raise_for_status()
function_response = response.json()
print(function_response["output"][0]["structuredContent"])
# .. end-##_Run_function

# .. start-##_Poll_execution
response = httpx.post(
    f"{BASE_URL}/v1/executions",
    json={
        "language_id": "python",
        "input": [
            {
                "type": "script",
                "source_code": "import time\ntime.sleep(1)\nprint('done')",
            }
        ],
        "wait": False,
    },
)
response.raise_for_status()
execution = response.json()

while execution["status"] not in {"completed", "failed", "timed_out", "cancelled"}:
    time.sleep(0.1)
    response = httpx.get(f"{BASE_URL}/v1/executions/{execution['id']}")
    response.raise_for_status()
    execution = response.json()

print(execution)
# .. end-##_Poll_execution
