# WayFlow Core – Assistant Operating Manual

This repository powers the WayFlow agent platform. These instructions exist so
coding assistants act like productive teammates: fast, accurate, and aligned
with how the project actually runs. Read the “Zero-Step Contract” before every
task. Treat everything else as the living field guide.


## Zero-Step Contract (always obey)

1. **Plan mode** – Max 4 bullets, ≤6 words each. End with open questions or
   write `Questions: None`.
2. **Validation loop** – `python -m pip install -e .[oci,datastore,a2a]`
   → `ruff --fix src tests` → `black src tests` → `tox -e lint`
   → `tests/run_tests.sh [--parallel]`. If you skip anything, state why and the next step.
3. **Bounded actions** – No background processes, no guessing commands. Ask for missing info in the plan.
4. **Repo hygiene** – Only create artifacts under sanctioned dirs (`build/`, `dist/`, `testing_scripts/tmp`).
5. **Scope discipline** – Touch only relevant files; mirror each code change with matching tests/docs when applicable.


## Project Snapshot

- **Purpose** – Provide a composable runtime for agents, flows, swarms, and tooling across multiple LLM providers (OCI, OpenAI, Ollama, VLLM, etc.).
- **Packaging** – Ships to PyPI as `wayflowcore`; source under `src/wayflowcore/`.
- **Key abstractions** – Agent (`agent.py`), Flow (`flow.py`), Swarm (`swarm.py`), Manager worker pool (`managerworkers.py`), OCI Agent (`ociagent.py`).
- **Primary services** – Tooling layer (`tools/`), model integrations (`models/`), agent server (`agentserver/`), persistence (`datastore/`), evaluation/telemetry (`evaluation/`, `events/`, `tracing/`).


## Repository Map

| Area | Location | Notes |
| --- | --- | --- |
| Agents & Conversations | `agent.py`, `agentconversation.py`, `conversation.py`, `messagelist.py`, `tokenusage.py` | Manages agent prompts, descriptors, token accounting. |
| Flows & Steps | `flow.py`, `flowconversation.py`, `steps/`, `flowhelpers.py`, `stepdescription.py`, `controlconnection.py`, `dataconnection.py` | Flow graphs, transitions, data edges, descriptor resolution. |
| Swarms & A2A | `swarm.py`, `a2a/`, `managerworkers.py`, `_threading.py` | Multi-agent orchestration, worker lifecycle, scheduling. |
| Tools | `tools/`, `toolbox.py`, `servertools.py`, `remotetools.py`, `toolhelpers.py`, `mcp/` | Tool definitions (client/server), MCP adapters, conversion helpers. |
| Models | `models/` | OCI (`ocigenaimodel.py`), OpenAI (`openaimodel.py`), Ollama, VLLM, factory + generation configs. |
| OCI Integrations | `ociagent.py`, `models/ociclientconfig.py`, `datastore/` | Handles tenancy, compartments, Oracle DB/Postgres persistence. |
| Agent Server & CLI | `agentserver/`, `cli/` | FastAPI app + command-line runner (`wayflow`). |
| Serialization & Utils | `serialization/`, `_utils/`, `idgeneration.py`, `outputparser.py`, `planning.py`, `variable.py`, `property.py` | Core helpers for data handling, planning, descriptors. |
| Evaluation & Telemetry | `evaluation/`, `events/`, `tracing/`, `transforms/` | Benchmarking, event streaming, tracing instrumentation, message transforms. |
| Tests | `tests/` (mirrors packages), `tests_fuzz/` | Pytest suite, security harness, PythonFuzz. |
| Tooling Assets | `dev_scripts/`, `testing_scripts/`, `model_test_results*/`, `support_matrix*.html`, `res.md`, `improvements.jsonl` | Schema generators, debugging scripts, regression tracking, flow validation notes. |


## Execution & Architecture

### Agent Lifecycle
1. **Construction** – `Agent(llm, tools, flows, agents, ...)`. `ToolBox` converts legacy tool configs. Input/output descriptors auto-inferred from templates; manual overrides require `_update_internal_state()`.
2. **Conversation start** – `start_conversation()` returning `AgentConversation`. `ConversationExecutor` handles reason/act loop, using `ManagerWorkerPool` for asynchronous steps.
3. **Context** – `ContextProvider` classes populate variables, orchestrated via `property.py` and `variable.py`.
4. **Tooling** – Tools resolved through `Tool`, `ToolBox`, `ServerTool`. Server tools convert older schemas via `_convert_previously_supported_tools_if_needed`.
5. **Persistence & Events** – `events/` capture message history, tool calls; `datastore/` stores conversation state when server mode is enabled.

### Flow Lifecycle
1. **Definition** – Steps (e.g., `InputMessageStep`, `PromptExecutionStep`, `OutputMessageStep`) wired by control and data edges.
2. **Validation** – `res.md` lists warnings (missing transitions, duplicate inputs). Keep flows spec-compliant; no ad-hoc hacks.
3. **Execution** – `FlowConversation` orchestrates step activation while `FlowConversationExecutor` enforces descriptors and data propagation.

