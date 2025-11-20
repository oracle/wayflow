# 🔗 WayFlow Core

[![PyPI - Version](https://img.shields.io/pypi/v/wayflowcore?label=PyPI)](https://pypi.org/project/wayflowcore/#history)
[![PyPI - License](https://img.shields.io/pypi/l/wayflowcore)](#license)
[![PyPI - Downloads](https://img.shields.io/pepy/dt/wayflowcore)](https://pypistats.org/packages/wayflowcore)

**WayFlow Core** is the foundational Python library of the WayFlow ecosystem.
It provides the runtime engine, abstractions, and components needed to build powerful AI assistants using **Agents**, **Flows**, or hybrid architectures.

WayFlow Core is:

- **🔧 Flexible** — Build assistants using Agents, Flows, or both
- **🔗 Interoperable** — Works with OCI GenAI, OpenAI, Ollama, and other LLM providers
- **🧩 Composable** — Encourages modular, reusable building blocks
- **🚀 Extensible & Open** — Designed for advanced agentic applications

---

## ⚡ Quick Install

```bash
pip install wayflowcore
````

(Optional, faster installation using `uv`)

```bash
pip install uv
uv pip install wayflowcore
```

---

## 🧠 Quick Start

### 1. Initialize an LLM

Initialize a Large Language Model (LLM) of your choice:

| OCI Gen AI                                                                                                                                                                                                                                                   | Open AI                                                                                                         | Ollama                                                                                                          |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| <pre>from wayflowcore.models import OCIGenAIModel<br><br>llm = OCIGenAIModel(<br>   model_id="provider.model-id",<br>   service_endpoint="https://url-to-service-endpoint.com",<br>   compartment_id="compartment-id",<br>   auth_type="API_KEY",<br>)</pre> | <pre>from wayflowcore.models import OpenAIModel<br><br>llm = OpenAIModel(<br>   model_id="model-id",<br>)</pre> | <pre>from wayflowcore.models import OllamaModel<br><br>llm = OllamaModel(<br>   model_id="model-id",<br>)</pre> |


### 2. Create an Assistant

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

---

## 🧩 What You Can Build

WayFlow Core supports a wide range of agentic patterns:

* 💬 Conversational assistants
* 🔁 Flow-based assistants with structured sequencing
* 🤝 Multi-agent systems
* 🛠️ Tool-calling agents
* 🧪 Automated code review assistants
* 📚 Domain-specific knowledge assistants

---

## 💁 Contributing

Contributions are welcome!
Please refer to the contributor guide located at the root of the repository.

---

## 🔐 Security

For responsibly reporting security issues, please refer to the project's security guidelines.

---

## 📄 License

WayFlow Core is dual-licensed under:

- **Apache License 2.0** – see [`LICENSE-APACHE.txt`](https://github.com/oracle/wayflow/blob/main/LICENSE-APACHE.txt)
- **Universal Permissive License (UPL) 1.0** – see [`LICENSE-UPL.txt`](https://github.com/oracle/wayflow/blob/main/LICENSE-UPL.txt)
