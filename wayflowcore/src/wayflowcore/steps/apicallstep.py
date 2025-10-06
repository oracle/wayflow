# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import ipaddress
import json
import logging
import re
import unicodedata
import warnings
from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional, Tuple, Union
from urllib.parse import parse_qs, quote, quote_plus, unquote, urlencode, urlparse, urlunparse

import httpx
import jq
from pydantic import AnyUrl

from wayflowcore._metadata import MetadataType
from wayflowcore._utils._templating_helpers import (
    get_variable_names_from_object,
    render_nested_object_template,
    render_str_template,
)
from wayflowcore.property import IntegerProperty, Property, StringProperty, string_to_property
from wayflowcore.steps.step import Step, StepResult

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation

URL_ENCODED_SLASH = quote_plus("/")

logger = logging.getLogger(__name__)


class _NormalizedParseResult(NamedTuple):
    scheme: str
    netloc: str
    path: str
    params: str
    query: str
    fragment: str


def _is_allowed_url(parsed_url: _NormalizedParseResult, pattern: str) -> bool:

    parsed_pattern = _normalize_parse_url(pattern)
    if not parsed_pattern:
        raise ValueError("An error occurred when normalizing the URL.")

    if not parsed_url.scheme == parsed_pattern.scheme:
        return False

    if not parsed_pattern.netloc == parsed_url.netloc:
        return False

    if parsed_pattern.path and not parsed_url.path.startswith(parsed_pattern.path):
        return False

    return True


