.. _top-simple_code_review_assistant:

====================================
Build a Simple Code Review Assistant
====================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/usecase_prbot.py
        :link-alt: Simple Code Review Assistant tutorial script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

   This guide does not assume any prior knowledge about Project WayFlow. However, it assumes the reader has a basic knowledge of LLMs.

   You will need a working installation of WayFlow - see :doc:`Installation <../installation>`.

Learning goals
==============

In this use-case tutorial, you will build a more advanced WayFlow application, a **Pull Request (PR) Reviewing Assistant**, using a WayFlow
:ref:`Flow <flow>` to automate basic reviews of Python source code.

In this tutorial you will:

#. Learn the basics of using :ref:`Flows <flow>` to build an assistant.
#. Learn how to compose multiple sub-flows to create a more complex :ref:`Flow <flow>`.
#. Learn more about building :ref:`Tools <servertool>` that can be used within your :ref:`Flows <flow>`.

You can download a Jupyter Notebook for this use-case to follow along from :download:`Code PR Review Bot Tutorial  <../_static/usecases/usecase_prbot.ipynb>`.

Introduction to the task
========================

Code reviews are crucial for maintaining code quality and reviewers often spend considerable time pointing out
routine issues such as the presence of debug statements, formatting inconsistencies, or common coding convention violations that may not
be fully captured by static code analysis tools. This consumes valuable time that could be spent on reviewing more important things such as the
*core logic*, *architecture*, and *business requirements*.

.. note::

   Building an agent with WayFlow to perform such code reviews has a number of advantages:

   #. Review rules can be written using natural language, making an agent much more flexible than a simple static checker.
   #. Writing rules in natural language makes updating the rules very easy.
   #. More general issues can be captured. You can allow the LLM to infer from the rule to more general cases that could be missed by a simple static checker.
   #. New review rules can be generated from the collected comments of existing PRs.

In this tutorial, you will create a WayFlow Flow assistant designed to scan Python pull requests for common oversights such as:

* Having TODO comments without associated tickets.
* Using unclear or ambiguous variable naming.
* Using risky Python code practices such as mutable defaults.

To build this assistant you will break the task into configuration and two sub-flows that will be composed into a single flow:

\

.. image:: ../_static/usecases/prbot_main.svg
   :align: center
   :scale: 90%
   :alt: Complete Flow of the PR Bot

\

#. Configure your application, choose an LLM and import required modules [*Part 1*].
#. The first sub-flow retrieves and diffs information from a local codebase in a Git repository [*Part 2*].
#. The second sub-flow iterates over the file diffs using a :ref:`MapStep <mapstep>` and generates comments with an LLM using the :ref:`PromptExecutionStep <promptexecutionstep>` [*Step 3*].

You will also learn how to extract information using the :ref:`RegexExtractionStep <regexextractionstep>` and the :ref:`ExtractValueFromJsonStep <extractvaluefromjsonstep>`, and how to build and execute
tools with the :ref:`ServerTool <servertool>` and the :ref:`ToolExecutionStep <toolexecutionstep>`.

.. note::
   This is not a production-ready code review assistant that can be used as-is.

Setup
=====

First, let's set up the environment. For this tutorial you need to have ``wayflowcore`` installed (for additional information please read the
:doc:`installation guide <../installation>`).

Next download the example codebase Git repository, :download:`example codebase Git repository <../_static/usecases/agentix.zip>`. This will be used
to generate the sample code diffs for the assistant to review.

Extract the codebase Git repository folder from the compressed archive. Make a note of where the codebase Git repository is extracted to.

Part 1: Imports and LLM configuration
=====================================

First, set up the environment. For this tutorial you need to have ``wayflowcore`` installed, for additional information, read the
:doc:`installation guide <../installation>`.

WayFlow supports several LLMs API providers. To learn more about the supported LLM providers, read the guide,
:doc:`how to use LLMs from different providers <../howtoguides/llm_from_different_providers>`.

First choose an LLM from one of the options below:

.. include:: ../_components/llm_config_tabs.rst

.. note::
   API keys should never be stored in code. Use environment variables and/or tools such as `python-dotenv <https://pypi.org/project/python-dotenv/>`_
   instead.

   Be cautious when using external LLM providers and ensure that you comply with your organization's
   security policies and any applicable laws and regulations. Consider using a self-hosted LLM solution or
   a provider that offers on-premises deployment options if you need to maintain strict control over your code and data.


