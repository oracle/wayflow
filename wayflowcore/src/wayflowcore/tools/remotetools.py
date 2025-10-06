# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from wayflowcore._metadata import MetadataType
from wayflowcore.property import Property
from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject

from .servertools import ServerTool


@dataclass
class RemoteTool(SerializableDataclassMixin, ServerTool, SerializableObject):
    """
    A Remote tool is a ServerTool that performs a web request.

    .. caution::
        Since the Agent can generate arguments (url, method, json_body, data, params, headers,
        cookies) or parts of these arguments in the respective Jinja templates, this can impose a
        security risk of information leakage and enable specific attack vectors like automated DDOS
        attacks. Please use ``RemoteTool`` responsibly and ensure that only valid URLs can be given
        as arguments or that no sensitive information is used for any of these arguments by the
        agent. Please use the ``url_allow_list``, ``allow_credentials`` and ``allow_fragments``
        parameters to control which URLs are treated as valid.

    Parameters
    ----------
    name
        The name of the tool
    description
        The description of the tool. This text is passed in prompt of LLMs to guide the usage of the tool
    url
        Url to call.
        Can be templated using jinja templates.
    method
        HTTP method to call.
        Common methods are: GET, OPTIONS, HEAD, POST, PUT, PATCH, or DELETE.
        Can be templated using jinja templates.
    json_body
        A json-serializable object that will automatically be converted to json and sent as a body.
        Cannot be used in combination with ``data``.
        Can be templated using jinja templates.

        .. note::
            Special case: if the ``json_body`` is a ``str`` it will be taken as a literal json string.
            Setting this parameter automatically sets the ``Content-Type: application/json`` header.

        .. warning::
            The ``json_body`` parameter is only relevant for http methods that allow bodies, e.g. POST, PUT, PATCH.

    data
        Raw data that will be sent in the body.
        Semantics of this are the same as in the ``requests`` library.
        Cannot be used in combination with ``json_body``.
        Can be templated using jinja templates.

        .. warning::
            The ``data`` parameter is only relevant for http methods that allow bodies, e.g. POST, PUT, PATCH.
    params
        Data to send as query-parameters (i.e. the ``?foo=bar&gnu=gna`` part of queries)
        Semantics of this are the same as in the ``requests`` library.
        Can be templated using jinja templates.
    headers
        Explicitly set headers.
        Can be templated using jinja templates.

        .. note::
            This will override any of the implicitly set headers (e.g. ``Content-Type`` from ``json_body``).
    cookies
        Cookies to transmit.
        Can be templated using jinja templates.
    output_jq_query
        A jq query to extract some data from the json response. If left to None, the whole response is returned
    ignore_bad_http_requests
        If ``True``, don't throw an exception when query results in a bad status code (e.g. 4xx, 5xx); if ``False`` throws an exception.
    num_retry_on_bad_http_request
        Number of times to retry a failed http request before continuing (depending on the ``ignore_bad_http_requests`` setting above).
    allow_insecure_http:
        If ``True``, allows url to have a unsecured non-ssl http scheme. Default is ``False`` and throws a ValueError if url is unsecure.
    url_allow_list
       A list of URLs that any request URL is matched against.
        If there is at least one entry in the allow list that the requested URL matches,
        the request is considered allowed.

        We consider URLs following the generic-URL syntax as defined in `RFC 1808`_:
        ``<scheme>://<net_loc>/<path>;<params>?<query>#<fragment>``

        Matching is done according to the following rules:

        * URL scheme must match exactly
        * URL authority (net_loc) must match exactly
        * URL path must prefix match the path given by the entry in the allow list
        * We do not support matching against specific params, fragments or query elements of the URLs.

        Examples of matches:

        * URL: "https://example.com/page", allow_list: ["https://example.com"]
        * URL: "https://specific.com/path/and/more", allow_list: ["https://specific.com/path"]

        Examples of mismatches:

        * URL: "http://someurl.example.com", allow_list: ["http://other.example.com"]
        * URL: "http://someurl.example.com/endpoint", allow_list: ["http://"] (results in a validation error)

        .. _RFC 1808: https://datatracker.ietf.org/doc/html/rfc1808.html

        Can be used to restrict requests to a set of allowed urls.
    allow_credentials
        Whether to allow URLs containing credentials.
        If set to ``False``, requested URLs and those in the allow list containing credentials will be rejected.
        Default is ``True``.

        Example of a URL containing credentials: "https://user:pass@example.com/"
    allow_fragments
        Whether to allow fragments in requested URLs and in entries in the allow list.
        If set to ``False``, fragments will not be allowed. Default is ``True``.

        We consider URLs following the generic-URL syntax as defined in `RFC 1808`_:
        ``<scheme>://<net_loc>/<path>;<params>?<query>#<fragment>``

        .. _RFC 1808: https://datatracker.ietf.org/doc/html/rfc1808.html
    default_ports
        A dictionary containing default schemes and their respective ports.
        These ports will be removed from URLs requested or from entries in the allow list during URL normalization.
        Default is ``{'http': 80, 'https': 443}``.


    Examples
    --------

    Below is an example of a remote tool that is configured to update the value of a field on a Jira ticket


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
    ...     json_body={"fields": {"customfield_12602": "{{root_cause}}"}},
    ...     headers={
    ...         "Authorization": f"Bearer {JIRA_ACCESS_TOKEN}",
    ...         "Content-Type": "application/json",
    ...     },
    ...     url_allow_list=[JIRA_API_BASE_URL]
    ... )

    You can then give the tool to either an :ref:`Agent <Agent>` or to a
    :ref:`ToolExecutionStep <ToolExecutionStep>` to be used in a :ref:`Flow <Flow>`.
    Additionally, you can test the tool in isolation by invoking it as below:

    .. code-block:: python

        record_incident_root_cause_tool.func(
            jira_issue_id="test-ticket",
            root_cause="this is the root cause"
        )

    """

    name: str
    description: str
    url: str
    method: str
    json_body: Optional[Any]
    data: Optional[Union[Dict[Any, Any], List[Tuple[Any, Any]], str, bytes]]
    params: Optional[Union[Dict[Any, Any], List[Tuple[Any, Any]], str, bytes]]
    headers: Optional[Dict[str, str]]
    cookies: Optional[Dict[str, str]]
    output_jq_query: Optional[str]
    ignore_bad_http_requests: bool
    num_retry_on_bad_http_request: int
    input_descriptors: List[Property]
    output_descriptors: List[Property]
    allow_insecure_http: bool
    url_allow_list: Optional[List[str]]
    allow_credentials: bool
    allow_fragments: bool
    default_ports: Dict[str, int]

    def __init__(
        self,
        *,
        url: str,
        method: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        json_body: Optional[Any] = None,
        data: Optional[Union[Dict[Any, Any], List[Tuple[Any, Any]], str, bytes]] = None,
        params: Optional[Union[Dict[Any, Any], List[Tuple[Any, Any]], str, bytes]] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        output_jq_query: Optional[str] = None,
        ignore_bad_http_requests: bool = False,
        num_retry_on_bad_http_request: int = 3,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        allow_insecure_http: bool = False,
        url_allow_list: Optional[List[str]] = None,
        allow_credentials: bool = True,
        allow_fragments: bool = True,
        default_ports: Dict[str, int] = {"http": 80, "https": 443},
        id: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_description: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        from wayflowcore.steps import ApiCallStep

        step_output = ApiCallStep.HTTP_RESPONSE if output_jq_query is None else "step_output"
        api_call_step = ApiCallStep(
            url=url,
            method=method,
            json_body=json_body,
            data=data,
            params=params,
            headers=headers,
            cookies=cookies,
            ignore_bad_http_requests=ignore_bad_http_requests,
            num_retry_on_bad_http_request=num_retry_on_bad_http_request,
            allow_insecure_http=allow_insecure_http,
            url_allow_list=url_allow_list,
            allow_credentials=allow_credentials,
            allow_fragments=allow_fragments,
            default_ports=default_ports,
            store_response=True if output_jq_query is None else False,
            output_values_json={step_output: output_jq_query} if output_jq_query else None,
        )
        name = name or tool_name
        description = description or tool_description
        if name is None:
            raise ValueError("RemoteTool should have a name, but got None")
        if description is None:
            raise ValueError("RemoteTool should have a description, but got None")

        tmp_tool = ServerTool.from_step(api_call_step, name, description, step_output)
        super().__init__(
            name=tmp_tool.name,
            description=tmp_tool.description or "",
            input_descriptors=input_descriptors or tmp_tool.input_descriptors,
            output_descriptors=output_descriptors or tmp_tool.output_descriptors,
            func=tmp_tool.func,
            id=id,
            __metadata_info__=__metadata_info__,
        )
        self.tool_name = self.name
        self.tool_description = self.description
        self.url = url
        self.method = method
        self.json_body = json_body
        self.data = data
        self.params = params
        self.headers = headers
        self.cookies = cookies
        self.output_jq_query = output_jq_query
        self.ignore_bad_http_requests = ignore_bad_http_requests
        self.num_retry_on_bad_http_request = num_retry_on_bad_http_request
        self.allow_insecure_http = allow_insecure_http
        self.url_allow_list = url_allow_list
        self.allow_credentials = allow_credentials
        self.allow_fragments = allow_fragments
        self.default_ports = default_ports
