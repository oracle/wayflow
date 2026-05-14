# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import socket
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

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


def test_get_available_port_skips_ports_occupied_on_ipv6(
    monkeypatch, tmp_path_factory: pytest.TempPathFactory
):
    if not socket.has_ipv6:
        pytest.skip("IPv6 is not available on this host")

    # Simulate a host where ``localhost`` binds through ::1 while the allocator
    # would otherwise only see 127.0.0.1 as free.
    occupied_socket = None
    occupied_port = None
    for port in range(21000, 21100):
        try:
            occupied_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            occupied_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            occupied_socket.bind(("::1", port))
            occupied_socket.listen(1)
            occupied_port = port
            break
        except OSError:
            if occupied_socket is not None:
                occupied_socket.close()

    if occupied_socket is None or occupied_port is None:
        pytest.skip("No free IPv6 loopback port available for test setup")

    with closing(occupied_socket):
        monkeypatch.setenv("WAYFLOW_TEST_PORT_BASE", str(occupied_port))
        monkeypatch.setenv("WAYFLOW_TEST_PORT_SPAN", "20")

        temp_dir = tmp_path_factory.mktemp(f"port-retrieval-ipv6-{uuid.uuid4().hex}")
        port = get_available_port(str(temp_dir))

    assert port != occupied_port