### Swarms & A2A
- `swarm.py` coordinates multi-agent delegations, merging outputs with aggregator logic.
- `a2a/` implements agent-to-agent RPC and server interaction patterns.
- `managerworkers.py` ensures pooled workers remain bounded and cancellable.

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
- `ruff --fix src tests` for lint fixes.
- `black src tests` (88 char limit). Keep import order consistent with `ruff` configuration; no isort script exists, so rely on `ruff`.

### Type Checking
- `mypy` (root config) + supplemental datasets under `mypy-precision/`.
- Add type stubs via `requirements-dev.txt` entries when needed.

### Security
- `nosec_ignore.csv` tracks exceptions. Pair every `# nosec` usage with a comment and entry.
- `tests/security/logging_tests.sh` ensures logging hygiene (runs automatically after pytest).


## Testing Playbook

### Core Commands
- `tests/run_tests.sh` – main entry point. Supports `--parallel`; automatically runs the security script afterward.
- Direct pytest (during iteration):
  - `pytest tests/path/to/test_file.py`
  - `pytest tests --maxfail=1 -k <keyword>`
- Integration tests require env vars (see `tests/conftest.py`): `LLAMA_API_URL`, `OCI_REASONING_MODEL`, `COMPARTMENT_ID`, `GEMMA_API_URL`, etc. Document absences.
- Fuzz testing: `python -m pythonfuzz.tests_fuzz.test_fuzz` (long-running; only run when necessary).

### Fixtures & Helpers
- `tests/_utils/`, `tests/testhelpers/`, `tests/utils.py` provide mocked models, message builders, datastore stubs.
- `tests/conftest.py` configures environment, threadpool cleanup (`shutdown_threadpool`). Use fixtures like `session_tmp_path`, OCI configs, or dummy models.

### Security Harness
- `tests/security/` wraps logging and filesystem checks. Never bypass.
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
  - Add regression tests for serialization/deserialization paths.

### Logging & Warnings
- Use `logging.getLogger(__name__)`. No `print()` in library code.
- If a feature intentionally emits warnings, cover them using `pytest.warns`.

### Concurrency & Background Work
- Use `managerworkers.ManagerWorkerPool` or `_threading` helpers for threads.
- Always trigger `shutdown_threadpool()` in teardown (see tests) to avoid leaks.
- Do not spawn raw threads or asynchronous tasks outside these utilities.

### Security & Credentials
- All OCI credentials must flow through `OCIClientConfig*` and `ociagent.py`.
- Never hardcode secrets. Tests rely on environment variables or fixtures.


## Packaging & Release

- Build artifacts using `python -m build` or `python setup.py sdist bdist_wheel`.
- Distribution metadata stored in `_metadata.py`; override via `BUILD_VERSION` env var if triggered by CI.
- `MANIFEST.in` ensures licenses and generated assets are included. Update when adding new static resources.
- Maintain compatibility docs: update `support_matrix*.html` and `model_test_results*/` when broadening provider support or adjusting defaults.


## Workflow Expectations

1. **Plan** – concise bullets + open questions.
2. **Inspect** – identify relevant modules/tests before coding.
3. **Implement** – small, cohesive diffs. Update docs/matrices when behavior changes.
4. **Validate** – run formatting, linting, targeted tests (document any skips).
5. **Summarize** – final message lists changes, validation, follow-ups.

If blocked, surface the question in the plan and pause.


## Common Playbooks

### Adding a Tool
1. Create tool implementation in `tools/` (client/server). Follow existing patterns (`Tool`, `ToolBox`).
2. Update tool registry if needed (`servertools.py`, `toolbox.py`).
3. Wire new tool into agent/server configs.
4. Add tests under `tests/tools/` or relevant integration directory.

### Extending a Flow
1. Modify step definitions in `steps/` or compose new ones in `flowhelpers.py`.
2. Update flow graph: transitions (`ControlFlowEdge`), data edges (`DataFlowEdge`).
3. Regenerate descriptors if templates changed.
4. Run flow-specific tests (`tests/test_flowconversation.py`, etc.) and update `res.md` if new warnings apply.

### Adding an LLM Provider
1. Implement new model class under `models/` (+ request helpers if needed).
2. Register provider with `LlmModelFactory`.
3. Update token usage helpers, generation configs.
4. Document in README + support matrix; add tests under `tests/models/`.

### Updating Agent Server Behavior
1. Modify FastAPI app (`agentserver/app.py`) or storage helpers.
2. Adjust CLI flags in `cli/serve.py` if the interface changes.
3. Update documentation (README + AGENTS.md if workflow shifts).
4. Extend tests under `tests/agentserver/` and security harness if needed.


## Resources & References

- `README.md` – High-level overview + quick start.
- `testing_scripts/` – Flaky analyzer, REPL for serialized graphs, templates.
- `dev_scripts/openai-models-gen/` – Model schema generation utilities.
- `nosec_ignore.csv` – Security exceptions log (keep minimal).

When uncertain, ask. The best teammates surface gaps early and keep the loop tight.
