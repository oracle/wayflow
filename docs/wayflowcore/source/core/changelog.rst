Changelog
=========

WayFlow 26.1.0
--------------

New features
^^^^^^^^^^^^

* **Agent Spec Tracing support:**

  Open Agent Specification Tracing (short: Agent Spec Tracing) is an extension of
  Agent Spec that standardizes how agent and flow executions emit traces.
  Wayflow now supports the emission of traces according to the Agent Spec Tracing standard.

  For more information read the guide on :doc:`How to Enable Tracing in WayFlow <howtoguides/howto_tracing>`.

* **WayFlow Plugins:**

  Wayflow plugins allow users extending existing components (like Tools, Steps, etc.), or even creating
  new ones, and seamlessly integrate them in WayFlow and Agent Spec serialization and deserialization. For more information read the guide on :doc:`how to use WayFlow plugins <howtoguides/howto_plugins>`.

* **OpenAI Responses API Support:**

  :ref:`OpenAICompatibleModel<openaicompatiblemodel>` now supports OpenAI Responses API, which can be configured
  using the ``api_type`` parameter, which accepts values from :ref:`OpenAIAPIType<openaiapitype>`.

  This enhancement allows recent OpenAI models to better leverage advanced reasoning capabilities, resulting in significant performance improvements for Wayflow-powered workflows.

  For more information check out :doc:`the how-to guide on LLMs from different providers <howtoguides/llm_from_different_providers>`.

* **Serve agents via OpenAI Responses API:**

  Added :ref:`OpenAIResponsesServer <openairesponsesserver>` and
  :ref:`ServerStorageConfig <serverstorageconfig>` to host WayFlow agents behind OpenAI
  Responses-compatible endpoints, with optional persistence through supported datastores.

  See :doc:`the new how-to guide on serving agents <howtoguides/howto_serve_agents>` for in-memory
  setup, datastore persistence, and Agent Spec export/reload examples.

* **Serve agents via A2A protocol:**
  Introduced the :ref:`A2AServer <a2aserver>` class for serving WayFlow conversational components using the A2A protocol.

  For more information check out :doc:`how to serve assistants with A2A protocol <howtoguides/howto_a2a_serving>`.

Improvements
^^^^^^^^^^^^

* **Support list, dict and tuple output types in MCP tools:**

  MCP tools now support non-string output types (list of string, dictionary of strings
  and tuple of these types)

  For more information see the guide on :doc:`using MCP tools <howtoguides/howto_mcp>`.


* **Connection persistence for MCP servers:**

  MCP client sessions are now reused which improves MCP calls latency and enables
  uses where maintaining a session is required.

  This does not require any change to existing assistants or execution loops.

* **Deserialization:**

  Deserialization of large conversations with many agents is now much faster due to optimizations in
  the deserialization code.

* **Long Message Summarization including Image Support**

  Added `MessageSummarizationTransform` which summarizes messages (including images) exceeding a configurable length
  threshold using a specified LLM and caches the summaries in a user-provided `DataStore` with
  configurable size, LRU eviction, and entry lifetime.

* **Long Conversation Summarization including Image Support**

  Added `ConversationSummarizationTransform` which summarizes conversations exceeding a configurable number of messages
  using a specified LLM and caches the summaries in a user-provided `DataStore` with configurable size, LRU eviction,
  and entry lifetime. This helps manage long conversation contexts by summarizing older parts while preserving recent
  messages.

  Transforms can now be assigned to an agent through its constructor. (This is not supported in `agentspec`, so attempting to convert agents with transforms to `agentspec` will raise a `NotImplementedError`)

* **Improve Swarm prompt template and introduce HandoffMode:**

  Removed redundant agent descriptions from the Swarm template and added a guidance rule that encourages agents to hand off when appropriate.
  Introduced ``HandoffMode`` to Swarm. In addition to the existing modes (``True`` → ``HandoffMode.OPTIONAL``, ``False`` → ``HandoffMode.NEVER``),
  a new mode ``HandoffMode.ALWAYS`` is now supported, requiring agents to always use the handoff
  mechanism when delegating tasks to other agents. Read more at :ref:`HandoffMode <HandoffMode>`.

  This significantly reduces token usage and improves execution speed.

