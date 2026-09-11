Frequently Asked Questions
==========================

**What types of assistants can I create using WayFlow?**

    You can create two main types of assistants: :ref:`Agents <agent>` and :ref:`Flows <flow>`. Agents are conversational assistants that can
    perform tasks and ask follow-up questions, while Flows are workflow-based assistants that can be represented as a flow of steps.

**What is the main difference between Agents and Flows?**

    Agents are more autonomous but less reliable and harder to run in production, while Flows are more predictable and easier to debug.

**How do I serialize or deserialize my assistant?**

    You can use the APIs provided by WayFlow to export/load your assistants to/from Agent Spec. You can use a few lines of code to export
    your assistant and load it in WayFlow using a JSON file. See the :doc:`API reference <api/agentspec>` for more information.

**What common steps are available to build Flows in WayFlow?**

    The central step in WayFlow is the :ref:`prompt execution step <promptexecutionstep>`, which allows you to generate prompts with an LLM.
    Other steps include :ref:`regex extraction <regexextractionstep>`, :ref:`extract from JSON <extractvaluefromjsonstep>`,
    :ref:`branching <branchingstep>`, :ref:`user input <inputmessagestep>`, :ref:`output <outputmessagestep>`,
    :ref:`flow execution <flowexecutionstep>`, :ref:`MapStep <mapstep>`, :ref:`ApiCallStep <apicallstep>`, and others.

**What models are available?**

    All WayFlow LLM models have the same API, but they are powered by different models underneath. WayFlow currently supports
    :ref:`Self-hosted models <vllmmodel>`, :ref:`OCI GenAI models <ocigenaimodel>`, and :ref:`3rd party models <openaimodel>`. See the :ref:`API reference <llmmodel>` for
    more information.

**How do I interact with data?**

    You can use the ``Datastore`` abstraction to interact with data structures.
    See the :ref:`API reference <datastores>` for more information.


**Why should I implement my assistant as a config file rather than custom code?**

    To avoid custom steps as much as possible, as they are difficult to test and make it harder to understand the logic of the application.
    Instead, you can use the base classes provided by WayFlow to create your assistant.
