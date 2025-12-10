# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

import argparse
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str


class SchemaCollector:
    def __init__(self, spec: Dict[str, Any]):
        self.spec = spec
        self.components: Dict[str, Any] = spec.get("components", {}).get("schemas", {})
        self.needed: set[str] = set()
        self.queue: deque[str] = deque()

    def add_ref(self, ref: str | None) -> None:
        if not ref or not ref.startswith("#/components/schemas/"):
            return
        name = ref.split("/")[-1]
        if name not in self.needed:
            self.needed.add(name)
            self.queue.append(name)

    def add_endpoint(self, endpoint: Endpoint) -> None:
        path_item = self.spec["paths"].get(endpoint.path)
        if not path_item:
            return
        operation = path_item.get(endpoint.method.lower())
        if not operation:
            return

        request_body = operation.get("requestBody", {})
        for media in request_body.get("content", {}).values():
            schema = media.get("schema", {})
            if isinstance(schema, dict):
                self.add_ref(schema.get("$ref"))

        for response in operation.get("responses", {}).values():
            content = response.get("content", {})
            for media in content.values():
                schema = media.get("schema", {})
                if isinstance(schema, dict):
                    self.add_ref(schema.get("$ref"))

    def collect(self) -> set[str]:
        processed: set[str] = set()
        while self.queue:
            name = self.queue.popleft()
            if name in processed:
                continue
            processed.add(name)
            schema = self.components.get(name)
            if not isinstance(schema, dict):
                continue
            self._walk(schema)
        return self.needed

    def _walk(self, node: Any) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if ref:
                self.add_ref(ref)
            else:
                for value in node.values():
                    self._walk(value)
        elif isinstance(node, list):
            for item in node:
                self._walk(item)


def load_spec(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_partial_spec(
    spec: Dict[str, Any], schema_names: set[str], endpoints: Iterable[Endpoint]
) -> Dict[str, Any]:
    partial_paths: Dict[str, Any] = {}
    for endpoint in endpoints:
        if endpoint.path in partial_paths:
            continue
        path_item = spec["paths"].get(endpoint.path)
        if path_item:
            partial_paths[endpoint.path] = path_item

    components = spec.get("components", {}).get("schemas", {})
    partial_components = {name: components[name] for name in schema_names if name in components}

    return {
        "openapi": spec.get("openapi", "3.1.0"),
        "info": spec.get("info", {}),
        "paths": partial_paths,
        "components": {"schemas": partial_components},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate trimmed OpenAPI spec for selected endpoints."
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("data/openapi.documented.yml"),
        help="Path to the OpenAPI spec file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/openapi.partial.json"),
        help="Path to write the partial spec.",
    )
    parser.add_argument(
        "--endpoint", action="append", help="Endpoint in the form METHOD:/path. Can be repeated."
    )

    args = parser.parse_args()

    if args.endpoint:
        endpoints = [Endpoint(*(item.split(":", 1))) for item in args.endpoint]
    else:
        endpoints = [
            Endpoint("POST", "/responses"),
            Endpoint("GET", "/responses"),
            Endpoint("GET", "/models"),
        ]

    spec = load_spec(args.spec)

    collector = SchemaCollector(spec)
    for endpoint in endpoints:
        collector.add_endpoint(endpoint)
    schema_names = collector.collect()

    partial_spec = build_partial_spec(spec, schema_names, endpoints)

    args.output.write_text(json.dumps(partial_spec, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
