[![WayFlow](docs/wayflowcore/source/_static/logo-light.svg)][website-wayflow]


[![WayFlow downloads][badge-dl]][downloads] [![WayFlow docs][badge-docs]][docs] [![WayFlow Reference Sheet][badge-reference-sheet]][reference-sheet] [![License][badge-license]](#license)


# WayFlow

WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants. It includes a standard library of plan steps to streamline the creation of AI-powered assistants, supports re-usability and is ideal for rapid development.


## Get started


To get started, set up your Python environment (Python 3.10 or newer required), and then install the WayFlow Core package.

### venv

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install wayflowcore
```

### uv

You can also use [uv](https://docs.astral.sh/uv/) for faster install times:

```bash
pip install uv
uv pip install wayflowcore
```

## Hello world example

Initialize a Large Language Model (LLM) of your choice:

| OCI Gen AI                                                                                                                                                                                                                                                   | Open AI                                                                                                         | Ollama                                                                                                          |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| <pre>from wayflowcore.models import OCIGenAIModel<br><br>llm = OCIGenAIModel(<br>   model_id="provider.model-id",<br>   service_endpoint="https://url-to-service-endpoint.com",<br>   compartment_id="compartment-id",<br>   auth_type="API_KEY",<br>)</pre> | <pre>from wayflowcore.models import OpenAIModel<br><br>llm = OpenAIModel(<br>   model_id="model-id",<br>)</pre> | <pre>from wayflowcore.models import OllamaModel<br><br>llm = OllamaModel(<br>   model_id="model-id",<br>)</pre> |


> See the list of supported LLMs in the [WayFlow documentation](https://oracle.github.io/wayflow/development/core/howtoguides/llm_from_different_providers.html).


Then, create an agent using a [WayFlow Agent](https://oracle.github.io/wayflow/development/core/api/agent.html#wayflowcore.agent.Agent):

```python
from wayflowcore.agent import Agent

assistant = Agent(llm=llm)

conversation = assistant.start_conversation()
conversation.append_user_message("I need help regarding my sql query")
conversation.execute()

# get the assistant's response to your query
assistant_answer = conversation.get_last_message()
assistant_answer.content
# I'd be happy to help with your SQL query...
```

For more information on how to build flexible Agents, structured Flows and multi-agent patterns, read the [WayFlow Tutorials](https://oracle.github.io/wayflow/development/core/tutorials/index.html)


## Why WayFlow?

* **Flexibility** : WayFlow supports multiple approaches to building AI Assistants, including Agents and Flows.
* **Interoperability** : WayFlow works with LLMs from many different vendors and supports an open approach to integration.
* **Reusability** : WayFlow enables you to build reusable and composable components for rapid development of AI assistants.
* **Extensibility** : WayFlow has powerful abstractions to handle all types of LLM applications and provides a standard library of steps.
* **Openness** : WayFlow is an open-source project, welcoming contributions from diverse teams looking to take AI agents to the next step.

## Positioning in the Agentic Ecosystem


WayFlow is the reference runtime implementation for [Open Agent Spec][website-agentspec].

[![Positioning](docs/wayflowcore/source/_static/agentspec_spec_img/agentspec_positioning.svg)][website-ecosystem]



## Examples

Explore practical examples for working with WayFlow.

Name         | Description
------------ | -------------
[Build a Simple Conversational Assistant with Agents](https://oracle.github.io/wayflow/development/core/tutorials/basic_agent.html) | A demo using dummy HR data to answer employee-related questions with an agent.
[Build a Simple Fixed-Flow Assistant with Flows](https://oracle.github.io/wayflow/development/core/tutorials/basic_flow.html) | A basic HR chatbot built as a fixed-flow assistant to answer employee questions.
[Build a Simple Code Review Assistant](https://oracle.github.io/wayflow/development/core/tutorials/usecase_prbot.html) | An advanced assistant using Flows to automate Python pull request reviews.

## Get Support

* Open a [GitHub issue][issues] for bug reports, questions, or requests for enhancements.
* Report a security vulnerability according to the [Reporting Vulnerabilities guide][reporting-vulnerabilities].


## Contributing

This project welcomes contributions from the community. Before submitting a pull request, please review the [contributor guide](./CONTRIBUTING.md).

## Security

Please refer to the [security guide](./SECURITY.md) for information on responsibly disclosing security vulnerabilities.

## License
Copyright (c) 2025 Oracle and/or its affiliates.

This software is under the Apache License 2.0 (LICENSE-APACHE or [http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0)) or Universal Permissive License (UPL) 1.0 (LICENSE-UPL or [https://oss.oracle.com/licenses/upl](https://oss.oracle.com/licenses/upl)), at your option.



[badge-dl]: https://img.shields.io/pepy/dt/wayflowcore
[badge-docs]: https://img.shields.io/badge/documentation-WayFlow-orange
[badge-license]: https://img.shields.io/badge/license-apache_2.0+UPL_1.0-green
[badge-reference-sheet]: https://img.shields.io/badge/reference%20sheet-read-red
[contributors]: https://oracle.github.io/wayflow/development/core/contributing.html
[docs]: https://oracle.github.io/wayflow/index.html
[downloads]: https://oracle.github.io/wayflow/development/core/installation.html
[getting-started]: https://oracle.github.io/wayflow/development/core/index.html
[issues]: https://github.com/oracle/wayflow/issues
[reference-sheet]: https://oracle.github.io/wayflow/development/core/misc/reference_sheet.html
[reporting-vulnerabilities]: https://www.oracle.com/corporate/security-practices/assurance/vulnerability/reporting.html
[website-wayflow]: https://oracle.github.io/wayflow/
[website-agentspec]: https://oracle.github.io/agent-spec/
[website-ecosystem]: https://oracle.github.io/agent-spec/agentspec/positioning.html
