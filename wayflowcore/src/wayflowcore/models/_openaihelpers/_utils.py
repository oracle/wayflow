# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import logging
from copy import deepcopy
from typing import Any, Dict

import json_repair

from wayflowcore.models.openaiapitype import OpenAIAPIType
from wayflowcore.property import JsonSchemaParam, Property

logger = logging.getLogger(__name__)


def _prepare_openai_compatible_json_schema(response_format: Property) -> Dict[str, Any]:
    return {
        "name": response_format.name,
        "strict": True,
        "schema": _property_to_openai_schema(response_format),
    }


def _property_to_openai_schema(property_: Property) -> Dict[str, Any]:
    schema = dict(property_.to_json_schema())
    if "properties" in schema and isinstance(schema["properties"], dict):
        # openai requires all properties to be marked required
        # https://platform.openai.com/docs/guides/structured-outputs#all-fields-must-be-required,
        schema["required"] = list(schema["properties"].keys())
        # logs a message for each default value to indicate to the user that it will not be used
        _logs_about_default_values_not_used(schema)
    if "additionalProperties" not in schema:
        # openai requires to always pass additionalProperties
        schema["additionalProperties"] = False
    return schema


def _logs_about_default_values_not_used(schema: Dict[str, Any]) -> None:
    for property_name, property_ in schema["properties"].items():
        if "default" in property_:
            logger.info(
                "The LLM cannot access the default value of the property `%s=%s`. "
                "If you need to preserve this behavior, define the property as a union "
                "with `NullProperty` and handle the default manually.",
                property_name,
                property_["default"],
            )


def _remove_optional_from_signature(
    param: JsonSchemaParam, _deepcopy: bool = True
) -> JsonSchemaParam:
    """
    This functions transforms the var: Optional[X] into var: X = None to respect the behavior that
    Langchain was using, which improves performance on weaker models like Llama.
    """
    if not isinstance(param, dict):
        return param
    if _deepcopy:
        param = deepcopy(param)
    if (
        "anyOf" in param
        and len(param["anyOf"]) == 2
        and any(s == {"type": "null"} for s in param["anyOf"])
    ):
        param.update(next(s for s in param.pop("anyOf") if s != {"type": "null"}))
    for k, v in param.items():
        if k == "items":
            _remove_optional_from_signature(v, False)  # type: ignore
        elif k == "additionalProperties":
            _remove_optional_from_signature(v, False)  # type: ignore
        elif k == "properties" and isinstance(v, dict):
            for _, t in v.items():
                _remove_optional_from_signature(t, False)
    return param


_api_type_to_url_str = {
    OpenAIAPIType.CHAT_COMPLETIONS: "/chat/completions",
    OpenAIAPIType.RESPONSES: "/responses",
}


def _build_request_url(base_url: str, api_type: OpenAIAPIType) -> str:
    base = base_url.strip()

    # Default scheme if missing
    if not base.startswith(("http://", "https://")):
        base = "http://" + base

    # Normalize trailing slash for checks
    base = base.rstrip("/")

    # If already points to api-specific end, keep as is
    if base.endswith(_api_type_to_url_str[api_type]):
        return base

    # If already ends with /v1, just append api-specific end
    if base.endswith("/v1"):
        return f"{base}{_api_type_to_url_str[api_type]}"

    # Otherwise, append  v1 + api-specific end
    return f"{base}/v1{_api_type_to_url_str[api_type]}"


def _safe_json_loads(text: str) -> Any:
    """Tries loading with JSON, defaults to repair_json if the json is wrongly
    formatted (can happen for some remote LLMs)"""
    try:
        json_dict = json.loads(text)
        if not isinstance(json_dict, dict):
            raise TypeError(f"Expected a dict, but got: {type(json_dict)}")
        return json_dict
    except (json.decoder.JSONDecodeError, TypeError) as e:
        logger.debug(
            "Failed to decode JSON in the tool call returned by the LLM: %s. Will fallback on json_repair",
            e,
        )
        repaired_json_struct = json_repair.loads(text)
        if isinstance(repaired_json_struct, dict):
            return repaired_json_struct
        return {"wrong_arg_name": repaired_json_struct}
