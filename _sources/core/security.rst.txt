Security Considerations
=======================

Scope: WayFlow Agents, Flows, Steps, or Tools in any environment (development, staging, production).

Why it matters: WayFlow integrates LLMs, Python, tools, and APIs. Its attack surface spans all Steps, Agents, Flows, Tools, and Context Providers. A single untrusted component (e.g., an unsafe tool or poorly-scoped ``ContextProvider``) can compromise the entire runtime.

Considerations regarding tools
-------------------------------

WayFlow allows LLMs to interact with applications via **Tools** (:ref:`ClientTool <clienttool>`, :ref:`ServerTool <servertool>`, or :ref:`RemoteTool <remotetool>`), granting access to state or operations. Since tool inputs often come from LLMs or users, rigorous input sanitization and validation are crucial.

**Key Principles for Tool Security:**

*   **Mandatory Input Validation**: Always validate tool inputs.

    *   For :ref:`ClientTool <clienttool>` and :ref:`ServerTool <servertool>`, use ``input_descriptors`` to define/enforce schemas (types and descriptions) as a primary defense. Note that ``input_descriptors`` do not support constraints like ranges or max lengths, so you must implement additional validation in your tool's code.
    *   For :ref:`RemoteTool <remotetool>`, which constructs HTTP requests, validation is critical for all parameters that can be templated (e.g., ``url``, ``method``, ``json_body``, ``data``, ``params``, ``headers``, ``cookies``). While ``input_descriptors`` can define the schema for arguments *passed to* the :ref:`RemoteTool <remotetool>`, the core security lies in controlling how these arguments are used to form the request and in features like ``url_allow_list``.
*   **Output Scrutiny**: Define expected outputs with ``output_descriptors``. For :ref:`ClientTool <clienttool>`, clients post results; for :ref:`ServerTool <servertool>`, the server ``func`` generates them. Calling Flows/Agents must treat incoming :ref:`ToolResult <toolresult>` content as untrusted until validated/sanitized.
*   **Least Privilege**: Grant tools only permissions essential for their function.

Tool Security Specifics
~~~~~~~~~~~~~~~~~~~~~~~

.. important::

   Rigorously sanitize all tool inputs. Tools, bridging LLM understanding with system operations, are prime targets. Validate types, lengths, and semantic correctness before core logic execution.

**`ServerTool` Considerations:**

*   **Callable Security (`func`)**: The ``func`` callable in :ref:`ServerTool <servertool>` is the primary security concern. Harden this server-executed code against vulnerabilities.
*   **Isolation for High-Risk Tools**: Run high-risk :ref:`ServerTool <servertool>` instances (e.g., with elevated permissions, network/filesystem access) in sandboxed environments (containers/pods) with minimal IAM roles. Deny network/filesystem writes unless essential.
*   **Tools from `Flows` or `Steps`**:

    *   When creating a :ref:`ServerTool <servertool>` via :meth:`.Flow.from_flow`, or :meth:`.Flow.from_step`, its security is inherited. Ensure source ``Flow`` or ``Step`` tools are secure.

**`ClientTool` Considerations:**

*   **Client-Side Execution**: :ref:`ClientTool <clienttool>` execution occurs on the client. Client environment security, though outside WayFlow's control, impacts overall application security.
*   **Untrusted `ToolRequest`**: Clients receive a :ref:`ToolRequest <toolrequest>`. Though WayFlow generates ``name`` and ``tool_request_id``, client code must parse ``args`` with a strict schema, avoiding direct use in shell commands or sensitive OS functions.
*   **Untrusted Client `ToolResult`**: Server-side WayFlow components must treat :ref:`ToolResult <toolresult>` from clients as untrusted. Validate its ``content`` before processing.

**`RemoteTool` Considerations:**