Part 2: Retrieve the PR diff information
========================================

The first phase of the assistant requires retrieving information about the code diffs from a code repository. You have already extracted the sample
codebase Git repository to your local environment.

This will be a sub-flow that consists of two simple steps:

* :ref:`ToolExecutionStep <toolexecutionstep>` that collects PR diff information using a Python subprocess to run the Git command.
* :ref:`RegexExtractionStep <regexextractionstep>` which separates the raw diff information into diffs for each file.

\

.. image:: ../_static/usecases/prbot_retrieve_diffs.svg
   :align: center
   :scale: 100%
   :alt: Steps to retrieve the PR diff information

\

First, take a look at what a diff looks like. The following example shows how a real diff appears when using Git:

.. literalinclude:: ../code_examples/usecase_prbot.py
   :language: python
   :start-after: .. start-##_Define_a_mocked_PR_diff
   :end-before: .. end-##_Define_a_mocked_PR_diff

**Reading a diff**: Removals are identified by the "-" marks and additions by the "+" marks.
In this example, there were only additions.

The diff above contains information about two files, ``calculators/utils.py`` and ``example/utils.py``.
This is an example diff and it is different from the diff that will be generated from the sample codebase.
It is included here to show how a Git diff looks and is shorter than the diff that you generate from the sample codebase.

Build a tool
------------

You need to create a tool to extract a code diff from the local code repository.
The :ref:`@tool <tooldecorator>` decorator can be used for that purpose by simply wrapping a Python function.

The function, ``local_get_pr_diff_tool``, in the code below does the work of extracting the diffs by
running the ``git diff HEAD`` shell command and capturing the output. It uses a subprocess to run the shell command.

To turn this function into a WayFlow tool, a ``@tool`` annotation is used to create a :ref:`ServerTool <servertool>` from the function.

.. literalinclude:: ../code_examples/usecase_prbot.py
   :language: python
   :linenos:
   :start-after: .. start-##_Define_the_tool_that_retrieves_the_PR_diff
   :end-before: .. end-##_Define_the_tool_that_retrieves_the_PR_diff

Building the steps and the sub-flow
-----------------------------------

Let's write the code for the first sub-flow.

.. literalinclude:: ../code_examples/usecase_prbot.py
   :language: python
   :linenos:
   :start-after: .. start-##_Create_the_flow_that_retrieves_the_diff_of_a_PR
   :end-before: .. end-##_Create_the_flow_that_retrieves_the_diff_of_a_PR

**API Reference:** :ref:`Flow <flow>` | :ref:`RegexExtractionStep <regexextractionstep>` | :ref:`ToolExecutionStep <toolexecutionstep>` | **API Reference:** :ref:`tool <tooldecorator>`

The code does the following:

#. It lists the names of the steps and input/output variables for the sub-flow.
#. It then creates the different steps within the sub-flow.
#. Finally, it instantiates the sub-flow. This will be covered in more detail later in the tutorial.

For clarity, the variable names are also prefixed with a dollar ($) sign. This is not necessary and is only done for code clarity. The variable
``REPO_DIRPATH_IO`` is used to hold the file path to the sample codebase Git repository and you will use this to pass in the location of the
codebase Git repository.

Additionally, you can give explicit names to the input/output variables used in the Flow, e.g. "$repo_dirpath_io" for the variable holding the
path to the local repository. Finally, we define those explicit names as string variables (e.g. ``REPO_DIRPATH_IO``) to minimize the number of
magic strings in the code.

.. seealso::
   To learn about the basics of Flows, check out our, :doc:`introductory tutorial on WayFlow Flows <basic_flow>`.

Now take a look at each of the steps used in the sub-flow in more detail.

Get the PR diff, ``get_pr_diff_step``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This uses a ``ToolExecutionStep`` to gather the diff information - see the notes on how this is done earlier. When creating it, you need to
provide the following:

