Changelog
=========

WayFlow 25.4.2
--------------------------------

New features
^^^^^^^^^^^^

* **Added Tool Confirmation before Execution:**
  Introduced a `requires_confirmation` flag to the base Tool Class. When enabled, this flag will pause tool execution and emit a `ToolExecutionConfirmationStatus`, requiring explicit user confirmation before proceeding.
  During confirmation, users may edit the tool’s arguments or provide a rejection reason. The tool executes only after confirmation is granted.

  For more information check out :doc:`the corresponding how-to guide <howtoguides/howto_userconfirmation>`


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
