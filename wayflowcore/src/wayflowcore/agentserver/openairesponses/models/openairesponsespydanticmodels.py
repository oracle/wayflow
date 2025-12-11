# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# THIS FILE IS AUTO-GENERATED, DO NOT EDIT.
# See wayflowcore/dev_scripts/openai-models-gen

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

# Special aliases
ChatModel: TypeAlias = str

ContainerMemoryLimit: TypeAlias = Any

ResponseFormatJsonSchemaSchema: TypeAlias = Dict[str, Any]

Order: TypeAlias = Literal["asc", "desc"]

ResponseAdditionalContent: TypeAlias = Literal[
    "file_search_call.results",
    "web_search_call.results",
    "web_search_call.action.sources",
    "message.input_image.image_url",
    "computer_call_output.output.image_url",
    "code_interpreter_call.outputs",
    "reasoning.encrypted_content",
    "message.output_text.logprobs",
]


class FileCitationBody(BaseModel):
    """A citation to a file."""

    type: Literal["file_citation"] = Field(
        "file_citation", description="The type of the file citation. Always `file_citation`."
    )
    file_id: str = Field(..., description="The ID of the file.")
    index: int = Field(..., description="The index of the file in the list of files.")
    filename: str = Field(..., description="The filename of the file cited.")


class UrlCitationBody(BaseModel):
    """A citation for a web resource used to generate a model response."""

    type: Literal["url_citation"] = Field(
        "url_citation", description="The type of the URL citation. Always `url_citation`."
    )
    url: str = Field(..., description="The URL of the web resource.")
    start_index: int = Field(
        ..., description="The index of the first character of the URL citation in the message."
    )
    end_index: int = Field(
        ..., description="The index of the last character of the URL citation in the message."
    )
    title: str = Field(..., description="The title of the web resource.")


class ContainerFileCitationBody(BaseModel):
    """A citation for a container file used to generate a model response."""

    type: Literal["container_file_citation"] = Field(
        "container_file_citation",
        description="The type of the container file citation. Always `container_file_citation`.",
    )
    container_id: str = Field(..., description="The ID of the container file.")
    file_id: str = Field(..., description="The ID of the file.")
    start_index: int = Field(
        ...,
        description="The index of the first character of the container file citation in the message.",
    )
    end_index: int = Field(
        ...,
        description="The index of the last character of the container file citation in the message.",
    )
    filename: str = Field(..., description="The filename of the container file cited.")


class FilePath(BaseModel):
    """A path to a file."""

    type: Literal["file_path"] = Field(
        "file_path", description="The type of the file path. Always `file_path`.\n"
    )
    file_id: str = Field(..., description="The ID of the file.\n")
    index: int = Field(..., description="The index of the file in the list of files.\n")


"""A citation to a file."""
Annotation: TypeAlias = Annotated[
    FileCitationBody | UrlCitationBody | ContainerFileCitationBody | FilePath,
    Field(discriminator="type"),
]