* ``tool``: Specifies the tool that will called within the step. This is the tool that was created earlier, ``local_get_pr_diff_tool``.
* ``raise_exceptions``: Whether to raise exceptions generated by the tool that is called. Here it is set to ``True`` and so exceptions will be raised.
* ``input_mapping``: Specifies the names used for the input parameters of the step. See :ref:`ToolExecutionStep <toolexecutionstep>` for more details on using an ``input_mapping`` with this type of step.
* ``output_mapping``: Specifies the name used foe the output parameter of the step. The name held in ``PR_DIFF_IO`` will be mapped to the name for the output parameter of the step. Again, see :ref:`ToolExecutionStep <toolexecutionstep>` for more details on using an ``output_mapping`` with this type of step.

Extract file diffs into a list, ``extract_into_list_of_file_diff_step``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You now have the diff information from the PR. This step performs a regex extraction on the raw diff text to extract the code to review.

Use a ``RegexExtractionStep`` to perform this action. When creating the step, you need to provide the following:

* ``regex_pattern``: The regex pattern for the extraction. This uses ``re.findall`` underneath.
* ``return_first_match_only``: You want to return all results, so set this to ``False``.
* ``input_mapping``: Specifies the names used for the input parameters of the step. The input parameter will be mapped to the name, held in ``PR_DIFF_IO``. See :ref:`RegexExtractionStep <regexextractionstep>` for more details on using an ``input_mapping`` with this type of step.
* ``output_mapping``: Specifies the name used for the output parameter of the step. Here, the default name ``RegexExtractionStep.TEXT`` is renamed to the name defined in ``PR_DIFF_IO``. Again, see :ref:`RegexExtractionStep <regexextractionstep>` for more details on using an ``output_mapping`` with this type of step.

**About the pattern:**

.. code-block:: bash

   (diff --git[\s\S]*?)(?=diff --git|$)

The pattern looks for text starting with ``diff --git``, followed by any characters (both whitespace [\s] and non-whitespace [\S]), until it
encounters either another ``diff --git`` or the end of the text ($). However, it does not include the next ``diff --git`` or the end in the match.

The \*? makes it "lazy" or non-greedy, meaning it takes the shortest possible match, rather than the longest.

.. tip::
   Recent Large Language Models are very helpful tools to create, debug and explain Regex patterns given a natural language
   description.

Finally, create the sub-flow using the :ref:`Flow <flow>` class. You specify the steps in the Flow, the starting step of the Flow, the transitions
between steps and how data, from the variables, is to pass from one step to the next.

The transitions between steps are defined with :ref:`ControlFlowEdges <controlflowedge>`. These take a source step and a destination step. Each
``ControlFlowEdge`` maps one such transition.

Passing values between steps is a very common occurrence when building Flows. This is done using :ref:`DataFlowEdges <dataflowedge>` which define
that a value is passed from one step to another.

Inputs to a step will most commonly be for parameters within a Jinja template, of which there are several examples of in this tutorial, or parameters to
callables used by tools. In a :ref:`DataFlowEdge <dataflowedge>` you can use the name of the parameter, a string, to act as the destination of
a value that is being passed in. It is often less error-prone if you create a variable that is set to the name.

Similarly, when a value is the output of a step, such as when a user's input is captured in an :ref:`InputMessageStep <inputmessagestep>`, the value is
available as a property of the step, for example ``InputMessageStep.USER_PROVIDED_INPUT``. But, it lacks a meaningful name, so it is often helpful to
specify one. This is done using an ``output_mapping`` when creating the step. Again, you will want to create a variable to hold the name to avoid
errors.

Defining a Flow
---------------

Defining the Flow is the last step in the code shown above. There are a couple of things that are worth highlighting:

* ``begin_step``: A start step needs to be defined for a :ref:`Flow <flow>`.
* ``control_flow_edges``: The transitions between the steps in the :ref:`Flow <flow>` are defined as :ref:`ControlFlowEdges <controlflowedge>`. They have a ``source_step``, which defines the start of a transition, and a ``destination_step``, which defines the destination of a transition. All transitions for the flow will need to be defined.
* ``data_flow_edges``: Maps the variables between steps connected by a transition using :ref:`DataFlowEdges <dataflowedge>`. It maps variables from a source step into variables in a destination step. You only need to do this for the variables that need to be passed between steps.

Testing the flow
----------------

You can test this sub-flow by creating an assistant conversation with :meth:`.Flow.start_conversation` and specifying the inputs,
in this case the location of the Git repository. The conversation can then be executed with :meth:`.Conversation.execute`.
This returns an object that represents the status of the conversation which you can check to confirm that the conversation has successfully finished.

