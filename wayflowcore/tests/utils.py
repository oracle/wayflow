# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
from collections import deque
from contextlib import closing
from typing import Optional

import httpx


class LogTee:
    def __init__(self, stream, prefix: str, max_lines: int = 400):
        self.stream = stream
        self.prefix = prefix
        self.lines = deque(maxlen=max_lines)
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self._stop.set()
        self.thread.join(timeout=2)

    def _run(self):
        for line in iter(self.stream.readline, ""):
            if self._stop.is_set():
                break
            line = line.rstrip("\n")
            self.lines.append(line)
            # forward to CI log immediately
            print(f"{self.prefix}{line}", file=sys.stdout, flush=True)

    def dump(self) -> str:
        return "\n".join(self.lines)


def _terminate_process_tree(process: subprocess.Popen, timeout: float = 5.0) -> None:
    """Best-effort, cross-platform termination with escalation and stdout close."""
    try:
        if process.poll() is not None:
            return  # already exited
        # Prefer group termination on POSIX if we started a new session
        if os.name == "posix":
            try:
                pgid = os.getpgid(process.pid)
                # 1) Graceful: SIGTERM to the group
                os.killpg(pgid, signal.SIGTERM)
            except Exception:
                # Fall back to terminating the single process
                try:
                    process.terminate()
                except Exception:
                    pass
        else:
            # Windows or other: terminate the single process
            try:
                process.terminate()
            except Exception:
                pass

        # Give it a moment to exit cleanly
        try:
            process.wait(timeout=timeout)
            return
        except Exception:
            pass

        # 2) Forceful: SIGKILL the group (POSIX), otherwise kill the process
        if os.name == "posix":
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except Exception:
                # Fall back to killing the single process
                try:
                    process.kill()
                except Exception:
                    pass
        else:
            try:
                process.kill()
            except Exception:
                pass

        # Ensure it is gone
        try:
            process.wait(timeout=timeout)
        except Exception:
            pass
    finally:
        # Close stdout to avoid ResourceWarning if we used a PIPE
        try:
            if getattr(process, "stdout", None) and not process.stdout.closed:
                process.stdout.close()
        except Exception:
            pass


def _check_server_is_up(
    url: str,
    client_key_path: Optional[str] = None,
    client_cert_path: Optional[str] = None,
    ca_cert_path: Optional[str] = None,
    timeout_s: float = 5.0,
) -> bool:
    verify: ssl.SSLContext | bool = False
    if client_key_path and client_cert_path and ca_cert_path:
        ssl_ctx = ssl.create_default_context(cafile=ca_cert_path)
        ssl_ctx.load_cert_chain(certfile=client_cert_path, keyfile=client_key_path)
        verify = ssl_ctx

    last_exc: Optional[Exception] = None
    deadline = time.time() + timeout_s
    with httpx.Client(verify=verify, timeout=1.0) as client:
        while time.time() < deadline:
            try:
                resp = client.get(url)
                if resp.status_code < 500:
                    return True
            except Exception as e:
                last_exc = e
            time.sleep(0.2)
    if last_exc:
        print(
            f"Server not ready after {timeout_s}s. Last error: {last_exc}",
            file=sys.stderr,
            flush=True,
        )
    return False


def get_available_port(tmp_path: str):
    """
    Allocate a TCP port in a way that is safe across multiple pytest processes and
    across concurrent jobs running on the same machine.

    Strategy:
    - Use a per-namespace monotonic counter persisted in a file under pytest tmp folder,
      protected by an OS file lock, to avoid collisions between independent Python interpreters.
    - The namespace is based on environment variables:
        WAYFLOW_TEST_PORT_BASE  base port (int), default is 10000
        WAYFLOW_TEST_PORT_SPAN  size of the port window starting at BASE (int), default is 500
    - Within the critical section, probe ports by attempting a bind; skip ports already in use.

    The parameter tmp_path is where the file used for the lock is located. It should be consistent
    across threads in order to ensure that they acquire the lock on the same file, so we should
    always call this method passing the value of the `session_tmp_path` fixture.
    """

    base = int(os.environ.get("WAYFLOW_TEST_PORT_BASE", 10000))
    span = int(os.environ.get("WAYFLOW_TEST_PORT_SPAN", 500))

    state_path = f"{tmp_path}/wayflow_ports.state"
    lock_path = f"{tmp_path}/wayflow_ports.lock"

    def _bindable(port: int) -> bool:
        try:
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False

    # Acquire an interprocess lock, POSIX only. On non-POSIX, degrade to probing loop.
    if os.name == "posix":
        import fcntl

        with open(lock_path, "a+") as lockf:
            # We take an exclusive lock on the file, so that we ensure that no other thread/process
            # is going to try to get an available port at the same time
            fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
            try:
                # Read last used port
                try:
                    with open(state_path, "r") as sf:
                        content = sf.read().strip()
                    candidate = int(content) + 1
                except (FileNotFoundError, TypeError, ValueError):
                    candidate = base

                # Probe within window
                for _ in range(span):
                    if candidate >= base + span or candidate < base:
                        candidate = base
                    if _bindable(candidate):
                        # Persist chosen port for next allocation
                        with open(state_path, "w") as sf:
                            sf.write(str(candidate))
                        return candidate
                    candidate += 1
                # Fallback to kernel-chosen ephemeral if window exhausted
                with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                    s.bind(("", 0))
                    return s.getsockname()[1]
            finally:
                fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
    else:
        # Non-POSIX fallback: try a few random ports, then kernel ephemeral
        for _ in range(50):
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.bind(("", 0))
                p = s.getsockname()[1]
            if _bindable(p):
                return p
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(("", 0))
            return s.getsockname()[1]
