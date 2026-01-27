# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from ..utils import get_available_port


def test_get_available_port_returns_unique_ports_in_parallel(
    monkeypatch, tmp_path_factory: pytest.TempPathFactory
):
    monkeypatch.setenv("WAYFLOW_TEST_PORT_BASE", "7000")
    monkeypatch.setenv("WAYFLOW_TEST_PORT_SPAN", "200")

    temp_dir = tmp_path_factory.mktemp(f"port-retrieval-{uuid.uuid4().hex}")
    request_count = 30
    with ThreadPoolExecutor(max_workers=request_count) as executor:
        futures = [executor.submit(get_available_port, str(temp_dir)) for _ in range(request_count)]
    ports = {future.result() for future in futures}
    assert len(ports) == request_count