The code below shows how the inputs are passed in. Set the ``PATH_TO_DIR`` to the actual path you extracted the sample codebase
Git repository to. You then extract the outputs from the conversation.

The full code for testing the sub-flow is shown below:

.. literalinclude:: ../code_examples/usecase_prbot.py
   :language: python
   :linenos:
   :start-after: .. start-##_Test_the_flow_that_retrieves_the_PR_diff
   :end-before: .. end-##_Test_the_flow_that_retrieves_the_PR_diff

**API Reference:** :ref:`Flow <flow>`


Part 3: Review the list of diffs
================================

Now that we have a list of diffs for each file, we can review them and generate comments using an LLM.

This task can be broken into a sub-flow made up of five steps:

* :ref:`OutputMessageStep <outputmessagestep>`: This converts the file diff list into a string to be processed by the following steps.
* :ref:`ToolExecutionStep <toolexecutionstep>`: This prefixes the diffs with line numbers for additional context to the LLM.
* :ref:`RegexExtractionStep <regexextractionstep>`: This extracts the file path from the diff string.
* :ref:`PromptExecutionStep <promptexecutionstep>`: This generates comments using the LLM based on a list of user-defined checks.
* :ref:`ExtractValueFromJsonStep <extractvaluefromjsonstep>`: This extracts the comments and lines they apply to from the LLM output.

\

.. image:: ../_static/usecases/prbot_generate_comment.svg
   :align: center
   :scale: 100%
   :alt: Sub Flow to review the PR diffs

\

Build the tools and checks
--------------------------

Before creating the steps and sub-flow to generate the comments, it is important to define the list of checks
the assistant should perform, along with any specific instructions. Additionally, a tool must be created to prefix
the diffs with line numbers, allowing the LLM to determine where to add comments.

Below is the full code to achieve this. It is broken into sections so that you can see, in detail, what is happening in each part.

.. literalinclude:: ../code_examples/usecase_prbot.py
   :language: python
   :linenos:
   :start-after: .. start-##_Define_the_tool_that_formats_the_diff_for_the_LLM
   :end-before: .. end-##_Define_the_tool_that_formats_the_diff_for_the_LLM

**API Reference:** :ref:`ExtractValueFromJsonStep <extractvaluefromjsonstep>` | :ref:`MapStep <mapstep>` |
:ref:`OutputMessageStep <outputmessagestep>` | :ref:`PromptExecutionStep <promptexecutionstep>` | :ref:`ToolExecutionStep <toolexecutionstep>`

Checks and LLM instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

You will use three simple checks that are shown below. For each check you specify a name, a description of what the LLM should be checking,
as well as a code and expected comment example so that the LLM gets a better understanding of what the task is about.

The prompt uses a simple structure:

#. **Role Definition**: Define who/what you want the LLM to act as (e.g., "You are a very experienced code reviewer").
#. **Context Section**: Provide relevant background information or specific circumstances that frame the task.
#. **Input Section**: Specify the exact information, data, or materials that the LLM will be provided with.
#. **Task Section**: Clearly state what you want the LLM to do with the input provided.
#. **Response Format Section**: Define how you want the response to be structured or formatted (e.g., bullet points, JSON, with XML tags, and so on).

The prompts are defined in the array, ``PR_BOT_CHECKS``. The individual prompts for the checks are then concatenated into a single string,
``CONCATENATED_CHECKS``, so that it can be used inside the system prompt you will be passing to the LLM.

Define a system prompt, or prompt template, ``PROMPT_TEMPLATE``. It contains placeholders for the diff and the checks that will be replaced
when specialising the prompt for each diff.

.. tip::
   **How to write high-quality prompts**

   There is no consensus on what makes the best LLM prompt. However, it is noted that for recent LLMs, a great strategy
   to use to prompt an LLM is simply to be very specific about the task to be solved, giving enough context and explaining
   potential edge cases to consider.

   Given a prompt, try to determine whether giving the set of instructions to an experienced colleague, that has no prior
   context about the task, to solve would be sufficient for them to get to the intended result.


Diff formatting tool
^^^^^^^^^^^^^^^^^^^^

You next need to create a tool using the :ref:`ServerTool <servertool>` to format the diffs in a manner that makes them consumable
by the LLM. A tool, as you will have already seen, is a simple wrapper around a ``python`` callable that makes it useable within a flow.

