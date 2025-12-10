# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

import argparse
import keyword
import textwrap
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, TypedDict

import yaml

HEADER = """# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# THIS FILE IS AUTO-GENERATED, DO NOT EDIT.
# See wayflowcore/dev_scripts/openai-models-gen
"""


class OverrideDict(TypedDict):
    text: str
    childs: List[str]


OVERRIDE_IMPLEM: Dict[str, OverrideDict] = {
    "InputItem": {
        "text": """InputItem: TypeAlias = EasyInputMessage | Item | ItemReferenceParam""",
        "childs": ["EasyInputMessage", "Item", "ItemReferenceParam"],
    },
    "Item": {
        "text": "Message: TypeAlias = Annotated[InputMessage | OutputMessage, Field(discriminator='role')]\n\nItem: TypeAlias = Annotated[Message | FileSearchToolCall | ComputerToolCall | ComputerCallOutputItemParam | WebSearchToolCall | FunctionToolCall | FunctionCallOutputItemParam | ReasoningItem | ImageGenToolCall | CodeInterpreterToolCall | LocalShellToolCall | LocalShellToolCallOutput | FunctionShellCallItemParam | FunctionShellCallOutputItemParam | ApplyPatchToolCallItemParam | ApplyPatchToolCallOutputItemParam | MCPListTools | MCPApprovalRequest | MCPApprovalResponse | MCPToolCall | CustomToolCallOutput | CustomToolCall, Field(discriminator='type')]",
        "childs": [
            "InputMessage",
            "OutputMessage",
            "FileSearchToolCall",
            "ComputerToolCall",
            "ComputerCallOutputItemParam",
            "WebSearchToolCall",
            "FunctionToolCall",
            "FunctionCallOutputItemParam",
            "ReasoningItem",
            "ImageGenToolCall",
            "CodeInterpreterToolCall",
            "LocalShellToolCall",
            "LocalShellToolCallOutput",
            "FunctionShellCallItemParam",
            "FunctionShellCallOutputItemParam",
            "ApplyPatchToolCallItemParam",
            "ApplyPatchToolCallOutputItemParam",
            "MCPListTools",
            "MCPApprovalRequest",
            "MCPApprovalResponse",
            "MCPToolCall",
            "CustomToolCallOutput",
            "CustomToolCall",
        ],
    },
    "ItemReferenceParam": {
        "text": 'class ItemReferenceParam(BaseModel):\n    """An internal identifier for an item to reference."""\n    type: Literal["item_reference"]\n    id: str = Field(..., description="The ID of the item to reference.")',
        "childs": [],
    },
    "ToolChoiceParam": {
        "text": "ToolChoiceParam: TypeAlias = ToolChoiceOptions",
        "childs": ["ToolChoiceOptions"],
    },
}


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str

    @classmethod
    def parse_many(cls, entries: Optional[Iterable[str]]) -> List["Endpoint"]:
        if not entries:
            return [cls("GET", "/responses"), cls("POST", "/responses"), cls("GET", "/models")]
        parsed: List[Endpoint] = []
        for entry in entries:
            try:
                method, path = entry.split(":", 1)
            except ValueError as exc:  # pragma: no cover - defensive
                raise ValueError(f"Invalid endpoint format: {entry}") from exc
            parsed.append(cls(method.upper(), path))
        return parsed


class SchemaCollector:
    def __init__(self, spec: Dict[str, Any]) -> None:
        self.spec = spec
        self.components: Dict[str, Dict[str, Any]] = spec.get("components", {}).get("schemas", {})
        self.needed: set[str] = set()
        self.queue: deque[str] = deque()

    def add_ref(self, ref: Optional[str]) -> None:
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
            schema = media.get("schema")
            if isinstance(schema, dict):
                self.add_ref(schema.get("$ref"))

        for response in operation.get("responses", {}).values():
            for media in response.get("content", {}).values():
                schema = media.get("schema")
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
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


