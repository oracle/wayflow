#!/bin/bash
#
# Copyright (C) 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

set -e  # Exit immediately if any command fails

REPO_ROOT=$( cd "$(dirname "${BASH_SOURCE[0]}")"/.. ; pwd -P )

# run all tests
if [ "$1" = "--parallel" ]; then
    # Run tests in parallel
    # disable a2a server tests (issue #40)  # tests/a2a
    pytest tests/test_docstring.py tests/datastores tests/agentserver tests/transforms/test_summarization_transforms.py tests/mcptools/test_mcp_tools.py
    pytest -n auto $REPO_ROOT/tests --dist loadscope --ignore=tests/datastores/ --ignore=tests/test_docstring.py --ignore=tests/agentserver/ --ignore=tests/transforms/test_summarization_transforms.py --ignore=tests/a2a --ignore=tests/mcptools/test_mcp_tools.py
else
    # Run tests normally
    pytest $REPO_ROOT/tests
fi

sh $REPO_ROOT/tests/security/logging_tests.sh $REPO_ROOT/tests/security