def _normalize_parse_url(
    url: str,
    allow_credentials: bool = True,
    allow_fragments: bool = True,
    default_ports: Dict[str, int] = {"http": 80, "https": 443},
) -> Optional[_NormalizedParseResult]:
    """
    Perform URL normalization.

    Args:
        url (str): The URL to normalize
        allow_credentials (bool): Whether to preserve username/password in URL (default: True)
        allow_fragments (bool): Whether to preserve fragments (default: True)
        default_ports (dict): Dictionary of default ports for schemes to remove (default: {'http': 80, 'https': 443})

    Returns:
        str: Normalized URL string or None if the URL is invalid or cannot be normalized safely
    """
    if not url or not isinstance(url, str):
        return None

    try:
        # Step 1: Basic validation and sanitation
        # Remove leading/trailing whitespace, control characters, and normalize Unicode
        # Control characters are removed to mitigate issues where hidden characters might alter the behavior of subsequent parsing.
        url = unicodedata.normalize("NFKC", url.strip())
        url = "".join(c for c in url if not unicodedata.category(c).startswith("C"))

        # Remove URL-encoded NULL bytes (%00), literal NULL characters (\0), and malformed percent-encoded sequences
        # (using re.search with a negative lookahead) to a guard against injection attacks or other forms of URL-based exploits.
        if "%00" in url or "\0" in url or re.search(r"%(?![\da-fA-F]{2})", url):
            logger.debug("Null byte detected during URL Normalization.")
            return None

        # Step 2: Parse the URL (without fully unquoting)
        parsed = urlparse(url)

        # Step 3: Validate and normalize scheme
        scheme = parsed.scheme.lower()

        # Step 4: Handle and validate netloc (credentials, hostname, port)
        netloc = parsed.netloc
        # Split credentials if present
        if "@" in netloc:
            credentials_part, hostport = netloc.rsplit("@", 1)
            if not allow_credentials:
                logger.debug("Credentials detected but allow_credentials==False.")
                return None
            # Reject if credentials contain multiple '@'
            if "@" in credentials_part:
                return None
            # Split credentials on ':' and re-encode after decoding
            if ":" in credentials_part:
                username, password = credentials_part.split(":", 1)
                username = quote(unquote(username), safe="")
                password = quote(unquote(password), safe="")
                credentials = f"{username}:{password}"
            else:
                credentials = quote(unquote(credentials_part), safe="")
        else:
            credentials = ""
            hostport = netloc

        hostport = hostport.lower()

        # Extract hostname and port if present (ignoring IPv6 special handling)
        if ":" in hostport:
            hostname, port_str = hostport.rsplit(":", 1)
            try:
                port = int(port_str)
                # Remove default ports
                if port == default_ports.get(scheme, -1):
                    port = -1
                elif port < 1 or port > 65535:
                    logger.debug("Host port is out of valid bounds (port < 1 or port > 65535).")
                    return None
            except ValueError:
                return None
        else:
            hostname = hostport
            port = None

        # Validate hostname
        if not hostname:
            logger.debug("Invalid hostname.")
            return None
        if ".." in hostname:
            logger.debug("Invalid hostname.")
            return None

        # Check if hostname is an IP address (for IPv4 and IPv6 literals)
        try:
            ipaddress.ip_address(hostname.strip("[]"))
            is_ip = True
        except ValueError:
            is_ip = False

        if not is_ip:
            # Validate hostname: only allow lowercase alphanumerics, hyphens, and dots
            # This might reject some valid hostnames containing underscores or non-Latin characters unless
            # they are already normalized to punycode
            if not re.match(r"^[a-z0-9]([a-z0-9\-\.]*[a-z0-9])?$", hostname):
                logger.debug(
                    "Hostname contains invalid characters or is not normalized to punycode."
                )
                return None
            # Handle punycode domains: ensure proper IDNA encoding/decoding
            if "xn--" in hostname:
                try:
                    hostname = hostname.encode("idna").decode("ascii")
                except UnicodeError:
                    return None

        # Step 5: Handle path
        # Use default path "/" if missing
        path = parsed.path or "/"
        # Decode the path
        decoded_path = unquote(path)
        # Normalize path: collapse multiple slashes and resolve dot segments
        decoded_path = re.sub(r"/+", "/", decoded_path)
        segments: list[str] = []
        had_trailing_slash = decoded_path.endswith("/")
        for segment in decoded_path.split("/"):
            if segment == "..":
                if segments:
                    segments.pop()
            elif segment and segment != ".":
                segments.append(segment)
        normalized_path = "/" + "/".join(segments)
        if had_trailing_slash and not normalized_path.endswith("/"):
            normalized_path += "/"
        # Re-encode the path to ensure unsafe characters are percent-encoded
        normalized_path = quote(normalized_path, safe="/~!$&'()*+,;=:@")

        # Step 6: Handle query parameters
        query = parsed.query
        if query:
            query_params = parse_qs(query, keep_blank_values=True)
            sorted_query = []
            for key in sorted(query_params.keys()):
                values = sorted(query_params[key])
                for value in values:
                    # Decode then re-encode each key and value
                    decoded_key = unquote(key)
                    decoded_value = unquote(value)
                    sorted_query.append((decoded_key, decoded_value))
            query = urlencode(sorted_query)

        # Step 7: Handle fragments
        fragment = parsed.fragment
        if fragment:
            if not allow_fragments:
                return None
            fragment = quote(unquote(fragment), safe="")

        # Step 8: Rebuild the netloc with credentials (if allowed) and port (if non-default)
        if credentials and allow_credentials:
            netloc = f"{credentials}@{hostname}"
        else:
            netloc = hostname
        if port != -1:
            netloc = f"{netloc}:{port}"

        # Return a named tuple
        return _NormalizedParseResult(
            scheme, netloc, normalized_path, parsed.params, query, fragment
        )

    except Exception:
        # Fail closed on any exception to ensure safety
        return None


def _normalize_allow_list(
    allow_list: List[str],
    allow_credentials: bool,
    allow_fragments: bool,
    default_ports: Dict[str, int],
) -> List[str]:
    for entry in allow_list:
        _ = AnyUrl(entry)
        normalized_tuple = _normalize_parse_url(
            entry,
            allow_credentials=allow_credentials,
            allow_fragments=allow_fragments,
            default_ports=default_ports,
        )
        if not normalized_tuple:
            raise ValueError("An error occurred when normalizing the URL.")
        entry = urlunparse(
            (
                normalized_tuple.scheme,
                normalized_tuple.netloc,
                normalized_tuple.path,
                normalized_tuple.params,
                normalized_tuple.query,
                normalized_tuple.fragment,
            )
        )
    return allow_list


