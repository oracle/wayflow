#!/bin/bash
#
# Copyright (C) 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

set -e  # Exit immediately if any command fails

REPO_ROOT=$( cd "$(dirname "${BASH_SOURCE[0]}")"/.. ; pwd -P )

# run all tests
pytest $REPO_ROOT/tests

sh $REPO_ROOT/tests/security/logging_tests.sh $REPO_ROOT/tests/security