Possibly Breaking Changes
^^^^^^^^^^^^^^^^^^^^^^^^^

* **Removed deprecated Agent/Flow.execute:**

  Removed the deprecated method of ``Agent/Flow.execute(conversation)`` in favor of ``conversation.execute()``.

* **Removed deprecated ChatHistoryContextProvider:**

  Removed the deprecated ``ChatHistoryContextProvider`` in favor of ``FlowContextProvider`` with a ``Flow`` with ``GetChatHistoryStep``.

* **Removed deprecated begin_step_name parameter of Flow:**

  Removed the deprecated parameter ``begin_step_name`` of the ``Flow`` class. Please use ``begin_step``, passing in a ``Step`` object instead.

* **Enforce valid tool names:**

  When creating any type of ``Tool``, its name field must not contain whitespaces or special characters, so that LLM APIs do not return errors. See bug fix below.

  - For now, a deprecation warning is raised; in the next cycle, an error will be thrown.

Bug fixes
^^^^^^^^^

* **Fixed several issues related to event tracing serialization when containing execution state:**

  Fixed an issue where ``FlowExecutionIterationStartedEvent`` and
  ``FlowExecutionIterationFinishedEvent`` could raise when the execution state contained values that
  are not supported by the serializer. The tracing helpers now fall back to stringifying those
  values while preserving container structures.

* **Recording of end span event in case of exception:**

  Fixed a bug where if an exception happened during a span, it would not be recorded and the span closing would
  raise an unwanted warning. Now properly records the exception as an ExceptionRaisedEvent and does not throw
  a warning.

* **Default values in agents inputs were ignored:**

  Fixed a bug where if agents had input descriptors with default values set, these defaults were ignored and not
  used when starting a conversation. Now default values of input descriptors are used if they are set, and no
  input entry with the descriptor name is passed to the ``start_conversation`` method.

* **Default values in tools outputs were ignored:**

  Fixed a bug where if tools had multiple output descriptors with default values set for some of them, these defaults were ignored and not
  set in the tool result if the tool execution did not produce a value for them. Tools that have a single output still ignore
  its default, as a return value is always assumed to be produced by the tool (possibly ``None``).

* **Fixed warnings raised when LLM streaming generator was not properly closed:**

  Fixed a bug where streaming LLM generation in a ``chainlit`` app could raise warnings due to a non-closed generator. The generator is now properly
  closed and we silence the known issue on the ``httpx`` library.

* **Continuing an agent conversation after an exception was raised could cause an exception:**

  Fixed a bug where if an exception would occur during a tool, a sub-agent or a sub-flow call of an agent, the conversation
  could not be resumed afterwards because the conversation would miss the tool results of any calls that should have
  been done after the call that raised. It now posts results mentioning the call was skipped due to a previous failure.

* **Some Agent and Flow names could cause issues when used in multi-agent patterns:**

  Fixed a bug where Agents or Flows, whose name contains whitespaces or special characters, would crash upon sending a request to the LLM provider

  - The cause was that internally, WayFlow converted a subagent of an Agent into a Tool, which is then converted to a JSON payload to submit to the LLM provider, which then returns an HTTP error if the tool's name does not match a regex.
  - Now, users may specify arbitrary names for Agents and Flows. Internally, when creating Tools out of subagents and subflows, their names would be sanitized.

* **Configuring Agents with PromptTemplates no longer requires custom instruction**

  Fixed a bug where instantiating an Agent with an ``agent_template``, ``initial_message=None`` and ``custom_instruction=None`` would raise an exception.
  Now, users can fully specify the agent template without having to additionally specify initial messages or custom instructions.

WayFlow 25.4.2
--------------

New features
^^^^^^^^^^^^