The function, ``format_git_diff``, in the code above does the work of formatting the diffs.

.. seealso::
    For more information about WayFlow tools please read our guide, :doc:`How to use tools <../howtoguides/howto_build_assistants_with_tools>`.

Building the steps and the sub-flow
-----------------------------------

With the prompts and diff formatting tool written you can now build the second sub-flow.
This sub-flow will iterate over the diffs, generated previously, and then use an LLM to generate review comments from them.

.. literalinclude:: ../code_examples/usecase_prbot.py
   :language: python
   :linenos:
   :start-after: .. start-##_Create_the_flow_that_generates_review_comments
   :end-before: .. end-##_Create_the_flow_that_generates_review_comments


**API Reference:** :ref:`Property <property>` | :ref:`ListProperty <listproperty>` | :ref:`DictProperty <dictproperty>` | :ref:`StringProperty <stringproperty>` |
:ref:`ExtractValueFromJsonStep <extractvaluefromjsonstep>` | :ref:`MapStep <mapstep>` | :ref:`OutputMessageStep <outputmessagestep>` | :ref:`PromptExecutionStep <promptexecutionstep>` | :ref:`ToolExecutionStep <toolexecutionstep>`

Take a look at each of the steps used in the sub-flow to get an understanding of what is happening.

Format diff to string, ``format_diff_to_string_step``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This step converts the file diff list into a string so that it can be used by the following steps.

This is done with the ``string`` Jinja filter as follows: ``{{ message | string }}``. It uses an :ref:`OutputMessageStep <outputmessagestep>`
to achieve this.

.. note::

    Jinja templating introduces security concerns that are addressed by WayFlow by restricting Jinja's rendering capabilities.
    Please check our guide on :ref:`How to write secure prompts with Jinja templating <securejinjatemplating>` for more information.


Add lines to the diff, ``add_lines_on_diff_step``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This step prefixes the diff with the line numbers required to review comments. It uses a, :ref:`ToolExecutionStep <toolexecutionstep>`, to run the
tool that you previously defined in order to do this.

The input to the tool, within the I/O dictionary, is specified using the ``input_mapping``. For all these steps, it is important to remember
that the outputs of one step are linked to the inputs of the next.

Extract file path, ``extract_file_path_step``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This extracts the file path from the diff string. The file path is needed for assigning the review comments. The :ref:`RegexExtractionStep <regexextractionstep>` step
is used to extract the file path from the diff.

The regular expression is applied to the diff string, extracted form the input map using the ``input_mapping`` parameter.

Note: Compared to the :ref:`RegexExtractionStep <regexextractionstep>` used in Part 1, here only the first match is required.

Generate comments, ``generate_comments_step``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This generates comments using the LLM and the prompt template defined earlier. The :ref:`PromptExecutionStep <promptexecutionstep>` step executes
the prompt with the LLM defined earlier in this tutorial.

Since the list of checks has already been defined, the template can be pre-rendered using the ``render_template_partially`` method. This renders the parts of the
template that have been provided, while the remaining information is gathered from the I/O dictionary.

Extract comments from JSON, ``extract_comments_from_json_step``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This extracts the comments and line numbers from the generated LLM output, which is a serialized JSON structure due to the prompt used.
A :ref:`ExtractValueFromJsonStep <extractvaluefromjsonstep>` is used to do the extraction. When creating the step, specify the following in
addition to the usual ``input_mapping`` and ``output_mapping``:

* ``output_values``: This defines the `JQ <https://jqlang.github.io/jq/>`_ query to extract the comments form the JSON generated by the LLM.
* ``llms``: An LLM that can be used to help resolve any parsing errors. This is related to ``retry``.
* ``retry``: If parsing fails, you may want to retry. This is set to ``True``, which results in trying to use the LLM to help resolve any such issues.

Create the sub-flow, ``generate_comments_subflow``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Here you define what steps are in the sub-flow, what the transitions between the steps are and what will be the starting step. This is exactly
the same process you did previously when defining the sub-flow to fetch the PR data.

Applying the comment generation to all file diffs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Now that you have the sub-flow create, you need to apply it to every file diff. This is done using a :ref:`MapStep <mapstep>`.
``MapStep`` takes a sub-flow as input, in this case, the ``generate_comments_subflow``, and applies it to an iterable—in this case, the list of file
diffs.