SPECIAL_ALIASES: Dict[str, str] = {
    "ChatModel": "str",
    "ContainerMemoryLimit": "Any",
    "ResponseFormatJsonSchemaSchema": "Dict[str, Any]",
}

ADDITIONAL_CLASSES: Dict[str, str] = {
    "Order": 'Literal["asc", "desc"]',
    "ResponseAdditionalContent": 'Literal["file_search_call.results", "web_search_call.results", "web_search_call.action.sources", "message.input_image.image_url", "computer_call_output.output.image_url", "code_interpreter_call.outputs", "reasoning.encrypted_content", "message.output_text.logprobs"]',
}


class ModelBuilder:
    def __init__(self, spec: Dict[str, Any], schema_names: Iterable[str]):
        self.component_schemas: Dict[str, Dict[str, Any]] = spec.get("components", {}).get(
            "schemas", {}
        )

        self.original_to_python: Dict[str, str] = {}
        self.python_to_original: Dict[str, str] = {}
        used: Set[str] = set()
        for original in schema_names:
            python_name = to_python_class_name(original)
            while python_name in used:
                python_name += "_"
            self.original_to_python[original] = python_name
            self.python_to_original[python_name] = original
            used.add(python_name)

        self.aliases: Dict[str, str] = {
            self.original_to_python[name]: SPECIAL_ALIASES[name]
            for name in SPECIAL_ALIASES
            if name in schema_names and name in self.component_schemas
        }
        self.overrides: Dict[str, OverrideDict] = {
            self.original_to_python[name]: OVERRIDE_IMPLEM[name]
            for name in OVERRIDE_IMPLEM
            if name in schema_names and name in self.component_schemas
        }

        self.schemas: Dict[str, Dict[str, Any]] = {
            self.original_to_python[original]: self.component_schemas[original]
            for original in schema_names
            if original in self.component_schemas
            and original not in SPECIAL_ALIASES  # and original not in OVERRIDE_IMPLEM
        }

        self.lines: List[str] = []
        self.processed: set[str] = set()

    def build(self) -> str:
        self.lines.append(HEADER + "\n")
        self.lines.append("from __future__ import annotations\n")
        self.lines.append("from enum import Enum\n")
        self.lines.append("from typing import Annotated, Any, Dict, List, Literal, TypeAlias\n")
        self.lines.append(
            "from pydantic import BaseModel, Field, ConfigDict, RootModel, model_validator \n\n"
        )

        self.lines.append("# Special aliases\n")
        for alias_name in sorted(self.aliases):
            self.lines.append(f"{alias_name}: TypeAlias = {self.aliases[alias_name]}\n\n")

        for var_name, var_type in ADDITIONAL_CLASSES.items():
            self.lines.append(f"{var_name}: TypeAlias = {var_type}\n\n")

        for name in sorted(self.schemas):
            self._emit_schema(name)

        return "".join(self.lines)

    def _emit_schema(self, name: str, schema: Optional[Dict[str, Any]] = None) -> None:
        if name in self.processed:
            return

        if schema is not None:
            schema = self.schemas.get(name)
        if not schema:
            original = self.python_to_original.get(name)
            if original:
                schema = self.component_schemas.get(original)
            if not schema:
                return
        self.processed.add(name)

        has_override = name in self.overrides

        if schema.get("type") == "string" and "enum" in schema:
            self._emit_enum(name, schema)
        elif "anyOf" in schema or "oneOf" in schema:
            for variant in schema.get("anyOf") or schema.get("oneOf") or []:
                if isinstance(variant, dict) and "$ref" in variant:
                    ref_name = variant["$ref"].split("/")[-1]
                    python_name = self.original_to_python.get(ref_name)
                    if (
                        python_name
                        and python_name not in self.aliases
                        and (not has_override or python_name in self.overrides[name]["childs"])
                    ):
                        self._emit_schema(python_name)
                elif isinstance(variant, dict) and variant.get("type") == "object":
                    self._emit_schema(name=to_python_class_name(f"{name}Ref"), schema=variant)
            if has_override:
                self.lines.append(f'{self.overrides[name]["text"]}\n\n')
            else:
                self._emit_union(name, schema)
        elif "items" in schema:
            variant = schema["items"]
            if isinstance(variant, dict) and "$ref" in variant:
                ref_name = variant["$ref"].split("/")[-1]
                python_name = self.original_to_python.get(ref_name)
                if (
                    python_name
                    and python_name not in self.aliases
                    and (not has_override or python_name in self.overrides[name]["childs"])
                ):
                    self._emit_schema(python_name)
            if has_override:
                self.lines.append(f'{self.overrides[name]["text"]}\n\n')
            else:
                self._emit_list(name, schema)
        else:
            if "allOf" in schema:
                for part in schema["allOf"]:
                    if isinstance(part, dict) and "$ref" in part:
                        ref_name = part["$ref"].split("/")[-1]
                        python_name = self.original_to_python.get(ref_name)
                        if (
                            python_name
                            and python_name not in self.aliases
                            and (not has_override or python_name in self.overrides[name]["childs"])
                        ):
                            self._emit_schema(python_name)
            if "anyOf" in schema:
                for part in schema["anyOf"]:
                    if isinstance(part, dict) and "$ref" in part:
                        ref_name = part["$ref"].split("/")[-1]
                        python_name = self.original_to_python.get(ref_name)
                        if (
                            python_name
                            and python_name not in self.aliases
                            and (not has_override or python_name in self.overrides[name]["childs"])
                        ):
                            self._emit_schema(python_name)

            if has_override:
                self.lines.append(f'{self.overrides[name]["text"]}\n\n')
            else:
                self._emit_model(name, schema)

    def _emit_enum(self, name: str, schema: Dict[str, Any]) -> None:
        self.lines.append(f"class {name}(Enum):\n")
        description = schema.get("description")
        if description:
            self.lines.append(indent_doc(description))
        for value in schema["enum"]:
            member = to_enum_member(value)
            self.lines.append(f"    {member} = {value!r}\n")
        self.lines.append("\n")

    def _emit_list(self, name: str, schema: Dict[str, Any]) -> None:
        description = schema.get("description")
        if description:
            self.lines.append(indent_doc(description, class_doc=True))
        self.lines.append(f'{name}: TypeAlias = List[{self._render_type(schema["items"])}]\n\n')

    def _emit_union(self, name: str, schema: Dict[str, Any]) -> None:
        variants = schema.get("anyOf") or schema.get("oneOf") or []
        description = schema.get("description") or schema.get("title")
        if not description:
            for variant in variants:
                variant_description = self._variant_description(variant)
                if variant_description:
                    description = variant_description
                    break
        if description:
            self.lines.append(format_docstring(description))
        type_expr = " | ".join(self._render_type(variant) for variant in variants)

        if "discriminator" in schema:
            discriminator = schema["discriminator"]["propertyName"]
            self.lines.append(
                f"{name}: TypeAlias = Annotated[{type_expr}, Field(discriminator={discriminator!r})]\n\n"
            )
        else:
            self.lines.append(f"{name}: TypeAlias = {type_expr}\n\n")

    def _emit_model(self, name: str, schema: Dict[str, Any]) -> None:
        description = schema.get("description") or schema.get("title")

        has_any_of = None
        if "anyOf" in schema:
            possible_values = schema.get("anyOf") or []

            real_schemas = [
                s
                for s in possible_values
                if "type" not in s
                or s["type"] not in ["null", "integer", "boolean", "number", "string"]
            ]
            if len(real_schemas) == 1:
                schema = real_schemas[0]
                has_any_of = [s for s in possible_values if s != has_any_of]

        bases: List[str] = []
        if "allOf" in schema:
            for part in schema["allOf"]:
                if "$ref" in part:
                    ref_name = part["$ref"].split("/")[-1]
                    bases.append(
                        self.original_to_python.get(ref_name, to_python_class_name(ref_name))
                    )
        if len(bases) == 0:
            bases.append("BaseModel")

        base_clause = "(" + ", ".join(dict.fromkeys(bases)) + ")"
        self.lines.append(f'class {"Any" if has_any_of else ""}{name}{base_clause}:\n')
        if description:
            self.lines.append(render_docstring(description))

        properties = self._collect_properties(schema)
        if not properties:
            raise ValueError(f"name={name}, schema={schema}")

        required: Set[str] = set(schema.get("required", []))
        if "allOf" in schema:
            for part in schema["allOf"]:
                if isinstance(part, dict):
                    required.update(part.get("required", []))

        for prop_name, prop_schema in properties.items():
            field_name = camel_to_snake(prop_name)
            type_expr = self._render_type(prop_schema)
            nullable = allows_null(prop_schema)

            if nullable and prop_name != "type":
                type_expr = add_union_member(type_expr, "None")
            optional = prop_name not in required

            if optional and prop_name != "type":
                type_expr = add_union_member(type_expr, "None")

            annotation = f"{field_name}: {type_expr}"

            field_args: List[str] = []
            description = prop_schema.get("description")
            if description:
                field_args.append(f"description={description!r}")

            const_value = None
            enum_values = prop_schema.get("enum")
            if enum_values and len(enum_values) == 1:
                const_value = enum_values[0]

            default_expr = None
            if const_value is not None:
                default_expr = repr(const_value)
            elif optional:
                default_expr = "None"

            if field_args:
                default_for_field = default_expr if default_expr is not None else "..."
                self.lines.append(
                    f"    {annotation} = Field({default_for_field}, "
                    + ", ".join(field_args)
                    + ")\n"
                )
            else:
                if default_expr is not None:
                    self.lines.append(f"    {annotation} = {default_expr}\n")
                else:
                    # hard code fix this, otherwise mypy raises
                    if prop_name == "schema":
                        annotation = (
                            annotation.replace("schema", "schema_")
                            + ' = Field(alias="schema")\n    model_config = ConfigDict(populate_by_name=True)\n'
                        )
                    self.lines.append(f"    {annotation}\n")

        # allow to have more parameters for the openai-client paging
        if name == "ListModelsResponse":
            self.lines.append('    model_config = ConfigDict(extra="allow")\n')

        self.lines.append("\n")

        if has_any_of:
            other_values = " | ".join(self._render_type(s) for s in has_any_of)
            self.lines.append(f"{name}: TypeAlias = Any{name} | {other_values}\n\n")

    def _collect_properties(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        properties: Dict[str, Any] = {}
        if "allOf" in schema:
            for part in schema["allOf"]:
                if isinstance(part, dict):
                    properties.update(part.get("properties", {}))
        properties.update(schema.get("properties", {}))
        return properties

    def _variant_description(self, variant: Dict[str, Any]) -> Optional[str]:
        if not isinstance(variant, dict):
            return None
        if "description" in variant:
            return str(variant["description"]) if variant["description"] else None
        ref = variant.get("$ref")
        if not ref:
            return None
        name = ref.split("/")[-1]
        target = self.component_schemas.get(name)
        if target:
            return target.get("description") or target.get("title")
        return None

    def _render_type(self, schema: Dict[str, Any]) -> str:
        if "$ref" in schema:
            ref_name = schema["$ref"].split("/")[-1]
            return self.original_to_python.get(ref_name, to_python_class_name(ref_name))
        schema_type = schema.get("type")
        if schema_type == "string":
            enum = schema.get("enum")
            if enum:
                return "Literal[" + ", ".join(repr(value) for value in enum) + "]"
            return "str"
        if schema_type == "integer":
            return "int"
        if schema_type == "number":
            return "float"
        if schema_type == "boolean":
            return "bool"
        if schema_type == "null":
            return "None"
        if schema_type == "array":
            item_schema = schema.get("items", {})
            item_type = self._render_type(item_schema)
            return f"List[{item_type}]"
        if schema_type == "object":
            additional = schema.get("additionalProperties")
            if isinstance(additional, dict):
                return f"Dict[str, {self._render_type(additional)}]"
            return "Dict[str, Any]"
        if "allOf" in schema:
            return self._combine_union([self._render_type(part) for part in schema["allOf"]])
        if "anyOf" in schema:
            return self._combine_union([self._render_type(part) for part in schema["anyOf"]])
        if "oneOf" in schema:
            return self._combine_union([self._render_type(part) for part in schema["oneOf"]])
        return "Any"

    def _combine_union(self, types: Iterable[str]) -> str:
        flattened: List[str] = []
        for type_expr in types:
            for part in split_union(type_expr):
                if part not in flattened:
                    flattened.append(part)
        return join_union(flattened) if flattened else "Any"


def indent_doc(text: str, class_doc: bool = False) -> str:
    text = textwrap.dedent(text).strip()
    lines = text.splitlines()
    if len(lines) == 1:
        if class_doc:
            return f'"""{lines[0]}"""\n'
        return f'    """{lines[0]}"""\n'
    inner = "\n".join(lines)
    if class_doc:
        return f'"""\n{inner}\n"""\n'
    return f'    """\n{inner}\n    """\n'


def render_docstring(text: str) -> str:
    formatted = indent_doc(text, class_doc=True)
    return textwrap.indent(formatted, "    ")


def format_docstring(text: str) -> str:
    text = textwrap.dedent(text).strip()
    if "\n" in text:
        return f'"""\n{text}\n"""\n'
    return f'"""{text}"""\n'


def camel_to_snake(name: str) -> str:
    name = name.replace("-", "")
    result: List[str] = []
    for index, char in enumerate(name):
        if (
            index
            and char.isupper()
            and (
                not name[index - 1].isupper()
                or (index + 1 < len(name) and not name[index + 1].isupper())
            )
        ):
            result.append("_")
        result.append(char.lower())
    candidate = "".join(result)
    if keyword.iskeyword(candidate):
        candidate += "_"
    return candidate


def to_enum_member(value: str) -> str:
    member = value.upper().replace("-", "").replace(".", "")
    if member and member[0].isdigit():
        member = "_" + member
    return member


def to_python_class_name(name: str) -> str:
    return name.replace("_", "").replace("-", "")


def allows_null(schema: Dict[str, Any]) -> bool:
    if schema.get("nullable") is True:
        return True
    if "type" in schema:
        schema_type = schema["type"]
        if isinstance(schema_type, list):
            return "null" in schema_type
        return bool(schema_type == "null")
    for option in schema.get("anyOf", []) + schema.get("oneOf", []):
        if isinstance(option, dict) and allows_null(option):
            return True
    return False


def add_union_member(type_expr: str, member: str) -> str:
    parts = split_union(type_expr)
    if member not in parts:
        parts.append(member)
    return join_union(parts)


def split_union(type_expr: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    for char in type_expr:
        if char == "[":
            depth += 1
        elif char == "]":
            depth = max(depth - 1, 0)
        if char == "|" and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    if current:
        part = "".join(current).strip()
        if part:
            parts.append(part)
    return parts


def join_union(parts: Iterable[str]) -> str:
    unique: List[str] = []
    for part in parts:
        part = part.strip()
        if part and part not in unique:
            unique.append(part)
    return " | ".join(unique)


def generate_models(spec: Dict[str, Any], endpoints: Iterable[Endpoint]) -> str:
    collector = SchemaCollector(spec)
    for endpoint in endpoints:
        collector.add_endpoint(endpoint)
    schema_names = collector.collect()
    builder = ModelBuilder(spec, schema_names)
    return builder.build()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Pydantic v2 models for selected OpenAPI endpoints."
    )
    parser.add_argument("--spec", type=Path, default=Path("data/openapi.documented.yml"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/openairesponsespydanticmodels.py")
    )
    parser.add_argument(
        "--endpoint",
        action="append",
        help="METHOD:/path (default: GET:/responses POST:/responses GET:/models)",
    )
    args = parser.parse_args()

    spec = load_spec(args.spec)
    endpoints = Endpoint.parse_many(args.endpoint)
    content = generate_models(spec, endpoints)
    args.output.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