* **Agent Spec structured generation:**
  Open Agent Specification introduced Structured Generation in version 25.4.2.
  Support for this new Agent Spec feature was added in converters.

  For more information check out :doc:`the how-to guide on Structured Generation <howtoguides/howto_promptexecutionstep>`

* **Added Tool Confirmation before Execution:**
  Introduced a `requires_confirmation` flag to the base Tool Class. When enabled, this flag will pause tool execution and emit a `ToolExecutionConfirmationStatus`, requiring explicit user confirmation before proceeding.
  During confirmation, users may edit the tool’s arguments or provide a rejection reason. The tool executes only after confirmation is granted.

  For more information check out :doc:`the corresponding how-to guide <howtoguides/howto_userconfirmation>`

* **Added SplitPromptOnMarkerMessageTransform:**
  Introduced a new Message Transform specialization that splits prompts on a marker into multiple messages with the same role.

  We thank @richl9 for the contribution!

Bug fixes
^^^^^^^^^

* **Flow input and output descriptors**

  Fixed a bug where Flow input and output descriptors were sometimes ignored:

  - All the inputs required by the steps that compose the Flow were used instead of the input descriptors provided.
  - The intersection of all the outputs generated by any branch in the Flow was used instead of the output descriptors provided.

  The behavior is now:

  - Input descriptors can now be a subset of all the inputs required by the steps that compose the Flow,
    as long as the missing step inputs have a default value.
  - Output descriptors can be a subset of the intersection of all the outputs generated by any branch in the Flow.
    This is now correctly reflected also in other parts of the package.

* **Datastore validation**

  Fixed a bug which might cause `OracleDatabaseDatastore` to raise an exception due to concurrent changes and unsupported
  data types on unrelated parts of the schema, i.e., tables and columns that are not included in the datastore schema itself.

Miscellaneous
^^^^^^^^^^^^^

* **Dependency Security Updates:**
  Upgraded **MCP** to **1.17.0** and **PyYAML** to **6.0.3** to resolve known security vulnerabilities, including
  `GHSA-j975-95f5-7wqh <https://github.com/advisories/GHSA-j975-95f5-7wqh>`_,
  `GHSA-3qhf-m339-9g5v <https://github.com/advisories/GHSA-3qhf-m339-9g5v>`_,
  `GHSA-6757-jp84-gxfx <https://github.com/advisories/GHSA-6757-jp84-gxfx>`_,
  and `GHSA-8q59-q68h-6hv4 <https://github.com/advisories/GHSA-8q59-q68h-6hv4>`_.

Improvements
^^^^^^^^^^^^

* **Use execution statuses to interact with the components**
  Users can now directly see the conversation state and interact with the agent via the execution status.

  .. code-block:: python

      agent = Agent(...)
      tools_dict = {...}

      conversation: Conversation = agent.start_conversation()

      while True:
          status = conversation.execute()

          if isintance(status, UserMessageRequestStatus):
              print('Agent >> ', status.message.content)
              user_response = input('User >> ')
              status.submit_user_response(user_response)
          elif isinstance(status, ToolRequestStatus):
              for tool_request in status.tool_requests:
                  tool_result = ToolResult(
                      tool_id=tool_request.tool_request_id,
                      content=tools_dict[tool_request.name](**tool_request.args)
                  )
                  status.submit_tool_result(tool_result)
          elif isinstance(status, FinishedStatus):
              break

  For more information check out :doc:`Reference Sheet <misc/reference_sheet>`


WayFlow 25.4.1 — Initial release
--------------------------------

**WayFlow is here:** Build advanced AI-powered assistants with ease!

With this release, WayFlow provides all you need for building AI-powered assistants, supporting structured workflows,
autonomous agents, multi-agent collaboration, human-in-the-loop capabilities, and tool-based extensibility.
Modular design ensures you can rapidly build, iterate, and customize both simple and complex assistants for any task.

Explore further:

- :doc:`How-to Guides <howtoguides/index>`
- :doc:`Tutorials <tutorials/index>`
- :doc:`API Reference <api/index>`
