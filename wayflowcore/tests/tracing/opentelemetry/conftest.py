# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import pytest

from .otel_server_utils import _start_otel_server

OTEL_SERVER_PORT = 4318


@pytest.fixture(scope="session")
def otel_server():
    process, url = _start_otel_server(host="localhost", port=OTEL_SERVER_PORT)
    yield url
    process.kill()
    process.wait()
