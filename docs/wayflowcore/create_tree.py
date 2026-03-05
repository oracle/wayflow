# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True)
class TreeNode:
    name: str
    is_dir: bool
    children: List["TreeNode"]


def _iter_children(path: Path) -> Iterable[Path]:
    try:
        return sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except FileNotFoundError:
        return []


def build_tree(root: Path, *, max_depth: int) -> TreeNode:
    root = root.resolve()

    def rec(current: Path, depth: int) -> TreeNode:
        if depth > max_depth:
            return TreeNode(name=current.name, is_dir=current.is_dir(), children=[])

        if current.is_dir():
            children: List[TreeNode] = []
            for child in _iter_children(current):
                # Skip hidden and underscore-prefixed directories (Sphinx internals like _static).
                if child.name.startswith("."):
                    continue
                if child.is_dir() and child.name.startswith("_"):
                    continue
                children.append(rec(child, depth + 1))
            return TreeNode(name=current.name, is_dir=True, children=children)

        # Files are ignored for the simplified navigation tree.
        return TreeNode(name=current.name, is_dir=False, children=[])

    return rec(root, 0)


def render_tree(node: TreeNode, *, indent: str = "  ") -> str:
    # If the root has a single child directory, show that as the top-level.
    start = node
    top_dirs = [c for c in node.children if c.is_dir]
    if node.is_dir and len(top_dirs) == 1:
        start = top_dirs[0]

    lines: List[str] = [start.name]

    def rec(n: TreeNode, level: int) -> None:
        for child in n.children:
            if not child.is_dir:
                continue
            prefix = indent * level + "- "
            lines.append(f"{prefix}{child.name} ({len(child.children)} items)")
            rec(child, level + 1)

    rec(start, 1)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a simplified docs tree.")
    parser.add_argument("root", type=Path, help="Root folder to scan")
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--ext", action="append", default=[".md"], help="Include extension")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root
    tree = build_tree(root, max_depth=args.max_depth)
    rendered = render_tree(tree)

    if rendered.strip() == root.resolve().name:
        raise SystemExit(f"No directory structure found under: {root}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
