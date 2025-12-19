Changelog
=========

WayFlow 25.4.3
--------------

Security
^^^^^^^^

* **Stricter environment for jinja templates rendering:**

  We now use a stricter version of the SandboxedEnvironment for rendering jinja templates.
  No access to object attributes is allowed, only key-based access to python dictionaries and main jinja LoopContext properties are allowed.

  Check the guide on :ref:`How to write secure prompts with Jinja templating <securejinjatemplating>` for more information.


WayFlow 25.4.2
--------------

Bug fixes
^^^^^^^^^

* **OpenAICompatibleModel supports API key from environment variable**

  Fixed a bug where it is unable to load an API key into ``OpenAICompatibleModel`` via an environment variable.
  In this patch, it is now possible to define an ``OPENAI_API_KEY`` environment variable, which is picked up by ``OpenAICompatibleModel``.
  This means, when importing from an AgentSpec component, users can now use LLMs models from various OpenAI-compatible servers such as OpenRouter, Together AI, etc.

* **Bug with internal handling of LLM API URL**

  Fixed a bug where API URLs (for LLMs) are sometimes not correctly used internally.

* **Remove global import of oci package and remove unused dependencies**

  Fixed an import bug where the ``oci`` optional dependency was treated as a mandatory, global dependency.
  In this patch, ``oci`` is an optional dependency, which can be installed with ``wayflowcore[oci]``.
  Other unused dependencies are also removed.


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