*   **Templated Request Arguments**: :ref:`RemoteTool <remotetool>` allows various parts of the HTTP request (URL, method, body, headers, etc.) to be templated using Jinja. This is powerful but introduces risks if the inputs to these templates are not strictly controlled. Maliciously crafted inputs could lead to information leakage (e.g., exposing sensitive data in URLs or headers) or enable attacks like SSRF (Server-Side Request Forgery) or automated DDoS.
*   **URL Allow List (`url_allow_list`)**: This is a critical security feature. Always define a ``url_allow_list`` to restrict the tool to a predefined set of allowed URLs or URL patterns. This significantly mitigates the risk of the tool being used to make requests to unintended or malicious endpoints. Refer to the API documentation for detailed matching rules.
*   **Secure Connections (`allow_insecure_http`)**: By default, :ref:`RemoteTool <remotetool>` disallows non-HTTPS URLs (``allow_insecure_http=False``). Maintain this default unless there's an explicit, well-justified reason to allow insecure HTTP, and ensure the risks are understood.
*   **Credential Handling (`allow_credentials`)**: By default (``allow_credentials=True``), URLs can contain credentials (e.g., ``https://user:pass@example.com``). If your use case does not require this, set ``allow_credentials=False`` to prevent accidental leakage or misuse of credentials in URLs.
*   **URL Fragments (`allow_fragments`)**: Control whether URL fragments (e.g., ``#section``) are permitted in requested URLs and allow list entries. Default is ``True``. Set to ``False`` if fragments are not needed and could introduce ambiguity or bypass attempts.
*   **Output Parsing (`output_jq_query`)**: If using ``output_jq_query`` to parse JSON responses, be aware that complex queries on very large or maliciously structured JSON could consume significant resources. While primarily a performance concern, extreme cases might have denial-of-service implications.

.. caution::

   As highlighted in the :ref:`RemoteTool <remotetool>` API, since the Agent can generate arguments
   (url, method, json_body, data, params, headers, cookies) or parts of these arguments in the respective
   Jinja templates, this can impose a security risk of information leakage and enable specific attack
   vectors like automated DDOS attacks. Please use :ref:`RemoteTool <remotetool>` responsibly and ensure
   that only valid URLs can be given as arguments or that no sensitive information is used for any of these
   arguments by the agent. Utilize ``url_allow_list``, ``allow_credentials``, and ``allow_fragments``
   to control URL validity.

Harden All Tools (ServerTool, ClientTool and RemoteTool)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table:: Tool Hardening Guidelines
   :widths: 30 70
   :header-rows: 1

   * - Risk
     - Guidance
   * - Unvalidated arguments (leading to injection, DoS, etc.)
     - **Primary Defense**:

       *  For :ref:`ClientTool <clienttool>` & :ref:`ServerTool <servertool>`: Use ``input_descriptors`` for basic type checking. In :ref:`ServerTool <servertool>`'s ``func``, add comprehensive validation (string length limits, numeric ranges, format constraints). Cap string lengths and numeric ranges in tool implementation code.
       *  For :ref:`RemoteTool <remotetool>`:

          *  Rigorously validate and sanitize any inputs used in templated arguments (``url``, ``method``, ``json_body``, ``data``, ``params``, ``headers``, ``cookies``).
          *  **Crucially, always configure `url_allow_list`** to restrict outbound requests to known, trusted endpoints.
          *  Leverage ``allow_insecure_http=False`` (default), and consider setting ``allow_credentials=False`` if not needed.
   * - Excessive privileges (for :ref:`ServerTool <servertool>`)
     - Run in least-privilege containers/pods.

       Separate network namespaces for sensitive data/external system access.

       Explicitly deny unnecessary filesystem/network access.
   * - Stateful tools
     - Prefer stateless tools. If stateful, use hardened datastores (e.g., Oracle Database) over in-memory objects where feasible.

       Implement optimistic locking and rigorous input sanitization for state-modifying operations.
   * - :ref:`ClientTool <clienttool>` misuse (client-side vulnerabilities)
     - Client apps handling :ref:`ToolRequest <toolrequest>` must treat ``args`` as untrusted.

       Validate/sanitize client-side `args` before local execution (esp. OS commands, sensitive API calls).
   * - Insecure underlying components (for tools from Flows, Steps)
     - Ensure source Flows or Steps tools for WayFlow :ref:`ServerTool <servertool>` are vetted; the tool inherits their security.
   * - Data leakage via :ref:`ToolResult <toolresult>`
     - Define ``output_descriptors`` clearly.

       Ensure :ref:`ServerTool <servertool>` ``func`` and :ref:`ClientTool <clienttool>` client code return only necessary data.

       Consuming Agent/Flow must validate/sanitize :ref:`ToolResult <toolresult>` `content`.


Considerations regarding network communication
----------------------------------------------

WayFlow components use the network for LLM communications, :ref:`ApiCallStep <apicallstep>` tool operations, and third-party integrations. Implement robust network security.

.. important::

   Adopt a defense-in-depth network security strategy for WayFlow, including supply-chain security for models/containers, network segmentation, encrypted communications, and strict egress controls.

Supply-Chain Security for WayFlow Assets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Model Integrity**: For third-party models used by WayFlow (fine-tuned, embeddings):
    * Download via HTTPS, pin SHA-256 digests and verify integrity before loading into WayFlow.
* **Container Security**: For containerized WayFlow:
    * Use minimal, regularly updated base images. Scan images (e.g., Trivy, Grype) for CVE. Sign (e.g., before pushing to a package index) and verify (e.g., when downloading) images.

Network Segmentation for WayFlow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Isolate WayFlow components to limit blast radius:

* **Subnet Isolation**:
    * LLM hosts (OCI Gen AI, vLLM) in dedicated subnets.
    * Tool backends and :ref:`ApiCallStep <apicallstep>` targets in isolated subnets.
    * Keep the WayFlow *control-flow* logic (e.g., Agents, Flows, BranchingSteps) separate from data processing (e.g., database mutations, data analytics)
* **TLS**:
    * Use mTLS for WayFlow service-to-service communications such as connecting to MCP servers, Monitoring/Telemetry services, File Storage Services, Databases, and so on.

Egress Controls for WayFlow Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Strict Egress Rules**: Default-deny outbound traffic:
    * Allow only Allow-Listed domains/IPs for WayFlow components (such as when using Tools like :ref:`RemoteTool <remotetool>` with its ``url_allow_list`` parameter, :ref:`ApiCallStep <apicallstep>`, or :ref:`PromptExecutionStep <promptexecutionstep>`)
* **Centralized Allow-Lists for WayFlow**:
    * LLM provider endpoints and Telemetry/logging destinations.
    * Approved Tool API endpoints for tools making external calls, such as :ref:`ApiCallStep <apicallstep>` and :ref:`RemoteTool <remotetool>` (enforced via its ``url_allow_list`` parameter).
    * Make sure to set up alert on policy violations.

Network Connection Requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table:: WayFlow Network Security: Key Implementations
   :widths: 40 60
   :header-rows: 1

   * - Area
     - WayFlow-Specific Implementation
   * - External LLM Traffic Encryption
     - • OCI Gen AI: HTTPS by default.

       • vLLM: Front with TLS terminator (Nginx/Caddy) or use mTLS ingress.

       • Verify TLS certs; pin where feasible.
   * - WayFlow Component Egress Rules
     - • Container network policies (iptables, Calico, Cilium) allowing only approved LLM endpoints, Tool API destinations, telemetry sinks, and DNS.
   * - External API Call Security (e.g., :ref:`ApiCallStep <apicallstep>`, :ref:`RemoteTool <remotetool>`)
     - • Enforce HTTPS: Use ``allow_insecure_http=False`` (default for both).
       • **URL Allow Lists**: For :ref:`RemoteTool <remotetool>`, always configure its ``url_allow_list`` parameter. For :ref:`ApiCallStep <apicallstep>`, ensure broader network-level allow-lists are in place.
       • Validate/sanitize templated URLs and other request parameters (headers, body) derived from potentially untrusted inputs.
       • Consider ``allow_credentials=False`` and ``allow_fragments=False`` for :ref:`RemoteTool <remotetool>` if those features are not strictly necessary.
       • Use connection timeouts/rate limiting (tool-specific or via infrastructure).
       • Log outbound requests (destination URLs, sanitized headers/bodies) for audit.
   * - Data Residency
     - • Ensure LLM providers meet data residency needs.
       • Use regional LLM endpoints for data locality with WayFlow.
   * - Network Monitoring & Alerting
     - • Maintain allow-list of approved hostnames and IPs for WayFlow traffic.

       • Alert on policy violations/unauthorized connection attempts from WayFlow components.


Considerations regarding API keys and secrets management
--------------------------------------------------------

Secure API key/secret management is critical for WayFlow deployments (LLM providers, external services, internal auth) to prevent unauthorized access and data breaches.

.. important::

   Never embed API keys, passwords, or other secrets directly in code, configuration files, or serialized JSON/YAML. Always use secure injection mechanisms and follow the principle of least privilege for credential access.

Control Secret Sprawl
~~~~~~~~~~~~~~~~~~~~~

Prevent hardcoded secrets in WayFlow:

* **Runtime injection for WayFlow required secrets (e.g., LLM API key or database credentials)**:

  * Avoid using Kubernetes/Docker secrets to deploy environment variables.
  * Use secrets managers (e.g., OCI Vault).
* **Avoid Baked Secrets in WayFlow**:

  * Never put API keys in WayFlow's serialized JSON/YAML.
  * Exclude secrets from Python source shown to LLMs during WayFlow development.
  * Use placeholders in version-controlled WayFlow configs.
  * Use pre-commit hooks to prevent committing secrets to source control.
* **Per-Flow Service Accounts & Rotation**:

  * Use dedicated service accounts per WayFlow Flow.
  * Rotate API keys regularly.
  * Automate key rotation if possible.
  * Monitor/audit credential use.

LLM Provider Authentication Security
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**OpenAI Models (`OpenAIModel`):**

* Injecting a Secret as an environment variable makes the value available to everything inside the Pod.
* We recommend exploring alternatives to sourcing the ``OPENAI_API_KEY`` env variable at runtime.
* Use organization-specific API keys with usage limits.
* Monitor :ref:`TokenUsage <tokenusage>` for anomaly detection.
* Secure proxy credentials separately for VPN proxies.

**OCI GenAI Models (`OCIGenAIModel`):**

* **Instance Principal** (:ref:`OCIClientConfigWithInstancePrincipal <ociclientconfigwithinstanceprincipal>`): Preferred for OCI Compute (no stored credentials).
* **API Key** (:ref:`OCIClientConfigWithApiKey <ociclientconfigwithapikey>`): Store private keys in key management; protect ``~/.oci/config`` (permissions 600).
* **User Authentication** (:ref:`OCIClientConfigWithUserAuthentication <ociclientconfigwithuserauthentication>`): Never log ``key_content``.

**vLLM Models (`VllmModel`):**

* Use internal DNS names and private networking
* Implement authentication at reverse proxy level


Credential Rotation and Monitoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Rotation**: Rotate WayFlow credentials regularly.
* **Monitoring**: Track WayFlow's :ref:`TokenUsage <tokenusage>` for anomalies.
* **Incident Response**: Have procedures to revoke compromised WayFlow credentials.

Considerations regarding Resource-exhaustion vectors
----------------------------------------------------

Resource-exhaustion events may stem from hostile over-use or from innocent implementation mistakes (e.g., unbounded loops, forgotten awaits), so interrupts should be viewed as guardrails against both abuse and developer error.
WayFlow provides two **soft execution-interrupts**, but they don't cover all vectors. This section details their use, limitations, and additional production hardening techniques.

Built-in execution interrupts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Class
     - Purpose / behaviour
   * - :ref:`SoftTimeoutExecutionInterrupt <softtimeoutexecutioninterrupt>`
     - Stops the assistant **after** a configurable wall-clock duration (default 10 min).

       • *Soft* → it *waits* until the current Step or FlowExecutionStep returns; it **cannot** pre-empt a long-running Tool call or LLM generation.
   * - :ref:`SoftTokenLimitExecutionInterrupt <softtokenlimitexecutioninterrupt>`
     - Aborts execution once an LLM (or group of LLMs) has emitted a specified number of tokens.

       • *Soft* → the check happens between steps; generation already in flight finishes first.

Usage example
~~~~~~~~~~~~~

.. code-block:: python

   from wayflowcore.agent import Agent
   from wayflowcore.executors.interrupts.timeoutexecutioninterrupt import SoftTimeoutExecutionInterrupt
   from wayflowcore.executors.interrupts.tokenlimitexecutioninterrupt import SoftTokenLimitExecutionInterrupt

   timeout_int   = SoftTimeoutExecutionInterrupt(timeout=30)          # 30 s max
   token_int     = SoftTokenLimitExecutionInterrupt(total_tokens=500) # 500 tokens
   status = conversation.execute(execution_interrupts=[timeout_int, token_int])


Gaps in coverage (what is **not** provided)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Memory limits** – no built-in interrupt for resident-set or GPU VRAM.
* **CPU / thread quotas** – Python loops can still hog a core until the Step returns.
* **Hard timeouts** inside a Tool – a Tool that calls a REST API may block indefinitely.
* **Concurrent-request ceilings** – ``MapStep(parallel_execution=True)`` fans-out one sub-flow (or Tool call) per element in the input list. Because there is no internal throttle, nothing stops 1000 parallel MapStep forks (possibly leading to CPU thrashing or OOM-kill) without your own semaphore.
* **LLM generation cancellation** – once a prompt is sent, the soft timeout waits for the model to answer.

Recommended hardening layers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. rubric:: OS / Container level

* **Resource Limits (cgroups/Kubernetes)** for WayFlow containers:
  Set CPU/memory requests and limits to prevent resource starvation by WayFlow processes.
  Example:
  ::

     resources:
       requests: { cpu: "500m", memory: "512Mi" }
       limits:   { cpu: "1",   memory: "1Gi" }

.. rubric:: Application level

* **Per-Tool timeouts**

  For WayFlow Tools involving long-running I/O, wrap calls in ``concurrent.futures.wait`` or ``subprocess.run`` with a ``timeout``. Raise a retryable error for the Flow.

* **Concurrency guard**

  For WayFlow's :ref:`MapStep <mapstep>` or similar fan-out patterns:

  .. code-block:: python

     from asyncio import Semaphore
     # Limit concurrent operations in a MapStep
     guard = Semaphore(value=16)

* **Input size validation**

  Limit list lengths, string sizes, and recursion depth for data fed into WayFlow's :ref:`MapStep <mapstep>` or recursive Agents to prevent exponential resource use.

* **Circuit-breaker patterns**

  For WayFlow interactions with LLMs or Tools, implement circuit breakers to trip after *n* failures/SLA breaches, returning a graceful error. Consider following code block for conceptual direction:

  .. code-block:: python

     from pybreaker import CircuitBreaker
     from wayflowcore.tools import tool, ToolExecutionStep
     from requests import get, RequestException

     # ❶ create a breaker: 5 failures trip; reset after 60 s
     api_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)

     @tool
     def robust_get(url: str) -> str:
         """GET url with breaker; raises CircuitBreakerError if OPEN"""
         try:
             with api_breaker:
                 resp = get(url, timeout=3)
                 resp.raise_for_status()
                 return resp.text
         except RequestException as e:
             # will count as a failure inside the breaker
             raise RuntimeError(f"downstream error: {e}") from e

     step = ToolExecutionStep(robust_get)          # use in a Flow

.. rubric:: LLM usage governance

* Combine WayFlow's ``SoftTokenLimitExecutionInterrupt`` with server-side LLM provider usage quotas (e.g., OpenAI hard limits, vLLM rate-limiting).


Considerations regarding input validation and sanitation
--------------------------------------------------------

WayFlow has no built-in input validation/sanitation. Developers are responsible for securing user inputs via validation, sanitation, and external guardrails.

.. important::

   All user-provided inputs—whether from chat interfaces, API payloads, or Tool arguments—should be treated as potentially malicious and require rigorous validation and sanitation before processing.

Core Input Security Requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Validation and Bounds Checking:**

* Validate length/structure of all inputs to WayFlow (chat, API, Tool arguments).
* Enforce max length limits on user inputs to WayFlow.
* Validate formats/types before passing to WayFlow components.
* Check inputs are within reasonable bounds for the WayFlow application.
* Use ``output_descriptors`` on :ref:`PromptExecutionStep <promptexecutionstep>` for JSON schemas to reduce prompt-injection leakage.


**External Guardrails Integration:**

WayFlow applications should leverage external security services to provide comprehensive input protection:

* **OCI Gen AI Inference Protection**: Built-in guardrails (toxicity, prompt-injection, jailbreak scanning) per Responsible AI.
* **Custom filtering for WayFlow**: Use regex/policy filters with open-source models in WayFlow.
* **LLM DevSecOps**: Apply `LLM DevSecOps guide <https://devsecopsguides.com/docs/rules/llm/>`_ practices to WayFlow development.

**Architectural Patterns for Input Security:**

* **Early filtering**: Insert a :ref:`BranchingStep <branchingstep>` at Flow start to route "unsafe" content to a refuse/retry branch.
* **Defense in depth**: Layer multiple validation/sanitation for WayFlow inputs.
* **Fail-safe defaults**: Reject ambiguous/malformed inputs to WayFlow.

Considerations regarding logging
--------------------------------

Error handling & exception hygiene
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Robust error handling is key for WayFlow stability and security.

*   **Custom WayFlow Steps**: Implement comprehensive error handling. Map exceptions to sanitized messages, avoiding internal detail leakage.
*   **`CatchExceptionStep`**: Configure to prevent stack trace/sensitive debug info leakage in user errors.
*   **Private Debug Logging**: Log full exception traces for WayFlow errors privately for debugging, while sanitizing user-facing messages.

Audit & observability
~~~~~~~~~~~~~~~~~~~~~

Comprehensive auditing/observability is vital for WayFlow.

*   **Structured Logs for WayFlow Events**: Log key WayFlow operations at ``INFO`` level:

    *   ``conversation_id``: Trace interaction lifecycle.
    *   ``step_name``: Executed WayFlow Step.
    *   ``input_hash``: Hash of Step/Tool input (avoid raw sensitive input).
    *   ``output_hash``: Hash of Step/Tool output.
    *   ``tool_name``: Called Tool.
*   **Tamper-Evident Log Storage for WayFlow**: Use secure, append-only storage for WayFlow logs.
*   **PII Scrubbing in WayFlow Logs**: Mask/redact/tokenize PII in WayFlow logs/traces before persistence for privacy compliance (GDPR, right to be forgotten). It may be beneficial to use frameworks for detecting, redacting, masking, and anonymizing sensitive data (PII) such as `Presidio <https://github.com/microsoft/presidio>`_

Considerations regarding Telemetry & observability
--------------------------------------------------

WayFlow can emit rich execution traces—**Spans**—that describe every
tool call, LLM invocation, and Step transition inside an Agent or Flow.
These traces are invaluable for debugging and performance tuning, **but
they may also contain sensitive data**.

1.  What's in a Span?
~~~~~~~~~~~~~~~~~~~~~

* Flow / Agent configuration snapshot
* Sequence of executed Steps (timestamps, duration)
* Input / output payloads, including user prompts and Tool arguments
* Status transitions and exception details

2.  Default behaviour
~~~~~~~~~~~~~~~~~~~~~

WayFlow sends **no traces by default**.
To enable exporting you must supply a custom
:ref:`SpanExporter <spanexporter>`.

.. danger::
   Raw Spans can expose PII, secrets, or proprietary model prompts. PII/secrets must be removed/hashed from logs/metrics.

3.  Implementing a SpanExporter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from wayflowcore.tracing.spanexporter import SpanExporter
   from wayflowcore.tracing.span import Span
   import asyncio, aiohttp

   class AsyncHTTPSExporter(SpanExporter):
       async def _send(self, span: Span) -> None:
           payload = sanitize(span)           # e.g., redact secrets here
           async with aiohttp.ClientSession() as s:
               await s.post("https://trace.local/ingest", json=payload, timeout=3)

       def export(self, span: Span) -> None:
           asyncio.create_task(self._send(span))   # non-blocking

Key points:

* **Async / non-blocking** - keep the exporter off the critical path.
* **Robust error handling** - never raise from ``export``; drop or queue on
  failure.
* **Back-pressure** - apply rate limits or batch Spans to avoid DoS on the
  collector.

4.  SpanProcessor guidance
~~~~~~~~~~~~~~~~~~~~~~~~~~

When you add a custom :ref:`SpanProcessor <spanprocessor>`:

* Apply sampling early to reduce volume.
* Use bounded queues to cap memory.
* Log (INFO) when Spans are dropped due to back-pressure.


Considerations regarding UI rendering
-------------------------------------

WayFlow uses **Jinja 2** for templates in core components like:

* :ref:`TemplateRenderingStep <templaterenderingstep>`
* :ref:`OutputMessageStep <outputmessagestep>`
* :ref:`ContextProvider <contextprovider>`-driven templates interpolating values into messages

Jinja 2's automatic HTML-escaping is **disabled by design** in WayFlow to:

* deliver prompt text to LLMs without foreign escape sequences, and
* prevent mangling of deliberately model-generated HTML tags.

This preserves model fidelity/latency but removes default XSS/code-injection safeguards.

.. important::

   **Never render the raw output of a WayFlow step directly to a browser.**
   Treat every ``step.<OUTPUT>`` or ``Message.content`` string as *untrusted*
   and sanitise or escape it before display. Failure to do so can lead to
   HTML/JS injection (stored XSS) where malicious scripts sent in chat can be
   executed by the browser if auto-escaping is off.

Recommended mitigations
~~~~~~~~~~~~~~~~~~~~~~~

#. **Segregate rendering responsibilities**

   * Use WayFlow only for *data generation*.
   * Delegate structured text generation (e.g., HTML, XML, Markdown, SQL) to a
     dedicated renderer that offers context-aware auto-escaping.

#. **Sanitise any LLM or user-supplied markup**

   For example, to sanitise HTML:

   .. code-block:: python

      import bleach

      safe_html = bleach.clean(
          raw_wayflow_output,
          tags=["b", "i", "u", "br", "p"],   # whitelisted tags
          attributes={},
          strip=True
      )

   Similar libraries exist for other markup languages.

#. **Adopt strict content policies**

   Where the rendering context provides it (e.g., web browsers), enforce a
   strict Content-Security-Policy to mitigate the risk of unsanitised content
   executing. For other contexts (e.g., generating code), ensure the output is
   treated as data and never directly executed.

#. **Use an “escape hatch” for deliberate rich content**

   If you *need* the LLM to emit rich content (e.g., HTML e-mails, reports),
   treat it as a download-only artifact where possible. If it must be
   displayed, use a sandboxed environment (like an ``<iframe>``) to isolate it
   from the main application.

#. **Audit TemplateRenderingStep usage**

   * Maintain a code-search pattern for ``TemplateRenderingStep(..., template=)``.
   * Review every instance to ensure it is not piped straight to a renderer without escaping.


Extended API-specific guidance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **`OutputMessageStep`**

  This class returns strings and performs *no* escaping. When its output is propagated to a web front-end (often via ``DataFlowEdge → OutputMessageStep.OUTPUT``), apply HTML escaping there.

* **`MessageList` / `ChatHistoryContextProvider`**

  Chat histories can contain user HTML. If displaying transcripts, pipe the history through the same sanitiser used for new LLM outputs.

* **`ServerTool` results**

  :ref:`ServerTool <servertool>` instances may return Markdown or HTML. Mark the result type explicitly (e.g., ``text/plain`` vs ``text/markdown``) and render with a Markdown library that sanitises HTML by default (e.g., ``markdown-it-py`` with ``linkify=False``).


Considerations regarding assistant/flow serialization
-----------------------------------------------------

WayFlow components inheriting from :ref:`SerializableObject <serializableobject>` can be converted to/from a dictionary representation (typically YAML) using :ref:`serialize <serialize>`.

Serialized JSON of assistants/flows are computational programs. **Executing deserialized objects is like executing code.** Ensuring integrity/authenticity before deserialization is key to prevent Arbitrary Code Execution (ACE).


Secure Deserialization Practices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Deserializing data from untrusted sources is inherently risky. Always treat serialized WayFlow objects from external or unverified origins as potentially malicious.

1.  **Verify Data Integrity and Authenticity**:
    Before attempting to deserialize, ensure the JSON/YAML data comes from a trusted source and has not been tampered with. Implement mechanisms such as digital signatures to verify the origin and integrity of the serialized data.

2.  **Choose JSON over YAML**:
    When serializing data, JSON if preferred over YAML as YAML presents the risk unsafe deserialization allowing remote code execution.

3.  **Use Safe Loading if using YAML**:
    The YAML data itself should be parsed safely before passing it to WayFlow's deserialization functions. Always use ``yaml.safe_load()`` from the PyYAML library instead of ``yaml.load()`` to prevent the execution of arbitrary Python code embedded within the YAML structure itself.

4.  **Controlled Deserialization Context**:
    While :ref:`autodeserialize <autodeserialize>` accepts a ``deserialization_context``, ensure a reused context doesn't carry over state from a prior untrusted deserialization that could be exploited.

**Example of a safer deserialization pipeline:**

.. code-block:: python

  from yaml import safe_load # Crucially, use safe_load, not load
  from wayflowcore.serialization.serializer import autodeserialize
  # Assume verify_signature_and_integrity is a custom function you've implemented
  # to check the signature against the raw_yaml_string and a trusted key.
  # This step is conceptual and depends on your specific trust model.

  raw_yaml_string, signature = get_potentially_untrusted_yaml_and_signature()
  is_trusted_source = verify_signature_and_integrity(raw_yaml_string, signature)

  if is_trusted_source:
      # First, safely parse the YAML string to a Python object structure
      parsed_yaml_object = safe_load(raw_yaml_string)
      # Then, deserialize the WayFlow object using autodeserialize
      if isinstance(parsed_yaml_object, dict):
          assistant_or_flow = autodeserialize(parsed_yaml_object)

Remember that :ref:`autodeserialize <autodeserialize>` expects parsed YAML (a Python dictionary), not the raw YAML string, if using ``safe_load``. Passing a string directly to ``autodeserialize`` makes it use ``yaml.safe_load`` internally. Explicit ``safe_load`` first allows pre-validation of the YAML structure.


Other Security Concerns
-----------------------

For any other security concerns, please submit a `GitHub issue <https://github.com/oracle/wayflow/issues>`_.
