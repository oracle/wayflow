# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
"""Runtime ToolFromCode implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.notgiven import NOT_GIVEN
from wayflowcore.property import JsonSchemaParam, Property
from wayflowcore.serialization.serializer import autodeserialize_from_dict, deserialize_from_dict

from .servertools import ServerTool
from .tools import SupportedToolTypesT

if TYPE_CHECKING:
    from .codeexecutors import CodeExecutor
    from .codeexecutors._utils import CodeExecutionStatus

if TYPE_CHECKING:
    from wayflowcore.serialization.context import DeserializationContext, SerializationContext


class ToolFromCode(ServerTool):
    """ServerTool backed by source code executed through a CodeExecutor."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        language: str,
        code: str,
        code_executor: "CodeExecutor",
        main_function: str | None = None,
        dependencies: Optional[List[str]] = None,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        parameters: Optional[Dict[str, JsonSchemaParam]] = None,
        output: Optional[JsonSchemaParam] = None,
        requires_confirmation: bool = False,
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        """Create a code-backed WayFlow server tool.

        Parameters
        ----------
        name:
            Tool name exposed to WayFlow and to tool-calling models.
        description:
            Human-readable tool description exposed to callers.
        language:
            Language identifier sent to the configured code executor.
        code:
            Source code that defines the tool function.
        code_executor:
            Code executor configuration used to run the function.
        main_function:
            Function name to call in ``code``. When omitted, ``name`` is used.
        dependencies:
            Optional dependency declarations sent with each execution.
        input_descriptors:
            WayFlow input descriptors for the tool. Use either this argument or
            ``parameters``.
        output_descriptors:
            WayFlow output descriptors for the tool. Use either this argument
            or ``output``.
        requires_confirmation:
            Whether normal WayFlow tool confirmation is required before
            execution.

        """

        self.language = language
        self.code = code
        self.code_executor = code_executor
        self.main_function = main_function
        self.dependencies = list(dependencies or [])
        super().__init__(
            name=name,
            description=description,
            func=self._invoke_without_tool_request,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            parameters=parameters,
            output=output,
            requires_confirmation=requires_confirmation,
            id=id,
            __metadata_info__=__metadata_info__,
        )

    @property
    def _tool_type(self) -> SupportedToolTypesT:
        return "toolfromcode"

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the code-backed tool directly without a WayFlow ToolRequest id."""
        from .codeexecutors import CodeExecutor

        if not isinstance(self.code_executor, CodeExecutor):
            raise TypeError("code_executor must be a CodeExecutor")
        if args:
            raise TypeError("ToolFromCode.run only accepts keyword arguments.")
        return self._execute_status(
            self.code_executor._execute_function(
                code=self.code,
                language=self.language,
                function_name=self.main_function or self.name,
                arguments=kwargs,
                dependencies=self.dependencies,
                metadata=self._execution_metadata(),
            )
        )

    async def run_async(self, *args: Any, **kwargs: Any) -> Any:
        """Run the code-backed tool asynchronously."""
        if args:
            raise TypeError("ToolFromCode.run_async only accepts keyword arguments.")
        status = await self.code_executor._execute_function_async(
            code=self.code,
            language=self.language,
            function_name=self.main_function or self.name,
            arguments=kwargs,
            dependencies=self.dependencies,
            metadata=self._execution_metadata(),
        )
        return self._execute_status(status)

    def _invoke_without_tool_request(self, **kwargs: Any) -> Any:
        return self.run(**kwargs)

    def _execute_status(self, status: CodeExecutionStatus) -> Any:
        """Convert one code execution status into a tool result."""
        from .codeexecutors._utils import CodeExecutionSucceeded

        if not isinstance(status, CodeExecutionSucceeded):
            message = getattr(status, "message", None) or status.metadata.get("error")
            raise RuntimeError(message or f"Code execution {status.status}.")
        if status.result is NOT_GIVEN:
            raise RuntimeError("Function execution did not return a structured result.")
        return self._add_defaults_to_tool_outputs(status.result)

    def _execution_metadata(self) -> Dict[str, Any]:
        return {
            "feature": "tools_from_code",
            "tool_name": self.name,
            "tool_id": self.id,
        }

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        from wayflowcore.serialization.serializer import serialize_to_dict

        config = super()._serialize_to_dict(serialization_context)
        config.update(
            {
                "language": self.language,
                "code": self.code,
                "code_executor": serialize_to_dict(self.code_executor, serialization_context),
                "main_function": self.main_function,
                "dependencies": self.dependencies,
            }
        )
        return config

    @classmethod
    def _deserialize_from_dict(
        cls,
        input_dict: Dict[str, Any],
        deserialization_context: "DeserializationContext",
    ) -> "ToolFromCode":
        code_executor = autodeserialize_from_dict(
            input_dict["code_executor"],
            deserialization_context,
        )
        from .codeexecutors import CodeExecutor

        if not isinstance(code_executor, CodeExecutor):
            raise TypeError(
                f"Expected CodeExecutor in ToolFromCode serialization, got {type(code_executor)!r}."
            )
        return cls(
            name=input_dict["name"],
            description=input_dict["description"],
            language=input_dict["language"],
            code=input_dict["code"],
            code_executor=code_executor,
            main_function=input_dict.get("main_function"),
            dependencies=input_dict.get("dependencies"),
            input_descriptors=[
                deserialize_from_dict(Property, prop_dict, deserialization_context)
                for prop_dict in input_dict["input_descriptors"]
            ],
            output_descriptors=[
                deserialize_from_dict(Property, prop_dict, deserialization_context)
                for prop_dict in input_dict["output_descriptors"]
            ],
            requires_confirmation=input_dict.get("requires_confirmation", False),
            id=input_dict.get("id"),
            __metadata_info__=input_dict.get("__metadata_info__"),
        )