class ApplyPatchCallOutputStatus(Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class ApplyPatchCallOutputStatusParam(Enum):
    """Outcome values reported for apply_patch tool call outputs."""

    COMPLETED = "completed"
    FAILED = "failed"


class ApplyPatchCallStatus(Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ApplyPatchCallStatusParam(Enum):
    """Status values reported for apply_patch tool calls."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ApplyPatchCreateFileOperation(BaseModel):
    """Instruction describing how to create a file via the apply_patch tool."""

    type: Literal["create_file"] = Field(
        "create_file", description="Create a new file with the provided diff."
    )
    path: str = Field(..., description="Path of the file to create.")
    diff: str = Field(..., description="Diff to apply.")


class ApplyPatchCreateFileOperationParam(BaseModel):
    """Instruction for creating a new file via the apply_patch tool."""

    type: Literal["create_file"] = Field(
        "create_file", description="The operation type. Always `create_file`."
    )
    path: str = Field(..., description="Path of the file to create relative to the workspace root.")
    diff: str = Field(..., description="Unified diff content to apply when creating the file.")


class ApplyPatchDeleteFileOperation(BaseModel):
    """Instruction describing how to delete a file via the apply_patch tool."""

    type: Literal["delete_file"] = Field("delete_file", description="Delete the specified file.")
    path: str = Field(..., description="Path of the file to delete.")


class ApplyPatchDeleteFileOperationParam(BaseModel):
    """Instruction for deleting an existing file via the apply_patch tool."""

    type: Literal["delete_file"] = Field(
        "delete_file", description="The operation type. Always `delete_file`."
    )
    path: str = Field(..., description="Path of the file to delete relative to the workspace root.")


class ApplyPatchUpdateFileOperationParam(BaseModel):
    """Instruction for updating an existing file via the apply_patch tool."""

    type: Literal["update_file"] = Field(
        "update_file", description="The operation type. Always `update_file`."
    )
    path: str = Field(..., description="Path of the file to update relative to the workspace root.")
    diff: str = Field(..., description="Unified diff content to apply to the existing file.")


"""One of the create_file, delete_file, or update_file operations supplied to the apply_patch tool."""
ApplyPatchOperationParam: TypeAlias = Annotated[
    ApplyPatchCreateFileOperationParam
    | ApplyPatchDeleteFileOperationParam
    | ApplyPatchUpdateFileOperationParam,
    Field(discriminator="type"),
]


class ApplyPatchToolCall(BaseModel):
    """A tool call that applies file diffs by creating, deleting, or updating files."""

    type: Literal["apply_patch_call"] = Field(
        "apply_patch_call", description="The type of the item. Always `apply_patch_call`."
    )
    id: str = Field(
        ...,
        description="The unique ID of the apply patch tool call. Populated when this item is returned via API.",
    )
    call_id: str = Field(
        ..., description="The unique ID of the apply patch tool call generated by the model."
    )
    status: ApplyPatchCallStatus = Field(
        ...,
        description="The status of the apply patch tool call. One of `in_progress` or `completed`.",
    )
    operation: (
        ApplyPatchCreateFileOperation
        | ApplyPatchDeleteFileOperation
        | ApplyPatchUpdateFileOperation
    ) = Field(
        ...,
        description="One of the create_file, delete_file, or update_file operations applied via apply_patch.",
    )
    created_by: str | None = Field(
        None, description="The ID of the entity that created this tool call."
    )


class ApplyPatchToolCallItemParam(BaseModel):
    """A tool call representing a request to create, delete, or update files using diff patches."""

    type: Literal["apply_patch_call"] = Field(
        "apply_patch_call", description="The type of the item. Always `apply_patch_call`."
    )
    id: str | None = None
    call_id: str = Field(
        ..., description="The unique ID of the apply patch tool call generated by the model."
    )
    status: ApplyPatchCallStatusParam = Field(
        ...,
        description="The status of the apply patch tool call. One of `in_progress` or `completed`.",
    )
    operation: ApplyPatchOperationParam = Field(
        ...,
        description="The specific create, delete, or update instruction for the apply_patch tool call.",
    )


class ApplyPatchToolCallOutput(BaseModel):
    """The output emitted by an apply patch tool call."""

    type: Literal["apply_patch_call_output"] = Field(
        "apply_patch_call_output",
        description="The type of the item. Always `apply_patch_call_output`.",
    )
    id: str = Field(
        ...,
        description="The unique ID of the apply patch tool call output. Populated when this item is returned via API.",
    )
    call_id: str = Field(
        ..., description="The unique ID of the apply patch tool call generated by the model."
    )
    status: ApplyPatchCallOutputStatus = Field(
        ...,
        description="The status of the apply patch tool call output. One of `completed` or `failed`.",
    )
    output: str | None = None
    created_by: str | None = Field(
        None, description="The ID of the entity that created this tool call output."
    )


class ApplyPatchToolCallOutputItemParam(BaseModel):
    """The streamed output emitted by an apply patch tool call."""

    type: Literal["apply_patch_call_output"] = Field(
        "apply_patch_call_output",
        description="The type of the item. Always `apply_patch_call_output`.",
    )
    id: str | None = None
    call_id: str = Field(
        ..., description="The unique ID of the apply patch tool call generated by the model."
    )
    status: ApplyPatchCallOutputStatusParam = Field(
        ...,
        description="The status of the apply patch tool call output. One of `completed` or `failed`.",
    )
    output: str | None = None


class ApplyPatchToolParam(BaseModel):
    """Allows the assistant to create, delete, or update files using unified diffs."""

    type: Literal["apply_patch"] = Field(
        "apply_patch", description="The type of the tool. Always `apply_patch`."
    )


class ApplyPatchUpdateFileOperation(BaseModel):
    """Instruction describing how to update a file via the apply_patch tool."""

    type: Literal["update_file"] = Field(
        "update_file", description="Update an existing file with the provided diff."
    )
    path: str = Field(..., description="Path of the file to update.")
    diff: str = Field(..., description="Diff to apply.")


class ApproximateLocation(BaseModel):
    type: Literal["approximate"] = Field(
        "approximate", description="The type of location approximation. Always `approximate`."
    )
    country: str | None = None
    region: str | None = None
    city: str | None = None
    timezone: str | None = None


class ClickButtonType(Enum):
    LEFT = "left"
    RIGHT = "right"
    WHEEL = "wheel"
    BACK = "back"
    FORWARD = "forward"


class ClickParam(BaseModel):
    """A click action."""

    type: Literal["click"] = Field(
        "click",
        description="Specifies the event type. For a click action, this property is always `click`.",
    )
    button: ClickButtonType = Field(
        ...,
        description="Indicates which mouse button was pressed during the click. One of `left`, `right`, `wheel`, `back`, or `forward`.",
    )
    x: int = Field(..., description="The x-coordinate where the click occurred.")
    y: int = Field(..., description="The y-coordinate where the click occurred.")


class CodeInterpreterContainerAuto(BaseModel):
    """Configuration for a code interpreter container. Optionally specify the IDs of the files to run the code on."""

    type: Literal["auto"] = Field("auto", description="Always `auto`.")
    file_ids: List[str] | None = Field(
        None, description="An optional list of uploaded files to make available to your code."
    )
    memory_limit: ContainerMemoryLimit | None = None


class CodeInterpreterOutputImage(BaseModel):
    """The image output from the code interpreter."""

    type: Literal["image"] = Field("image", description="The type of the output. Always `image`.")
    url: str = Field(..., description="The URL of the image output from the code interpreter.")


class CodeInterpreterOutputLogs(BaseModel):
    """The logs output from the code interpreter."""

    type: Literal["logs"] = Field("logs", description="The type of the output. Always `logs`.")
    logs: str = Field(..., description="The logs output from the code interpreter.")


class CodeInterpreterTool(BaseModel):
    """A tool that runs Python code to help generate a response to a prompt."""

    type: Literal["code_interpreter"] = Field(
        "code_interpreter",
        description="The type of the code interpreter tool. Always `code_interpreter`.\n",
    )
    container: str | CodeInterpreterContainerAuto = Field(
        ...,
        description="The code interpreter container. Can be a container ID or an object that\nspecifies uploaded file IDs to make available to your code.\n",
    )


class CodeInterpreterToolCall(BaseModel):
    """A tool call to run code."""

    type: Literal["code_interpreter_call"] = Field(
        "code_interpreter_call",
        description="The type of the code interpreter tool call. Always `code_interpreter_call`.\n",
    )
    id: str = Field(..., description="The unique ID of the code interpreter tool call.\n")
    status: Literal["in_progress", "completed", "incomplete", "interpreting", "failed"] = Field(
        ...,
        description="The status of the code interpreter tool call. Valid values are `in_progress`, `completed`, `incomplete`, `interpreting`, and `failed`.\n",
    )
    container_id: str = Field(..., description="The ID of the container used to run the code.\n")
    code: str | None
    outputs: List[CodeInterpreterOutputLogs | CodeInterpreterOutputImage] | None


class ComparisonFilter(BaseModel):
    """A filter used to compare a specified attribute key to a given value using a defined comparison operation."""

    type: Literal["eq", "ne", "gt", "gte", "lt", "lte"] = Field(
        ...,
        description="Specifies the comparison operator: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `nin`.\n- `eq`: equals\n- `ne`: not equal\n- `gt`: greater than\n- `gte`: greater than or equal\n- `lt`: less than\n- `lte`: less than or equal\n- `in`: in\n- `nin`: not in\n",
    )
    key: str = Field(..., description="The key to compare against the value.")
    value: str | float | bool | List[ComparisonFilterValueItems] = Field(
        ...,
        description="The value to compare against the attribute key; supports string, number, or boolean types.",
    )


ComparisonFilterValueItems: TypeAlias = str | float


class CompoundFilter(BaseModel):
    """Combine multiple filters using `and` or `or`."""

    type: Literal["and", "or"] = Field(..., description="Type of operation: `and` or `or`.")
    filters: List[ComparisonFilter | Any] = Field(
        ...,
        description="Array of filters to combine. Items can be `ComparisonFilter` or `CompoundFilter`.",
    )


class DoubleClickAction(BaseModel):
    """A double click action."""

    type: Literal["double_click"] = Field(
        "double_click",
        description="Specifies the event type. For a double click action, this property is always set to `double_click`.",
    )
    x: int = Field(..., description="The x-coordinate where the double click occurred.")
    y: int = Field(..., description="The y-coordinate where the double click occurred.")


class Drag(BaseModel):
    """A drag action."""

    type: Literal["drag"] = Field(
        "drag",
        description="Specifies the event type. For a drag action, this property is \nalways set to `drag`.\n",
    )
    path: List[DragPoint] = Field(
        ...,
        description="An array of coordinates representing the path of the drag action. Coordinates will appear as an array\nof objects, eg\n```\n[\n  { x: 100, y: 200 },\n  { x: 200, y: 300 }\n]\n```\n",
    )


class KeyPressAction(BaseModel):
    """A collection of keypresses the model would like to perform."""

    type: Literal["keypress"] = Field(
        "keypress",
        description="Specifies the event type. For a keypress action, this property is always set to `keypress`.",
    )
    keys: List[str] = Field(
        ...,
        description="The combination of keys the model is requesting to be pressed. This is an array of strings, each representing a key.",
    )


class Move(BaseModel):
    """A mouse move action."""

    type: Literal["move"] = Field(
        "move",
        description="Specifies the event type. For a move action, this property is \nalways set to `move`.\n",
    )
    x: int = Field(..., description="The x-coordinate to move to.\n")
    y: int = Field(..., description="The y-coordinate to move to.\n")


class Screenshot(BaseModel):
    """A screenshot action."""

    type: Literal["screenshot"] = Field(
        "screenshot",
        description="Specifies the event type. For a screenshot action, this property is \nalways set to `screenshot`.\n",
    )


class Scroll(BaseModel):
    """A scroll action."""

    type: Literal["scroll"] = Field(
        "scroll",
        description="Specifies the event type. For a scroll action, this property is \nalways set to `scroll`.\n",
    )
    x: int = Field(..., description="The x-coordinate where the scroll occurred.\n")
    y: int = Field(..., description="The y-coordinate where the scroll occurred.\n")
    scroll_x: int = Field(..., description="The horizontal scroll distance.\n")
    scroll_y: int = Field(..., description="The vertical scroll distance.\n")


class Type(BaseModel):
    """An action to type in text."""

    type: Literal["type"] = Field(
        "type",
        description="Specifies the event type. For a type action, this property is \nalways set to `type`.\n",
    )
    text: str = Field(..., description="The text to type.\n")


class Wait(BaseModel):
    """A wait action."""

    type: Literal["wait"] = Field(
        "wait",
        description="Specifies the event type. For a wait action, this property is \nalways set to `wait`.\n",
    )


"""A click action."""
ComputerAction: TypeAlias = Annotated[
    ClickParam
    | DoubleClickAction
    | Drag
    | KeyPressAction
    | Move
    | Screenshot
    | Scroll
    | Type
    | Wait,
    Field(discriminator="type"),
]


class ComputerCallOutputItemParam(BaseModel):
    """The output of a computer tool call."""

    id: str | None = None
    call_id: str = Field(
        ..., description="The ID of the computer tool call that produced the output."
    )
    type: Literal["computer_call_output"] = Field(
        "computer_call_output",
        description="The type of the computer tool call output. Always `computer_call_output`.",
    )
    output: ComputerScreenshotImage
    acknowledged_safety_checks: List[ComputerCallSafetyCheckParam] | None = None
    status: FunctionCallItemStatus | None = None


class ComputerCallSafetyCheckParam(BaseModel):
    """A pending safety check for the computer call."""

    id: str = Field(..., description="The ID of the pending safety check.")
    code: str | None = None
    message: str | None = None


class ComputerEnvironment(Enum):
    WINDOWS = "windows"
    MAC = "mac"
    LINUX = "linux"
    UBUNTU = "ubuntu"
    BROWSER = "browser"


class ComputerScreenshotImage(BaseModel):
    """A computer screenshot image used with the computer use tool."""

    type: Literal["computer_screenshot"] = Field(
        "computer_screenshot",
        description="Specifies the event type. For a computer screenshot, this property is \nalways set to `computer_screenshot`.\n",
    )
    image_url: str | None = Field(None, description="The URL of the screenshot image.")
    file_id: str | None = Field(
        None, description="The identifier of an uploaded file that contains the screenshot."
    )


class ComputerToolCall(BaseModel):
    """
    A tool call to a computer use tool. See the
    [computer use guide](https://platform.openai.com/docs/guides/tools-computer-use) for more information.
    """

    type: Literal["computer_call"] = Field(
        "computer_call", description="The type of the computer call. Always `computer_call`."
    )
    id: str = Field(..., description="The unique ID of the computer call.")
    call_id: str = Field(
        ..., description="An identifier used when responding to the tool call with output.\n"
    )
    action: ComputerAction
    pending_safety_checks: List[ComputerCallSafetyCheckParam] = Field(
        ..., description="The pending safety checks for the computer call.\n"
    )
    status: Literal["in_progress", "completed", "incomplete"] = Field(
        ...,
        description="The status of the item. One of `in_progress`, `completed`, or\n`incomplete`. Populated when items are returned via API.\n",
    )


class ComputerUsePreviewTool(BaseModel):
    """A tool that controls a virtual computer. Learn more about the [computer tool](https://platform.openai.com/docs/guides/tools-computer-use)."""

    type: Literal["computer_use_preview"] = Field(
        "computer_use_preview",
        description="The type of the computer use tool. Always `computer_use_preview`.",
    )
    environment: ComputerEnvironment = Field(
        ..., description="The type of computer environment to control."
    )
    display_width: int = Field(..., description="The width of the computer display.")
    display_height: int = Field(..., description="The height of the computer display.")


class Conversation2(BaseModel):
    """The conversation that this response belongs to. Input items and output items from this response are automatically added to this conversation."""

    id: str = Field(..., description="The unique ID of the conversation.")


class ConversationParam2(BaseModel):
    """The conversation that this response belongs to."""

    id: str = Field(..., description="The unique ID of the conversation.")


"""
The conversation that this response belongs to. Items from this conversation are prepended to `input_items` for this response request.
Input items and output items from this response are automatically added to this conversation after this response completes.
"""
ConversationParam: TypeAlias = str | ConversationParam2


class ModelResponseProperties(BaseModel):
    metadata: Metadata | None = None
    top_logprobs: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    user: str | None = Field(
        None,
        description="This field is being replaced by `safety_identifier` and `prompt_cache_key`. Use `prompt_cache_key` instead to maintain caching optimizations.\nA stable identifier for your end-users.\nUsed to boost cache hit rates by better bucketing similar requests and  to help OpenAI detect and prevent abuse. [Learn more](https://platform.openai.com/docs/guides/safety-best-practices#safety-identifiers).\n",
    )
    safety_identifier: str | None = Field(
        None,
        description="A stable identifier used to help detect users of your application that may be violating OpenAI's usage policies.\nThe IDs should be a string that uniquely identifies each user. We recommend hashing their username or email address, in order to avoid sending us any identifying information. [Learn more](https://platform.openai.com/docs/guides/safety-best-practices#safety-identifiers).\n",
    )
    prompt_cache_key: str | None = Field(
        None,
        description="Used by OpenAI to cache responses for similar requests to optimize your cache hit rates. Replaces the `user` field. [Learn more](https://platform.openai.com/docs/guides/prompt-caching).\n",
    )
    service_tier: ServiceTier | None = None
    prompt_cache_retention: Literal["in-memory", "24h"] | None = None


class CreateModelResponseProperties(ModelResponseProperties):
    top_logprobs: int | None = Field(
        None,
        description="An integer between 0 and 20 specifying the number of most likely tokens to\nreturn at each token position, each with an associated log probability.\n",
    )


class ResponseProperties(BaseModel):
    previous_response_id: str | None = None
    model: ModelIdsResponses | None = Field(
        None,
        description="Model ID used to generate the response, like `gpt-4o` or `o3`. OpenAI\noffers a wide range of models with different capabilities, performance\ncharacteristics, and price points. Refer to the [model guide](https://platform.openai.com/docs/models)\nto browse and compare available models.\n",
    )
    reasoning: Reasoning | None = None
    background: bool | None = None
    max_output_tokens: int | None = None
    max_tool_calls: int | None = None
    text: ResponseTextParam | None = None
    tools: ToolsArray | None = None
    tool_choice: ToolChoiceParam | None = None
    prompt: Prompt | None = None
    truncation: Literal["auto", "disabled"] | None = None


class CreateResponse(CreateModelResponseProperties, ResponseProperties):
    input: InputParam | None = None
    include: List[IncludeEnum] | None = None
    parallel_tool_calls: bool | None = None
    store: bool | None = None
    instructions: str | None = None
    stream: bool | None = None
    stream_options: ResponseStreamOptions | None = None
    conversation: ConversationParam | None = None


class CustomGrammarFormatParam(BaseModel):
    """A grammar defined by the user."""

    type: Literal["grammar"] = Field("grammar", description="Grammar format. Always `grammar`.")
    syntax: GrammarSyntax1 = Field(
        ..., description="The syntax of the grammar definition. One of `lark` or `regex`."
    )
    definition: str = Field(..., description="The grammar definition.")


class CustomTextFormatParam(BaseModel):
    """Unconstrained free-form text."""

    type: Literal["text"] = Field("text", description="Unconstrained text format. Always `text`.")


class CustomToolCall(BaseModel):
    """A call to a custom tool created by the model."""

    type: Literal["custom_tool_call"] = Field(
        "custom_tool_call",
        description="The type of the custom tool call. Always `custom_tool_call`.\n",
    )
    id: str | None = Field(
        None, description="The unique ID of the custom tool call in the OpenAI platform.\n"
    )
    call_id: str = Field(
        ..., description="An identifier used to map this custom tool call to a tool call output.\n"
    )
    name: str = Field(..., description="The name of the custom tool being called.\n")
    input: str = Field(
        ..., description="The input for the custom tool call generated by the model.\n"
    )


class CustomToolCallOutput(BaseModel):
    """The output of a custom tool call from your code, being sent back to the model."""

    type: Literal["custom_tool_call_output"] = Field(
        "custom_tool_call_output",
        description="The type of the custom tool call output. Always `custom_tool_call_output`.\n",
    )
    id: str | None = Field(
        None, description="The unique ID of the custom tool call output in the OpenAI platform.\n"
    )
    call_id: str = Field(
        ...,
        description="The call ID, used to map this custom tool call output to a custom tool call.\n",
    )
    output: str | List[FunctionAndCustomToolCallOutput] = Field(
        ...,
        description="The output from the custom tool call generated by your code.\nCan be a string or an list of output content.\n",
    )


class CustomToolParam(BaseModel):
    """A custom tool that processes input using a specified format. Learn more about   [custom tools](https://platform.openai.com/docs/guides/function-calling#custom-tools)"""

    type: Literal["custom"] = Field(
        "custom", description="The type of the custom tool. Always `custom`."
    )
    name: str = Field(
        ..., description="The name of the custom tool, used to identify it in tool calls."
    )
    description: str | None = Field(
        None, description="Optional description of the custom tool, used to provide more context."
    )
    format: CustomTextFormatParam | CustomGrammarFormatParam | None = Field(
        None, description="The input format for the custom tool. Default is unconstrained text."
    )


class DetailEnum(Enum):
    LOW = "low"
    HIGH = "high"
    AUTO = "auto"


class DragPoint(BaseModel):
    """An x/y coordinate pair, e.g. `{ x: 100, y: 200 }`."""

    x: int = Field(..., description="The x-coordinate.")
    y: int = Field(..., description="The y-coordinate.")


class EasyInputMessage(BaseModel):
    """
    A message input to the model with a role indicating instruction following
    hierarchy. Instructions given with the `developer` or `system` role take
    precedence over instructions given with the `user` role. Messages with the
    `assistant` role are presumed to have been generated by the model in previous
    interactions.
    """

    role: Literal["user", "assistant", "system", "developer"] = Field(
        ...,
        description="The role of the message input. One of `user`, `assistant`, `system`, or\n`developer`.\n",
    )
    content: str | InputMessageContentList = Field(
        ...,
        description="Text, image, or audio input to the model, used to generate a response.\nCan also contain previous assistant responses.\n",
    )
    type: Literal["message"] = Field(
        "message", description="The type of the message input. Always `message`.\n"
    )


class FileSearchTool(BaseModel):
    """A tool that searches for relevant content from uploaded files. Learn more about the [file search tool](https://platform.openai.com/docs/guides/tools-file-search)."""

    type: Literal["file_search"] = Field(
        "file_search", description="The type of the file search tool. Always `file_search`."
    )
    vector_store_ids: List[str] = Field(..., description="The IDs of the vector stores to search.")
    max_num_results: int | None = Field(
        None,
        description="The maximum number of results to return. This number should be between 1 and 50 inclusive.",
    )
    ranking_options: RankingOptions | None = Field(None, description="Ranking options for search.")
    filters: Filters | None = None


class FileSearchToolCall(BaseModel):
    """
    The results of a file search tool call. See the
    [file search guide](https://platform.openai.com/docs/guides/tools-file-search) for more information.
    """

    id: str = Field(..., description="The unique ID of the file search tool call.\n")
    type: Literal["file_search_call"] = Field(
        "file_search_call",
        description="The type of the file search tool call. Always `file_search_call`.\n",
    )
    status: Literal["in_progress", "searching", "completed", "incomplete", "failed"] = Field(
        ...,
        description="The status of the file search tool call. One of `in_progress`,\n`searching`, `incomplete` or `failed`,\n",
    )
    queries: List[str] = Field(..., description="The queries used to search for files.\n")
    results: List[Dict[str, Any]] | None = None


"""A filter used to compare a specified attribute key to a given value using a defined comparison operation."""
Filters: TypeAlias = ComparisonFilter | CompoundFilter


class InputTextContent(BaseModel):
    """A text input to the model."""

    type: Literal["input_text"] = Field(
        "input_text", description="The type of the input item. Always `input_text`."
    )
    text: str = Field(..., description="The text input to the model.")


class InputImageContent(BaseModel):
    """An image input to the model. Learn about [image inputs](https://platform.openai.com/docs/guides/vision)."""

    type: Literal["input_image"] = Field(
        "input_image", description="The type of the input item. Always `input_image`."
    )
    image_url: str | None = None
    file_id: str | None = None
    detail: ImageDetail = Field(
        ...,
        description="The detail level of the image to be sent to the model. One of `high`, `low`, or `auto`. Defaults to `auto`.",
    )


class InputFileContent(BaseModel):
    """A file input to the model."""

    type: Literal["input_file"] = Field(
        "input_file", description="The type of the input item. Always `input_file`."
    )
    file_id: str | None = None
    filename: str | None = Field(None, description="The name of the file to be sent to the model.")
    file_url: str | None = Field(None, description="The URL of the file to be sent to the model.")
    file_data: str | None = Field(
        None, description="The content of the file to be sent to the model.\n"
    )


"""A text input to the model."""
FunctionAndCustomToolCallOutput: TypeAlias = Annotated[
    InputTextContent | InputImageContent | InputFileContent, Field(discriminator="type")
]


class FunctionCallItemStatus(Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"


class FunctionCallOutputItemParam(BaseModel):
    """The output of a function tool call."""

    id: str | None = None
    call_id: str = Field(
        ..., description="The unique ID of the function tool call generated by the model."
    )
    type: Literal["function_call_output"] = Field(
        "function_call_output",
        description="The type of the function tool call output. Always `function_call_output`.",
    )
    output: (
        str | List[InputTextContentParam | InputImageContentParamAutoParam | InputFileContentParam]
    ) = Field(..., description="Text, image, or file output of the function tool call.")
    status: FunctionCallItemStatus | None = None


class FunctionShellAction(BaseModel):
    """Execute a shell command."""

    commands: List[str]
    timeout_ms: int | None
    max_output_length: int | None


class FunctionShellActionParam(BaseModel):
    """Commands and limits describing how to run the function shell tool call."""

    commands: List[str] = Field(
        ..., description="Ordered shell commands for the execution environment to run."
    )
    timeout_ms: int | None = None
    max_output_length: int | None = None


class FunctionShellCall(BaseModel):
    """A tool call that executes one or more shell commands in a managed environment."""

    type: Literal["shell_call"] = Field(
        "shell_call", description="The type of the item. Always `shell_call`."
    )
    id: str = Field(
        ...,
        description="The unique ID of the function shell tool call. Populated when this item is returned via API.",
    )
    call_id: str = Field(
        ..., description="The unique ID of the function shell tool call generated by the model."
    )
    action: FunctionShellAction = Field(
        ..., description="The shell commands and limits that describe how to run the tool call."
    )
    status: LocalShellCallStatus = Field(
        ...,
        description="The status of the shell call. One of `in_progress`, `completed`, or `incomplete`.",
    )
    created_by: str | None = Field(
        None, description="The ID of the entity that created this tool call."
    )


class FunctionShellCallItemParam(BaseModel):
    """A tool representing a request to execute one or more shell commands."""

    id: str | None = None
    call_id: str = Field(
        ..., description="The unique ID of the function shell tool call generated by the model."
    )
    type: Literal["shell_call"] = Field(
        "shell_call", description="The type of the item. Always `function_shell_call`."
    )
    action: FunctionShellActionParam = Field(
        ..., description="The shell commands and limits that describe how to run the tool call."
    )
    status: FunctionShellCallItemStatus | None = None


class FunctionShellCallItemStatus(Enum):
    """Status values reported for function shell tool calls."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"


class FunctionShellCallOutput(BaseModel):
    """The output of a shell tool call."""

    type: Literal["shell_call_output"] = Field(
        "shell_call_output",
        description="The type of the shell call output. Always `shell_call_output`.",
    )
    id: str = Field(
        ...,
        description="The unique ID of the shell call output. Populated when this item is returned via API.",
    )
    call_id: str = Field(
        ..., description="The unique ID of the shell tool call generated by the model."
    )
    output: List[FunctionShellCallOutputContent] = Field(
        ..., description="An array of shell call output contents"
    )
    max_output_length: int | None
    created_by: str | None = None


class FunctionShellCallOutputContent(BaseModel):
    """The content of a shell call output."""

    stdout: str
    stderr: str
    outcome: FunctionShellCallOutputTimeoutOutcome | FunctionShellCallOutputExitOutcome = Field(
        ...,
        description="Represents either an exit outcome (with an exit code) or a timeout outcome for a shell call output chunk.",
    )
    created_by: str | None = None


class FunctionShellCallOutputContentParam(BaseModel):
    """Captured stdout and stderr for a portion of a function shell tool call output."""

    stdout: str = Field(..., description="Captured stdout output for this chunk of the shell call.")
    stderr: str = Field(..., description="Captured stderr output for this chunk of the shell call.")
    outcome: FunctionShellCallOutputOutcomeParam = Field(
        ..., description="The exit or timeout outcome associated with this chunk."
    )


class FunctionShellCallOutputExitOutcome(BaseModel):
    """Indicates that the shell commands finished and returned an exit code."""

    type: Literal["exit"] = Field("exit", description="The outcome type. Always `exit`.")
    exit_code: int = Field(..., description="Exit code from the shell process.")


class FunctionShellCallOutputExitOutcomeParam(BaseModel):
    """Indicates that the shell commands finished and returned an exit code."""

    type: Literal["exit"] = Field("exit", description="The outcome type. Always `exit`.")
    exit_code: int = Field(..., description="The exit code returned by the shell process.")


class FunctionShellCallOutputItemParam(BaseModel):
    """The streamed output items emitted by a function shell tool call."""

    id: str | None = None
    call_id: str = Field(
        ..., description="The unique ID of the function shell tool call generated by the model."
    )
    type: Literal["shell_call_output"] = Field(
        "shell_call_output",
        description="The type of the item. Always `function_shell_call_output`.",
    )
    output: List[FunctionShellCallOutputContentParam] = Field(
        ...,
        description="Captured chunks of stdout and stderr output, along with their associated outcomes.",
    )
    max_output_length: int | None = None


class FunctionShellCallOutputTimeoutOutcomeParam(BaseModel):
    """Indicates that the function shell call exceeded its configured time limit."""

    type: Literal["timeout"] = Field("timeout", description="The outcome type. Always `timeout`.")


"""The exit or timeout outcome associated with this chunk."""
FunctionShellCallOutputOutcomeParam: TypeAlias = Annotated[
    FunctionShellCallOutputTimeoutOutcomeParam | FunctionShellCallOutputExitOutcomeParam,
    Field(discriminator="type"),
]


class FunctionShellCallOutputTimeoutOutcome(BaseModel):
    """Indicates that the function shell call exceeded its configured time limit."""

    type: Literal["timeout"] = Field("timeout", description="The outcome type. Always `timeout`.")


class FunctionShellToolParam(BaseModel):
    """A tool that allows the model to execute shell commands."""

    type: Literal["shell"] = Field(
        "shell", description="The type of the shell tool. Always `shell`."
    )


class FunctionTool(BaseModel):
    """Defines a function in your own code the model can choose to call. Learn more about [function calling](https://platform.openai.com/docs/guides/function-calling)."""

    type: Literal["function"] = Field(
        "function", description="The type of the function tool. Always `function`."
    )
    name: str = Field(..., description="The name of the function to call.")
    description: str | None = None
    parameters: Dict[str, Any] | None
    strict: bool | None


class FunctionToolCall(BaseModel):
    """
    A tool call to run a function. See the
    [function calling guide](https://platform.openai.com/docs/guides/function-calling) for more information.
    """

    id: str | None = Field(None, description="The unique ID of the function tool call.\n")
    type: Literal["function_call"] = Field(
        "function_call", description="The type of the function tool call. Always `function_call`.\n"
    )
    call_id: str = Field(
        ..., description="The unique ID of the function tool call generated by the model.\n"
    )
    name: str = Field(..., description="The name of the function to run.\n")
    arguments: str = Field(
        ..., description="A JSON string of the arguments to pass to the function.\n"
    )
    status: Literal["in_progress", "completed", "incomplete"] | None = Field(
        None,
        description="The status of the item. One of `in_progress`, `completed`, or\n`incomplete`. Populated when items are returned via API.\n",
    )


class GrammarSyntax1(Enum):
    LARK = "lark"
    REGEX = "regex"


class HybridSearchOptions(BaseModel):
    embedding_weight: float = Field(
        ..., description="The weight of the embedding in the reciprocal ranking fusion."
    )
    text_weight: float = Field(
        ..., description="The weight of the text in the reciprocal ranking fusion."
    )


class ImageDetail(Enum):
    LOW = "low"
    HIGH = "high"
    AUTO = "auto"


class ImageGenTool(BaseModel):
    """A tool that generates images using a model like `gpt-image-1`."""

    type: Literal["image_generation"] = Field(
        "image_generation",
        description="The type of the image generation tool. Always `image_generation`.\n",
    )
    model: Literal["gpt-image-1", "gpt-image-1-mini"] | None = Field(
        None, description="The image generation model to use. Default: `gpt-image-1`.\n"
    )
    quality: Literal["low", "medium", "high", "auto"] | None = Field(
        None,
        description="The quality of the generated image. One of `low`, `medium`, `high`,\nor `auto`. Default: `auto`.\n",
    )
    size: Literal["1024x1024", "1024x1536", "1536x1024", "auto"] | None = Field(
        None,
        description="The size of the generated image. One of `1024x1024`, `1024x1536`,\n`1536x1024`, or `auto`. Default: `auto`.\n",
    )
    output_format: Literal["png", "webp", "jpeg"] | None = Field(
        None,
        description="The output format of the generated image. One of `png`, `webp`, or\n`jpeg`. Default: `png`.\n",
    )
    output_compression: int | None = Field(
        None, description="Compression level for the output image. Default: 100.\n"
    )
    moderation: Literal["auto", "low"] | None = Field(
        None, description="Moderation level for the generated image. Default: `auto`.\n"
    )
    background: Literal["transparent", "opaque", "auto"] | None = Field(
        None,
        description="Background type for the generated image. One of `transparent`,\n`opaque`, or `auto`. Default: `auto`.\n",
    )
    input_fidelity: InputFidelity | None = None
    input_image_mask: Dict[str, Any] | None = Field(
        None,
        description="Optional mask for inpainting. Contains `image_url`\n(string, optional) and `file_id` (string, optional).\n",
    )
    partial_images: int | None = Field(
        None,
        description="Number of partial images to generate in streaming mode, from 0 (default value) to 3.\n",
    )


class ImageGenToolCall(BaseModel):
    """An image generation request made by the model."""

    type: Literal["image_generation_call"] = Field(
        "image_generation_call",
        description="The type of the image generation call. Always `image_generation_call`.\n",
    )
    id: str = Field(..., description="The unique ID of the image generation call.\n")
    status: Literal["in_progress", "completed", "generating", "failed"] = Field(
        ..., description="The status of the image generation call.\n"
    )
    result: str | None


class IncludeEnum(Enum):
    """
    Specify additional output data to include in the model response. Currently supported values are:
    - `web_search_call.action.sources`: Include the sources of the web search tool call.
    - `code_interpreter_call.outputs`: Includes the outputs of python code execution in code interpreter tool call items.
    - `computer_call_output.output.image_url`: Include image urls from the computer call output.
    - `file_search_call.results`: Include the search results of the file search tool call.
    - `message.input_image.image_url`: Include image urls from the input message.
    - `message.output_text.logprobs`: Include logprobs with assistant messages.
    - `reasoning.encrypted_content`: Includes an encrypted version of reasoning tokens in reasoning item outputs. This enables reasoning items to be used in multi-turn conversations when using the Responses API statelessly (like when the `store` parameter is set to `false`, or when an organization is enrolled in the zero data retention program).
    """

    FILE_SEARCH_CALLRESULTS = "file_search_call.results"
    WEB_SEARCH_CALLRESULTS = "web_search_call.results"
    WEB_SEARCH_CALLACTIONSOURCES = "web_search_call.action.sources"
    MESSAGEINPUT_IMAGEIMAGE_URL = "message.input_image.image_url"
    COMPUTER_CALL_OUTPUTOUTPUTIMAGE_URL = "computer_call_output.output.image_url"
    CODE_INTERPRETER_CALLOUTPUTS = "code_interpreter_call.outputs"
    REASONINGENCRYPTED_CONTENT = "reasoning.encrypted_content"
    MESSAGEOUTPUT_TEXTLOGPROBS = "message.output_text.logprobs"


"""A text input to the model."""
InputContent: TypeAlias = Annotated[
    InputTextContent | InputImageContent | InputFileContent, Field(discriminator="type")
]


class InputFidelity(Enum):
    """Control how much effort the model will exert to match the style and features, especially facial features, of input images. This parameter is only supported for `gpt-image-1`. Unsupported for `gpt-image-1-mini`. Supports `high` and `low`. Defaults to `low`."""

    HIGH = "high"
    LOW = "low"


class InputFileContentParam(BaseModel):
    """A file input to the model."""

    type: Literal["input_file"] = Field(
        "input_file", description="The type of the input item. Always `input_file`."
    )
    file_id: str | None = None
    filename: str | None = None
    file_data: str | None = None
    file_url: str | None = None


class InputImageContentParamAutoParam(BaseModel):
    """An image input to the model. Learn about [image inputs](https://platform.openai.com/docs/guides/vision)"""

    type: Literal["input_image"] = Field(
        "input_image", description="The type of the input item. Always `input_image`."
    )
    image_url: str | None = None
    file_id: str | None = None
    detail: DetailEnum | None = None


class InputMessage(BaseModel):
    """
    A message input to the model with a role indicating instruction following
    hierarchy. Instructions given with the `developer` or `system` role take
    precedence over instructions given with the `user` role.
    """

    type: Literal["message"] = Field(
        "message", description="The type of the message input. Always set to `message`.\n"
    )
    role: Literal["user", "system", "developer"] = Field(
        ..., description="The role of the message input. One of `user`, `system`, or `developer`.\n"
    )
    status: Literal["in_progress", "completed", "incomplete"] | None = Field(
        None,
        description="The status of item. One of `in_progress`, `completed`, or\n`incomplete`. Populated when items are returned via API.\n",
    )
    content: InputMessageContentList


class OutputMessage(BaseModel):
    """An output message from the model."""

    id: str = Field(..., description="The unique ID of the output message.\n")
    type: Literal["message"] = Field(
        "message", description="The type of the output message. Always `message`.\n"
    )
    role: Literal["assistant"] = Field(
        "assistant", description="The role of the output message. Always `assistant`.\n"
    )
    content: List[OutputMessageContent] = Field(
        ..., description="The content of the output message.\n"
    )
    status: Literal["in_progress", "completed", "incomplete"] = Field(
        ...,
        description="The status of the message input. One of `in_progress`, `completed`, or\n`incomplete`. Populated when input items are returned via API.\n",
    )


class WebSearchToolCall(BaseModel):
    """
    The results of a web search tool call. See the
    [web search guide](https://platform.openai.com/docs/guides/tools-web-search) for more information.
    """

    id: str = Field(..., description="The unique ID of the web search tool call.\n")
    type: Literal["web_search_call"] = Field(
        "web_search_call",
        description="The type of the web search tool call. Always `web_search_call`.\n",
    )
    status: Literal["in_progress", "searching", "completed", "failed"] = Field(
        ..., description="The status of the web search tool call.\n"
    )
    action: Dict[str, Any] = Field(
        ...,
        description="An object describing the specific action taken in this web search call.\nIncludes details on how the model used the web (search, open_page, find).\n",
    )


class ReasoningItem(BaseModel):
    """
    A description of the chain of thought used by a reasoning model while generating
    a response. Be sure to include these items in your `input` to the Responses API
    for subsequent turns of a conversation if you are manually
    [managing context](https://platform.openai.com/docs/guides/conversation-state).
    """

    type: Literal["reasoning"] = Field(
        "reasoning", description="The type of the object. Always `reasoning`.\n"
    )
    id: str = Field(..., description="The unique identifier of the reasoning content.\n")
    encrypted_content: str | None = None
    summary: List[Summary] = Field(..., description="Reasoning summary content.\n")
    content: List[ReasoningTextContent] | None = Field(
        None, description="Reasoning text content.\n"
    )
    status: Literal["in_progress", "completed", "incomplete"] | None = Field(
        None,
        description="The status of the item. One of `in_progress`, `completed`, or\n`incomplete`. Populated when items are returned via API.\n",
    )


class LocalShellToolCall(BaseModel):
    """A tool call to run a command on the local shell."""

    type: Literal["local_shell_call"] = Field(
        "local_shell_call",
        description="The type of the local shell call. Always `local_shell_call`.\n",
    )
    id: str = Field(..., description="The unique ID of the local shell call.\n")
    call_id: str = Field(
        ..., description="The unique ID of the local shell tool call generated by the model.\n"
    )
    action: LocalShellExecAction
    status: Literal["in_progress", "completed", "incomplete"] = Field(
        ..., description="The status of the local shell call.\n"
    )


class LocalShellToolCallOutput(BaseModel):
    """The output of a local shell tool call."""

    type: Literal["local_shell_call_output"] = Field(
        "local_shell_call_output",
        description="The type of the local shell tool call output. Always `local_shell_call_output`.\n",
    )
    id: str = Field(
        ..., description="The unique ID of the local shell tool call generated by the model.\n"
    )
    output: str = Field(
        ..., description="A JSON string of the output of the local shell tool call.\n"
    )
    status: Literal["in_progress", "completed", "incomplete"] | None = None


class MCPListTools(BaseModel):
    """A list of tools available on an MCP server."""

    type: Literal["mcp_list_tools"] = Field(
        "mcp_list_tools", description="The type of the item. Always `mcp_list_tools`.\n"
    )
    id: str = Field(..., description="The unique ID of the list.\n")
    server_label: str = Field(..., description="The label of the MCP server.\n")
    tools: List[MCPListToolsTool] = Field(..., description="The tools available on the server.\n")
    error: str | None = None


class MCPApprovalRequest(BaseModel):
    """A request for human approval of a tool invocation."""

    type: Literal["mcp_approval_request"] = Field(
        "mcp_approval_request", description="The type of the item. Always `mcp_approval_request`.\n"
    )
    id: str = Field(..., description="The unique ID of the approval request.\n")
    server_label: str = Field(..., description="The label of the MCP server making the request.\n")
    name: str = Field(..., description="The name of the tool to run.\n")
    arguments: str = Field(..., description="A JSON string of arguments for the tool.\n")


class MCPApprovalResponse(BaseModel):
    """A response to an MCP approval request."""

    type: Literal["mcp_approval_response"] = Field(
        "mcp_approval_response",
        description="The type of the item. Always `mcp_approval_response`.\n",
    )
    id: str | None = None
    approval_request_id: str = Field(
        ..., description="The ID of the approval request being answered.\n"
    )
    approve: bool = Field(..., description="Whether the request was approved.\n")
    reason: str | None = None


class MCPToolCall(BaseModel):
    """An invocation of a tool on an MCP server."""

    type: Literal["mcp_call"] = Field(
        "mcp_call", description="The type of the item. Always `mcp_call`.\n"
    )
    id: str = Field(..., description="The unique ID of the tool call.\n")
    server_label: str = Field(..., description="The label of the MCP server running the tool.\n")
    name: str = Field(..., description="The name of the tool that was run.\n")
    arguments: str = Field(..., description="A JSON string of the arguments passed to the tool.\n")
    output: str | None = None
    error: str | None = None
    status: MCPToolCallStatus | None = Field(
        None,
        description="The status of the tool call. One of `in_progress`, `completed`, `incomplete`, `calling`, or `failed`.\n",
    )
    approval_request_id: str | None = None


Message: TypeAlias = Annotated[InputMessage | OutputMessage, Field(discriminator="role")]

Item: TypeAlias = Annotated[
    Message
    | FileSearchToolCall
    | ComputerToolCall
    | ComputerCallOutputItemParam
    | WebSearchToolCall
    | FunctionToolCall
    | FunctionCallOutputItemParam
    | ReasoningItem
    | ImageGenToolCall
    | CodeInterpreterToolCall
    | LocalShellToolCall
    | LocalShellToolCallOutput
    | FunctionShellCallItemParam
    | FunctionShellCallOutputItemParam
    | ApplyPatchToolCallItemParam
    | ApplyPatchToolCallOutputItemParam
    | MCPListTools
    | MCPApprovalRequest
    | MCPApprovalResponse
    | MCPToolCall
    | CustomToolCallOutput
    | CustomToolCall,
    Field(discriminator="type"),
]


class ItemReferenceParam(BaseModel):
    """An internal identifier for an item to reference."""

    type: Literal["item_reference"]
    id: str = Field(..., description="The ID of the item to reference.")


InputItem: TypeAlias = EasyInputMessage | Item | ItemReferenceParam

"""
A list of one or many input items to the model, containing different content
types.
"""
InputMessageContentList: TypeAlias = List[InputContent]

"""
Text, image, or file inputs to the model, used to generate a response.

Learn more:
- [Text inputs and outputs](https://platform.openai.com/docs/guides/text)
- [Image inputs](https://platform.openai.com/docs/guides/images)
- [File inputs](https://platform.openai.com/docs/guides/pdf-files)
- [Conversation state](https://platform.openai.com/docs/guides/conversation-state)
- [Function calling](https://platform.openai.com/docs/guides/function-calling)
"""
InputParam: TypeAlias = str | List[InputItem]


class InputTextContentParam(BaseModel):
    """A text input to the model."""

    type: Literal["input_text"] = Field(
        "input_text", description="The type of the input item. Always `input_text`."
    )
    text: str = Field(..., description="The text input to the model.")


class ListModelsResponse(BaseModel):
    object: Literal["list"] = "list"
    data: List[Model]
    model_config = ConfigDict(extra="allow")


class LocalShellCallStatus(Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"


class LocalShellExecAction(BaseModel):
    """Execute a shell command on the server."""

    type: Literal["exec"] = Field(
        "exec", description="The type of the local shell action. Always `exec`."
    )
    command: List[str] = Field(..., description="The command to run.")
    timeout_ms: int | None = None
    working_directory: str | None = None
    env: Dict[str, str] = Field(..., description="Environment variables to set for the command.")
    user: str | None = None


class LocalShellToolParam(BaseModel):
    """A tool that allows the model to execute shell commands in a local environment."""

    type: Literal["local_shell"] = Field(
        "local_shell", description="The type of the local shell tool. Always `local_shell`."
    )


class LogProb(BaseModel):
    """The log probability of a token."""

    token: str
    logprob: float
    bytes: List[int]
    top_logprobs: List[TopLogProb]


class MCPListToolsTool(BaseModel):
    """A tool available on an MCP server."""

    name: str = Field(..., description="The name of the tool.\n")
    description: str | None = None
    input_schema: Dict[str, Any] = Field(
        ..., description="The JSON schema describing the tool's input.\n"
    )
    annotations: Dict[str, Any] | None = None


class MCPTool(BaseModel):
    """
    Give the model access to additional tools via remote Model Context Protocol
    (MCP) servers. [Learn more about MCP](https://platform.openai.com/docs/guides/tools-remote-mcp).
    """

    type: Literal["mcp"] = Field("mcp", description="The type of the MCP tool. Always `mcp`.")
    server_label: str = Field(
        ..., description="A label for this MCP server, used to identify it in tool calls.\n"
    )
    server_url: str | None = Field(
        None,
        description="The URL for the MCP server. One of `server_url` or `connector_id` must be\nprovided.\n",
    )
    connector_id: (
        Literal[
            "connector_dropbox",
            "connector_gmail",
            "connector_googlecalendar",
            "connector_googledrive",
            "connector_microsoftteams",
            "connector_outlookcalendar",
            "connector_outlookemail",
            "connector_sharepoint",
        ]
        | None
    ) = Field(
        None,
        description="Identifier for service connectors, like those available in ChatGPT. One of\n`server_url` or `connector_id` must be provided. Learn more about service\nconnectors [here](https://platform.openai.com/docs/guides/tools-remote-mcp#connectors).\n\nCurrently supported `connector_id` values are:\n\n- Dropbox: `connector_dropbox`\n- Gmail: `connector_gmail`\n- Google Calendar: `connector_googlecalendar`\n- Google Drive: `connector_googledrive`\n- Microsoft Teams: `connector_microsoftteams`\n- Outlook Calendar: `connector_outlookcalendar`\n- Outlook Email: `connector_outlookemail`\n- SharePoint: `connector_sharepoint`\n",
    )
    authorization: str | None = Field(
        None,
        description="An OAuth access token that can be used with a remote MCP server, either\nwith a custom MCP server URL or a service connector. Your application\nmust handle the OAuth authorization flow and provide the token here.\n",
    )
    server_description: str | None = Field(
        None, description="Optional description of the MCP server, used to provide more context.\n"
    )
    headers: Dict[str, str] | None = None
    allowed_tools: List[str] | MCPToolFilter | None = None
    require_approval: Dict[str, Any] | Literal["always", "never"] | None = None


class MCPToolCallStatus(Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    CALLING = "calling"
    FAILED = "failed"


class MCPToolFilter(BaseModel):
    """A filter object to specify which tools are allowed."""

    tool_names: List[str] | None = Field(None, description="List of allowed tool names.")
    read_only: bool | None = Field(
        None,
        description="Indicates whether or not a tool modifies data or is read-only. If an\nMCP server is [annotated with `readOnlyHint`](https://modelcontextprotocol.io/specification/2025-06-18/schema#toolannotations-readonlyhint),\nit will match this filter.\n",
    )


"""
Set of 16 key-value pairs that can be attached to an object. This can be
useful for storing additional information about the object in a structured
format, and querying for objects via API or the dashboard.

Keys are strings with a maximum length of 64 characters. Values are strings
with a maximum length of 512 characters.
"""
Metadata: TypeAlias = Dict[str, str] | None


class Model(BaseModel):
    """Describes an OpenAI model offering that can be used with the API."""

    id: str = Field(
        ..., description="The model identifier, which can be referenced in the API endpoints."
    )
    created: int = Field(
        ..., description="The Unix timestamp (in seconds) when the model was created."
    )
    object: Literal["model"] = Field(
        "model", description='The object type, which is always "model".'
    )
    owned_by: str = Field(..., description="The organization that owns the model.")


ModelIdsShared: TypeAlias = str | ChatModel

ModelIdsResponses: TypeAlias = (
    ModelIdsShared
    | Literal[
        "o1-pro",
        "o1-pro-2025-03-19",
        "o3-pro",
        "o3-pro-2025-06-10",
        "o3-deep-research",
        "o3-deep-research-2025-06-26",
        "o4-mini-deep-research",
        "o4-mini-deep-research-2025-06-26",
        "computer-use-preview",
        "computer-use-preview-2025-03-11",
        "gpt-5-codex",
        "gpt-5-pro",
        "gpt-5-pro-2025-10-06",
    ]
)


class OutputTextContent(BaseModel):
    """A text output from the model."""

    type: Literal["output_text"] = Field(
        "output_text", description="The type of the output text. Always `output_text`."
    )
    text: str = Field(..., description="The text output from the model.")
    annotations: List[Annotation] = Field(..., description="The annotations of the text output.")
    logprobs: List[LogProb] | None = None


class RefusalContent(BaseModel):
    """A refusal from the model."""

    type: Literal["refusal"] = Field(
        "refusal", description="The type of the refusal. Always `refusal`."
    )
    refusal: str = Field(..., description="The refusal explanation from the model.")


class ReasoningTextContent(BaseModel):
    """Reasoning text from the model."""

    type: Literal["reasoning_text"] = Field(
        "reasoning_text", description="The type of the reasoning text. Always `reasoning_text`."
    )
    text: str = Field(..., description="The reasoning text from the model.")


"""A text output from the model."""
OutputContent: TypeAlias = Annotated[
    OutputTextContent | RefusalContent | ReasoningTextContent, Field(discriminator="type")
]

"""An output message from the model."""
OutputItem: TypeAlias = Annotated[
    OutputMessage
    | FileSearchToolCall
    | FunctionToolCall
    | WebSearchToolCall
    | ComputerToolCall
    | ReasoningItem
    | ImageGenToolCall
    | CodeInterpreterToolCall
    | LocalShellToolCall
    | FunctionShellCall
    | FunctionShellCallOutput
    | ApplyPatchToolCall
    | ApplyPatchToolCallOutput
    | MCPToolCall
    | MCPListTools
    | MCPApprovalRequest
    | CustomToolCall,
    Field(discriminator="type"),
]

"""A text output from the model."""
OutputMessageContent: TypeAlias = Annotated[
    OutputTextContent | RefusalContent, Field(discriminator="type")
]

"""
Reference to a prompt template and its variables.
[Learn more](https://platform.openai.com/docs/guides/text?api-mode=responses#reusable-prompts).
"""
Prompt: TypeAlias = Dict[str, Any] | None


class RankerVersionType(Enum):
    AUTO = "auto"
    DEFAULT20241115 = "default-2024-11-15"


class RankingOptions(BaseModel):
    ranker: RankerVersionType | None = Field(
        None, description="The ranker to use for the file search."
    )
    score_threshold: float | None = Field(
        None,
        description="The score threshold for the file search, a number between 0 and 1. Numbers closer to 1 will attempt to return only the most relevant results, but may return fewer results.",
    )
    hybrid_search: HybridSearchOptions | None = Field(
        None,
        description="Weights that control how reciprocal rank fusion balances semantic embedding matches versus sparse keyword matches when hybrid search is enabled.",
    )


class Reasoning(BaseModel):
    """
    **gpt-5 and o-series models only**

    Configuration options for
    [reasoning models](https://platform.openai.com/docs/guides/reasoning).
    """

    effort: ReasoningEffort | None = None
    summary: Literal["auto", "concise", "detailed"] | None = None
    generate_summary: Literal["auto", "concise", "detailed"] | None = None


"""
Constrains effort on reasoning for
[reasoning models](https://platform.openai.com/docs/guides/reasoning).
Currently supported values are `none`, `minimal`, `low`, `medium`, and `high`. Reducing
reasoning effort can result in faster responses and fewer tokens used
on reasoning in a response.

- `gpt-5.1` defaults to `none`, which does not perform reasoning. The supported reasoning values for `gpt-5.1` are `none`, `low`, `medium`, and `high`. Tool calls are supported for all reasoning values in gpt-5.1.
- All models before `gpt-5.1` default to `medium` reasoning effort, and do not support `none`.
- The `gpt-5-pro` model defaults to (and only supports) `high` reasoning effort.
"""
ReasoningEffort: TypeAlias = Literal["none", "minimal", "low", "medium", "high"] | None


class Response(ModelResponseProperties, ResponseProperties):
    """The response object"""

    id: str = Field(..., description="Unique identifier for this Response.\n")
    object: Literal["response"] = Field(
        "response", description="The object type of this resource - always set to `response`.\n"
    )
    status: (
        Literal["completed", "failed", "in_progress", "cancelled", "queued", "incomplete"] | None
    ) = Field(
        None,
        description="The status of the response generation. One of `completed`, `failed`,\n`in_progress`, `cancelled`, `queued`, or `incomplete`.\n",
    )
    created_at: float = Field(
        ..., description="Unix timestamp (in seconds) of when this Response was created.\n"
    )
    error: ResponseError
    incomplete_details: Dict[str, Any] | None
    output: List[OutputItem] = Field(
        ...,
        description="An array of content items generated by the model.\n\n- The length and order of items in the `output` array is dependent\n  on the model's response.\n- Rather than accessing the first item in the `output` array and\n  assuming it's an `assistant` message with the content generated by\n  the model, you might consider using the `output_text` property where\n  supported in SDKs.\n",
    )
    instructions: str | List[InputItem] | None
    output_text: str | None = None
    usage: ResponseUsage | None = None
    parallel_tool_calls: bool = Field(
        ..., description="Whether to allow the model to run tool calls in parallel.\n"
    )
    conversation: Conversation2 | None = None


class ResponseAudioDeltaEvent(BaseModel):
    """Emitted when there is a partial audio response."""

    type: Literal["response.audio.delta"] = Field(
        "response.audio.delta",
        description="The type of the event. Always `response.audio.delta`.\n",
    )
    sequence_number: int = Field(
        ..., description="A sequence number for this chunk of the stream response.\n"
    )
    delta: str = Field(..., description="A chunk of Base64 encoded response audio bytes.\n")


class ResponseAudioDoneEvent(BaseModel):
    """Emitted when the audio response is complete."""

    type: Literal["response.audio.done"] = Field(
        "response.audio.done", description="The type of the event. Always `response.audio.done`.\n"
    )
    sequence_number: int = Field(..., description="The sequence number of the delta.\n")


class ResponseAudioTranscriptDeltaEvent(BaseModel):
    """Emitted when there is a partial transcript of audio."""

    type: Literal["response.audio.transcript.delta"] = Field(
        "response.audio.transcript.delta",
        description="The type of the event. Always `response.audio.transcript.delta`.\n",
    )
    delta: str = Field(..., description="The partial transcript of the audio response.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseAudioTranscriptDoneEvent(BaseModel):
    """Emitted when the full audio transcript is completed."""

    type: Literal["response.audio.transcript.done"] = Field(
        "response.audio.transcript.done",
        description="The type of the event. Always `response.audio.transcript.done`.\n",
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseCodeInterpreterCallCodeDeltaEvent(BaseModel):
    """Emitted when a partial code snippet is streamed by the code interpreter."""

    type: Literal["response.code_interpreter_call_code.delta"] = Field(
        "response.code_interpreter_call_code.delta",
        description="The type of the event. Always `response.code_interpreter_call_code.delta`.",
    )
    output_index: int = Field(
        ...,
        description="The index of the output item in the response for which the code is being streamed.",
    )
    item_id: str = Field(
        ..., description="The unique identifier of the code interpreter tool call item."
    )
    delta: str = Field(
        ..., description="The partial code snippet being streamed by the code interpreter."
    )
    sequence_number: int = Field(
        ..., description="The sequence number of this event, used to order streaming events."
    )


class ResponseCodeInterpreterCallCodeDoneEvent(BaseModel):
    """Emitted when the code snippet is finalized by the code interpreter."""

    type: Literal["response.code_interpreter_call_code.done"] = Field(
        "response.code_interpreter_call_code.done",
        description="The type of the event. Always `response.code_interpreter_call_code.done`.",
    )
    output_index: int = Field(
        ...,
        description="The index of the output item in the response for which the code is finalized.",
    )
    item_id: str = Field(
        ..., description="The unique identifier of the code interpreter tool call item."
    )
    code: str = Field(..., description="The final code snippet output by the code interpreter.")
    sequence_number: int = Field(
        ..., description="The sequence number of this event, used to order streaming events."
    )


class ResponseCodeInterpreterCallCompletedEvent(BaseModel):
    """Emitted when the code interpreter call is completed."""

    type: Literal["response.code_interpreter_call.completed"] = Field(
        "response.code_interpreter_call.completed",
        description="The type of the event. Always `response.code_interpreter_call.completed`.",
    )
    output_index: int = Field(
        ...,
        description="The index of the output item in the response for which the code interpreter call is completed.",
    )
    item_id: str = Field(
        ..., description="The unique identifier of the code interpreter tool call item."
    )
    sequence_number: int = Field(
        ..., description="The sequence number of this event, used to order streaming events."
    )


class ResponseCodeInterpreterCallInProgressEvent(BaseModel):
    """Emitted when a code interpreter call is in progress."""

    type: Literal["response.code_interpreter_call.in_progress"] = Field(
        "response.code_interpreter_call.in_progress",
        description="The type of the event. Always `response.code_interpreter_call.in_progress`.",
    )
    output_index: int = Field(
        ...,
        description="The index of the output item in the response for which the code interpreter call is in progress.",
    )
    item_id: str = Field(
        ..., description="The unique identifier of the code interpreter tool call item."
    )
    sequence_number: int = Field(
        ..., description="The sequence number of this event, used to order streaming events."
    )


class ResponseCodeInterpreterCallInterpretingEvent(BaseModel):
    """Emitted when the code interpreter is actively interpreting the code snippet."""

    type: Literal["response.code_interpreter_call.interpreting"] = Field(
        "response.code_interpreter_call.interpreting",
        description="The type of the event. Always `response.code_interpreter_call.interpreting`.",
    )
    output_index: int = Field(
        ...,
        description="The index of the output item in the response for which the code interpreter is interpreting code.",
    )
    item_id: str = Field(
        ..., description="The unique identifier of the code interpreter tool call item."
    )
    sequence_number: int = Field(
        ..., description="The sequence number of this event, used to order streaming events."
    )


class ResponseCompletedEvent(BaseModel):
    """Emitted when the model response is complete."""

    type: Literal["response.completed"] = Field(
        "response.completed", description="The type of the event. Always `response.completed`.\n"
    )
    response: Response = Field(..., description="Properties of the completed response.\n")
    sequence_number: int = Field(..., description="The sequence number for this event.")


class ResponseContentPartAddedEvent(BaseModel):
    """Emitted when a new content part is added."""

    type: Literal["response.content_part.added"] = Field(
        "response.content_part.added",
        description="The type of the event. Always `response.content_part.added`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the output item that the content part was added to.\n"
    )
    output_index: int = Field(
        ..., description="The index of the output item that the content part was added to.\n"
    )
    content_index: int = Field(..., description="The index of the content part that was added.\n")
    part: OutputContent = Field(..., description="The content part that was added.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseContentPartDoneEvent(BaseModel):
    """Emitted when a content part is done."""

    type: Literal["response.content_part.done"] = Field(
        "response.content_part.done",
        description="The type of the event. Always `response.content_part.done`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the output item that the content part was added to.\n"
    )
    output_index: int = Field(
        ..., description="The index of the output item that the content part was added to.\n"
    )
    content_index: int = Field(..., description="The index of the content part that is done.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.")
    part: OutputContent = Field(..., description="The content part that is done.\n")


class ResponseCreatedEvent(BaseModel):
    """An event that is emitted when a response is created."""

    type: Literal["response.created"] = Field(
        "response.created", description="The type of the event. Always `response.created`.\n"
    )
    response: Response = Field(..., description="The response that was created.\n")
    sequence_number: int = Field(..., description="The sequence number for this event.")


class ResponseCustomToolCallInputDeltaEvent(BaseModel):
    """Event representing a delta (partial update) to the input of a custom tool call."""

    type: Literal["response.custom_tool_call_input.delta"] = Field(
        "response.custom_tool_call_input.delta", description="The event type identifier."
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")
    output_index: int = Field(..., description="The index of the output this delta applies to.")
    item_id: str = Field(
        ..., description="Unique identifier for the API item associated with this event."
    )
    delta: str = Field(
        ..., description="The incremental input data (delta) for the custom tool call."
    )


class ResponseCustomToolCallInputDoneEvent(BaseModel):
    """Event indicating that input for a custom tool call is complete."""

    type: Literal["response.custom_tool_call_input.done"] = Field(
        "response.custom_tool_call_input.done", description="The event type identifier."
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")
    output_index: int = Field(..., description="The index of the output this event applies to.")
    item_id: str = Field(
        ..., description="Unique identifier for the API item associated with this event."
    )
    input: str = Field(..., description="The complete input data for the custom tool call.")


"""An error object returned when the model fails to generate a Response."""
ResponseError: TypeAlias = Dict[str, Any] | None


class ResponseErrorCode(Enum):
    """The error code for the response."""

    SERVER_ERROR = "server_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_PROMPT = "invalid_prompt"
    VECTOR_STORE_TIMEOUT = "vector_store_timeout"
    INVALID_IMAGE = "invalid_image"
    INVALID_IMAGE_FORMAT = "invalid_image_format"
    INVALID_BASE64_IMAGE = "invalid_base64_image"
    INVALID_IMAGE_URL = "invalid_image_url"
    IMAGE_TOO_LARGE = "image_too_large"
    IMAGE_TOO_SMALL = "image_too_small"
    IMAGE_PARSE_ERROR = "image_parse_error"
    IMAGE_CONTENT_POLICY_VIOLATION = "image_content_policy_violation"
    INVALID_IMAGE_MODE = "invalid_image_mode"
    IMAGE_FILE_TOO_LARGE = "image_file_too_large"
    UNSUPPORTED_IMAGE_MEDIA_TYPE = "unsupported_image_media_type"
    EMPTY_IMAGE_FILE = "empty_image_file"
    FAILED_TO_DOWNLOAD_IMAGE = "failed_to_download_image"
    IMAGE_FILE_NOT_FOUND = "image_file_not_found"


class ResponseErrorEvent(BaseModel):
    """Emitted when an error occurs."""

    type: Literal["error"] = Field("error", description="The type of the event. Always `error`.\n")
    code: str | None
    message: str = Field(..., description="The error message.\n")
    param: str | None
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseFailedEvent(BaseModel):
    """An event that is emitted when a response fails."""

    type: Literal["response.failed"] = Field(
        "response.failed", description="The type of the event. Always `response.failed`.\n"
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")
    response: Response = Field(..., description="The response that failed.\n")


class ResponseFileSearchCallCompletedEvent(BaseModel):
    """Emitted when a file search call is completed (results found)."""

    type: Literal["response.file_search_call.completed"] = Field(
        "response.file_search_call.completed",
        description="The type of the event. Always `response.file_search_call.completed`.\n",
    )
    output_index: int = Field(
        ..., description="The index of the output item that the file search call is initiated.\n"
    )
    item_id: str = Field(
        ..., description="The ID of the output item that the file search call is initiated.\n"
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseFileSearchCallInProgressEvent(BaseModel):
    """Emitted when a file search call is initiated."""

    type: Literal["response.file_search_call.in_progress"] = Field(
        "response.file_search_call.in_progress",
        description="The type of the event. Always `response.file_search_call.in_progress`.\n",
    )
    output_index: int = Field(
        ..., description="The index of the output item that the file search call is initiated.\n"
    )
    item_id: str = Field(
        ..., description="The ID of the output item that the file search call is initiated.\n"
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseFileSearchCallSearchingEvent(BaseModel):
    """Emitted when a file search is currently searching."""

    type: Literal["response.file_search_call.searching"] = Field(
        "response.file_search_call.searching",
        description="The type of the event. Always `response.file_search_call.searching`.\n",
    )
    output_index: int = Field(
        ..., description="The index of the output item that the file search call is searching.\n"
    )
    item_id: str = Field(
        ..., description="The ID of the output item that the file search call is initiated.\n"
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseFormatJsonObject(BaseModel):
    """
    JSON object response format. An older method of generating JSON responses.
    Using `json_schema` is recommended for models that support it. Note that the
    model will not generate JSON without a system or user message instructing it
    to do so.
    """

    type: Literal["json_object"] = Field(
        "json_object",
        description="The type of response format being defined. Always `json_object`.",
    )


class ResponseFormatText(BaseModel):
    """Default response format. Used to generate text responses."""

    type: Literal["text"] = Field(
        "text", description="The type of response format being defined. Always `text`."
    )


class ResponseFunctionCallArgumentsDeltaEvent(BaseModel):
    """Emitted when there is a partial function-call arguments delta."""

    type: Literal["response.function_call_arguments.delta"] = Field(
        "response.function_call_arguments.delta",
        description="The type of the event. Always `response.function_call_arguments.delta`.\n",
    )
    item_id: str = Field(
        ...,
        description="The ID of the output item that the function-call arguments delta is added to.\n",
    )
    output_index: int = Field(
        ...,
        description="The index of the output item that the function-call arguments delta is added to.\n",
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")
    delta: str = Field(..., description="The function-call arguments delta that is added.\n")


class ResponseFunctionCallArgumentsDoneEvent(BaseModel):
    """Emitted when function-call arguments are finalized."""

    type: Literal["response.function_call_arguments.done"] = "response.function_call_arguments.done"
    item_id: str = Field(..., description="The ID of the item.")
    name: str = Field(..., description="The name of the function that was called.")
    output_index: int = Field(..., description="The index of the output item.")
    sequence_number: int = Field(..., description="The sequence number of this event.")
    arguments: str = Field(..., description="The function-call arguments.")


class ResponseImageGenCallCompletedEvent(BaseModel):
    """Emitted when an image generation tool call has completed and the final image is available."""

    type: Literal["response.image_generation_call.completed"] = Field(
        "response.image_generation_call.completed",
        description="The type of the event. Always 'response.image_generation_call.completed'.",
    )
    output_index: int = Field(
        ..., description="The index of the output item in the response's output array."
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")
    item_id: str = Field(
        ..., description="The unique identifier of the image generation item being processed."
    )


class ResponseImageGenCallGeneratingEvent(BaseModel):
    """Emitted when an image generation tool call is actively generating an image (intermediate state)."""

    type: Literal["response.image_generation_call.generating"] = Field(
        "response.image_generation_call.generating",
        description="The type of the event. Always 'response.image_generation_call.generating'.",
    )
    output_index: int = Field(
        ..., description="The index of the output item in the response's output array."
    )
    item_id: str = Field(
        ..., description="The unique identifier of the image generation item being processed."
    )
    sequence_number: int = Field(
        ..., description="The sequence number of the image generation item being processed."
    )


class ResponseImageGenCallInProgressEvent(BaseModel):
    """Emitted when an image generation tool call is in progress."""

    type: Literal["response.image_generation_call.in_progress"] = Field(
        "response.image_generation_call.in_progress",
        description="The type of the event. Always 'response.image_generation_call.in_progress'.",
    )
    output_index: int = Field(
        ..., description="The index of the output item in the response's output array."
    )
    item_id: str = Field(
        ..., description="The unique identifier of the image generation item being processed."
    )
    sequence_number: int = Field(
        ..., description="The sequence number of the image generation item being processed."
    )


class ResponseImageGenCallPartialImageEvent(BaseModel):
    """Emitted when a partial image is available during image generation streaming."""

    type: Literal["response.image_generation_call.partial_image"] = Field(
        "response.image_generation_call.partial_image",
        description="The type of the event. Always 'response.image_generation_call.partial_image'.",
    )
    output_index: int = Field(
        ..., description="The index of the output item in the response's output array."
    )
    item_id: str = Field(
        ..., description="The unique identifier of the image generation item being processed."
    )
    sequence_number: int = Field(
        ..., description="The sequence number of the image generation item being processed."
    )
    partial_image_index: int = Field(
        ...,
        description="0-based index for the partial image (backend is 1-based, but this is 0-based for the user).",
    )
    partial_image_b64: str = Field(
        ..., description="Base64-encoded partial image data, suitable for rendering as an image."
    )


class ResponseInProgressEvent(BaseModel):
    """Emitted when the response is in progress."""

    type: Literal["response.in_progress"] = Field(
        "response.in_progress",
        description="The type of the event. Always `response.in_progress`.\n",
    )
    response: Response = Field(..., description="The response that is in progress.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseIncompleteEvent(BaseModel):
    """An event that is emitted when a response finishes as incomplete."""

    type: Literal["response.incomplete"] = Field(
        "response.incomplete", description="The type of the event. Always `response.incomplete`.\n"
    )
    response: Response = Field(..., description="The response that was incomplete.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseLogProb(BaseModel):
    """
    A logprob is the logarithmic probability that the model assigns to producing
    a particular token at a given position in the sequence. Less-negative (higher)
    logprob values indicate greater model confidence in that token choice.
    """

    token: str = Field(..., description="A possible text token.")
    logprob: float = Field(..., description="The log probability of this token.\n")
    top_logprobs: List[Dict[str, Any]] | None = Field(
        None, description="The log probability of the top 20 most likely tokens.\n"
    )


class ResponseMCPCallArgumentsDeltaEvent(BaseModel):
    """Emitted when there is a delta (partial update) to the arguments of an MCP tool call."""

    type: Literal["response.mcp_call_arguments.delta"] = Field(
        "response.mcp_call_arguments.delta",
        description="The type of the event. Always 'response.mcp_call_arguments.delta'.",
    )
    output_index: int = Field(
        ..., description="The index of the output item in the response's output array."
    )
    item_id: str = Field(
        ..., description="The unique identifier of the MCP tool call item being processed."
    )
    delta: str = Field(
        ...,
        description="A JSON string containing the partial update to the arguments for the MCP tool call.\n",
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseMCPCallArgumentsDoneEvent(BaseModel):
    """Emitted when the arguments for an MCP tool call are finalized."""

    type: Literal["response.mcp_call_arguments.done"] = Field(
        "response.mcp_call_arguments.done",
        description="The type of the event. Always 'response.mcp_call_arguments.done'.",
    )
    output_index: int = Field(
        ..., description="The index of the output item in the response's output array."
    )
    item_id: str = Field(
        ..., description="The unique identifier of the MCP tool call item being processed."
    )
    arguments: str = Field(
        ..., description="A JSON string containing the finalized arguments for the MCP tool call.\n"
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseMCPCallCompletedEvent(BaseModel):
    """Emitted when an MCP  tool call has completed successfully."""

    type: Literal["response.mcp_call.completed"] = Field(
        "response.mcp_call.completed",
        description="The type of the event. Always 'response.mcp_call.completed'.",
    )
    item_id: str = Field(..., description="The ID of the MCP tool call item that completed.")
    output_index: int = Field(..., description="The index of the output item that completed.")
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseMCPCallFailedEvent(BaseModel):
    """Emitted when an MCP  tool call has failed."""

    type: Literal["response.mcp_call.failed"] = Field(
        "response.mcp_call.failed",
        description="The type of the event. Always 'response.mcp_call.failed'.",
    )
    item_id: str = Field(..., description="The ID of the MCP tool call item that failed.")
    output_index: int = Field(..., description="The index of the output item that failed.")
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseMCPCallInProgressEvent(BaseModel):
    """Emitted when an MCP  tool call is in progress."""

    type: Literal["response.mcp_call.in_progress"] = Field(
        "response.mcp_call.in_progress",
        description="The type of the event. Always 'response.mcp_call.in_progress'.",
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")
    output_index: int = Field(
        ..., description="The index of the output item in the response's output array."
    )
    item_id: str = Field(
        ..., description="The unique identifier of the MCP tool call item being processed."
    )


class ResponseMCPListToolsCompletedEvent(BaseModel):
    """Emitted when the list of available MCP tools has been successfully retrieved."""

    type: Literal["response.mcp_list_tools.completed"] = Field(
        "response.mcp_list_tools.completed",
        description="The type of the event. Always 'response.mcp_list_tools.completed'.",
    )
    item_id: str = Field(
        ..., description="The ID of the MCP tool call item that produced this output."
    )
    output_index: int = Field(..., description="The index of the output item that was processed.")
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseMCPListToolsFailedEvent(BaseModel):
    """Emitted when the attempt to list available MCP tools has failed."""

    type: Literal["response.mcp_list_tools.failed"] = Field(
        "response.mcp_list_tools.failed",
        description="The type of the event. Always 'response.mcp_list_tools.failed'.",
    )
    item_id: str = Field(..., description="The ID of the MCP tool call item that failed.")
    output_index: int = Field(..., description="The index of the output item that failed.")
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseMCPListToolsInProgressEvent(BaseModel):
    """Emitted when the system is in the process of retrieving the list of available MCP tools."""

    type: Literal["response.mcp_list_tools.in_progress"] = Field(
        "response.mcp_list_tools.in_progress",
        description="The type of the event. Always 'response.mcp_list_tools.in_progress'.",
    )
    item_id: str = Field(
        ..., description="The ID of the MCP tool call item that is being processed."
    )
    output_index: int = Field(
        ..., description="The index of the output item that is being processed."
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")


class ResponseOutputItemAddedEvent(BaseModel):
    """Emitted when a new output item is added."""

    type: Literal["response.output_item.added"] = Field(
        "response.output_item.added",
        description="The type of the event. Always `response.output_item.added`.\n",
    )
    output_index: int = Field(..., description="The index of the output item that was added.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.\n")
    item: OutputItem = Field(..., description="The output item that was added.\n")


class ResponseOutputItemDoneEvent(BaseModel):
    """Emitted when an output item is marked done."""

    type: Literal["response.output_item.done"] = Field(
        "response.output_item.done",
        description="The type of the event. Always `response.output_item.done`.\n",
    )
    output_index: int = Field(
        ..., description="The index of the output item that was marked done.\n"
    )
    sequence_number: int = Field(..., description="The sequence number of this event.\n")
    item: OutputItem = Field(..., description="The output item that was marked done.\n")


class ResponseOutputTextAnnotationAddedEvent(BaseModel):
    """Emitted when an annotation is added to output text content."""

    type: Literal["response.output_text.annotation.added"] = Field(
        "response.output_text.annotation.added",
        description="The type of the event. Always 'response.output_text.annotation.added'.",
    )
    item_id: str = Field(
        ..., description="The unique identifier of the item to which the annotation is being added."
    )
    output_index: int = Field(
        ..., description="The index of the output item in the response's output array."
    )
    content_index: int = Field(
        ..., description="The index of the content part within the output item."
    )
    annotation_index: int = Field(
        ..., description="The index of the annotation within the content part."
    )
    sequence_number: int = Field(..., description="The sequence number of this event.")
    annotation: Dict[str, Any] = Field(
        ..., description="The annotation object being added. (See annotation schema for details.)"
    )


"""
Optional map of values to substitute in for variables in your
prompt. The substitution values can either be strings, or other
Response input types like images or files.
"""
ResponsePromptVariables: TypeAlias = (
    Dict[str, str | InputTextContent | InputImageContent | InputFileContent] | None
)


class ResponseQueuedEvent(BaseModel):
    """Emitted when a response is queued and waiting to be processed."""

    type: Literal["response.queued"] = Field(
        "response.queued", description="The type of the event. Always 'response.queued'."
    )
    response: Response = Field(..., description="The full response object that is queued.")
    sequence_number: int = Field(..., description="The sequence number for this event.")


class ResponseReasoningSummaryPartAddedEvent(BaseModel):
    """Emitted when a new reasoning summary part is added."""

    type: Literal["response.reasoning_summary_part.added"] = Field(
        "response.reasoning_summary_part.added",
        description="The type of the event. Always `response.reasoning_summary_part.added`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the item this summary part is associated with.\n"
    )
    output_index: int = Field(
        ..., description="The index of the output item this summary part is associated with.\n"
    )
    summary_index: int = Field(
        ..., description="The index of the summary part within the reasoning summary.\n"
    )
    sequence_number: int = Field(..., description="The sequence number of this event.\n")
    part: Dict[str, Any] = Field(..., description="The summary part that was added.\n")


class ResponseReasoningSummaryPartDoneEvent(BaseModel):
    """Emitted when a reasoning summary part is completed."""

    type: Literal["response.reasoning_summary_part.done"] = Field(
        "response.reasoning_summary_part.done",
        description="The type of the event. Always `response.reasoning_summary_part.done`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the item this summary part is associated with.\n"
    )
    output_index: int = Field(
        ..., description="The index of the output item this summary part is associated with.\n"
    )
    summary_index: int = Field(
        ..., description="The index of the summary part within the reasoning summary.\n"
    )
    sequence_number: int = Field(..., description="The sequence number of this event.\n")
    part: Dict[str, Any] = Field(..., description="The completed summary part.\n")


class ResponseReasoningSummaryTextDeltaEvent(BaseModel):
    """Emitted when a delta is added to a reasoning summary text."""

    type: Literal["response.reasoning_summary_text.delta"] = Field(
        "response.reasoning_summary_text.delta",
        description="The type of the event. Always `response.reasoning_summary_text.delta`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the item this summary text delta is associated with.\n"
    )
    output_index: int = Field(
        ...,
        description="The index of the output item this summary text delta is associated with.\n",
    )
    summary_index: int = Field(
        ..., description="The index of the summary part within the reasoning summary.\n"
    )
    delta: str = Field(..., description="The text delta that was added to the summary.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.\n")


class ResponseReasoningSummaryTextDoneEvent(BaseModel):
    """Emitted when a reasoning summary text is completed."""

    type: Literal["response.reasoning_summary_text.done"] = Field(
        "response.reasoning_summary_text.done",
        description="The type of the event. Always `response.reasoning_summary_text.done`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the item this summary text is associated with.\n"
    )
    output_index: int = Field(
        ..., description="The index of the output item this summary text is associated with.\n"
    )
    summary_index: int = Field(
        ..., description="The index of the summary part within the reasoning summary.\n"
    )
    text: str = Field(..., description="The full text of the completed reasoning summary.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.\n")


class ResponseReasoningTextDeltaEvent(BaseModel):
    """Emitted when a delta is added to a reasoning text."""

    type: Literal["response.reasoning_text.delta"] = Field(
        "response.reasoning_text.delta",
        description="The type of the event. Always `response.reasoning_text.delta`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the item this reasoning text delta is associated with.\n"
    )
    output_index: int = Field(
        ...,
        description="The index of the output item this reasoning text delta is associated with.\n",
    )
    content_index: int = Field(
        ..., description="The index of the reasoning content part this delta is associated with.\n"
    )
    delta: str = Field(..., description="The text delta that was added to the reasoning content.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.\n")


class ResponseReasoningTextDoneEvent(BaseModel):
    """Emitted when a reasoning text is completed."""

    type: Literal["response.reasoning_text.done"] = Field(
        "response.reasoning_text.done",
        description="The type of the event. Always `response.reasoning_text.done`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the item this reasoning text is associated with.\n"
    )
    output_index: int = Field(
        ..., description="The index of the output item this reasoning text is associated with.\n"
    )
    content_index: int = Field(..., description="The index of the reasoning content part.\n")
    text: str = Field(..., description="The full text of the completed reasoning content.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.\n")


class ResponseRefusalDeltaEvent(BaseModel):
    """Emitted when there is a partial refusal text."""

    type: Literal["response.refusal.delta"] = Field(
        "response.refusal.delta",
        description="The type of the event. Always `response.refusal.delta`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the output item that the refusal text is added to.\n"
    )
    output_index: int = Field(
        ..., description="The index of the output item that the refusal text is added to.\n"
    )
    content_index: int = Field(
        ..., description="The index of the content part that the refusal text is added to.\n"
    )
    delta: str = Field(..., description="The refusal text that is added.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.\n")


class ResponseRefusalDoneEvent(BaseModel):
    """Emitted when refusal text is finalized."""

    type: Literal["response.refusal.done"] = Field(
        "response.refusal.done",
        description="The type of the event. Always `response.refusal.done`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the output item that the refusal text is finalized.\n"
    )
    output_index: int = Field(
        ..., description="The index of the output item that the refusal text is finalized.\n"
    )
    content_index: int = Field(
        ..., description="The index of the content part that the refusal text is finalized.\n"
    )
    refusal: str = Field(..., description="The refusal text that is finalized.\n")
    sequence_number: int = Field(..., description="The sequence number of this event.\n")


class ResponseTextDeltaEvent(BaseModel):
    """Emitted when there is an additional text delta."""

    type: Literal["response.output_text.delta"] = Field(
        "response.output_text.delta",
        description="The type of the event. Always `response.output_text.delta`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the output item that the text delta was added to.\n"
    )
    output_index: int = Field(
        ..., description="The index of the output item that the text delta was added to.\n"
    )
    content_index: int = Field(
        ..., description="The index of the content part that the text delta was added to.\n"
    )
    delta: str = Field(..., description="The text delta that was added.\n")
    sequence_number: int = Field(..., description="The sequence number for this event.")
    logprobs: List[ResponseLogProb] = Field(
        ..., description="The log probabilities of the tokens in the delta.\n"
    )


class ResponseTextDoneEvent(BaseModel):
    """Emitted when text content is finalized."""

    type: Literal["response.output_text.done"] = Field(
        "response.output_text.done",
        description="The type of the event. Always `response.output_text.done`.\n",
    )
    item_id: str = Field(
        ..., description="The ID of the output item that the text content is finalized.\n"
    )
    output_index: int = Field(
        ..., description="The index of the output item that the text content is finalized.\n"
    )
    content_index: int = Field(
        ..., description="The index of the content part that the text content is finalized.\n"
    )
    text: str = Field(..., description="The text content that is finalized.\n")
    sequence_number: int = Field(..., description="The sequence number for this event.")
    logprobs: List[ResponseLogProb] = Field(
        ..., description="The log probabilities of the tokens in the delta.\n"
    )


class ResponseWebSearchCallCompletedEvent(BaseModel):
    """Emitted when a web search call is completed."""

    type: Literal["response.web_search_call.completed"] = Field(
        "response.web_search_call.completed",
        description="The type of the event. Always `response.web_search_call.completed`.\n",
    )
    output_index: int = Field(
        ...,
        description="The index of the output item that the web search call is associated with.\n",
    )
    item_id: str = Field(
        ..., description="Unique ID for the output item associated with the web search call.\n"
    )
    sequence_number: int = Field(
        ..., description="The sequence number of the web search call being processed."
    )


class ResponseWebSearchCallInProgressEvent(BaseModel):
    """Emitted when a web search call is initiated."""

    type: Literal["response.web_search_call.in_progress"] = Field(
        "response.web_search_call.in_progress",
        description="The type of the event. Always `response.web_search_call.in_progress`.\n",
    )
    output_index: int = Field(
        ...,
        description="The index of the output item that the web search call is associated with.\n",
    )
    item_id: str = Field(
        ..., description="Unique ID for the output item associated with the web search call.\n"
    )
    sequence_number: int = Field(
        ..., description="The sequence number of the web search call being processed."
    )


class ResponseWebSearchCallSearchingEvent(BaseModel):
    """Emitted when a web search call is executing."""

    type: Literal["response.web_search_call.searching"] = Field(
        "response.web_search_call.searching",
        description="The type of the event. Always `response.web_search_call.searching`.\n",
    )
    output_index: int = Field(
        ...,
        description="The index of the output item that the web search call is associated with.\n",
    )
    item_id: str = Field(
        ..., description="Unique ID for the output item associated with the web search call.\n"
    )
    sequence_number: int = Field(
        ..., description="The sequence number of the web search call being processed."
    )


"""Emitted when there is a partial audio response."""
ResponseStreamEvent: TypeAlias = Annotated[
    ResponseAudioDeltaEvent
    | ResponseAudioDoneEvent
    | ResponseAudioTranscriptDeltaEvent
    | ResponseAudioTranscriptDoneEvent
    | ResponseCodeInterpreterCallCodeDeltaEvent
    | ResponseCodeInterpreterCallCodeDoneEvent
    | ResponseCodeInterpreterCallCompletedEvent
    | ResponseCodeInterpreterCallInProgressEvent
    | ResponseCodeInterpreterCallInterpretingEvent
    | ResponseCompletedEvent
    | ResponseContentPartAddedEvent
    | ResponseContentPartDoneEvent
    | ResponseCreatedEvent
    | ResponseErrorEvent
    | ResponseFileSearchCallCompletedEvent
    | ResponseFileSearchCallInProgressEvent
    | ResponseFileSearchCallSearchingEvent
    | ResponseFunctionCallArgumentsDeltaEvent
    | ResponseFunctionCallArgumentsDoneEvent
    | ResponseInProgressEvent
    | ResponseFailedEvent
    | ResponseIncompleteEvent
    | ResponseOutputItemAddedEvent
    | ResponseOutputItemDoneEvent
    | ResponseReasoningSummaryPartAddedEvent
    | ResponseReasoningSummaryPartDoneEvent
    | ResponseReasoningSummaryTextDeltaEvent
    | ResponseReasoningSummaryTextDoneEvent
    | ResponseReasoningTextDeltaEvent
    | ResponseReasoningTextDoneEvent
    | ResponseRefusalDeltaEvent
    | ResponseRefusalDoneEvent
    | ResponseTextDeltaEvent
    | ResponseTextDoneEvent
    | ResponseWebSearchCallCompletedEvent
    | ResponseWebSearchCallInProgressEvent
    | ResponseWebSearchCallSearchingEvent
    | ResponseImageGenCallCompletedEvent
    | ResponseImageGenCallGeneratingEvent
    | ResponseImageGenCallInProgressEvent
    | ResponseImageGenCallPartialImageEvent
    | ResponseMCPCallArgumentsDeltaEvent
    | ResponseMCPCallArgumentsDoneEvent
    | ResponseMCPCallCompletedEvent
    | ResponseMCPCallFailedEvent
    | ResponseMCPCallInProgressEvent
    | ResponseMCPListToolsCompletedEvent
    | ResponseMCPListToolsFailedEvent
    | ResponseMCPListToolsInProgressEvent
    | ResponseOutputTextAnnotationAddedEvent
    | ResponseQueuedEvent
    | ResponseCustomToolCallInputDeltaEvent
    | ResponseCustomToolCallInputDoneEvent,
    Field(discriminator="type"),
]

"""Options for streaming responses. Only set this when you set `stream: true`."""
ResponseStreamOptions: TypeAlias = Dict[str, Any] | None


class ResponseTextParam(BaseModel):
    """
    Configuration options for a text response from the model. Can be plain
    text or structured JSON data. Learn more:
    - [Text inputs and outputs](https://platform.openai.com/docs/guides/text)
    - [Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
    """

    format: TextResponseFormatConfiguration | None = None
    verbosity: Verbosity | None = None


class ResponseUsage(BaseModel):
    """
    Represents token usage details including input tokens, output tokens,
    a breakdown of output tokens, and the total tokens used.
    """

    input_tokens: int = Field(..., description="The number of input tokens.")
    input_tokens_details: Dict[str, Any] = Field(
        ..., description="A detailed breakdown of the input tokens."
    )
    output_tokens: int = Field(..., description="The number of output tokens.")
    output_tokens_details: Dict[str, Any] = Field(
        ..., description="A detailed breakdown of the output tokens."
    )
    total_tokens: int = Field(..., description="The total number of tokens used.")


class SearchContextSize(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


"""
Specifies the processing type used for serving the request.
  - If set to 'auto', then the request will be processed with the service tier configured in the Project settings. Unless otherwise configured, the Project will use 'default'.
  - If set to 'default', then the request will be processed with the standard pricing and performance for the selected model.
  - If set to '[flex](https://platform.openai.com/docs/guides/flex-processing)' or '[priority](https://openai.com/api-priority-processing/)', then the request will be processed with the corresponding service tier.
  - When not set, the default behavior is 'auto'.

  When the `service_tier` parameter is set, the response body will include the `service_tier` value based on the processing mode actually used to serve the request. This response value may be different from the value set in the parameter.
"""
ServiceTier: TypeAlias = Literal["auto", "default", "flex", "scale", "priority"] | None


class SpecificApplyPatchParam(BaseModel):
    """Forces the model to call the apply_patch tool when executing a tool call."""

    type: Literal["apply_patch"] = Field(
        "apply_patch", description="The tool to call. Always `apply_patch`."
    )


class SpecificFunctionShellParam(BaseModel):
    """Forces the model to call the function shell tool when a tool call is required."""

    type: Literal["shell"] = Field("shell", description="The tool to call. Always `shell`.")


class Summary(BaseModel):
    """A summary text from the model."""

    type: Literal["summary_text"] = Field(
        "summary_text", description="The type of the object. Always `summary_text`."
    )
    text: str = Field(..., description="A summary of the reasoning output from the model so far.")


class TextResponseFormatJsonSchema(BaseModel):
    """
    JSON Schema response format. Used to generate structured JSON responses.
    Learn more about [Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs).
    """

    type: Literal["json_schema"] = Field(
        "json_schema",
        description="The type of response format being defined. Always `json_schema`.",
    )
    description: str | None = Field(
        None,
        description="A description of what the response format is for, used by the model to\ndetermine how to respond in the format.\n",
    )
    name: str = Field(
        ...,
        description="The name of the response format. Must be a-z, A-Z, 0-9, or contain\nunderscores and dashes, with a maximum length of 64.\n",
    )
    schema_: ResponseFormatJsonSchemaSchema = Field(alias="schema")
    model_config = ConfigDict(populate_by_name=True)

    strict: bool | None = None


"""
An object specifying the format that the model must output.

Configuring `{ "type": "json_schema" }` enables Structured Outputs,
which ensures the model will match your supplied JSON schema. Learn more in the
[Structured Outputs guide](https://platform.openai.com/docs/guides/structured-outputs).

The default format is `{ "type": "text" }` with no additional options.

**Not recommended for gpt-4o and newer models:**

Setting to `{ "type": "json_object" }` enables the older JSON mode, which
ensures the message the model generates is valid JSON. Using `json_schema`
is preferred for models that support it.
"""
TextResponseFormatConfiguration: TypeAlias = Annotated[
    ResponseFormatText | TextResponseFormatJsonSchema | ResponseFormatJsonObject,
    Field(discriminator="type"),
]


class WebSearchTool(BaseModel):
    """
    Search the Internet for sources related to the prompt. Learn more about the
    [web search tool](https://platform.openai.com/docs/guides/tools-web-search).
    """

    type: Literal["web_search", "web_search_2025_08_26"] = Field(
        ...,
        description="The type of the web search tool. One of `web_search` or `web_search_2025_08_26`.",
    )
    filters: Dict[str, Any] | None = None
    user_location: WebSearchApproximateLocation | None = None
    search_context_size: Literal["low", "medium", "high"] | None = Field(
        None,
        description="High level guidance for the amount of context window space to use for the search. One of `low`, `medium`, or `high`. `medium` is the default.",
    )


class WebSearchPreviewTool(BaseModel):
    """This tool searches the web for relevant results to use in a response. Learn more about the [web search tool](https://platform.openai.com/docs/guides/tools-web-search)."""

    type: Literal["web_search_preview", "web_search_preview_2025_03_11"] = Field(
        ...,
        description="The type of the web search tool. One of `web_search_preview` or `web_search_preview_2025_03_11`.",
    )
    user_location: ApproximateLocation | None = None
    search_context_size: SearchContextSize | None = Field(
        None,
        description="High level guidance for the amount of context window space to use for the search. One of `low`, `medium`, or `high`. `medium` is the default.",
    )


"""A tool that can be used to generate a response."""
Tool: TypeAlias = Annotated[
    FunctionTool
    | FileSearchTool
    | ComputerUsePreviewTool
    | WebSearchTool
    | MCPTool
    | CodeInterpreterTool
    | ImageGenTool
    | LocalShellToolParam
    | FunctionShellToolParam
    | CustomToolParam
    | WebSearchPreviewTool
    | ApplyPatchToolParam,
    Field(discriminator="type"),
]


class ToolChoiceAllowed(BaseModel):
    """Constrains the tools available to the model to a pre-defined set."""

    type: Literal["allowed_tools"] = Field(
        "allowed_tools", description="Allowed tool configuration type. Always `allowed_tools`."
    )
    mode: Literal["auto", "required"] = Field(
        ...,
        description="Constrains the tools available to the model to a pre-defined set.\n\n`auto` allows the model to pick from among the allowed tools and generate a\nmessage.\n\n`required` requires the model to call one or more of the allowed tools.\n",
    )
    tools: List[Dict[str, Any]] = Field(
        ...,
        description='A list of tool definitions that the model should be allowed to call.\n\nFor the Responses API, the list of tool definitions might look like:\n```json\n[\n  { "type": "function", "name": "get_weather" },\n  { "type": "mcp", "server_label": "deepwiki" },\n  { "type": "image_generation" }\n]\n```\n',
    )


class ToolChoiceCustom(BaseModel):
    """Use this option to force the model to call a specific custom tool."""

    type: Literal["custom"] = Field(
        "custom", description="For custom tool calling, the type is always `custom`."
    )
    name: str = Field(..., description="The name of the custom tool to call.")


class ToolChoiceFunction(BaseModel):
    """Use this option to force the model to call a specific function."""

    type: Literal["function"] = Field(
        "function", description="For function calling, the type is always `function`."
    )
    name: str = Field(..., description="The name of the function to call.")


class ToolChoiceMCP(BaseModel):
    """Use this option to force the model to call a specific tool on a remote MCP server."""

    type: Literal["mcp"] = Field("mcp", description="For MCP tools, the type is always `mcp`.")
    server_label: str = Field(..., description="The label of the MCP server to use.\n")
    name: str | None = None


class ToolChoiceOptions(Enum):
    """
    Controls which (if any) tool is called by the model.

    `none` means the model will not call any tool and instead generates a message.

    `auto` means the model can pick between generating a message or calling one or
    more tools.

    `required` means the model must call one or more tools.
    """

    NONE = "none"
    AUTO = "auto"
    REQUIRED = "required"


ToolChoiceParam: TypeAlias = ToolChoiceOptions


class ToolChoiceTypes(BaseModel):
    """
    Indicates that the model should use a built-in tool to generate a response.
    [Learn more about built-in tools](https://platform.openai.com/docs/guides/tools).
    """

    type: Literal[
        "file_search",
        "web_search_preview",
        "computer_use_preview",
        "web_search_preview_2025_03_11",
        "image_generation",
        "code_interpreter",
    ] = Field(
        ...,
        description="The type of hosted tool the model should to use. Learn more about\n[built-in tools](https://platform.openai.com/docs/guides/tools).\n\nAllowed values are:\n- `file_search`\n- `web_search_preview`\n- `computer_use_preview`\n- `code_interpreter`\n- `image_generation`\n",
    )


"""
An array of tools the model may call while generating a response. You
can specify which tool to use by setting the `tool_choice` parameter.

We support the following categories of tools:
- **Built-in tools**: Tools that are provided by OpenAI that extend the
  model's capabilities, like [web search](https://platform.openai.com/docs/guides/tools-web-search)
  or [file search](https://platform.openai.com/docs/guides/tools-file-search). Learn more about
  [built-in tools](https://platform.openai.com/docs/guides/tools).
- **MCP Tools**: Integrations with third-party systems via custom MCP servers
  or predefined connectors such as Google Drive and SharePoint. Learn more about
  [MCP Tools](https://platform.openai.com/docs/guides/tools-connectors-mcp).
- **Function calls (custom tools)**: Functions that are defined by you,
  enabling the model to call your own code with strongly typed arguments
  and outputs. Learn more about
  [function calling](https://platform.openai.com/docs/guides/function-calling). You can also use
  custom tools to call your own code.
"""
ToolsArray: TypeAlias = List[Tool]


class TopLogProb(BaseModel):
    """The top log probability of a token."""

    token: str
    logprob: float
    bytes: List[int]


"""
Set of 16 key-value pairs that can be attached to an object. This can be
useful for storing additional information about the object in a structured
format, and querying for objects via API or the dashboard. Keys are strings
with a maximum length of 64 characters. Values are strings with a maximum
length of 512 characters, booleans, or numbers.
"""
VectorStoreFileAttributes: TypeAlias = Dict[str, str | float | bool] | None

"""
Constrains the verbosity of the model's response. Lower values will result in
more concise responses, while higher values will result in more verbose responses.
Currently supported values are `low`, `medium`, and `high`.
"""
Verbosity: TypeAlias = Literal["low", "medium", "high"] | None


class WebSearchActionFind(BaseModel):
    """Action type "find": Searches for a pattern within a loaded page."""

    type: Literal["find"] = Field("find", description="The action type.\n")
    url: str = Field(..., description="The URL of the page searched for the pattern.\n")
    pattern: str = Field(..., description="The pattern or text to search for within the page.\n")


class WebSearchActionOpenPage(BaseModel):
    """Action type "open_page" - Opens a specific URL from search results."""

    type: Literal["open_page"] = Field("open_page", description="The action type.\n")
    url: str = Field(..., description="The URL opened by the model.\n")


class WebSearchActionSearch(BaseModel):
    """Action type "search" - Performs a web search query."""

    type: Literal["search"] = Field("search", description="The action type.\n")
    query: str = Field(..., description="The search query.\n")
    sources: List[Dict[str, Any]] | None = Field(
        None, description="The sources used in the search.\n"
    )


"""The approximate location of the user."""
WebSearchApproximateLocation: TypeAlias = Dict[str, Any] | None
