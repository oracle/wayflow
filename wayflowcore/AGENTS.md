# WayFlow Core – Assistant Operating Manual

This repository powers the WayFlow agent platform. These instructions exist so
coding assistants act like productive teammates: fast, accurate, and aligned
with how the project actually runs. Read the “Zero-Step Contract” before every
task. Treat everything else as the living field guide.


## Zero-Step Contract (always obey)

1. **Plan mode** – Max 4 bullets, ≤6 words each. End with open questions or
   write `Questions: None`.
2. **Validation loop** – `pytest wayflowcore/tests/<specific_file>`. Only run the tests associated to the feature that is being developed.
3. **Bounded actions** – No background processes, no guessing commands. Ask for missing info in the plan.
4. **Scope discipline** – Touch only relevant files; mirror each code change with matching tests/docs when applicable.
5. **Report** - Summarize your actions (a few words) and add entry in changelog (`docs/wayflowcore/source/core/changelog.rst`)


## Project Snapshot

- **Purpose** – Provide a composable runtime for agents, flows, swarms, and tooling across multiple LLM providers (OCI, OpenAI, Ollama, VLLM, etc.).
- **Packaging** – Ships to PyPI as `wayflowcore`; source under `src/wayflowcore/`.
- **Key abstractions** – Agent (`agent.py`), Flow (`flow.py`), Swarm (`swarm.py`), Manager worker (`managerworkers.py`), OCI Agent (`ociagent.py`).
- **Primary services** – Tooling layer (`tools/`), model integrations (`models/`), agent server (`agentserver/`), persistence (`datastore/`), evaluation/telemetry (`evaluation/`, `events/`, `tracing/`).
- **AgentSpec adapters** - Layer to convert agent spec components into wayflow and the other way around. AgentSpec is a python SDK for an agentic specification. Most abstractions are common between AgentSpec and WayFlow, but have small differences.

Different types of conversational components can be built, such as:
- Agents for autonomous and/or conversational task completion with tools
- Flows for completing tasks with a structured sequence of steps
- Multi-agent patterns (Swarms, ManagerWorkers)

All conversational components have inputs and outputs. They run using a conversation:
```python
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus, ToolRequestStatus

conversation = component.start_conversation()
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    status.submit_user_response('response_from_the_user')
elif isinstance(status, FinishedStatus):
    outputs = status.output_values
elif isinstance(status, ToolRequestStatus):
    for tool_request in status.tool_requests:
        status.submit_tool_result("tool_execution_result")
status = conversation.execute() # to continue given the results ...
```

## Repository Map

| Area                        | Location                                                                                                       | Notes                                                                                            |
|-----------------------------|----------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| Agents & Conversations      | `agent.py`, `conversation.py`, `messagelist.py`, `tokenusage.py`                                               | Manages agent prompts, descriptors, token accounting.                                            |
| Flows & Steps               | `flow.py`, `steps/`, `flowhelpers.py`, `controlconnection.py`, `dataconnection.py`                             | Flow graphs, transitions, data edges, descriptor resolution.                                     |
| Swarms & A2A                | `swarm.py`, `a2a/`, `ociagent.py`, `managerworkers.py`, `_threading.py`                                        | Multi-agent orchestration, A2A agent protocol, OCI agents                                        |
| Execution logic             | `executors/`                                                                                                   | Execution logic of all classes.                                                                  |
| Tools                       | `tools/`, `toolbox.py`, `servertools.py`, `remotetools.py`, `toolhelpers.py`, `mcp/`                           | Tool definitions (client/server), MCP adapters (Model context protocol), conversion helpers.     |
| Models                      | `models/`                                                                                                      | OCI (`ocigenaimodel.py`), OpenAI (`openaimodel.py`), Ollama, VLLM, factory + generation configs. |
| Prompts & Templates         | `templates/`, `outputparser.py`, `transforms/`,                                                                | Schema generators, debugging scripts, regression tracking, flow validation notes.                |
| Data handling & Persistence | `datastore/`                                                                                                   | Handles connection to databases, Oracle DB/Postgres persistence.                                 |
| Agent Server & CLI          | `agentserver/`, `cli/`                                                                                         | FastAPI app + command-line runner (`wayflow`) for openai responses and a2a servers.              |
| Serialization & Utils       | `serialization/`, `_utils/`, `idgeneration.py`, `outputparser.py`, `planning.py`, `variable.py`, `property.py` | Core helpers for data handling, planning, descriptors.                                           |
| Evaluation & Telemetry      | `evaluation/`, `events/`, `tracing/`,                                                                          | Benchmarking, event streaming, tracing instrumentation,                                          |
| Tests                       | `tests/` (mirrors packages), `tests_fuzz/`                                                                     | Pytest suite                                                                                     |

Documentation of the package lives in another folder `../docs/wayflowcore/source`.

## Execution & Architecture