You simply specify:

* ``flow``: The sub-flow to map, that is applied to the iterable.
* ``unpack_input``: Defines how to unpack the input. A `JQ <https://jqlang.github.io/jq/>`_  query can be used to transform the input, but in this case, it is kept as a list.
* ``input_mapping``: Defines what the sub-flow will iterate over. The key, ``MapStep.ITERATED_INPUT``, is used to pass in the diffs.
* ``output_descriptors``: Specifies the values to collect from the output generated by applying the sub-flow. In this case, these will be the generated comments and the associated file path.

.. note::
   The :ref:`MapStep <mapstep>` works similarly to how the Python map function works. For more information, see
   https://docs.python.org/3/library/functions.html#map

Finally, create the sub-flow to generate all comments using the helper method ``create_single_step_flow``.

Testing the sub-flow
--------------------

You can test the sub-flow by creating a conversation, as shown in the code below, and specifying the inputs as done in, ``Part 2: Retrieve the PR diff information``.

Since each sub-flow is tested independently, you can reuse the output from the first sub-flow.

.. literalinclude:: ../code_examples/usecase_prbot.py
   :language: python
   :linenos:
   :start-after: .. start-##_Test_the_flow_that_generates_review_comments
   :end-before: .. end-##_Test_the_flow_that_generates_review_comments

Building the final Flow
=======================

Congratulations! You have completed the three sub-flows, which, when combined into a single flow, will retrieve the PR diff information,
generate comments on the diffs using an LLM.

You will wire the sub-flows that you have built together by wrapping them in a :ref:`FlowExecutionStep <flowexecutionstep>`. The
:ref:`FlowExecutionSteps <flowexecutionstep>` are then composed into the final combined Flow.

The code for this is shown below:

.. literalinclude:: ../code_examples/usecase_prbot.py
   :language: python
   :linenos:
   :start-after: .. start-##_Create_flow_that_performs_the_review
   :end-before: .. end-##_Create_flow_that_performs_the_review

**API Reference:** :ref:`Flow <flow>` | :ref:`FlowExecutionStep <flowexecutionstep>`

Testing the combined assistant
------------------------------

You can now run the PR bot end-to-end on your repo or locally.

Set the ``PATH_TO_DIR`` to the actual path you extracted the sample codebase Git repository to. You can also see how the output of the conversation
is extracted from the ``execution_status`` object, ``execution_status.output_values``.

.. literalinclude:: ../code_examples/usecase_prbot.py
   :language: python
   :linenos:
   :start-after: .. start-##_Tests_flow_that_performs_the_review
   :end-before: .. end-##_Tests_flow_that_performs_the_review


Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/usecase_prbot.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/usecase_prbot.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/usecase_prbot.yaml
            :language: yaml


You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/usecase_prbot.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginOutputMessageNode``
    - ``PluginExtractNode``
    - ``PluginRegexNode``
    - ``ExtendedLlmNode``
    - ``ExtendedToolNode``
    - ``ExtendedMapNode``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


Recap
=====

In this tutorial you learned how to build a simple PR bot using WayFlow Flows, and learned:

- How to use core steps such as the :ref:`OutputMessageStep <outputmessagestep>` and :ref:`PromptExecutionStep <promptexecutionstep>`.
- How to build and execute tools using the :ref:`ServerTool <servertool>` and the :ref:`ToolExecutionStep <toolexecutionstep>`.
- How to extract information using the :ref:`RegexExtractionStep <regexextractionstep>` and the :ref:`ExtractValueFromJsonStep <extractvaluefromjsonstep>`.
- How to apply a sub flow over an iterable data using the :ref:`MapStep <mapstep>`.

Finally, you learned how to structure code when building assistant as code and how to execute and combine sub flows to build complex assistant.

This is an example of the kind of fully featured tool that you can build with WayFlow.


Next Steps
==========

Now that you learned how to build a PR reviewing assistant, you may want to check our other guides such as:

- :doc:`Build a Simple Agent <basic_agent>`
- :doc:`How to Catch Exceptions in Flows <../howtoguides/catching_exceptions>`


Full Code
=========

Click on the card at the :ref:`top of this page <top-simple_code_review_assistant>` to download the full code
for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/usecase_prbot.py
    :language: python
    :linenos:
