# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""

MCP Server Example - WayFlow Docs MCP
-------------------------------------

This module defines a MCP Server to easily fetch context about the WayFlow documentation.


How to use
^^^^^^^^^^

This MCP server can be used in coding assistants, e.g., Codex:

```bash
codex mcp add wayflow_docs -- python docs_mcp.py --base-docs-url https://oracle.github.io/wayflow/development
```

Or add to your config.toml

[mcp_servers.wayflow_docs]
command = "python"
args = ["docs_mcp.py", "--base-docs-url", "https://oracle.github.io/wayflow/development"]


"""

from __future__ import annotations

import argparse
import io
import logging
import os
import re
import shlex
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, cast

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


class _CommandError(ValueError):
    pass


@dataclass(frozen=True)
class _CommandResult:
    stdout: str
    stderr: str
    exit_code: int


_SED_RANGE_RE = re.compile(r"^(?P<start>\d+),(?P<end>\d+)p$")
_HEAD_TAIL_N_RE = re.compile(r"^\d+$")
_MAX_HEAD_TAIL_LINES = 500


def _is_within_root(root: Path, path: Path) -> bool:
    root = root.resolve()
    path = path.resolve()
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_no_shell_metacharacters(raw: str) -> None:
    forbidden = [";", "&&", "||", ">", "<", "`", "$("]
    for token in forbidden:
        if token in raw:
            raise _CommandError(f"Unsupported shell syntax: {token}")

    if raw.count("|") > 1:
        raise _CommandError("Only a single pipe is supported")


def _run_supported_command(
    command: str,
    *,
    root_dir: str | Path = ".",
    cwd: str | Path | None = None,
    max_output_bytes: int = 200_000,
    timeout_seconds: int = 5,
) -> _CommandResult:
    """Run a constrained subset of shell-like commands.

    Supported:
    - rg --files [--glob/-g ...] [<path>]
    - ls [path] or ls -la [path]
    - sed -n 'START,ENDp' <file>
    - head [-n N] <file>
    - tail [-n N] <file>
    - <producer> | head [-n N]
    - <producer> | tail [-n N]
    - <producer> | rg [-i] [-F] [-v] [-n] PATTERN

    Notes:
    - Exactly one pipe is supported.
    - All paths must remain within root_dir.
    """

    _validate_no_shell_metacharacters(command)
    root = Path(root_dir).resolve()
    working_dir = Path(cwd).resolve() if cwd is not None else root
    if not _is_within_root(root, working_dir):
        raise _CommandError("cwd must be within root_dir")

    if "|" in command:
        left_raw, right_raw = [part.strip() for part in command.split("|", maxsplit=1)]
        if not left_raw or not right_raw:
            raise _CommandError("Invalid pipe syntax")
        producer_result = _run_non_pipeline_command(
            left_raw,
            root=root,
            cwd=working_dir,
            max_output_bytes=max_output_bytes,
            timeout_seconds=timeout_seconds,
        )
        if producer_result.exit_code != 0:
            return producer_result
        return _run_pipeline_consumer(
            right_raw,
            input_text=producer_result.stdout,
            max_output_bytes=max_output_bytes,
        )

    return _run_non_pipeline_command(
        command,
        root=root,
        cwd=working_dir,
        max_output_bytes=max_output_bytes,
        timeout_seconds=timeout_seconds,
    )


def _run_non_pipeline_command(
    command: str,
    *,
    root: Path,
    cwd: Path,
    max_output_bytes: int,
    timeout_seconds: int,
) -> _CommandResult:
    args = shlex.split(command)
    if not args:
        raise _CommandError("Empty command")

    prog = args[0]
    if prog == "rg":
        return _run_rg_files(
            args,
            root=root,
            cwd=cwd,
            max_output_bytes=max_output_bytes,
            timeout_seconds=timeout_seconds,
        )
    if prog == "ls":
        return _run_ls(
            args,
            root=root,
            cwd=cwd,
            max_output_bytes=max_output_bytes,
            timeout_seconds=timeout_seconds,
        )
    if prog == "sed":
        return _run_sed(
            args,
            root=root,
            cwd=cwd,
            max_output_bytes=max_output_bytes,
        )
    if prog == "head":
        return _run_head_tail(
            args,
            root=root,
            cwd=cwd,
            max_output_bytes=max_output_bytes,
            mode="head",
        )
    if prog == "tail":
        return _run_head_tail(
            args,
            root=root,
            cwd=cwd,
            max_output_bytes=max_output_bytes,
            mode="tail",
        )

    raise _CommandError(f"Unsupported command: {prog}")


def _run_pipeline_consumer(
    command: str,
    *,
    input_text: str,
    max_output_bytes: int,
) -> _CommandResult:
    args = shlex.split(command)
    if not args:
        raise _CommandError("Empty pipeline consumer")

    prog = args[0]
    if prog == "head":
        return _run_head_tail_on_text(
            args, input_text=input_text, max_output_bytes=max_output_bytes, mode="head"
        )
    if prog == "tail":
        return _run_head_tail_on_text(
            args, input_text=input_text, max_output_bytes=max_output_bytes, mode="tail"
        )
    if prog == "rg":
        return _run_rg_filter(args, input_text=input_text, max_output_bytes=max_output_bytes)

    raise _CommandError(f"Unsupported pipe target: {prog}")


def _run_rg_files(
    args: List[str],
    *,
    root: Path,
    cwd: Path,
    timeout_seconds: int,
    max_output_bytes: int,
) -> _CommandResult:
    # Allowed forms:
    #   rg --files [--glob/-g PATTERN]... [PATH]
    if "--files" not in args:
        raise _CommandError("Only 'rg --files' is supported")

    allowed_flags_with_value = {"--glob", "-g"}
    allowed_flags = {"--files"}

    parsed: List[str] = ["rg"]
    idx = 1
    path_arg: Optional[str] = None
    while idx < len(args):
        arg_ = args[idx]
        if arg_ in allowed_flags:
            parsed.append(arg_)
            idx += 1
            continue
        if arg_ in allowed_flags_with_value:
            if idx + 1 >= len(args):
                raise _CommandError(f"Missing value for {arg_}")
            parsed.extend([arg_, args[idx + 1]])
            idx += 2
            continue
        if arg_.startswith("-"):
            raise _CommandError(f"Unsupported rg flag: {arg_}")
        if path_arg is not None:
            raise _CommandError("Too many path arguments")
        path_arg = arg_
        idx += 1

    if path_arg is not None:
        candidate = (cwd / path_arg).resolve()
        if not _is_within_root(root, candidate):
            raise _CommandError("Path escapes root_dir")
        # Keep the user's relative path for rg.
        parsed.append(path_arg)

    return _rg_files_inprocess(
        parsed,
        root=root,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )


def _run_ls(
    args: List[str],
    *,
    root: Path,
    cwd: Path,
    timeout_seconds: int,
    max_output_bytes: int,
) -> _CommandResult:
    # Allowed forms:
    #   ls
    #   ls PATH
    #   ls -la [PATH]
    flags: List[str] = []
    paths: List[str] = []
    for arg_ in args[1:]:
        if arg_.startswith("-"):
            if arg_ != "-la":
                raise _CommandError(f"Unsupported ls flag: {arg_}")
            flags.append(arg_)
        else:
            paths.append(arg_)

    if len(paths) > 1:
        raise _CommandError("Only one path argument is supported")
    if len(flags) > 1:
        raise _CommandError("Duplicate flags")

    argv = ["ls", *flags]
    if paths:
        candidate = (cwd / paths[0]).resolve()
        if not _is_within_root(root, candidate):
            raise _CommandError("Path escapes root_dir")
        argv.append(paths[0])

    return _ls_inprocess(
        argv,
        root=root,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )


def _run_sed(
    args: List[str],
    *,
    root: Path,
    cwd: Path,
    max_output_bytes: int,
) -> _CommandResult:
    # Allowed form:
    #   sed -n 'START,ENDp' FILE
    if len(args) != 4:
        raise _CommandError("Only 'sed -n START,ENDp FILE' is supported")
    if args[1] != "-n":
        raise _CommandError("Only 'sed -n' is supported")

    range_expression = args[2]
    match = _SED_RANGE_RE.match(range_expression)
    if not match:
        raise _CommandError("sed range must be like '10,50p'")
    start_idx = int(match.group("start"))
    end_idx = int(match.group("end"))
    if start_idx < 1 or end_idx < 1 or end_idx < start_idx:
        raise _CommandError("Invalid sed range")
    if (end_idx - start_idx) > 5000:
        raise _CommandError("sed range too large")

    file_arg = args[3]
    candidate = (cwd / file_arg).resolve()
    if not _is_within_root(root, candidate):
        raise _CommandError("Path escapes root_dir")
    if not candidate.exists() or not candidate.is_file():
        raise _CommandError("File not found")

    return _sed_inprocess(
        start=start_idx,
        end=end_idx,
        file_path=candidate,
        max_output_bytes=max_output_bytes,
    )


def _parse_head_tail_args(
    args: List[str], *, allow_file: bool, mode: str
) -> tuple[int, Optional[str]]:
    count = 10
    file_arg: Optional[str] = None
    idx = 1
    while idx < len(args):
        arg_ = args[idx]
        if arg_ == "-n":
            if idx + 1 >= len(args):
                raise _CommandError(f"Missing value for {mode} -n")
            value = args[idx + 1]
            if not _HEAD_TAIL_N_RE.match(value):
                raise _CommandError(f"{mode} -n expects a positive integer")
            count = int(value)
            idx += 2
            continue
        if arg_.startswith("-"):
            raise _CommandError(f"Unsupported {mode} flag: {arg_}")
        if not allow_file:
            raise _CommandError(f"{mode} does not accept a file after a pipe")
        if file_arg is not None:
            raise _CommandError(f"Only one file argument is supported for {mode}")
        file_arg = arg_
        idx += 1

    if count < 1:
        raise _CommandError(f"{mode} -n expects a positive integer")
    if count > _MAX_HEAD_TAIL_LINES:
        raise _CommandError(f"{mode} -n too large")
    if allow_file and file_arg is None:
        raise _CommandError(f"{mode} requires a file path")
    return count, file_arg


def _run_head_tail(
    args: List[str],
    *,
    root: Path,
    cwd: Path,
    max_output_bytes: int,
    mode: str,
) -> _CommandResult:
    count, file_arg = _parse_head_tail_args(args, allow_file=True, mode=mode)
    if file_arg is None:
        raise _CommandError(f"Parsed file arg is None, from {args=}")
    candidate = (cwd / file_arg).resolve()
    if not _is_within_root(root, candidate):
        raise _CommandError("Path escapes root_dir")
    if not candidate.exists() or not candidate.is_file():
        raise _CommandError("File not found")

    return _head_tail_file_inprocess(
        file_path=candidate,
        count=count,
        mode=mode,
        max_output_bytes=max_output_bytes,
    )


def _run_head_tail_on_text(
    args: List[str],
    *,
    input_text: str,
    max_output_bytes: int,
    mode: str,
) -> _CommandResult:
    count, _ = _parse_head_tail_args(args, allow_file=False, mode=mode)
    return _head_tail_text_inprocess(
        input_text=input_text,
        count=count,
        mode=mode,
        max_output_bytes=max_output_bytes,
    )


def _run_rg_filter(
    args: List[str],
    *,
    input_text: str,
    max_output_bytes: int,
) -> _CommandResult:
    if "--files" in args:
        raise _CommandError("The piped rg form is only a line filter, not 'rg --files'")

    ignore_case = False
    fixed_strings = False
    invert_match = False
    show_line_numbers = False
    pattern: Optional[str] = None

    for arg_ in args[1:]:
        if arg_ == "-i":
            ignore_case = True
        elif arg_ == "-F":
            fixed_strings = True
        elif arg_ == "-v":
            invert_match = True
        elif arg_ == "-n":
            show_line_numbers = True
        elif arg_.startswith("-"):
            raise _CommandError(f"Unsupported piped rg flag: {arg_}")
        elif pattern is None:
            pattern = arg_
        else:
            raise _CommandError("Piped rg supports exactly one pattern and no path arguments")

    if pattern is None:
        raise _CommandError("Piped rg requires a pattern")

    return _rg_filter_inprocess(
        input_text=input_text,
        pattern=pattern,
        ignore_case=ignore_case,
        fixed_strings=fixed_strings,
        invert_match=invert_match,
        show_line_numbers=show_line_numbers,
        max_output_bytes=max_output_bytes,
    )


def _check_output_size(stdout: str, stderr: str, max_output_bytes: int) -> None:
    if (len(stdout.encode("utf-8")) + len(stderr.encode("utf-8"))) > max_output_bytes:
        raise _CommandError("Command output exceeded max_output_bytes")


def _ls_inprocess(
    argv: Sequence[str],
    *,
    root: Path,
    cwd: Path,
    timeout_seconds: int,
    max_output_bytes: int,
) -> _CommandResult:
    # argv is like: ["ls"] or ["ls", "-la"] or ["ls", "-la", "path"]
    _ = timeout_seconds  # no-op; kept for signature parity
    show_long = "-la" in argv
    target = cwd
    if len(argv) >= 2 and argv[-1] != "-la":
        candidate = (cwd / argv[-1]).resolve()
        if not _is_within_root(root, candidate):
            raise _CommandError("Path escapes root_dir")
        target = candidate

    if not target.exists():
        return _CommandResult(stdout="", stderr="No such file or directory\n", exit_code=2)

    if target.is_file():
        entries = [target]
    else:
        entries = sorted(target.iterdir(), key=lambda p: p.name)

    lines: List[str] = []
    for entry in entries:
        name = entry.name
        if not show_long:
            lines.append(name)
            continue
        st = entry.lstat()
        # Minimal long-ish format: mode links user group size mtime name
        mode = _format_mode(st.st_mode)
        nlink = getattr(st, "st_nlink", 1)
        uid = getattr(st, "st_uid", 0)
        gid = getattr(st, "st_gid", 0)
        size = st.st_size
        mtime = int(st.st_mtime)
        lines.append(f"{mode} {nlink:3d} {uid:5d} {gid:5d} {size:9d} {mtime:10d} {name}")

    stdout = "\n".join(lines) + ("\n" if lines else "")
    stderr = ""
    _check_output_size(stdout, stderr, max_output_bytes)
    return _CommandResult(stdout=stdout, stderr=stderr, exit_code=0)


def _format_mode(st_mode: int) -> str:
    import stat

    is_dir = "d" if stat.S_ISDIR(st_mode) else "-"
    perms = []
    for rbit, wbit, xbit in (
        (stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR),
        (stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP),
        (stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH),
    ):
        perms.append("r" if (st_mode & rbit) else "-")
        perms.append("w" if (st_mode & wbit) else "-")
        perms.append("x" if (st_mode & xbit) else "-")
    return is_dir + "".join(perms)


def _rg_files_inprocess(
    argv: Sequence[str],
    *,
    root: Path,
    cwd: Path,
    timeout_seconds: int,
    max_output_bytes: int,
) -> _CommandResult:
    # Implements a subset of `rg --files` with `--glob/-g` include patterns.
    # argv is like: ["rg", "--files", "-g", "*.md", "core"]
    import fnmatch
    import time

    start_time = time.time()
    globs: List[str] = []
    search_root = cwd

    idx = 1
    while idx < len(argv):
        arg_ = argv[idx]
        if arg_ == "--files":
            idx += 1
            continue
        if arg_ in {"-g", "--glob"}:
            globs.append(argv[idx + 1])
            idx += 2
            continue
        # path
        candidate = (cwd / arg_).resolve()
        if not _is_within_root(root, candidate):
            raise _CommandError("Path escapes root_dir")
        search_root = candidate
        idx += 1

    if not search_root.exists():
        return _CommandResult(stdout="", stderr="Path not found\n", exit_code=2)

    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(search_root):
        if (time.time() - start_time) > timeout_seconds:
            raise _CommandError("Command timed out")
        # Keep traversal within root (defense-in-depth)
        if not _is_within_root(root, Path(dirpath)):
            continue
        dirnames.sort()
        filenames.sort()
        for filename_ in filenames:
            full_path = Path(dirpath) / filename_
            rel = full_path.relative_to(cwd)
            rel_str = rel.as_posix()
            if globs and not any(
                fnmatch.fnmatch(rel_str, g) or fnmatch.fnmatch(filename_, g) for g in globs
            ):
                continue
            files.append(rel_str)

    stdout = "\n".join(files) + ("\n" if files else "")
    stderr = ""
    _check_output_size(stdout, stderr, max_output_bytes)
    return _CommandResult(stdout=stdout, stderr=stderr, exit_code=0)


def _sed_inprocess(
    *, start: int, end: int, file_path: Path, max_output_bytes: int
) -> _CommandResult:
    # Print inclusive 1-based line range.
    lines: List[str] = []
    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, start=1):
            if lineno < start:
                continue
            if lineno > end:
                break
            lines.append(line)

    stdout = "".join(lines)
    stderr = ""
    _check_output_size(stdout, stderr, max_output_bytes)
    return _CommandResult(stdout=stdout, stderr=stderr, exit_code=0)


def _head_tail_file_inprocess(
    *, file_path: Path, count: int, mode: str, max_output_bytes: int
) -> _CommandResult:
    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        input_text = f.read()
    return _head_tail_text_inprocess(
        input_text=input_text,
        count=count,
        mode=mode,
        max_output_bytes=max_output_bytes,
    )


def _head_tail_text_inprocess(
    *, input_text: str, count: int, mode: str, max_output_bytes: int
) -> _CommandResult:
    lines = input_text.splitlines(keepends=True)
    if mode == "head":
        selected = lines[:count]
    elif mode == "tail":
        selected = lines[-count:]
    else:
        raise _CommandError(f"Unsupported mode: {mode}")

    stdout = "".join(selected)
    stderr = ""
    _check_output_size(stdout, stderr, max_output_bytes)
    return _CommandResult(stdout=stdout, stderr=stderr, exit_code=0)


def _rg_filter_inprocess(
    *,
    input_text: str,
    pattern: str,
    ignore_case: bool,
    fixed_strings: bool,
    invert_match: bool,
    show_line_numbers: bool,
    max_output_bytes: int,
) -> _CommandResult:
    try:
        matcher = (
            None if fixed_strings else re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        )
    except re.error as exc:
        raise _CommandError(f"Invalid rg pattern: {exc}") from exc

    lines = input_text.splitlines(keepends=True)
    matched_lines: List[str] = []
    for lineno, line in enumerate(lines, start=1):
        haystack = line.rstrip("\n")
        if fixed_strings:
            needle = pattern.lower() if ignore_case else pattern
            subject = haystack.lower() if ignore_case else haystack
            is_match = needle in subject
        else:
            if matcher is None:
                raise _CommandError("Internal error")
            is_match = matcher.search(haystack) is not None
        if invert_match:
            is_match = not is_match
        if not is_match:
            continue
        prefix = f"{lineno}:" if show_line_numbers else ""
        matched_lines.append(f"{prefix}{line}")

    stdout = "".join(matched_lines)
    stderr = ""
    _check_output_size(stdout, stderr, max_output_bytes)
    return _CommandResult(stdout=stdout, stderr=stderr, exit_code=0)


_TOOL_DESCRIPTION_TEMPLATE = """Fetch context from the project Markdown documentation.

Use this tool to navigate a Markdown docs bundle and read parts of the docs.
It accepts a constrained subset of shell-like commands for predictable retrieval.

Typical workflow
1) Discover folders:
   - ls
   - ls folder_name
2) Enumerate Markdown files:
   - rg --files -g '*.md'
   - rg --files -g '*.md' folder_name
   - rg --files path/to/folder | rg mcp
   - rg --files path/to/folder | head -n 20
3) Read a specific excerpt from a page:
   - sed -n '1,80p' index.md
   - sed -n '120,170p' path/to/index.md
   - head -n 40 path/to/howto_do_x.md
   - sed -n '1,220p' path/to/howto_x.md | rg SomeClass

Supported commands
- ls [PATH] | ls -la [PATH]
- rg --files [-g/--glob PATTERN] [PATH]
- sed -n 'START,ENDp' FILE
- head FILE | head -n N FILE
- tail FILE | tail -n N FILE
- <producer> | head [-n N]
- <producer> | tail [-n N]
- <producer> | rg [-i] [-F] [-v] [-n] PATTERN

Where <producer> is one of:
- ls [PATH] | ls -la [PATH]
- rg --files [-g/--glob PATTERN] [PATH]
- sed -n 'START,ENDp' FILE

Safety rules
- Exactly one pipe is supported.
- Redirects, chaining, and subshell syntax are not supported.
- Paths are restricted to the downloaded docs root.
- Output is size-capped; traversal is time-bounded.

Docs tree (folders only)
{doc_tree}
"""


def _fetch_url(url: str, *, timeout_seconds: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mcp-docs-context/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:  # nosec: B310
        return cast(bytes, resp.read())


def _read_text_url(url: str) -> str:
    return _fetch_url(url).decode("utf-8", errors="replace")


def _derive_artifact_urls(base_url: str) -> tuple[str, str]:
    base = base_url.rstrip("/")
    return (
        f"{base}/markdown_bundle.zip",
        f"{base}/markdown_tree.txt",
    )


def _build_server(*, base_url: str, cache_dir: Path) -> FastMCP:
    zip_url, tree_url = _derive_artifact_urls(base_url)

    logger.info("Fetching docs tree from %s", tree_url)
    doc_tree = _read_text_url(tree_url)

    logger.info("Fetching markdown bundle from %s", zip_url)

    cache_dir.mkdir(parents=True, exist_ok=True)
    docs_root = cache_dir / "markdown"
    # Always refresh on startup for 'latest' behavior.
    if docs_root.exists():
        for path in docs_root.iterdir():
            if path.is_dir():
                import shutil

                shutil.rmtree(path)
            else:
                path.unlink()
    docs_root.mkdir(parents=True, exist_ok=True)

    blob = _fetch_url(zip_url)
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for member in zf.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RuntimeError("Refusing to extract unsafe zip entry")
        zf.extractall(docs_root)

    tool_description = _TOOL_DESCRIPTION_TEMPLATE.format(doc_tree=doc_tree.rstrip())
    server = FastMCP(
        name="Docs Context MCP Server",
        instructions="Provides safe navigation and excerpt retrieval for Markdown docs.",
    )

    @server.tool(description=tool_description)
    def get_docs(command: str) -> str:
        result = _run_supported_command(command, root_dir=docs_root, cwd=docs_root)
        if result.exit_code != 0:
            raise _CommandError(result.stderr.strip() or f"Command failed: {result.exit_code}")
        return result.stdout

    return server


def main() -> int:
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="MCP server for Markdown docs context.")
    parser.add_argument(
        "--base-docs-url",
        required=True,
        help=(
            "Base URL hosting markdown artifacts (expects markdown_bundle.zip and markdown_tree.txt)"
        ),
    )
    parser.add_argument(
        "--cache-dir",
        default=".docs_cache",
        help="Local folder where markdown bundle is extracted",
    )
    args = parser.parse_args()

    server = _build_server(base_url=args.base_docs_url, cache_dir=Path(args.cache_dir))
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