class ApiCallStep(Step):
    """A step for calling remote APIs.
    It can do GET/POST/PUT/DELETE/etc. requests to endpoints.
    The query parameters, body, headers, cookies can be configured and can be templated so that they
    take values from the IO system.
    If the response is JSON its contents can be automatically extracted using json queries.

    .. caution::
        Since the Agent can generate arguments (url, method, json_body, data, params, headers, cookies) or parts of these arguments in the respective Jinja
        templates, this can impose a security risk of information leakage and enable specific attack vectors like automated DDOS attacks. Please use
        ``ApiCallStep`` responsibly and ensure that only valid URLs can be given as arguments or that no sensitive information is used for any of these arguments by the agent.
        Please use the url_allow_list, allow_credentials and allow_fragments parameters to control which URLs are treated as valid.
    """

    HTTP_RESPONSE = "http_response"
    """str: Output key for the http response resulting from the API call."""
    HTTP_STATUS_CODE = "http_status_code"
    """str: Output key for the http status code resulting from the API call."""

    def __init__(
        self,
        url: str,
        method: str,
        json_body: Optional[Any] = None,
        data: Optional[Union[Dict[Any, Any], List[Tuple[Any, Any]], str, bytes]] = None,
        params: Optional[Union[Dict[Any, Any], List[Tuple[Any, Any]], str, bytes]] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        output_values_json: Optional[Dict[Union[str, Property], str]] = None,
        store_response: bool = False,
        ignore_bad_http_requests: bool = False,
        num_retry_on_bad_http_request: int = 3,
        allow_insecure_http: bool = False,
        name: Optional[str] = None,
        url_allow_list: Optional[List[str]] = None,
        allow_credentials: bool = True,
        allow_fragments: bool = True,
        default_ports: Dict[str, int] = {"http": 80, "https": 443},
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """Initializes the api call step.

        Note
        ----

        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        **Input descriptors**

        This step has for input descriptors all the variables extracted from the ``url``, ``method``, ``data``, ``json_body``, ``params``, ``headers`` or ``cookies`` templates. See :ref:`TemplateRenderingStep <TemplateRenderingStep>` for concrete examples on how descriptors are extracted from text prompts.

        **Output descriptors**

        This step has several output descriptors:

        * ``ApiCallStep.HTTP_STATUS_CODE``: ``IntegerProperty()``, status code of the API call
        * ``ApiCallStep.HTTP_RESPONSE``: ``StringProperty()``, http response of the API call if ``store_response`` is ``True``

        It also has one output descriptor per entry in the ``output_values_json`` mapping, which are ``AnyProperty()`` extract from the json response

        The requested URL is validated and normalized before the request is executed. Normalization expects URLs containing non-Latin characters or
        underscores to be normalized to punycode, else they will be rejected during normalization.

        Parameters
        ----------
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
        output_values_json
            Interpret the response as json and extract values according to the provided dict, which contains pairs of ("key-in-io": "jq-query"),
            This will extract from the response json the value described by the "jq-query" and store it in "key-in-io".

            .. note::
                By default this is ``None``, so if ``output_values_json`` is not set and the ``store_response`` parameter is not explicitly set to ``True``,
                this step will not return anything from the response.
        store_response
            If ``True``, store the complete response in the IO system under the key ``HTTP_RESPONSE``.
            (useful for e.g. later extraction through a specialized step, or if the response does not require extraction or is not json)

            .. note::
                By default this is ``False``, so if `output_values_json` is not set and the ``store_response`` parameter is not explicitly set to ``True``,
                this step will not return anything from the response body.
        ignore_bad_http_requests
            If ``True``, don't throw an exception when query results in a bad status code (e.g. 4xx, 5xx); if ``False`` throws an exception.
        num_retry_on_bad_http_request
            Number of times to retry a failed http request before continuing (depending on the ``ignore_bad_http_requests`` setting above).
        allow_insecure_http:
            If ``True``, allows url to have a unsecured non-ssl http scheme. Default is ``False`` and throws a ValueError if url is unsecure.
        name:
            Name of the step.
        url_allow_list:
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
        input_descriptors:
            Input descriptors of the step. ``None`` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.

        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically using its static
            configuration in a best effort manner.

        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.

        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.


        Raises
        ------
        ValueError
            Thrown when both ``json_body`` and ``data`` are set.

        Examples
        --------
        >>> from wayflowcore.steps.apicallstep import ApiCallStep
        >>> from wayflowcore.property import Property, ListProperty, IntegerProperty
        >>> call_current_weather_step = ApiCallStep(
        ...     url = "https://example.com/weather",     # call the URL https://example.com/weather
        ...     method = "GET",                          # using the GET method
        ...     params = {
        ...         "location": "zurich",                # hardcode a query parameter "location" to "zurich" (will result in a GET call to https://example.com/weather?location=zurich)
        ...     },
        ...     output_values_json = {                   # from the returned JSON extract the `.weather` and `.temperature.celsius` properties and put it on the IO system under the key `weather` and `temperature`
        ...         "weather": ".weather",
        ...         "temperature_c": ".temperature.celsius"
        ...     }
        ... )
        >>>
        >>> create_order_step = ApiCallStep(
        ...     url = "https://example.com/orders/{{ order_id }}",         # call the URL https://example.com/orders/{{ order_id }}
        ...     method = "POST",                            # using the POST method
        ...     json_body = {                               # sending an object which will automatically be transformed into JSON
        ...         "topic_id": 12345,                      # define a static body parameter
        ...         "item_id": "{{ item_id }}",             # define a templated body parameter. the value for {{ item_id }} will be taken from the IO system at runtime
        ...     },
        ...     params = {
        ...         "store_id": "{{ store_id }}",          # provide one templated query parameter called "store_id" which will take it's value from the IO system from key "store_id"
        ...     },
        ...     headers = {                                # set headers
        ...         "session_id": "{{ session_id }}",      # set header session_id. the value is coming from the IO system
        ...     },
        ...     output_values_json = {                     # from the returned JSON extract the `.weather` property and put it on the IO system under the key `weather`
        ...         "first_order_status": ".orders[0].status",                                                           # more complicated query,
        ...         ListProperty(
        ...             name="order_ids",
        ...             description="List of order ids",
        ...             item_type=IntegerProperty("inner_int")
        ...         ): "[.orders[].id]",  # extract a list of values
        ...     },
        ...     url_allow_list = ["https://example.com/orders/"] # Example usage of allow_list: Domains and base path are allowed explicitely. We allow any downstream path elements (like the order id in this example) since only the beginning of the path needs to precisely match. All other URLs are rejected.
        ... )
        >>>
        >>> call_current_weather_step = ApiCallStep(
        ...     url = "https://user:pass@example.com/weather",     # call the URL https://example.com/weather
        ...     method = "GET",                          # using the GET method
        ...     params = {
        ...         "location": "zurich",                # hardcode a query parameter "location" to "zurich" (will result in a GET call to https://example.com/weather?location=zurich)
        ...     },
        ...     output_values_json = {                   # from the returned JSON extract the `.weather` and `.temperature.celsius` properties and put it on the IO system under the key `weather` and `temperature`
        ...         "weather": ".weather",
        ...         "temperature_c": ".temperature.celsius"
        ...     },
        ...     allow_credentials = False,              # in this example requests will be rejected since we explicitely dissallow credentials in the URL.
        ... )
        >>>
        >>> call_current_weather_step = ApiCallStep(
        ...     url = "https://example.com/weather#switzerland",     # call the URL https://example.com/weather
        ...     method = "GET",                          # using the GET method
        ...     params = {
        ...         "location": "zurich",                # hardcode a query parameter "location" to "zurich" (will result in a GET call to https://example.com/weather?location=zurich)
        ...     },
        ...     output_values_json = {                   # from the returned JSON extract the `.weather` and `.temperature.celsius` properties and put it on the IO system under the key `weather` and `temperature`
        ...         "weather": ".weather",
        ...         "temperature_c": ".temperature.celsius"
        ...     },
        ...     allow_fragments = False,              # in this example the requests will be rejected since we explicitely dissallow fragments in the URL.
        ... )
        >>>
        """
        super().__init__(
            step_static_configuration=dict(
                url=url,
                method=method,
                json_body=json_body,
                data=data,
                params=params,
                headers=headers,
                cookies=cookies,
                output_values_json=output_values_json,
                store_response=store_response,
                ignore_bad_http_requests=ignore_bad_http_requests,
                num_retry_on_bad_http_request=num_retry_on_bad_http_request,
                allow_insecure_http=allow_insecure_http,
                url_allow_list=url_allow_list,
                allow_credentials=allow_credentials,
                allow_fragments=allow_fragments,
                default_ports=default_ports,
            ),
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )

        self.url = url

        if allow_insecure_http:
            warnings.warn(
                "Usage of non-encrypted requests to http urls is considered unsecure and strongly discouraged. "
                "This warning is generated because you defined allow_insecure_http=True."
                "Consider setting allow_insecure_http=False or continue on your own discretion.",
                category=UserWarning,
            )
        if not allow_insecure_http and urlparse(self.url).scheme == "http":
            raise ValueError("usage of unsecure http URL is not allowed")

        self.method = method
        self.json_body = json_body
        self.data = data
        self.params = params
        self.headers = headers
        self.cookies = cookies
        self.output_values_json = output_values_json

        if output_values_json:
            self.jq_processors = {
                (
                    output_descr.name if isinstance(output_descr, Property) else output_descr
                ): jq.compile(output_query)
                for output_descr, output_query in output_values_json.items()
            }
        self.store_response = store_response
        self.ignore_bad_http_requests = ignore_bad_http_requests
        self.num_retry_on_bad_http_request = num_retry_on_bad_http_request
        self.allow_insecure_http = allow_insecure_http
        self.url_allow_list = None
        if url_allow_list is not None:
            self.url_allow_list = list(
                set(
                    _normalize_allow_list(
                        url_allow_list, allow_credentials, allow_fragments, default_ports
                    )
                )
            )
        self.allow_credentials = allow_credentials
        self.allow_fragments = allow_fragments
        self.default_ports = default_ports

        if self.json_body and self.data:
            raise ValueError("Cannot set json_body and data at the same time")

    def _render_url(self, inputs: Dict[str, Any]) -> str:

        def sanitize_url_param(param: Any) -> str:
            if isinstance(param, str):
                return quote_plus(param)
            elif isinstance(param, int) or isinstance(param, float) or isinstance(param, bool):
                return str(param)
            else:
                raise ValueError(f"cannot use param of type {type(param)} in URL")

        variables = set(get_variable_names_from_object(self.url))
        if len(variables) == 0:
            return self.url

        sanitized_inputs = {
            key: sanitize_url_param(value) for key, value in inputs.items() if key in variables
        }

        return render_str_template(template=self.url, inputs=sanitized_inputs)

    def _prepare_request(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "url": self._render_url(inputs),
            "method": render_str_template(self.method, inputs),
        }
        request["headers"] = {}  # for type inference

        if self.json_body:
            if isinstance(self.json_body, str):
                request["headers"]["Content-type"] = "application/json"
                rendered_json_string = render_nested_object_template(self.json_body, inputs)
                # validate we generated valid json
                json.loads(rendered_json_string)
                request["data"] = render_nested_object_template(self.json_body, inputs).encode()
            else:
                request["json"] = render_nested_object_template(self.json_body, inputs)

        if self.data:
            rendered_data = render_nested_object_template(self.data, inputs)
            if isinstance(rendered_data, str):
                rendered_data = rendered_data.encode()
            request["data"] = rendered_data

        if self.params:
            request["params"] = render_nested_object_template(self.params, inputs)

        if self.headers:
            request["headers"].update(render_nested_object_template(self.headers, inputs))

        if self.cookies:
            request["cookies"] = render_nested_object_template(self.cookies, inputs)

        # remove headers entry if we haven't set anything
        if len(request["headers"]) == 0:
            del request["headers"]

        return request

    async def _execute_request(self, request: Dict[str, Any]) -> httpx.Response:
        if not self.allow_insecure_http and urlparse(request["url"]).scheme == "http":
            raise ValueError("usage of unsecure http URL is not allowed")
        # If URL is not valid a ValidationError will be thrown
        _ = AnyUrl(request["url"])

        parsed_url = _normalize_parse_url(
            request["url"],
            allow_credentials=self.allow_credentials,
            allow_fragments=self.allow_fragments,
            default_ports=self.default_ports,
        )
        if not parsed_url:
            raise ValueError("An error occurred when normalizing the URL.")

        if self.url_allow_list is not None:
            match_results = [
                _is_allowed_url(parsed_url, pattern) for pattern in self.url_allow_list
            ]

            if not any(match_results):
                raise ValueError(
                    f"Requested URL is not in allowed list.\
                                   Please contact the application adminstrator to help adding your URL to the list."
                )

        if self.num_retry_on_bad_http_request == 0:
            return httpx.request(**request)

        request_counter = 0
        while request_counter < self.num_retry_on_bad_http_request:
            request_counter += 1
            async with httpx.AsyncClient() as client:
                response = await client.request(**request)
                if response.is_success:
                    return response

        return response

    async def _invoke_step_async(
        self, inputs: Dict[str, Any], conversation: "FlowConversation"
    ) -> StepResult:
        request = self._prepare_request(inputs)
        response = await self._execute_request(request)

        if not self.ignore_bad_http_requests and not response.is_success:
            raise RuntimeError(
                f"error executing {self.method} request to {self.url}: {response.status_code}, {response.content.decode(errors='replace')}"
            )

        output_values = {}

        if self.output_values_json:
            response_value = response.json()
            for output_key, query in self.jq_processors.items():
                output_values[output_key] = query.input_value(response_value).first()

        if self.store_response:
            # TODO this assumes the api will return strings and that it's utf8 encoded -- if we want to support binary apis we need to change here
            output_values[ApiCallStep.HTTP_RESPONSE] = response.content.decode(errors="replace")

        output_values[ApiCallStep.HTTP_STATUS_CODE] = response.status_code

        return StepResult(
            outputs=output_values,
        )

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        return dict(
            url=str,
            method=str,
            json_body=Optional[Dict[str, str]],  # type: ignore
            data=Optional[str],  # type: ignore
            params=Optional[Dict[str, str]],  # type: ignore
            headers=Optional[Dict[str, str]],  # type: ignore
            cookies=Optional[Dict[str, str]],  # type: ignore
            # TODO: support keys being Property
            output_values_json=Optional[Dict[str, str]],  # type: ignore
            store_response=bool,
            ignore_bad_http_requests=bool,
            num_retry_on_bad_http_request=int,
            allow_insecure_http=bool,
            url_allow_list=Optional[List[str]],  # type: ignore
            allow_credentials=bool,
            allow_fragments=bool,
            default_ports=Dict[str, str],
        )

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        url: str,
        method: str,
        data: Optional[Union[Dict[Any, Any], List[Tuple[Any, Any]], str, bytes]],
        json_body: Optional[Any],
        params: Optional[Union[Dict[Any, Any], List[Tuple[Any, Any]], str, bytes]],
        headers: Optional[Dict[str, str]],
        cookies: Optional[Dict[str, str]],
        **kwargs: Dict[str, Any],
    ) -> List[Property]:
        return [
            StringProperty(
                name=variable,
                description=f"string template variable named {variable}",
            )
            for variable in get_variable_names_from_object(
                [url, method, data, json_body, params, headers, cookies]
            )
        ]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        output_values_json: Optional[Dict[Union[str, Property], str]],
        store_response: Optional[bool],
        **kwargs: Dict[str, Any],
    ) -> List[Property]:
        output_descriptors: List[Property] = [
            IntegerProperty(
                name=ApiCallStep.HTTP_STATUS_CODE,
                description="returned http status code",
            )
        ]

        if output_values_json:
            output_descriptors += [
                string_to_property(output_value) for output_value in output_values_json.keys()
            ]

        if store_response:
            output_descriptors.append(
                StringProperty(
                    name=ApiCallStep.HTTP_RESPONSE,
                    description="raw http response",
                )
            )

        return output_descriptors
