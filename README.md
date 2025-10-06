![WayFlow](docs/wayflowcore/source/_static/logo-light.svg)

# WayFlow

WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants. It includes a standard library of plan steps to streamline the creation of AI-powered assistants, supports re-usability and is ideal for rapid development.

## Why WayFlow?

* **Flexibility** : WayFlow supports multiple approaches to building AI Assistants, including Agents and Flows.
* **Interoperability** : WayFlow works with LLMs from many different vendors and supports an open approach to integration.
* **Reusability** : WayFlow enables you to build reusable and composable components for rapid development of AI assistants.
* **Extensibility** : WayFlow has powerful abstractions to handle all types of LLM applications and provides a standard library of steps.
* **Openness** : WayFlow is an open-source project, welcoming contributions from diverse teams looking to take AI agents to the next step.

## Getting Started

> **Note:**
> Python 3.10 is required. While `WayFlow` might work on later versions, those have not been tested.

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/oracle/wayflow.git
   ```

2. Create and activate a Python 3.10 virtual environment:

   ```bash
   python3.10 -m venv <venv_name>
   source <venv_name>/bin/activate
   ```

3. Navigate to the project directory:

   ```bash
   cd wayflowcore
   ```

4. Run the installation script:

   ```bash
   bash install-dev.sh
   ```

5. (For development) Install the pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Documentation

WayFlow documentation is available at the [website](https://oracle.github.io/wayflow/core/index.html).
Most of the documentation sources can be found in the _docs/_ directory, organized in the same hierarchy as presented on the site.

## Examples

Explore practical examples for working with WayFlow.

Name         | Description
------------ | -------------
[Build a Simple Conversational Assistant with Agents](https://oracle.github.io/wayflow/core/tutorials/basic_agent.html) | A demo using dummy HR data to answer employee-related questions with an agent.
[Build a Simple Fixed-Flow Assistant with Flows](https://oracle.github.io/wayflow/core/tutorials/basic_flow.html) | A basic HR chatbot built as a fixed-flow assistant to answer employee questions.
[Build a Simple Code Review Assistant](https://oracle.github.io/wayflow/core/tutorials/usecase_prbot.html) | An advanced assistant using Flows to automate Python pull request reviews.

## Help

Create a GitHub [issue](https://github.com/oracle/wayflow/issues).

## Contributing

This project welcomes contributions from the community. Before submitting a pull request, please review the [contributor guide](./CONTRIBUTING.md).

## Security

Please refer to the [security guide](./SECURITY.md) for information on responsibly disclosing security vulnerabilities.

## License
Copyright (c) 2025 Oracle and/or its affiliates.

This software is under the Universal Permissive License (UPL) 1.0 (LICENSE-UPL or [https://oss.oracle.com/licenses/upl](https://oss.oracle.com/licenses/upl)) or Apache License 2.0 (LICENSE-APACHE or [http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0)), at your option.