### Agent Lifecycle
1. **Construction** – `Agent(llm, tools, flows, agents, ...)`. `ToolBox` discovers tools are runtime. Input/output descriptors auto-inferred from templates; manual overrides in Agent require `_update_internal_state()`.
2. **Conversation start** – `start_conversation()` returning `AgentConversation`. `AgentConversationExecutor` handles reason/act loop.
3. **Context** – `ContextProvider` classes populate inputs that need to be refreshed each turn when required, configured via `property.py`.
4. **Tooling** – Tools resolved through `Tool`, `ToolBox`, `ServerTool`.
5. **Persistence & Events** – `events/` capture message history, tool calls; `datastore/` stores conversation state when server mode is enabled.

### Flow Lifecycle
1. **Definition** – Steps (e.g., `InputMessageStep`, `PromptExecutionStep`, `OutputMessageStep`) wired by control and data edges.
2. **Context** – `ContextProvider` classes populate inputs that need to be refreshed each turn when required, configured via `property.py`.
3. **Execution** – `FlowConversationExecutor` implements the flow execution loop.

### Swarms & A2A
- `swarm.py` coordinates multi-agent delegations, merging outputs with aggregator logic.
- `a2a/` implements agent-to-agent RPC and server interaction patterns.
- `managerworkers.py` uses a manager agent that delegates work to worker agents.

### Agent Server
- `cli/serve.py` exposes agents via OpenAI Responses or A2A. Configure via CLI flags or YAML files.
- `ServerStorageConfig` chooses persistence backend (`in-memory`, `oracle-db`, `postgres-db`). Oracle/Postgres setup helpers in `agentserver/_storagehelpers.py`.
- Supports tool registry modules and API key auth.


## Tooling & Environment

### Python & Dependencies
- Python 3.10–3.13 supported (see `setup.py`, `tox.ini`).
- Dependency pins in `constraints/constraints*.txt` (runtime + dev).
- `requirements-dev.txt` installs testing extras (starlette, uvicorn, litellm, google-adk[a2a], cryptography, etc.).
- Installation scripts (`install-dev.sh`, `install.sh`) rely on pip; **do not introduce `uv`**.

### Formatting & Linting
- Formatting is done by the git hook. Use the usual git commands but expect it to fail and reformat code.

### Type Checking
- Type checking is also done by the git hook
- `mypy` is used
- Add type stubs via `requirements-dev.txt` entries when needed.

### Security
- `nosec_ignore.csv` tracks exceptions. Pair every `# nosec` usage with a comment and entry.
- `tests/security/logging_tests.sh` ensures logging hygiene (runs automatically after pytest).


## Testing Playbook

### Core Commands
- Direct pytest (during iteration):
  - `pytest tests/path/to/test_file.py`
  - `DISABLE_RETRY=y pytest tests -k <keyword>` to disable the retry on some tests (`@retry_test` decorator).
- Use the `retry_test` decorator when the test relies on a particular behavior of the LLM. When using this test, you need first to compute the docstring using `FLAKY_TEST_EVALUATION_MODE=20 pytest tests/test_file.py::test_name` that will return the content of the docstring.
- Use the `patch_llm` context manager to mock LLM calls when possible in unit tests
- For integration tests, the `remotely_hosted_llm` fixture is used usually, and `big_llama` for tests that require slightly more reasoning.
- Integration tests require env vars (see `tests/conftest.py`): `LLAMA_API_URL`, `OCI_REASONING_MODEL`, `COMPARTMENT_ID`, `GEMMA_API_URL`, etc. Document absences.
- Fuzz testing: `python -m pythonfuzz.tests_fuzz.test_fuzz` (long-running; only run when necessary).

### Fixtures & Helpers
- `tests/_utils/`, `tests/testhelpers/`, `tests/utils.py` provide mocked models, message builders, datastore stubs.
- `tests/conftest.py` configures environment, threadpool cleanup (`shutdown_threadpool`). Use fixtures like `session_tmp_path`, OCI configs, or patched llms (`patch_llm` context manager).

### Security Harness
- `tests/security/` wraps logging and filesystem checks.
- For new security-sensitive features, add targeted tests or update `logging_tests.sh`.


## Coding Conventions & Guardrails

### Imports & Structure
- Library code: absolute `wayflowcore.*` imports. Tests also use absolute imports to match public API.
- Keep modules cohesive. Avoid creating new root-level packages; place helpers near their runtime counterparts.

### Descriptors & Serialization
- When adding dataclass fields to agents, flows, events, or serialization types:
  - Update descriptor lists (`input_descriptors`, `output_descriptors`).
  - Refresh caches via `_update_internal_state` or equivalent.
  - Extend serializer/deserializer logic (`serialization/serializer.py`).

### Logging & Warnings
- Use `logging.getLogger(__name__)`. No `print()` in library code.
- If a feature intentionally emits warnings, cover them using `pytest.warns`.

### Security & Credentials
- Never hardcode secrets. Tests rely on environment variables or fixtures.


## Workflow additional guidelines

- For new features, a how-to guide should be added in the documentation
- Any new feature / improvement / bugfix should be referenced in the `changelog.md`
