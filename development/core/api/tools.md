# Tools

This page presents all APIs and classes related to tools in WayFlow

![agentspec-icon](_static/icons/agentspec-icon.svg)

Visit the Agent Spec API Documentation to learn more about LLMs Components.

[Agent Spec - Tools API Reference](https://oracle.github.io/agent-spec/api/tools.html)

#### TIP
Click the button above ↑ to visit the [Agent Spec Documentation](https://oracle.github.io/agent-spec/index.html)

## Tool

This is the base class for tools.

<a id="id1"></a>

### *class* wayflowcore.tools.tools.Tool(name, description, input_descriptors=None, output_descriptors=None, parameters=None, output=None, id=None, \_\_metadata_info_\_=None, requires_confirmation=False)

* **Parameters:**
  * **name** (*str*)
  * **description** (*str*)
  * **input_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **output_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **parameters** (*Dict* *[**str* *,* [*JsonSchemaParam*](flows.md#wayflowcore.property.JsonSchemaParam) *]*  *|* *None*)
  * **output** ([*JsonSchemaParam*](flows.md#wayflowcore.property.JsonSchemaParam) *|* *None*)
  * **id** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **requires_confirmation** (*bool*)

#### DEFAULT_TOOL_NAME *: `ClassVar`[`str`]* *= 'tool_output'*

Default name of the tool output if none is provided

* **Type:**
  str

#### description *: `str`*

#### *property* might_yield *: bool*

Indicates that the tool might yield inside a step or a flow.

#### requires_confirmation *: `bool`*

#### to_dict()

* **Return type:**
  `Dict`[`str`, `Any`]

#### to_openai_format(api_type=None)

* **Return type:**
  `Dict`[`str`, `Any`]
* **Parameters:**
  **api_type** ([*OpenAIAPIType*](llmmodels.md#wayflowcore.models.openaiapitype.OpenAIAPIType) *|* *None*)

## Client Tool

<a id="clienttool"></a>

### *class* wayflowcore.tools.clienttools.ClientTool(name, description, input_descriptors=None, output_descriptors=None, parameters=None, output=None, requires_confirmation=False, id=None, \_\_metadata_info_\_=None)

Contains the description of a tool, including its name, documentation and schema of its
arguments. Instead of being run in the server, calling this tool will actually
yield to the client for them to compute the result, and post it back to continue
execution.

* **Parameters:**
  * **name** (*str*)
  * **description** (*str*)
  * **input_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **output_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **parameters** (*Dict* *[**str* *,* [*JsonSchemaParam*](flows.md#wayflowcore.property.JsonSchemaParam) *]*  *|* *None*)
  * **output** ([*JsonSchemaParam*](flows.md#wayflowcore.property.JsonSchemaParam) *|* *None*)
  * **requires_confirmation** (*bool*)
  * **id** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### name

name of the tool

#### description

description of the tool

#### input_descriptors

list of properties describing the inputs of the tool.

#### output_descriptors

list of properties describing the outputs of the tool.

If there is a single output descriptor, the tool needs to just return the value.
If there are several output descriptors, the tool needs to return a dict of all expected values.

If no output descriptor is passed, or if a single output descriptor is passed without a name, the output will
be automatically be named `Tool.DEFAULT_TOOL_NAME`.

#### requires_confirmation

Flag to make tool require confirmation before execution. Yields a ToolExecutionConfirmationStatus during execution.
If tool use is confirmed, then a ToolRequestStatus is raised to ask the client to execute the tool and provide the outputs.

* **Type:**
  bool

### Examples

```pycon
>>> from wayflowcore.tools import ClientTool
>>> from wayflowcore.property import FloatProperty
>>> addition_client_tool = ClientTool(
...    name="add_numbers",
...    description="Simply adds two numbers",
...    input_descriptors=[
...         FloatProperty(name="a", description="the first number", default_value=0),
...         FloatProperty(name="b", description="the second number"),
...    ],
... )
```

#### *property* might_yield *: bool*

Indicates that the client tool might yield (it always does).

## Server Tool

<a id="servertool"></a>

### *class* wayflowcore.tools.servertools.ServerTool(name, description, func, input_descriptors=None, output_descriptors=None, parameters=None, output=None, requires_confirmation=False, id=None, \_cpu_bounded=False, \_\_metadata_info_\_=None)

Contains the description and callable of a tool, including its name, documentation and schema of its
arguments. This tool is executed on the server side, with the provided callable.

* **Parameters:**
  * **name** (*str*)
  * **description** (*str*)
  * **func** (*Callable* *[* *[* *...* *]* *,* *Any* *]*)
  * **input_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **output_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **parameters** (*Dict* *[**str* *,* [*JsonSchemaParam*](flows.md#wayflowcore.property.JsonSchemaParam) *]*  *|* *None*)
  * **output** ([*JsonSchemaParam*](flows.md#wayflowcore.property.JsonSchemaParam) *|* *None*)
  * **requires_confirmation** (*bool*)
  * **id** (*str* *|* *None*)
  * **\_cpu_bounded** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### name

name of the tool

#### description

description of the tool

#### input_descriptors

list of properties describing the inputs of the tool.

#### output_descriptors

list of properties describing the outputs of the tool.

If there is a single output descriptor, the tool needs to just return the value.
If there are several output descriptors, the tool needs to return a dict of all expected values.

If no output descriptor is passed, or if a single output descriptor is passed without a name, the output will
be automatically be named `Tool.DEFAULT_TOOL_NAME`.

#### func

tool callable

* **Type:**
  Callable

#### requires_confirmation

Flag to make tool require confirmation before execution. Yields a ToolExecutionConfirmationStatus during execution.

* **Type:**
  bool

### Examples

```pycon
>>> from wayflowcore.tools import ServerTool
>>> from wayflowcore.property import FloatProperty
```

```pycon
>>> def add_tool(arg1, arg2):
...    return arg1 + arg2
```

```pycon
>>> addition_client_tool = ServerTool(
...     name="add_tool",
...     description="Simply adds two numbers",
...     input_descriptors=[
...         FloatProperty(name="a", description="the first number", default_value= 0.0),
...         FloatProperty(name="b", description="the second number"),
...     ],
...     output_descriptors=[FloatProperty()],
...     func=add_tool,
... )
```

You can also write tools with several outputs. Make sure the tool returns a dict with the appropriate names
and types, and specify the `output_descriptors`:

```pycon
>>> from typing import Any, Dict
>>> from wayflowcore.property import StringProperty, IntegerProperty
>>> def some_func(a: int, b: str) -> Dict[str, Any]:
...     return {'renamed_a': a, 'renamed_b': b} # keys and types of values need to correspond to output_descriptors
>>> tool = ServerTool(
...     name='my_tool',
...     description='some description',
...     input_descriptors=[
...         IntegerProperty(name='a'),
...         StringProperty(name='b'),
...     ],
...     output_descriptors=[
...         IntegerProperty(name='renamed_a'),
...         StringProperty(name='renamed_b'),
...     ],
...     func=some_func,
... )
```

#### *classmethod* from_any(tool, \*\*kwargs)

* **Return type:**
  [`ServerTool`](#wayflowcore.tools.servertools.ServerTool)
* **Parameters:**
  * **tool** ([*ServerTool*](#wayflowcore.tools.servertools.ServerTool) *|* [*Flow*](flows.md#wayflowcore.flow.Flow) *|* [*Step*](flows.md#wayflowcore.steps.step.Step) *|* [*DescribedFlow*](agent.md#wayflowcore.tools.DescribedFlow) *|* *Any*)
  * **kwargs** (*Any*)

#### *classmethod* from_flow(flow, flow_name, flow_description, flow_output=None)

Converts a flow into a server-side tool that will be executed on the server.

* **Parameters:**
  * **flow** ([`Flow`](flows.md#wayflowcore.flow.Flow)) – The flow to be executed as the tool
  * **flow_name** (`str`) – The name given to the flow to be used as the tool name
  * **flow_description** (`str`) – The description to be used as description of the tool
  * **flow_output** (`Union`[`List`[`str`], `str`, `None`]) – Optional list of flow outputs to collect. By default will collect all flow outputs,
    otherwise will only collect the outputs which names are specified in this argument.
* **Raises:**
  **ValueError** – If the input flow is a potentially-yielding flow (conversion to `ServerTool` is not
      supported).
* **Return type:**
  [`ServerTool`](#wayflowcore.tools.servertools.ServerTool)

#### *classmethod* from_langchain(tool)

Converts a usual Langchain tool into a server-side tool that will be executed on the server.

* **Parameters:**
  **tool** (`Any`) – langchain tool to convert
* **Return type:**
  [`ServerTool`](#wayflowcore.tools.servertools.ServerTool)

#### *classmethod* from_step(step, step_name, step_description, step_output=None)

Converts a step into a server-side tool that will be executed on the server.

* **Parameters:**
  * **step** ([`Step`](flows.md#wayflowcore.steps.step.Step)) – The step to be executed as the tool
  * **step_name** (`str`) – The name given to the step to be used as the tool name
  * **step_description** (`str`) – The description to be used as description of the tool
  * **step_output** (`Union`[`List`[`str`], `str`, `None`]) – Optional list of flow outputs to collect. By default will collect all flow outputs,
    otherwise will only collect the outputs which names are specified in this argument.
* **Raises:**
  **ValueError** – If the input step is a potentially-yielding step (conversion to `ServerTool` is not
      supported).
* **Return type:**
  [`ServerTool`](#wayflowcore.tools.servertools.ServerTool)

#### run(\*args, \*\*kwargs)

Runs the tool in a synchronous manner, no matter the
synchronous or asynchronous aspect of its func attribute.

* **Return type:**
  `Any`
* **Parameters:**
  * **args** (*Any*)
  * **kwargs** (*Any*)

#### *async* run_async(\*args, \*\*kwargs)

Runs the tool in an asynchronous manner, no matter the
synchronous or asynchronous aspect of its func attribute.
If func is synchronous, it will run in an anyio worker thread.

* **Return type:**
  `Any`
* **Parameters:**
  * **args** (*Any*)
  * **kwargs** (*Any*)

## Tool from ToolBox

<a id="toolfromtoolbox"></a>

### *class* wayflowcore.tools.toolfromtoolbox.ToolFromToolBox(tool_name, toolbox)

A Tool that is extracted from a toolbox by name.

On serialization to dict, includes the datastore config.
On deserialization, restores the datastore to full object form.

* **Parameters:**
  * **tool_name** (*str*)
  * **toolbox** ([*ToolBox*](#wayflowcore.tools.toolbox.ToolBox))

## Remote Tool

<a id="remotetool"></a>

### *class* wayflowcore.tools.remotetools.RemoteTool(\*, url, method, name=None, description=None, json_body=None, data=None, params=None, headers=None, sensitive_headers=None, cookies=None, output_jq_query=None, ignore_bad_http_requests=False, num_retry_on_bad_http_request=3, input_descriptors=None, output_descriptors=None, allow_insecure_http=False, url_allow_list=None, allow_credentials=True, allow_fragments=True, default_ports={'http': 80, 'https': 443}, id=None, tool_name=None, tool_description=None, \_\_metadata_info_\_=None, requires_confirmation=False)

A Remote tool is a ServerTool that performs a web request.

#### CAUTION
Since the Agent can generate arguments (url, method, data, params, headers,
cookies) or parts of these arguments in the respective Jinja templates, this can impose a
security risk of information leakage and enable specific attack vectors like automated DDOS
attacks. Please use `RemoteTool` responsibly and ensure that only valid URLs can be given
as arguments or that no sensitive information is used for any of these arguments by the
agent. Please use the `url_allow_list`, `allow_credentials` and `allow_fragments`
parameters to control which URLs are treated as valid.

* **Parameters:**
  * **name** (`Optional`[`str`]) – The name of the tool
  * **description** (`Optional`[`str`]) – The description of the tool. This text is passed in prompt of LLMs to guide the usage of the tool
  * **url** (`str`) – Url to call.
    Can be templated using jinja templates.
  * **method** (`str`) – HTTP method to call.
    Common methods are: GET, OPTIONS, HEAD, POST, PUT, PATCH, or DELETE.
    Can be templated using jinja templates.
  * **data** (`Optional`[`Any`]) – 

    Data that will be sent in the body.

    If the header `Content-Type": "application/x-www-form-urlencoded"` is provided
    and if it is a dictionary, then it is inferred as form-data to be sent through the http request.

    If such a header is not given, then it will be sent as either the JSON object or the bytes content.
    Cannot be used in combination with the deprecated `json_body`.
    Can be templated using jinja templates.

    #### NOTE
    Special case: if the `data` is a `str` it will be tried to taken as a literal json string.
    Setting this parameter automatically sets the `Content-Type: application/json`
    header if the header does not correspond to form-data (`Content-Type": "application/x-www-form-urlencoded`).

    #### WARNING
    The `data` parameter is only relevant for http methods that allow bodies, e.g. POST, PUT, PATCH.
  * **params** (`Union`[`Dict`[`Any`, `Any`], `List`[`Tuple`[`Any`, `Any`]], `str`, `bytes`, `None`]) – Data to send as query-parameters (i.e. the `?foo=bar&gnu=gna` part of queries)
    Semantics of this are the same as in the `requests` library.
    Can be templated using jinja templates.
  * **headers** (`Optional`[`Dict`[`str`, `str`]]) – 

    Explicitly set headers.
    Can be templated using jinja templates.
    Keys of `sensitive_headers` and `headers` dictionaries cannot overlap.

    #### NOTE
    This will override any of the implicitly set headers (e.g. `Content-Type` from `data`).
  * **sensitive_headers** (`Optional`[`Dict`[`str`, `str`]]) – Explicitly set headers that contain sensitive information.
    These headers will behave equivalently to the `headers` parameter, but it will be excluded
    from any serialization for security reasons.
    Keys of `sensitive_headers` and `headers` dictionaries cannot overlap.
  * **cookies** (`Optional`[`Dict`[`str`, `str`]]) – Cookies to transmit.
    Can be templated using jinja templates.
  * **output_jq_query** (`Optional`[`str`]) – A jq query to extract some data from the json response. If left to None, the whole response is returned
  * **ignore_bad_http_requests** (`bool`) – If `True`, don’t throw an exception when query results in a bad status code (e.g. 4xx, 5xx); if `False` throws an exception.
  * **num_retry_on_bad_http_request** (`int`) – Number of times to retry a failed http request before continuing (depending on the `ignore_bad_http_requests` setting above).
  * **allow_insecure_http** (`bool`) – If `True`, allows url to have a unsecured non-ssl http scheme. Default is `False` and throws a ValueError if url is unsecure.
  * **url_allow_list** (`Optional`[`List`[`str`]]) – 

    A list of URLs that any request URL is matched against.
    : If there is at least one entry in the allow list that the requested URL matches,
      the request is considered allowed.
      

      We consider URLs following the generic-URL syntax as defined in [RFC 1808](https://datatracker.ietf.org/doc/html/rfc1808.html):
      `<scheme>://<net_loc>/<path>;<params>?<query>#<fragment>`
      

      Matching is done according to the following rules:
      * URL scheme must match exactly
      * URL authority (net_loc) must match exactly
      * URL path must prefix match the path given by the entry in the allow list
      * We do not support matching against specific params, fragments or query elements of the URLs.
      

      Examples of matches:
      * URL: “[https://example.com/page](https://example.com/page)”, allow_list: [”[https://example.com](https://example.com)”]
      * URL: “[https://specific.com/path/and/more](https://specific.com/path/and/more)”, allow_list: [”[https://specific.com/path](https://specific.com/path)”]
      

      Examples of mismatches:
      * URL: “[http://someurl.example.com](http://someurl.example.com)”, allow_list: [”[http://other.example.com](http://other.example.com)”]
      * URL: “[http://someurl.example.com/endpoint](http://someurl.example.com/endpoint)”, allow_list: [”[http://](http://)”] (results in a validation error)
      

      Can be used to restrict requests to a set of allowed urls.
  * **allow_credentials** (`bool`) – 

    Whether to allow URLs containing credentials.
    If set to `False`, requested URLs and those in the allow list containing credentials will be rejected.
    Default is `True`.

    Example of a URL containing credentials: “[https://user:pass@example.com/](https://user:pass@example.com/)”
  * **allow_fragments** (`bool`) – 

    Whether to allow fragments in requested URLs and in entries in the allow list.
    If set to `False`, fragments will not be allowed. Default is `True`.

    We consider URLs following the generic-URL syntax as defined in [RFC 1808](https://datatracker.ietf.org/doc/html/rfc1808.html):
    `<scheme>://<net_loc>/<path>;<params>?<query>#<fragment>`
  * **default_ports** (`Dict`[`str`, `int`]) – A dictionary containing default schemes and their respective ports.
    These ports will be removed from URLs requested or from entries in the allow list during URL normalization.
    Default is `{'http': 80, 'https': 443}`.
  * **requires_confirmation** (`bool`) – Flag for yielding ToolExecutionConfirmationStatus whenever the RemoteTool is called by the agent
  * **json_body** (*Any* *|* *None*)
  * **input_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **output_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **id** (*str* *|* *None*)
  * **tool_name** (*str* *|* *None*)
  * **tool_description** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

Below is an example of a remote tool that is configured to update the value of a field on a Jira ticket

```pycon
>>> from wayflowcore.property import StringProperty
>>> from wayflowcore.tools.remotetools import RemoteTool
>>>
>>> JIRA_API_BASE_URL = "https://yourjirainstance.yourdomain.com"
>>> JIRA_ACCESS_TOKEN = "your_secret_access_token"
>>>
>>> record_incident_root_cause_tool = RemoteTool(
...     tool_name="record_incident_root_cause_tool",
...     tool_description="Updates the root cause of an incident in Jira",
...     url=JIRA_API_BASE_URL+"/rest/api/2/issue/{{jira_issue_id}}",
...     input_descriptors=[
...         StringProperty(name="jira_issue_id", description="The ID of the Jira issue to update"),
...         StringProperty(
...             name="root_cause", description="The root cause description to be recorded"
...         ),
...     ],
...     method="PUT",
...     data={"fields": {"customfield_12602": "{{root_cause}}"}},
...     headers={
...         "Authorization": f"Bearer {JIRA_ACCESS_TOKEN}",
...         "Content-Type": "application/json",
...     },
...     url_allow_list=[JIRA_API_BASE_URL]
... )
```

You can then give the tool to either an [Agent](agent.md#agent) or to a
[ToolExecutionStep](flows.md#toolexecutionstep) to be used in a [Flow](flows.md#flow).
Additionally, you can test the tool in isolation by invoking it as below:

```python
record_incident_root_cause_tool.func(
    jira_issue_id="test-ticket",
    root_cause="this is the root cause"
)
```

#### allow_credentials *: `bool`*

#### allow_fragments *: `bool`*

#### allow_insecure_http *: `bool`*

#### cookies *: `Optional`[`Dict`[`str`, `str`]]*

#### data *: `Optional`[`Any`]*

#### default_ports *: `Dict`[`str`, `int`]*

#### description *: `str`*

#### headers *: `Optional`[`Dict`[`str`, `str`]]*

#### ignore_bad_http_requests *: `bool`*

#### input_descriptors *: `List`[[`Property`](flows.md#wayflowcore.property.Property)]*

#### json_body *: `Optional`[`Any`]*

#### method *: `str`*

#### name *: `str`*

#### num_retry_on_bad_http_request *: `int`*

#### output_descriptors *: `List`[[`Property`](flows.md#wayflowcore.property.Property)]*

#### output_jq_query *: `Optional`[`str`]*

#### params *: `Union`[`Dict`[`Any`, `Any`], `List`[`Tuple`[`Any`, `Any`]], `str`, `bytes`, `None`]*

#### requires_confirmation *: `bool`*

#### sensitive_headers *: `Optional`[`Dict`[`str`, `str`]]*

#### url *: `str`*

#### url_allow_list *: `Optional`[`List`[`str`]]*

## MCP Tool

[Model Context Protocol](https://modelcontextprotocol.io/introduction) (MCP) is an open protocol that standardizes how applications provide context to LLMs.

<a id="mcptool"></a>

### *class* wayflowcore.mcp.MCPTool(name, client_transport, description=None, input_descriptors=None, output_descriptors=None, \_validate_server_exists=True, \_validate_tool_exist_on_server=True, \_\_metadata_info_\_=None, id=None, requires_confirmation=False)

Class to represent a MCP tool exposed by a MCP server to a ServerTool.

#### SEE ALSO
[How to connect MCP tools to Assistants](../howtoguides/howto_mcp.md#top-howtomcp)

* **Parameters:**
  * **name** (*str*)
  * **client_transport** ([*ClientTransport*](#wayflowcore.mcp.ClientTransport))
  * **description** (*str* *|* *None*)
  * **input_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **output_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **\_validate_server_exists** (*bool*)
  * **\_validate_tool_exist_on_server** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str* *|* *None*)
  * **requires_confirmation** (*bool*)

#### client_transport *: [`ClientTransport`](#wayflowcore.mcp.ClientTransport)*

Transport to use for establishing and managing connections to the MCP server.

#### *property* might_yield *: bool*

Indicates that the tool might yield inside a step or a flow.

#### run(\*args, \*\*kwargs)

Runs the MCP tool in a synchronous manner.

* **Return type:**
  `Any`
* **Parameters:**
  * **args** (*Any*)
  * **kwargs** (*Any*)

#### *async* run_async(\*args, \*\*kwargs)

Runs the MCP tool in an asynchronous manner.

* **Return type:**
  `Any`
* **Parameters:**
  * **args** (*Any*)
  * **kwargs** (*Any*)

<a id="mcptoolbox"></a>

### *class* wayflowcore.mcp.MCPToolBox(id=<factory>, requires_confirmation=None, client_transport=<factory>, tool_filter=None, \_validate_mcp_client_transport=True, \*, \_\_metadata_info_\_=<factory>, name='', description=None)

Class to dynamically expose a list of tools from a MCP Server.

* **Parameters:**
  * **id** (*str*)
  * **requires_confirmation** (*bool* *|* *None*)
  * **client_transport** ([*ClientTransport*](#wayflowcore.mcp.ClientTransport))
  * **tool_filter** (*List* *[**str* *|* [*Tool*](#wayflowcore.tools.tools.Tool) *]*  *|* *None*)
  * **\_validate_mcp_client_transport** (*dataclasses.InitVar* *[**bool* *]*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)

#### client_transport *: [`ClientTransport`](#wayflowcore.mcp.ClientTransport)*

Transport to use for establishing and managing connections to the MCP server.

#### tool_filter *: `Optional`[`List`[`Union`[`str`, [`Tool`](#wayflowcore.tools.tools.Tool)]]]* *= None*

Optional filter to select specific tools.

If None, exposes all tools from the MCP server.

* Specifying a tool name (`str`) indicates that a tool of the given name is expected from the MCP server.
* Specifying a tool signature (`Tool`) validate the presence and signature of the specified tool in the MCP Server.
  : * The name of the MCP tool should match the name of the tool from the MCP Server.
    * Specifying a non-empty description will override the remote tool description.
    * Input descriptors can be provided with description of each input. The names and types should match the remote tool schema.

<a id="mcpstreamingtool"></a>

### wayflowcore.mcp.mcphelpers.mcp_streaming_tool(func, context_cls=None)

Decorate an MCP tool callable to enable streaming tool outputs.

This decorator adapts a server-side async generator tool implementation so
that intermediate yielded values are streamed to the client as tool output
events, while the final yielded value is treated as the tool’s final result.

* **Parameters:**
  * **func** (`Callable`[`...`, `AsyncGenerator`[`TypeVar`(`ToolOutuptTypeT`), `None`]]) – An async callable that returns an async generator. Each `yield` emits
    a tool output chunk to be streamed. The generator should eventually
    complete, and the last yielded value is typically interpreted as the final
    tool result.
  * **context_cls** (`Optional`[`Type`[`ContextType`]]) – Context class used to access MCP request/response context.
    If `None`, the decorator uses the `Context` type from the official
    MCP SDK. When using third-party MCP libraries, provide the appropriate
    context class so the decorator can correctly locate and use the context.
* **Return type:**
  `Callable`[`...`, `Any`]

#### NOTE
#### IMPORTANT
The wrapper primes the async generator by pulling the first (and, if available, second) item up
front to distinguish single-yield generators (treated as a final result with no streamed progress)
from multi-yield generators (where earlier yields are streamed as progress and only the last yield
is returned). As a result, a generator that errors after its first yield may appear to have emitted
progress chunks server-side even if a client only consumes/observes the final result.

### Example

```pycon
>>> import anyio
>>> from typing import AsyncGenerator
>>> from mcp.server.fastmcp import FastMCP
>>> from wayflowcore.mcp.mcphelpers import mcp_streaming_tool
>>> server = FastMCP(
...     name="Example MCP Server",
...     instructions="A MCP Server.",
... )
>>> @server.tool(description="Stream intermediate outputs, then yield the final result.")
... @mcp_streaming_tool
... async def my_streaming_tool(topic: str) -> AsyncGenerator[str, None]:
...     all_sentences = [f"{topic} part {i}" for i in range(2)]
...     for i in range(2):
...         await anyio.sleep(0.2)  # simulate work
...         yield all_sentences[i]
...     yield ". ".join(all_sentences)
>>>
>>> # server.run(transport="streamable-http")
```

<a id="sessionparameters"></a>

### *class* wayflowcore.mcp.SessionParameters(read_timeout_seconds=60)

Keyword arguments for the MCP ClientSession constructor.

* **Parameters:**
  **read_timeout_seconds** (*float*)

#### read_timeout_seconds *: `float`* *= 60*

How long, in seconds, to wait for a network read before
aborting the operation. Adjust this to suit your network latency,
slow clients or servers, or to enforce stricter timeouts for
high-throughput scenarios.

<a id="enablemcpwithoutauth"></a>

### wayflowcore.mcp.enable_mcp_without_auth()

Helper function to enable the use of client transport without authentication.
:rtype: `None`

#### WARNING
This method should only be used in prototyping.

### Example

```pycon
>>> from wayflowcore.mcp import enable_mcp_without_auth, MCPToolBox, SSETransport
>>> enable_mcp_without_auth()
>>> transport = SSETransport(
...     url="https://localhost:8443/sse",
... )
>>> mcp_toolbox = MCPToolBox(client_transport=transport)
```

* **Return type:**
  None

<a id="mcpoauthconfigfactory"></a>

### *class* wayflowcore.mcp.MCPOAuthConfigFactory

Factory for producing OAuthConfig instances for MCP server authentication.

#### *static* with_dynamic_discovery(redirect_uri)

Create an OAuthConfig for MCP server supporting the OAuth 2.0
dynamic client registration (DCR) with discovery mechanism.

* **Parameters:**
  **redirect_uri** (*str*) – Redirect (callback) URI for the authorization code flow.
  e.g., “[http://localhost:8003/callback](http://localhost:8003/callback)”
* **Return type:**
  [`OAuthConfig`](auth.md#wayflowcore.auth.auth.OAuthConfig)

<a id="clienttransport"></a>

### *class* wayflowcore.mcp.ClientTransport(\_\_metadata_info_\_=None, id=None)

Base class for different MCP client transport mechanisms.

A Transport is responsible for establishing and managing connections
to an MCP server, and providing a ClientSession within an async context.

* **Parameters:**
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str* *|* *None*)

#### session_parameters *: [`SessionParameters`](#wayflowcore.mcp.SessionParameters)* *= Field(name=None,type=None,default=<dataclasses._MISSING_TYPE object>,default_factory=<class 'wayflowcore.mcp.clienttransport.SessionParameters'>,init=True,repr=True,hash=None,compare=True,metadata=mappingproxy({}),kw_only=<dataclasses._MISSING_TYPE object>,_field_type=None)*

Arguments for the MCP session.

<a id="stdiotransport"></a>

### *class* wayflowcore.mcp.StdioTransport(command=<factory>, args=<factory>, env=None, cwd=None, encoding='utf-8', encoding_error_handler='strict', session_parameters=<factory>, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Base transport for connecting to an MCP server via subprocess with stdio.

This is a base class that can be subclassed for specific command-based
transports like Python, Node, Uvx, etc.

#### NOTE
The **stdio** transport is the recommended mechanism when the MCP server is launched as a local
subprocess by the client application. This approach is ideal for scenarios where the server runs
on the same machine as the client.

For more information, visit [https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#stdio](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#stdio)

* **Parameters:**
  * **command** (*str*)
  * **args** (*List* *[**str* *]*)
  * **env** (*Dict* *[**str* *,* *str* *]*  *|* *None*)
  * **cwd** (*str* *|* *None*)
  * **encoding** (*str*)
  * **encoding_error_handler** (*Literal* *[* *'strict'* *,*  *'ignore'* *,*  *'replace'* *]*)
  * **session_parameters** ([*SessionParameters*](#wayflowcore.mcp.SessionParameters))
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### args *: `List`[`str`]*

Command line arguments to pass to the executable.

#### command *: `str`*

The executable to run to start the server.

#### cwd *: `Optional`[`str`]* *= None*

The working directory to use when spawning the process.

#### encoding *: `str`* *= 'utf-8'*

The text encoding used when sending/receiving messages to the server. Defaults to utf-8.

#### encoding_error_handler *: `Literal`[`'strict'`, `'ignore'`, `'replace'`]* *= 'strict'*

The text encoding error handler.

See [https://docs.python.org/3/library/codecs.html#codec-base-classes](https://docs.python.org/3/library/codecs.html#codec-base-classes) for
explanations of possible values.

#### env *: `Optional`[`Dict`[`str`, `str`]]* *= None*

The environment to use when spawning the process.

If not specified, the result of get_default_environment() will be used.

<a id="ssetransport"></a>

### *class* wayflowcore.mcp.SSETransport(url=<factory>, headers=None, sensitive_headers=None, timeout=5, sse_read_timeout=300, auth=None, follow_redirects=True, session_parameters=<factory>, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Transport implementation that connects to an MCP server via Server-Sent Events.

#### WARNING
This transport should be used for prototyping only. For production, please use
a transport that supports mTLS.

### Examples

```pycon
>>> from wayflowcore.mcp import SSETransport
>>> transport = SSETransport(url="https://server/sse")
```

* **Parameters:**
  * **url** (*str*)
  * **headers** (*Dict* *[**str* *,* *str* *]*  *|* *None*)
  * **sensitive_headers** (*Dict* *[**str* *,* *str* *]*  *|* *None*)
  * **timeout** (*float*)
  * **sse_read_timeout** (*float*)
  * **auth** ([*AuthConfig*](auth.md#wayflowcore.auth.auth.AuthConfig) *|* *None*)
  * **follow_redirects** (*bool*)
  * **session_parameters** ([*SessionParameters*](#wayflowcore.mcp.SessionParameters))
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

<a id="ssemtlstransport"></a>

### *class* wayflowcore.mcp.SSEmTLSTransport(url=<factory>, headers=None, sensitive_headers=None, timeout=5, sse_read_timeout=300, auth=None, follow_redirects=True, session_parameters=<factory>, key_file=<factory>, cert_file=<factory>, ssl_ca_cert=<factory>, check_hostname=False, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Transport layer for SSE with mTLS (mutual Transport Layer Security).

This transport establishes a secure, mutually authenticated TLS connection to the MCP server using client
certificates. Production deployments MUST use this transport to ensure both client and server identities
are verified.

### Notes

- Users MUST provide a valid client certificate (PEM format) and private key.
- Users MUST provide (or trust) the correct certificate authority (CA) for the server they’re connecting to.
- The client certificate/key and CA certificate paths can be managed via secrets, config files, or secure
  environment variables in any production system.
- Executors should ensure that these files are rotated and managed securely.

### Examples

```pycon
>>> from wayflowcore.mcp import SSEmTLSTransport
>>> mtls = SSEmTLSTransport(
...   url="https://server/sse",
...   key_file="/etc/certs/client.key",
...   cert_file="/etc/certs/client.pem",
...   ssl_ca_cert="/etc/certs/ca.pem"
... )
>>> # To pass a Bearer token, use the headers argument:
>>> mtls_2 = SSEmTLSTransport(
...   url="https://server/sse",
...   key_file="...",
...   cert_file="...",
...   ssl_ca_cert="...",
...   sensitive_headers={"Authorization": "Bearer <token>"}
... )
```

* **Parameters:**
  * **url** (*str*)
  * **headers** (*Dict* *[**str* *,* *str* *]*  *|* *None*)
  * **sensitive_headers** (*Dict* *[**str* *,* *str* *]*  *|* *None*)
  * **timeout** (*float*)
  * **sse_read_timeout** (*float*)
  * **auth** ([*AuthConfig*](auth.md#wayflowcore.auth.auth.AuthConfig) *|* *None*)
  * **follow_redirects** (*bool*)
  * **session_parameters** ([*SessionParameters*](#wayflowcore.mcp.SessionParameters))
  * **key_file** (*str*)
  * **cert_file** (*str*)
  * **ssl_ca_cert** (*str*)
  * **check_hostname** (*bool*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

<a id="streamablehttptransport"></a>

### *class* wayflowcore.mcp.StreamableHTTPTransport(url=<factory>, headers=None, sensitive_headers=None, timeout=5, sse_read_timeout=300, auth=None, follow_redirects=True, session_parameters=<factory>, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Transport implementation that connects to an MCP server via Streamable HTTP.
This transport is the recommended option when connecting to a remote MCP server.

#### WARNING
This transport should be used for prototyping only. For production, please use
a transport that supports mTLS.

### Examples

```pycon
>>> from wayflowcore.mcp import StreamableHTTPTransport
>>> transport = StreamableHTTPTransport(url="https://server/mcp")
```

* **Parameters:**
  * **url** (*str*)
  * **headers** (*Dict* *[**str* *,* *str* *]*  *|* *None*)
  * **sensitive_headers** (*Dict* *[**str* *,* *str* *]*  *|* *None*)
  * **timeout** (*float*)
  * **sse_read_timeout** (*float*)
  * **auth** ([*AuthConfig*](auth.md#wayflowcore.auth.auth.AuthConfig) *|* *None*)
  * **follow_redirects** (*bool*)
  * **session_parameters** ([*SessionParameters*](#wayflowcore.mcp.SessionParameters))
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

<a id="streamablehttpmtlstransport"></a>

### *class* wayflowcore.mcp.StreamableHTTPmTLSTransport(url=<factory>, headers=None, sensitive_headers=None, timeout=5, sse_read_timeout=300, auth=None, follow_redirects=True, session_parameters=<factory>, key_file=<factory>, cert_file=<factory>, ssl_ca_cert=<factory>, check_hostname=False, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Transport layer for streamable HTTP with mTLS (mutual Transport Layer Security).

This transport establishes a secure, mutually authenticated TLS connection to the MCP server using client
certificates. Production deployments MUST use this transport to ensure both client and server identities
are verified.

### Notes

- Users MUST provide a valid client certificate (PEM format) and private key.
- Users MUST provide (or trust) the correct certificate authority (CA) for the server they’re connecting to.
- The client certificate/key and CA certificate paths can be managed via secrets, config files, or secure
  environment variables in any production system.
- Executors should ensure that these files are rotated and managed securely.

### Examples

```pycon
>>> from wayflowcore.mcp import StreamableHTTPmTLSTransport
>>> mtls = StreamableHTTPmTLSTransport(
...   url="https://server/mcp",
...   key_file="/etc/certs/client.key",
...   cert_file="/etc/certs/client.pem",
...   ssl_ca_cert="/etc/certs/ca.pem"
... )
>>> # To pass a Bearer token, use the headers argument:
>>> mtls_2 = StreamableHTTPmTLSTransport(
...   url="https://server/mcp",
...   key_file="...",
...   cert_file="...",
...   ssl_ca_cert="...",
...   sensitive_headers={"Authorization": "Bearer <token>"}
... )
```

* **Parameters:**
  * **url** (*str*)
  * **headers** (*Dict* *[**str* *,* *str* *]*  *|* *None*)
  * **sensitive_headers** (*Dict* *[**str* *,* *str* *]*  *|* *None*)
  * **timeout** (*float*)
  * **sse_read_timeout** (*float*)
  * **auth** ([*AuthConfig*](auth.md#wayflowcore.auth.auth.AuthConfig) *|* *None*)
  * **follow_redirects** (*bool*)
  * **session_parameters** ([*SessionParameters*](#wayflowcore.mcp.SessionParameters))
  * **key_file** (*str*)
  * **cert_file** (*str*)
  * **ssl_ca_cert** (*str*)
  * **check_hostname** (*bool*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

## Tool decorator

<a id="tooldecorator"></a>

### wayflowcore.tools.toolhelpers.tool(\*args, description_mode=DescriptionMode.INFER_FROM_SIGNATURE, output_descriptors=None, requires_confirmation=False)

Make tools out of callables, can be used as a decorator or as a wrapper.

* **Parameters:**
  * **\*args** (*str* *|* *Callable* *[* *[* *...* *]* *,* *Any* *]*) – The optional name and callable to convert to a `ServerTool`.
    See the example section for common usage patterns.
  * **description_mode** (`Literal`[`<DescriptionMode.INFER_FROM_SIGNATURE: 'infer_from_signature'>`, `<DescriptionMode.ONLY_DOCSTRING: 'only_docstring'>`, `<DescriptionMode.EXTRACT_FROM_DOCSTRING: 'extract_from_docstring'>`]) – 

    Determines how parameter descriptions are set:
    * ”infer_from_signature”: Extracted from the function signature.
    * ”only_docstring”: Parameter descriptions are left empty; the full description is in the tool docstring.
    * ”extract_from_docstring”: Parameter descriptions are parsed from the function’s docstring. Currently not supported.

    Defaults to “infer_from_signature”.
  * **output_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – list of properties to describe the tool outputs. Needed in case of tools with several outputs.
  * **requires_confirmation** (*bool*) – Flag to make tool require confirmation before execution. Yields a ToolExecutionConfirmationStatus before its execution.
  * **Returns** – The decorated/wrapper callable as a `ServerTool`.
* **Return type:**
  `Union`[[`ServerTool`](#wayflowcore.tools.servertools.ServerTool), `Callable`[[`Callable`[`...`, `Any`]], [`ServerTool`](#wayflowcore.tools.servertools.ServerTool)]]

### Examples

The `tool` helper can be used as a decorator:

```pycon
>>> from wayflowcore.tools import tool
>>> @tool
... def my_callable() -> str:
...     """Callable description"""
...     return ""
```

Tools can be renamed:

```pycon
>>> @tool("my_renamed_tool")
... def my_callable() -> str:
...     """Callable description"""
...     return ""
```

The `tool` helper can automatically infer a tool input/output schema:

```pycon
>>> from typing import Annotated
>>> @tool
... def my_callable(param1: Annotated[int, "param1 description"] = 2) -> int:
...     """Callable description"""
...     return 0
```

The user can also specify not to infer the parameter descriptions (when they are in the docstring):

```pycon
>>> @tool(description_mode="only_docstring")
... def my_callable(param1: int = 2) -> int:
...     """Callable description
...     Parameters
...     ----------
...     param1:
...         Description of my parameter 1.
...     """
...     return 0
```

The `tool` helper can also be used as a wrapper:

```pycon
>>> def my_callable() -> str:
...     """Callable description"""
...     return ""
...
>>> my_tool = tool(my_callable)
```

Use the `tool` helper as a wrapper to create stateful tools (tools that modify the internal state of the object):

```pycon
>>> class MyClass:
...     def my_callable(
...         self, param1: Annotated[int, "param1 description"] = 2
...     ) -> Annotated[int, "output description"]:
...         """Callable description"""
...         return 0
...
>>> my_object = MyClass()
>>> my_stateful_tool = tool(my_object.my_callable)
```

Use the `output_descriptors` argument to make tools with several outputs:

```pycon
>>> from typing import Dict, Union
>>> from wayflowcore.property import StringProperty, IntegerProperty
>>> @tool(output_descriptors=[StringProperty(name='output1'), IntegerProperty(name='output2')])
... def my_callable() -> Dict[str, Union[str, int]]:
...     """Callable to return some outputs"""
...     return {'output1': 'some_output', 'output2': 2}
```

### Notes

When creating tools, follow these guidelines to optimize tool calling performance with Agents:

* **Choose descriptive names**: Select clear and concise names for your tools to facilitate understanding when using them in Agents.
* **Write precise descriptions**: Provide precise descriptions for your tools, including information about their purpose, inputs, outputs, and any relevant constraints or assumptions.
* **Use type annotations**: Annotate function parameters and return types with precise types to enable automatic schema inference and improve code readability.
* **Specify return types**: Always specify the return type of your tool to ensure clarity (mandatory).

## Tool Request and Result Classes

<a id="toolrequest"></a>

### *class* wayflowcore.tools.tools.ToolRequest(name, args, tool_request_id=<factory>, \_extra_content=None, \_requires_confirmation=False, \_tool_execution_confirmed=None, \_tool_rejection_reason=None)

* **Parameters:**
  * **name** (*str*)
  * **args** (*Dict* *[**str* *,* *Any* *]*)
  * **tool_request_id** (*str*)
  * **\_extra_content** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **\_requires_confirmation** (*bool*)
  * **\_tool_execution_confirmed** (*bool* *|* *None*)
  * **\_tool_rejection_reason** (*str* *|* *None*)

#### args *: `Dict`[`str`, `Any`]*

#### name *: `str`*

#### tool_request_id *: `str`*

<a id="toolresult"></a>

### *class* wayflowcore.tools.tools.ToolResult(content, tool_request_id)

* **Parameters:**
  * **content** (*Any*)
  * **tool_request_id** (*str*)

#### content *: `Any`*

#### tool_request_id *: `str`*

## ToolBox

<a id="id3"></a>

### *class* wayflowcore.tools.toolbox.ToolBox(id=<factory>, requires_confirmation=None)

Class to expose a list of tools to agentic components.

ToolBox is dynamic which means that agentic components equipped
with a toolbox can may see its tools to evolve throughout its
execution.

* **Parameters:**
  * **requires_confirmation** (`Optional`[`bool`]) – Flag to ask for user confirmation whenever executing any of this toolbox’s tools, yields `ToolExecutionConfirmationStatus` if True or if the `Tool` from the `ToolBox` requires confirmation.
  * **id** (*str*)

#### get_tools()

Return the list of tools exposed by the `ToolBox`.

Will be called at every iteration in the execution loop
of agentic components.

* **Return type:**
  `Sequence`[[`Tool`](#wayflowcore.tools.tools.Tool)]

#### *async* get_tools_async()

Return the list of tools exposed by the `ToolBox` in an asynchronous manner.

Will be called at every iteration in the execution loop
of agentic components.

* **Return type:**
  `Sequence`[[`Tool`](#wayflowcore.tools.tools.Tool)]

#### id *: `str`*

#### *property* might_yield *: bool*

#### requires_confirmation *: `Optional`[`bool`]* *= None*
