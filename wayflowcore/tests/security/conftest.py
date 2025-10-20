# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from ..conftest import TestOSError, check_allowed_filewrite


@contextmanager
def suppress_network(
    monkeypatch: Any, tmp_path: str, allowed_access_enabled: bool = True
) -> Iterator[bool]:
    """
    Context manager which raises an exception if network connection is requested.

    This is useful for detecting unit tests that inadvertently make network calls.
    We however allow localhost/filedescriptor sockets as they are needed by libraries
    to escape the Python Global Interpreter Lock.

    Parameters
    ----------
    monkeypatch : Any
        The monkeypatch
    tmp_path : str
        The path of the tmp directory used by pytest
    allowed_access_enabled : bool, default=True
        If true, will check that network access is on one of the allowed
        files. If false, all network access is suppressed
    """
    import socket

    orig_fn = socket.socket.connect

    def guard_connect(*args):
        """
        Mock the connect function of the socket module.

        The arguments are self (socket) and the address. The address can be a
        tuple (ip, port) or a filedescriptor string. We allow any filedescriptor
        and only the localhost socket.
        """
        assert allowed_access_enabled, "Code is accessing network when it shouldn't have"
        addr = args[1]
        if isinstance(addr, str) or addr[0] == "127.0.0.1":
            check_allowed_filewrite(addr, tmp_path=tmp_path, mode="w")
            return orig_fn(*args)
        # We must raise OSError (not Exception) similar to that raised
        # by socket.connect to support libraries that rely on this
        # behavior (e.g. Ray) for exception handling
        raise TestOSError(f"Network is being accessed at address {addr} of type {type(addr)}")

    with monkeypatch.context() as m:
        m.setattr(socket.socket, "connect", guard_connect)
        yield True


@pytest.fixture(scope="function")
def guard_network(monkeypatch: Any, tmp_path: str) -> Iterator[bool]:
    """
    Fixture which raises an exception if the network is accessed. It
    will not raise an exception for localhost, use guard_all_network_access
    to catch all network access

    Unit tests should not touch the network so this fixture helps guard
    against accidental network use.
    """
    with suppress_network(monkeypatch, tmp_path=tmp_path, allowed_access_enabled=True) as x:
        yield x


@pytest.fixture(scope="function")
def guard_all_network_access(monkeypatch: Any, tmp_path: str) -> Iterator[bool]:
    """Fixture which raises an exception if the network is accessed.

    Unit tests should not touch the network so this fixture helps guard
    against accidental network use.
    """
    with suppress_network(monkeypatch, tmp_path=tmp_path, allowed_access_enabled=False) as x:
        yield x
