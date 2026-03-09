<a id="top-simple-code-review-assistant"></a>

# Build a Simple Code Review Assistant![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Simple Code Review Assistant tutorial script](../end_to_end_code_examples/usecase_prbot.py)

#### Prerequisites
This guide does not assume any prior knowledge about Project WayFlow. However, it assumes the reader has a basic knowledge of LLMs.

You will need a working installation of WayFlow - see [Installation](../installation.md).

## Learning goals

In this use-case tutorial, you will build a more advanced WayFlow application, a **Pull Request (PR) Reviewing Assistant**, using a WayFlow
[Flow](../api/flows.md#flow) to automate basic reviews of Python source code.

In this tutorial you will:

1. Learn the basics of using [Flows](../api/flows.md#flow) to build an assistant.
2. Learn how to compose multiple sub-flows to create a more complex [Flow](../api/flows.md#flow).
3. Learn more about building [Tools](../api/tools.md#servertool) that can be used within your [Flows](../api/flows.md#flow).

You can download a Jupyter Notebook for this use-case to follow along from [`Code PR Review Bot Tutorial`](../_static/usecases/usecase_prbot.ipynb).

## Introduction to the task

Code reviews are crucial for maintaining code quality and reviewers often spend considerable time pointing out
routine issues such as the presence of debug statements, formatting inconsistencies, or common coding convention violations that may not
be fully captured by static code analysis tools. This consumes valuable time that could be spent on reviewing more important things such as the
*core logic*, *architecture*, and *business requirements*.

#### NOTE
Building an agent with WayFlow to perform such code reviews has a number of advantages:

1. Review rules can be written using natural language, making an agent much more flexible than a simple static checker.
2. Writing rules in natural language makes updating the rules very easy.
3. More general issues can be captured. You can allow the LLM to infer from the rule to more general cases that could be missed by a simple static checker.
4. New review rules can be generated from the collected comments of existing PRs.

In this tutorial, you will create a WayFlow Flow assistant designed to scan Python pull requests for common oversights such as:

* Having TODO comments without associated tickets.
* Using unclear or ambiguous variable naming.
* Using risky Python code practices such as mutable defaults.

To build this assistant you will break the task into configuration and two sub-flows that will be composed into a single flow:

![Complete Flow of the PR Bot](core/_static/usecases/prbot_main.svg)
1. Configure your application, choose an LLM and import required modules [*Part 1*].
2. The first sub-flow retrieves and diffs information from a local codebase in a Git repository [*Part 2*].
3. The second sub-flow iterates over the file diffs using a [MapStep](../api/flows.md#mapstep) and generates comments with an LLM using the [PromptExecutionStep](../api/flows.md#promptexecutionstep) [*Step 3*].

You will also learn how to extract information using the [RegexExtractionStep](../api/flows.md#regexextractionstep) and the [ExtractValueFromJsonStep](../api/flows.md#extractvaluefromjsonstep), and how to build and execute
tools with the [ServerTool](../api/tools.md#servertool) and the [ToolExecutionStep](../api/flows.md#toolexecutionstep).

#### NOTE
This is not a production-ready code review assistant that can be used as-is.

## Setup

First, let’s set up the environment. For this tutorial you need to have `wayflowcore` installed (for additional information please read the
[installation guide](../installation.md)).

Next download the example codebase Git repository, [`example codebase Git repository`](../_static/usecases/agentix.zip). This will be used
to generate the sample code diffs for the assistant to review.

Extract the codebase Git repository folder from the compressed archive. Make a note of where the codebase Git repository is extracted to.

## Part 1: Imports and LLM configuration

First, set up the environment. For this tutorial you need to have `wayflowcore` installed, for additional information, read the
[installation guide](../installation.md).

WayFlow supports several LLMs API providers. To learn more about the supported LLM providers, read the guide,
[how to use LLMs from different providers](../howtoguides/llm_from_different_providers.md).

First choose an LLM from one of the options below:




OCI GenAI

```python
from wayflowcore.models import OCIGenAIModel, OCIClientConfigWithApiKey

llm = OCIGenAIModel(
    model_id="provider.model-id",
    compartment_id="compartment-id",
    client_config=OCIClientConfigWithApiKey(
        service_endpoint="https://url-to-service-endpoint.com",
    ),
)
```

vLLM

```python
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)
```

Ollama

```python
from wayflowcore.models import OllamaModel

llm = OllamaModel(
    model_id="model-id",
)
```

#### NOTE
API keys should never be stored in code. Use environment variables and/or tools such as [python-dotenv](https://pypi.org/project/python-dotenv/)
instead.

Be cautious when using external LLM providers and ensure that you comply with your organization’s
security policies and any applicable laws and regulations. Consider using a self-hosted LLM solution or
a provider that offers on-premises deployment options if you need to maintain strict control over your code and data.

## Part 2: Retrieve the PR diff information

The first phase of the assistant requires retrieving information about the code diffs from a code repository. You have already extracted the sample
codebase Git repository to your local environment.

This will be a sub-flow that consists of two simple steps:

* [ToolExecutionStep](../api/flows.md#toolexecutionstep) that collects PR diff information using a Python subprocess to run the Git command.
* [RegexExtractionStep](../api/flows.md#regexextractionstep) which separates the raw diff information into diffs for each file.

![Steps to retrieve the PR diff information](core/_static/usecases/prbot_retrieve_diffs.svg)

First, take a look at what a diff looks like. The following example shows how a real diff appears when using Git:

```python
MOCK_DIFF = """
diff --git src://calculators/utils.py dst://calculators/utils.py
index 12345678..90123456 100644
--- src://calculators/utils.py
+++ dst://calculators/utils.py
@@ -10,6 +10,15 @@

 def calculate_total(data):
     # TODO: implement tax calculation
     return data

+def get_items(items=[]):
+    result = []
+    for item in items:
+        result.append(item * 2)
+    return result
+
+def process_numbers(numbers):
+    res = []
+    for x in numbers:
+        res.append(x + 1)
+    return res
+
 def calculate_average(numbers):
     return sum(numbers) / len(numbers)


diff --git src://example/utils.py dst://example/utils.py
index 000000000..123456789
--- /dev/null
+++ dst://example/utils.py
@@ -0,0 +1,20 @@
+# Copyright © 2024 Oracle and/or its affiliates.
+
+def calculate_sum(numbers=[]):
+    total = 0
+    for num in numbers:
+        total += num
+    return total
+
+
+def process_data(data):
+    # TODO: Handle exceptions here
+    result = data * 2
+    return result
+
+
+def main():
+    numbers = [1, 2, 3, 4, 5]
+    result = calculate_sum(numbers)
+    print("Sum:", result)
+    data = 10
+    processed_data = process_data(data)
+    print("Processed Data:", processed_data)
+
+
+if __name__ == "__main__":
+    main()
""".strip()
```

**Reading a diff**: Removals are identified by the “-” marks and additions by the “+” marks.
In this example, there were only additions.

The diff above contains information about two files, `calculators/utils.py` and `example/utils.py`.
This is an example diff and it is different from the diff that will be generated from the sample codebase.
It is included here to show how a Git diff looks and is shorter than the diff that you generate from the sample codebase.

### Build a tool

You need to create a tool to extract a code diff from the local code repository.
The [@tool](../api/tools.md#tooldecorator) decorator can be used for that purpose by simply wrapping a Python function.

The function, `local_get_pr_diff_tool`, in the code below does the work of extracting the diffs by
running the `git diff HEAD` shell command and capturing the output. It uses a subprocess to run the shell command.

To turn this function into a WayFlow tool, a `@tool` annotation is used to create a [ServerTool](../api/tools.md#servertool) from the function.

```python
from wayflowcore.tools import tool


@tool(description_mode="only_docstring")
def local_get_pr_diff_tool(repo_dirpath: str) -> str:
    """
    Retrieves code diff with a git command given the
    path to the repository root folder.
    """
    import subprocess

    result = subprocess.run(
        ["git", "diff", "HEAD"],
        capture_output=True,
        cwd=repo_dirpath,
        text=True,
    )
    return result.stdout.strip()
```

### Building the steps and the sub-flow

Let’s write the code for the first sub-flow.

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import RegexExtractionStep, StartStep, ToolExecutionStep

# IO Variable Names
REPO_DIRPATH_IO = "$repo_dirpath_io"
PR_DIFF_IO = "$raw_pr_diff"
FILE_DIFF_LIST_IO = "$file_diff_list"

# Define the steps

start_step = StartStep(name="start_step", input_descriptors=[StringProperty(name=REPO_DIRPATH_IO)])

# Step 1: Retrieve the pull request diff using the local tool
get_pr_diff_step = ToolExecutionStep(
    name="get_pr_diff",
    tool=local_get_pr_diff_tool,
    raise_exceptions=True,
    input_mapping={"repo_dirpath": REPO_DIRPATH_IO},
    output_mapping={ToolExecutionStep.TOOL_OUTPUT: PR_DIFF_IO},
)

# Step 2: Extract the file diffs from the raw diff using a regular expression
extract_into_list_of_file_diff_step = RegexExtractionStep(
    name="extract_into_list_of_file_diff",
    regex_pattern=r"(diff --git[\s\S]*?)(?=diff --git|$)",
    return_first_match_only=False,
    input_mapping={RegexExtractionStep.TEXT: PR_DIFF_IO},
    output_mapping={RegexExtractionStep.OUTPUT: FILE_DIFF_LIST_IO},
)

# Define the sub flow
retrieve_diff_subflow = Flow(
    name="Retrieve PR diff flow",
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=get_pr_diff_step),
        ControlFlowEdge(
            source_step=get_pr_diff_step, destination_step=extract_into_list_of_file_diff_step
        ),
        ControlFlowEdge(source_step=extract_into_list_of_file_diff_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            source_step=start_step,
            source_output=REPO_DIRPATH_IO,
            destination_step=get_pr_diff_step,
            destination_input=REPO_DIRPATH_IO,
        ),
        DataFlowEdge(
            source_step=get_pr_diff_step,
            source_output=PR_DIFF_IO,
            destination_step=extract_into_list_of_file_diff_step,
            destination_input=PR_DIFF_IO,
        ),
    ],
)
```

**API Reference:** [Flow](../api/flows.md#flow) | [RegexExtractionStep](../api/flows.md#regexextractionstep) | [ToolExecutionStep](../api/flows.md#toolexecutionstep) | **API Reference:** [tool](../api/tools.md#tooldecorator)

The code does the following:

1. It lists the names of the steps and input/output variables for the sub-flow.
2. It then creates the different steps within the sub-flow.
3. Finally, it instantiates the sub-flow. This will be covered in more detail later in the tutorial.

For clarity, the variable names are also prefixed with a dollar ($) sign. This is not necessary and is only done for code clarity. The variable
`REPO_DIRPATH_IO` is used to hold the file path to the sample codebase Git repository and you will use this to pass in the location of the
codebase Git repository.

Additionally, you can give explicit names to the input/output variables used in the Flow, e.g. “$repo_dirpath_io” for the variable holding the
path to the local repository. Finally, we define those explicit names as string variables (e.g. `REPO_DIRPATH_IO`) to minimize the number of
magic strings in the code.

#### SEE ALSO
To learn about the basics of Flows, check out our, [introductory tutorial on WayFlow Flows](basic_flow.md).

Now take a look at each of the steps used in the sub-flow in more detail.

#### Get the PR diff, `get_pr_diff_step`

This uses a `ToolExecutionStep` to gather the diff information - see the notes on how this is done earlier. When creating it, you need to
provide the following:

* `tool`: Specifies the tool that will called within the step. This is the tool that was created earlier, `local_get_pr_diff_tool`.
* `raise_exceptions`: Whether to raise exceptions generated by the tool that is called. Here it is set to `True` and so exceptions will be raised.
* `input_mapping`: Specifies the names used for the input parameters of the step. See [ToolExecutionStep](../api/flows.md#toolexecutionstep) for more details on using an `input_mapping` with this type of step.
* `output_mapping`: Specifies the name used foe the output parameter of the step. The name held in `PR_DIFF_IO` will be mapped to the name for the output parameter of the step. Again, see [ToolExecutionStep](../api/flows.md#toolexecutionstep) for more details on using an `output_mapping` with this type of step.

#### Extract file diffs into a list, `extract_into_list_of_file_diff_step`

You now have the diff information from the PR. This step performs a regex extraction on the raw diff text to extract the code to review.

Use a `RegexExtractionStep` to perform this action. When creating the step, you need to provide the following:

* `regex_pattern`: The regex pattern for the extraction. This uses `re.findall` underneath.
* `return_first_match_only`: You want to return all results, so set this to `False`.
* `input_mapping`: Specifies the names used for the input parameters of the step. The input parameter will be mapped to the name, held in `PR_DIFF_IO`. See [RegexExtractionStep](../api/flows.md#regexextractionstep) for more details on using an `input_mapping` with this type of step.
* `output_mapping`: Specifies the name used for the output parameter of the step. Here, the default name `RegexExtractionStep.TEXT` is renamed to the name defined in `PR_DIFF_IO`. Again, see [RegexExtractionStep](../api/flows.md#regexextractionstep) for more details on using an `output_mapping` with this type of step.

**About the pattern:**

```bash
(diff --git[\s\S]*?)(?=diff --git|$)
```

The pattern looks for text starting with `diff --git`, followed by any characters (both whitespace [s] and non-whitespace [S]), until it
encounters either another `diff --git` or the end of the text ($). However, it does not include the next `diff --git` or the end in the match.

The \*? makes it “lazy” or non-greedy, meaning it takes the shortest possible match, rather than the longest.

#### TIP
Recent Large Language Models are very helpful tools to create, debug and explain Regex patterns given a natural language
description.

Finally, create the sub-flow using the [Flow](../api/flows.md#flow) class. You specify the steps in the Flow, the starting step of the Flow, the transitions
between steps and how data, from the variables, is to pass from one step to the next.

The transitions between steps are defined with [ControlFlowEdges](../api/flows.md#controlflowedge). These take a source step and a destination step. Each
`ControlFlowEdge` maps one such transition.

Passing values between steps is a very common occurrence when building Flows. This is done using [DataFlowEdges](../api/flows.md#dataflowedge) which define
that a value is passed from one step to another.

Inputs to a step will most commonly be for parameters within a Jinja template, of which there are several examples of in this tutorial, or parameters to
callables used by tools. In a [DataFlowEdge](../api/flows.md#dataflowedge) you can use the name of the parameter, a string, to act as the destination of
a value that is being passed in. It is often less error-prone if you create a variable that is set to the name.

Similarly, when a value is the output of a step, such as when a user’s input is captured in an [InputMessageStep](../api/flows.md#inputmessagestep), the value is
available as a property of the step, for example `InputMessageStep.USER_PROVIDED_INPUT`. But, it lacks a meaningful name, so it is often helpful to
specify one. This is done using an `output_mapping` when creating the step. Again, you will want to create a variable to hold the name to avoid
errors.

### Defining a Flow

Defining the Flow is the last step in the code shown above. There are a couple of things that are worth highlighting:

* `begin_step`: A start step needs to be defined for a [Flow](../api/flows.md#flow).
* `control_flow_edges`: The transitions between the steps in the [Flow](../api/flows.md#flow) are defined as [ControlFlowEdges](../api/flows.md#controlflowedge). They have a `source_step`, which defines the start of a transition, and a `destination_step`, which defines the destination of a transition. All transitions for the flow will need to be defined.
* `data_flow_edges`: Maps the variables between steps connected by a transition using [DataFlowEdges](../api/flows.md#dataflowedge). It maps variables from a source step into variables in a destination step. You only need to do this for the variables that need to be passed between steps.

### Testing the flow

You can test this sub-flow by creating an assistant conversation with [`Flow.start_conversation()`](../api/flows.md#wayflowcore.flow.Flow.start_conversation) and specifying the inputs,
in this case the location of the Git repository. The conversation can then be executed with [`Conversation.execute()`](../api/conversation.md#wayflowcore.conversation.Conversation.execute).
This returns an object that represents the status of the conversation which you can check to confirm that the conversation has successfully finished.

The code below shows how the inputs are passed in. Set the `PATH_TO_DIR` to the actual path you extracted the sample codebase
Git repository to. You then extract the outputs from the conversation.

The full code for testing the sub-flow is shown below:

```python
from wayflowcore.executors.executionstatus import FinishedStatus

# Replace the path below with the path to your actual codebase sample git repository.
PATH_TO_DIR = "path/to/repository_root"

test_conversation = retrieve_diff_subflow.start_conversation(
    inputs={
        REPO_DIRPATH_IO: PATH_TO_DIR,
    }
)

execution_status = test_conversation.execute()

if not isinstance(execution_status, FinishedStatus):
    raise ValueError("Unexpected status type")

FILE_DIFF_LIST = execution_status.output_values[FILE_DIFF_LIST_IO]

print(FILE_DIFF_LIST[0])
```

**API Reference:** [Flow](../api/flows.md#flow)

## Part 3: Review the list of diffs

Now that we have a list of diffs for each file, we can review them and generate comments using an LLM.

This task can be broken into a sub-flow made up of five steps:

* [OutputMessageStep](../api/flows.md#outputmessagestep): This converts the file diff list into a string to be processed by the following steps.
* [ToolExecutionStep](../api/flows.md#toolexecutionstep): This prefixes the diffs with line numbers for additional context to the LLM.
* [RegexExtractionStep](../api/flows.md#regexextractionstep): This extracts the file path from the diff string.
* [PromptExecutionStep](../api/flows.md#promptexecutionstep): This generates comments using the LLM based on a list of user-defined checks.
* [ExtractValueFromJsonStep](../api/flows.md#extractvaluefromjsonstep): This extracts the comments and lines they apply to from the LLM output.

![Sub Flow to review the PR diffs](core/_static/usecases/prbot_generate_comment.svg)

### Build the tools and checks

Before creating the steps and sub-flow to generate the comments, it is important to define the list of checks
the assistant should perform, along with any specific instructions. Additionally, a tool must be created to prefix
the diffs with line numbers, allowing the LLM to determine where to add comments.

Below is the full code to achieve this. It is broken into sections so that you can see, in detail, what is happening in each part.

```python
PR_BOT_CHECKS = [
    """
Name: TODO_WITHOUT_TICKET
Description: TODO comments should reference a ticket number for tracking.
Example code:
```python
# TODO: Add validation here
def process_user_input(data):
    return data
```
Example comment:
[BOT] TODO_WITHOUT_TICKET: TODO comment should reference a ticket number for tracking (e.g., "TODO: Add validation here (TICKET-1234)").
""",
    """
Name: MUTABLE_DEFAULT_ARGUMENT
Description: Using mutable objects as default arguments can lead to unexpected behavior.
Example code:
```python
def add_item(item, items=[]):
    items.append(item)
    return items
```
Example comment:
[BOT] MUTABLE_DEFAULT_ARGUMENT: Avoid using mutable default arguments. Use None and initialize in the function: `def add_item(item, items=None): items = items or []`
""",
    """
Name: NON_DESCRIPTIVE_NAME
Description: Variable names should clearly indicate their purpose or content.
Example code:
```python
def process(lst):
    res = []
    for i in lst:
        res.append(i * 2)
    return res
```
Example comment:
[BOT] NON_DESCRIPTIVE_NAME: Use more descriptive names: 'lst' could be 'numbers', 'res' could be 'doubled_numbers', 'i' could be 'number'
""",
]

CONCATENATED_CHECKS = "\n\n---\n\n".join(check for check in PR_BOT_CHECKS)

PROMPT_TEMPLATE = """You are a very experienced code reviewer. You are given a git diff on a file: {{filename}}

## Context
The git diff contains all changes of a single file. All lines are prepended with their number. Lines without line number where removed from the file.
After the line number, a line that was changed has a "+" before the code. All lines without a "+" are just here for context, you will not comment on them.

## Input
### Code diff
{{diff}}

## Task
Your task is to review these changes, according to different rules. Only comment lines that were added, so the lines that have a + just after the line number.
The rules are the following:

{{checks}}

### Response Format
You need to return a review as a json as follows:
```json
[
    {
        "content": "the comment as a text",
        "suggestion": "if the change you propose is a single line, then put here the single line rewritten that includes your proposal change. IMPORTANT: a single line, which will erase the current line. Put empty string if no suggestion of if the suggestion is more than a single line",
        "line": "line number where the comment applies"
    },
    …
]
```
Please use triple backticks ``` to delimitate your JSON list of comments. Don't output more than 5 comments, only comment the most relevant sections.
If there are no comments and the code seems fine, just output an empty JSON list."""


@tool(description_mode="only_docstring")
def format_git_diff(diff_text: str) -> str:
    """
    Formats a git diff by adding line numbers to each line except removal lines.
    """

    def pad_number(number: int, width: int) -> str:
        """Right-align a number with specified width using space padding."""
        return str(number).rjust(width)

    LINE_NUMBER_WIDTH = 5
    PADDING_WIDTH = LINE_NUMBER_WIDTH + 1
    current_line_number = 0
    formatted_lines = []

    for line in diff_text.split("\n"):
        # Handle diff header lines (e.g., "@@ -1,7 +1,6 @@")
        if line.startswith("@@"):
            try:
                # Extract the starting line number and line count
                _, position_info, _ = line.split("@@")
                new_file_info = position_info.split()[1][1:]  # Remove the '+' prefix
                start_line, line_count = map(int, new_file_info.split(","))

                current_line_number = start_line
                formatted_lines.append(line)
                continue

            except (ValueError, IndexError):
                raise ValueError(f"Invalid diff header format: {line}")

        # Handle content lines
        if current_line_number > 0 and line:
            if not line.startswith("-"):
                # Add line number for added/context lines
                line_prefix = pad_number(current_line_number, LINE_NUMBER_WIDTH)
                formatted_lines.append(f"{line_prefix} {line}")
                current_line_number += 1
            else:
                # Just add padding for removal lines
                formatted_lines.append(" " * PADDING_WIDTH + line)

    return "\n".join(formatted_lines)
```

**API Reference:** [ExtractValueFromJsonStep](../api/flows.md#extractvaluefromjsonstep) | [MapStep](../api/flows.md#mapstep) |
[OutputMessageStep](../api/flows.md#outputmessagestep) | [PromptExecutionStep](../api/flows.md#promptexecutionstep) | [ToolExecutionStep](../api/flows.md#toolexecutionstep)

#### Checks and LLM instructions

You will use three simple checks that are shown below. For each check you specify a name, a description of what the LLM should be checking,
as well as a code and expected comment example so that the LLM gets a better understanding of what the task is about.

The prompt uses a simple structure:

1. **Role Definition**: Define who/what you want the LLM to act as (e.g., “You are a very experienced code reviewer”).
2. **Context Section**: Provide relevant background information or specific circumstances that frame the task.
3. **Input Section**: Specify the exact information, data, or materials that the LLM will be provided with.
4. **Task Section**: Clearly state what you want the LLM to do with the input provided.
5. **Response Format Section**: Define how you want the response to be structured or formatted (e.g., bullet points, JSON, with XML tags, and so on).

The prompts are defined in the array, `PR_BOT_CHECKS`. The individual prompts for the checks are then concatenated into a single string,
`CONCATENATED_CHECKS`, so that it can be used inside the system prompt you will be passing to the LLM.

Define a system prompt, or prompt template, `PROMPT_TEMPLATE`. It contains placeholders for the diff and the checks that will be replaced
when specialising the prompt for each diff.

#### TIP
**How to write high-quality prompts**

There is no consensus on what makes the best LLM prompt. However, it is noted that for recent LLMs, a great strategy
to use to prompt an LLM is simply to be very specific about the task to be solved, giving enough context and explaining
potential edge cases to consider.

Given a prompt, try to determine whether giving the set of instructions to an experienced colleague, that has no prior
context about the task, to solve would be sufficient for them to get to the intended result.

#### Diff formatting tool

You next need to create a tool using the [ServerTool](../api/tools.md#servertool) to format the diffs in a manner that makes them consumable
by the LLM. A tool, as you will have already seen, is a simple wrapper around a `python` callable that makes it useable within a flow.

The function, `format_git_diff`, in the code above does the work of formatting the diffs.

#### SEE ALSO
For more information about WayFlow tools please read our guide, [How to use tools](../howtoguides/howto_build_assistants_with_tools.md).

### Building the steps and the sub-flow

With the prompts and diff formatting tool written you can now build the second sub-flow.
This sub-flow will iterate over the diffs, generated previously, and then use an LLM to generate review comments from them.

```python
from wayflowcore._utils._templating_helpers import render_template_partially
from wayflowcore.property import AnyProperty, DictProperty, ListProperty, StringProperty
from wayflowcore.steps import (
    ExtractValueFromJsonStep,
    MapStep,
    OutputMessageStep,
    PromptExecutionStep,
    ToolExecutionStep,
)

# IO Variable Names
DIFF_TO_STRING_IO = "$diff_to_string"
DIFF_WITH_LINES_IO = "$diff_with_lines"
FILEPATH_IO = "$filename"
JSON_COMMENTS_IO = "$json_comments"
EXTRACTED_COMMENTS_IO = "$extracted_comments"
NESTED_COMMENT_LIST_IO = "$nested_comment_list"
FILEPATH_LIST_IO = "$filepath_list"

# Define the steps

# Step 1: Format the diff to a string
format_diff_to_string_step = OutputMessageStep(
    name="format_diff_to_string",
    message_template="{{ message | string }}",
    output_mapping={OutputMessageStep.OUTPUT: DIFF_TO_STRING_IO},
)

# Step 2: Add lines on the diff using a tool
add_lines_on_diff_step = ToolExecutionStep(
    name="add_lines_on_diff",
    tool=format_git_diff,
    input_mapping={"diff_text": DIFF_TO_STRING_IO},
    output_mapping={ToolExecutionStep.TOOL_OUTPUT: DIFF_WITH_LINES_IO},
)

# Step 3: Extract the file path from the diff string using a regular expression
extract_file_path_step = RegexExtractionStep(
    name="extract_file_path",
    regex_pattern=r"diff --git src://(.+?) dst://",
    return_first_match_only=True,
    input_mapping={RegexExtractionStep.TEXT: DIFF_TO_STRING_IO},
    output_mapping={RegexExtractionStep.OUTPUT: FILEPATH_IO},
)

# Step 4: Generate comments using a prompt
generate_comments_step = PromptExecutionStep(
    name="generate_comments",
    prompt_template=render_template_partially(PROMPT_TEMPLATE, {"checks": CONCATENATED_CHECKS}),
    llm=llm,
    input_mapping={"diff": DIFF_WITH_LINES_IO, "filename": FILEPATH_IO},
    output_mapping={PromptExecutionStep.OUTPUT: JSON_COMMENTS_IO},
)

# Step 5: Extract comments from the JSON output
# Define the value type for extracted comments
comments_valuetype = ListProperty(
    name="values",
    description="The extracted comments content and line number",
    item_type=DictProperty(value_type=AnyProperty()),
    default_value=[],
)
extract_comments_from_json_step = ExtractValueFromJsonStep(
    name="extract_comments_from_json",
    output_values={comments_valuetype: '[.[] | {"content": .["content"], "line": .["line"]}]'},
    retry=True,
    llm=llm,
    input_mapping={ExtractValueFromJsonStep.TEXT: JSON_COMMENTS_IO},
    output_mapping={"values": EXTRACTED_COMMENTS_IO},
)

# Define the sub flow to generate comments for each file diff
generate_comments_subflow = Flow(
    name="Generate review comments flow",
    begin_step=format_diff_to_string_step,
    control_flow_edges=[
        ControlFlowEdge(format_diff_to_string_step, add_lines_on_diff_step),
        ControlFlowEdge(add_lines_on_diff_step, extract_file_path_step),
        ControlFlowEdge(extract_file_path_step, generate_comments_step),
        ControlFlowEdge(generate_comments_step, extract_comments_from_json_step),
        ControlFlowEdge(extract_comments_from_json_step, None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            format_diff_to_string_step, DIFF_TO_STRING_IO, add_lines_on_diff_step, DIFF_TO_STRING_IO
        ),
        DataFlowEdge(
            format_diff_to_string_step, DIFF_TO_STRING_IO, extract_file_path_step, DIFF_TO_STRING_IO
        ),
        DataFlowEdge(
            add_lines_on_diff_step, DIFF_WITH_LINES_IO, generate_comments_step, DIFF_WITH_LINES_IO
        ),
        DataFlowEdge(extract_file_path_step, FILEPATH_IO, generate_comments_step, FILEPATH_IO),
        DataFlowEdge(
            generate_comments_step,
            JSON_COMMENTS_IO,
            extract_comments_from_json_step,
            JSON_COMMENTS_IO,
        ),
    ],
)

# Use the MapStep to apply the sub flow to each file
for_each_file_step = MapStep(
    flow=generate_comments_subflow,
    unpack_input={"message": "."},
    input_mapping={MapStep.ITERATED_INPUT: FILE_DIFF_LIST_IO},
    output_descriptors=[
        ListProperty(name=NESTED_COMMENT_LIST_IO, item_type=AnyProperty()),
        ListProperty(name=FILEPATH_LIST_IO, item_type=StringProperty()),
    ],
    output_mapping={EXTRACTED_COMMENTS_IO: NESTED_COMMENT_LIST_IO, FILEPATH_IO: FILEPATH_LIST_IO},
)

generate_all_comments_subflow = Flow.from_steps([for_each_file_step])
```

**API Reference:** [Property](../api/flows.md#property) | [ListProperty](../api/flows.md#listproperty) | [DictProperty](../api/flows.md#dictproperty) | [StringProperty](../api/flows.md#stringproperty) |
[ExtractValueFromJsonStep](../api/flows.md#extractvaluefromjsonstep) | [MapStep](../api/flows.md#mapstep) | [OutputMessageStep](../api/flows.md#outputmessagestep) | [PromptExecutionStep](../api/flows.md#promptexecutionstep) | [ToolExecutionStep](../api/flows.md#toolexecutionstep)

Take a look at each of the steps used in the sub-flow to get an understanding of what is happening.

#### Format diff to string, `format_diff_to_string_step`

This step converts the file diff list into a string so that it can be used by the following steps.

This is done with the `string` Jinja filter as follows: `{{ message | string }}`. It uses an [OutputMessageStep](../api/flows.md#outputmessagestep)
to achieve this.

#### NOTE
Jinja templating introduces security concerns that are addressed by WayFlow by restricting Jinja’s rendering capabilities.
Please check our guide on [How to write secure prompts with Jinja templating](../howtoguides/howto_promptexecutionstep.md#securejinjatemplating) for more information.

#### Add lines to the diff, `add_lines_on_diff_step`

This step prefixes the diff with the line numbers required to review comments. It uses a, [ToolExecutionStep](../api/flows.md#toolexecutionstep), to run the
tool that you previously defined in order to do this.

The input to the tool, within the I/O dictionary, is specified using the `input_mapping`. For all these steps, it is important to remember
that the outputs of one step are linked to the inputs of the next.

#### Extract file path, `extract_file_path_step`

This extracts the file path from the diff string. The file path is needed for assigning the review comments. The [RegexExtractionStep](../api/flows.md#regexextractionstep) step
is used to extract the file path from the diff.

The regular expression is applied to the diff string, extracted form the input map using the `input_mapping` parameter.

Note: Compared to the [RegexExtractionStep](../api/flows.md#regexextractionstep) used in Part 1, here only the first match is required.

#### Generate comments, `generate_comments_step`

This generates comments using the LLM and the prompt template defined earlier. The [PromptExecutionStep](../api/flows.md#promptexecutionstep) step executes
the prompt with the LLM defined earlier in this tutorial.

Since the list of checks has already been defined, the template can be pre-rendered using the `render_template_partially` method. This renders the parts of the
template that have been provided, while the remaining information is gathered from the I/O dictionary.

#### Extract comments from JSON, `extract_comments_from_json_step`

This extracts the comments and line numbers from the generated LLM output, which is a serialized JSON structure due to the prompt used.
A [ExtractValueFromJsonStep](../api/flows.md#extractvaluefromjsonstep) is used to do the extraction. When creating the step, specify the following in
addition to the usual `input_mapping` and `output_mapping`:

* `output_values`: This defines the [JQ](https://jqlang.github.io/jq/) query to extract the comments form the JSON generated by the LLM.
* `llms`: An LLM that can be used to help resolve any parsing errors. This is related to `retry`.
* `retry`: If parsing fails, you may want to retry. This is set to `True`, which results in trying to use the LLM to help resolve any such issues.

#### Create the sub-flow, `generate_comments_subflow`

Here you define what steps are in the sub-flow, what the transitions between the steps are and what will be the starting step. This is exactly
the same process you did previously when defining the sub-flow to fetch the PR data.

#### Applying the comment generation to all file diffs

Now that you have the sub-flow create, you need to apply it to every file diff. This is done using a [MapStep](../api/flows.md#mapstep).
`MapStep` takes a sub-flow as input, in this case, the `generate_comments_subflow`, and applies it to an iterable—in this case, the list of file
diffs.

You simply specify:

* `flow`: The sub-flow to map, that is applied to the iterable.
* `unpack_input`: Defines how to unpack the input. A [JQ](https://jqlang.github.io/jq/)  query can be used to transform the input, but in this case, it is kept as a list.
* `input_mapping`: Defines what the sub-flow will iterate over. The key, `MapStep.ITERATED_INPUT`, is used to pass in the diffs.
* `output_descriptors`: Specifies the values to collect from the output generated by applying the sub-flow. In this case, these will be the generated comments and the associated file path.

#### NOTE
The [MapStep](../api/flows.md#mapstep) works similarly to how the Python map function works. For more information, see
[https://docs.python.org/3/library/functions.html#map](https://docs.python.org/3/library/functions.html#map)

Finally, create the sub-flow to generate all comments using the helper method `create_single_step_flow`.

### Testing the sub-flow

You can test the sub-flow by creating a conversation, as shown in the code below, and specifying the inputs as done in, `Part 2: Retrieve the PR diff information`.

Since each sub-flow is tested independently, you can reuse the output from the first sub-flow.

```python
# we reuse the FILE_DIFF_LIST from the previous test
test_conversation = generate_all_comments_subflow.start_conversation(
    inputs={
        FILE_DIFF_LIST_IO: FILE_DIFF_LIST,
    }
)

execution_status = test_conversation.execute()

if not isinstance(execution_status, FinishedStatus):
    raise ValueError("Unexpected status type")

NESTED_COMMENT_LIST = execution_status.output_values[NESTED_COMMENT_LIST_IO]
FILEPATH_LIST = execution_status.output_values[FILEPATH_LIST_IO]
print(NESTED_COMMENT_LIST[0])
print(FILEPATH_LIST)
```

## Building the final Flow

Congratulations! You have completed the three sub-flows, which, when combined into a single flow, will retrieve the PR diff information,
generate comments on the diffs using an LLM.

You will wire the sub-flows that you have built together by wrapping them in a [FlowExecutionStep](../api/flows.md#flowexecutionstep). The
[FlowExecutionSteps](../api/flows.md#flowexecutionstep) are then composed into the final combined Flow.

The code for this is shown below:

```python
from wayflowcore.steps import FlowExecutionStep


# Steps
retrieve_diff_flowstep = FlowExecutionStep(name="retrieve_diff_flowstep", flow=retrieve_diff_subflow)
generate_all_comments_flowstep = FlowExecutionStep(
    name="generate_comments_flowstep",
    flow=generate_all_comments_subflow,
)

pr_bot = Flow(
    name="PR bot flow",
    begin_step=retrieve_diff_flowstep,
    control_flow_edges=[
        ControlFlowEdge(retrieve_diff_flowstep, generate_all_comments_flowstep),
        ControlFlowEdge(generate_all_comments_flowstep, None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            retrieve_diff_flowstep,
            FILE_DIFF_LIST_IO,
            generate_all_comments_flowstep,
            FILE_DIFF_LIST_IO,
        )
    ],
)
```

**API Reference:** [Flow](../api/flows.md#flow) | [FlowExecutionStep](../api/flows.md#flowexecutionstep)

### Testing the combined assistant

You can now run the PR bot end-to-end on your repo or locally.

Set the `PATH_TO_DIR` to the actual path you extracted the sample codebase Git repository to. You can also see how the output of the conversation
is extracted from the `execution_status` object, `execution_status.output_values`.

```python
# Replace the path below with the path to your actual codebase sample git repository.
PATH_TO_DIR = "path/to/repository_root"

conversation = pr_bot.start_conversation(inputs={REPO_DIRPATH_IO: PATH_TO_DIR})

execution_status = conversation.execute()

if not isinstance(execution_status, FinishedStatus):
    raise ValueError("Unexpected status type")

print(execution_status.output_values)

NESTED_COMMENT_LIST = execution_status.output_values[NESTED_COMMENT_LIST_IO]
```

## Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(pr_bot)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "Flow",
  "id": "9c65246d-a0dd-4ec4-801d-afd640b2488e",
  "name": "PR bot flow",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [
    {
      "type": "string",
      "title": "$repo_dirpath_io"
    }
  ],
  "outputs": [
    {
      "type": "array",
      "items": {
        "type": "string"
      },
      "title": "$filepath_list"
    },
    {
      "type": "array",
      "items": {},
      "title": "$nested_comment_list"
    },
    {
      "type": "string",
      "title": "$raw_pr_diff"
    },
    {
      "description": "the list of extracted value using the regex \"(diff --git[\\s\\S]*?)(?=diff --git|$)\" from the raw input",
      "type": "array",
      "items": {
        "type": "string"
      },
      "title": "$file_diff_list",
      "default": []
    }
  ],
  "start_node": {
    "$component_ref": "020c885e-6d0b-472a-bb91-246ab70ab1db"
  },
  "nodes": [
    {
      "$component_ref": "47e367be-4d74-49dc-ac3b-89bb97ffa7df"
    },
    {
      "$component_ref": "43d58c76-23a0-4d10-943d-f9c5e0835a7c"
    },
    {
      "$component_ref": "020c885e-6d0b-472a-bb91-246ab70ab1db"
    },
    {
      "$component_ref": "a544af64-e63b-4ccf-9ab0-8d25cdbc0b93"
    }
  ],
  "control_flow_connections": [
    {
      "component_type": "ControlFlowEdge",
      "id": "a5c123ff-c14c-4291-b174-61d61170f187",
      "name": "retrieve_diff_flowstep_to_generate_comments_flowstep_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "47e367be-4d74-49dc-ac3b-89bb97ffa7df"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "43d58c76-23a0-4d10-943d-f9c5e0835a7c"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "8a10b23a-2d0c-46c4-82ac-e66ad0b9399b",
      "name": "__StartStep___to_retrieve_diff_flowstep_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "020c885e-6d0b-472a-bb91-246ab70ab1db"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "47e367be-4d74-49dc-ac3b-89bb97ffa7df"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "dac07720-8a5a-4a61-b1e7-50be506ed937",
      "name": "generate_comments_flowstep_to_None End node_control_flow_edge",
      "description": null,
      "metadata": {},
      "from_node": {
        "$component_ref": "43d58c76-23a0-4d10-943d-f9c5e0835a7c"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "a544af64-e63b-4ccf-9ab0-8d25cdbc0b93"
      }
    }
  ],
  "data_flow_connections": [
    {
      "component_type": "DataFlowEdge",
      "id": "7b12dfed-309b-46ff-8a2d-bb6f2a3154b6",
      "name": "retrieve_diff_flowstep_$file_diff_list_to_generate_comments_flowstep_$file_diff_list_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "47e367be-4d74-49dc-ac3b-89bb97ffa7df"
      },
      "source_output": "$file_diff_list",
      "destination_node": {
        "$component_ref": "43d58c76-23a0-4d10-943d-f9c5e0835a7c"
      },
      "destination_input": "$file_diff_list"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "51122844-22d3-40a8-b652-1b020ce24945",
      "name": "__StartStep___$repo_dirpath_io_to_retrieve_diff_flowstep_$repo_dirpath_io_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "020c885e-6d0b-472a-bb91-246ab70ab1db"
      },
      "source_output": "$repo_dirpath_io",
      "destination_node": {
        "$component_ref": "47e367be-4d74-49dc-ac3b-89bb97ffa7df"
      },
      "destination_input": "$repo_dirpath_io"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "72aa469c-98cd-4f0d-9496-0aa454373aef",
      "name": "generate_comments_flowstep_$filepath_list_to_None End node_$filepath_list_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "43d58c76-23a0-4d10-943d-f9c5e0835a7c"
      },
      "source_output": "$filepath_list",
      "destination_node": {
        "$component_ref": "a544af64-e63b-4ccf-9ab0-8d25cdbc0b93"
      },
      "destination_input": "$filepath_list"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "eac1b375-1541-41f7-87f3-f3e626cc2c9c",
      "name": "generate_comments_flowstep_$nested_comment_list_to_None End node_$nested_comment_list_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "43d58c76-23a0-4d10-943d-f9c5e0835a7c"
      },
      "source_output": "$nested_comment_list",
      "destination_node": {
        "$component_ref": "a544af64-e63b-4ccf-9ab0-8d25cdbc0b93"
      },
      "destination_input": "$nested_comment_list"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "0869acb5-4d8f-4b17-b59b-3b915912b628",
      "name": "retrieve_diff_flowstep_$raw_pr_diff_to_None End node_$raw_pr_diff_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "47e367be-4d74-49dc-ac3b-89bb97ffa7df"
      },
      "source_output": "$raw_pr_diff",
      "destination_node": {
        "$component_ref": "a544af64-e63b-4ccf-9ab0-8d25cdbc0b93"
      },
      "destination_input": "$raw_pr_diff"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "9fb2ab9e-ece1-4195-8f51-ef618dcb72bb",
      "name": "retrieve_diff_flowstep_$file_diff_list_to_None End node_$file_diff_list_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "47e367be-4d74-49dc-ac3b-89bb97ffa7df"
      },
      "source_output": "$file_diff_list",
      "destination_node": {
        "$component_ref": "a544af64-e63b-4ccf-9ab0-8d25cdbc0b93"
      },
      "destination_input": "$file_diff_list"
    }
  ],
  "$referenced_components": {
    "43d58c76-23a0-4d10-943d-f9c5e0835a7c": {
      "component_type": "FlowNode",
      "id": "43d58c76-23a0-4d10-943d-f9c5e0835a7c",
      "name": "generate_comments_flowstep",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "iterated input for the map step",
          "type": "array",
          "items": {
            "description": "\"message\" input variable for the template",
            "title": "message"
          },
          "title": "$file_diff_list"
        }
      ],
      "outputs": [
        {
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "$filepath_list"
        },
        {
          "type": "array",
          "items": {},
          "title": "$nested_comment_list"
        }
      ],
      "branches": [
        "next"
      ],
      "subflow": {
        "component_type": "Flow",
        "id": "f95e0e5d-f573-4e25-9d68-8508371246f9",
        "name": "flow_028a7dfb__auto",
        "description": "",
        "metadata": {
          "__metadata_info__": {}
        },
        "inputs": [
          {
            "description": "iterated input for the map step",
            "type": "array",
            "items": {
              "description": "\"message\" input variable for the template",
              "title": "message"
            },
            "title": "$file_diff_list"
          }
        ],
        "outputs": [
          {
            "type": "array",
            "items": {
              "type": "string"
            },
            "title": "$filepath_list"
          },
          {
            "type": "array",
            "items": {},
            "title": "$nested_comment_list"
          }
        ],
        "start_node": {
          "$component_ref": "367ae568-317d-42ec-ae70-4c41afe0dbd0"
        },
        "nodes": [
          {
            "$component_ref": "f127a297-842d-4d17-bc89-4704019458d7"
          },
          {
            "$component_ref": "367ae568-317d-42ec-ae70-4c41afe0dbd0"
          },
          {
            "$component_ref": "6f62aecf-03a1-4e38-b551-8eef0efaf4bb"
          }
        ],
        "control_flow_connections": [
          {
            "component_type": "ControlFlowEdge",
            "id": "85a2cdff-6ad4-4f58-8d1c-c8deeb05880c",
            "name": "__StartStep___to_step_0_control_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "from_node": {
              "$component_ref": "367ae568-317d-42ec-ae70-4c41afe0dbd0"
            },
            "from_branch": null,
            "to_node": {
              "$component_ref": "f127a297-842d-4d17-bc89-4704019458d7"
            }
          },
          {
            "component_type": "ControlFlowEdge",
            "id": "396e218f-225e-4e36-a33c-a176ca77d345",
            "name": "step_0_to_None End node_control_flow_edge",
            "description": null,
            "metadata": {},
            "from_node": {
              "$component_ref": "f127a297-842d-4d17-bc89-4704019458d7"
            },
            "from_branch": null,
            "to_node": {
              "$component_ref": "6f62aecf-03a1-4e38-b551-8eef0efaf4bb"
            }
          }
        ],
        "data_flow_connections": [
          {
            "component_type": "DataFlowEdge",
            "id": "6c8b8f78-b587-49ff-a401-6262cdafb0ee",
            "name": "__StartStep___$file_diff_list_to_step_0_$file_diff_list_data_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "source_node": {
              "$component_ref": "367ae568-317d-42ec-ae70-4c41afe0dbd0"
            },
            "source_output": "$file_diff_list",
            "destination_node": {
              "$component_ref": "f127a297-842d-4d17-bc89-4704019458d7"
            },
            "destination_input": "$file_diff_list"
          },
          {
            "component_type": "DataFlowEdge",
            "id": "84d3a783-38c8-4d53-bc0b-4205732d1fbf",
            "name": "step_0_$filepath_list_to_None End node_$filepath_list_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
              "$component_ref": "f127a297-842d-4d17-bc89-4704019458d7"
            },
            "source_output": "$filepath_list",
            "destination_node": {
              "$component_ref": "6f62aecf-03a1-4e38-b551-8eef0efaf4bb"
            },
            "destination_input": "$filepath_list"
          },
          {
            "component_type": "DataFlowEdge",
            "id": "b7ffd4c3-4a03-47f0-95fc-0ba670010729",
            "name": "step_0_$nested_comment_list_to_None End node_$nested_comment_list_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
              "$component_ref": "f127a297-842d-4d17-bc89-4704019458d7"
            },
            "source_output": "$nested_comment_list",
            "destination_node": {
              "$component_ref": "6f62aecf-03a1-4e38-b551-8eef0efaf4bb"
            },
            "destination_input": "$nested_comment_list"
          }
        ],
        "$referenced_components": {
          "f127a297-842d-4d17-bc89-4704019458d7": {
            "component_type": "ExtendedMapNode",
            "id": "f127a297-842d-4d17-bc89-4704019458d7",
            "name": "step_0",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "description": "iterated input for the map step",
                "type": "array",
                "items": {
                  "description": "\"message\" input variable for the template",
                  "title": "message"
                },
                "title": "$file_diff_list"
              }
            ],
            "outputs": [
              {
                "type": "array",
                "items": {},
                "title": "$nested_comment_list"
              },
              {
                "type": "array",
                "items": {
                  "type": "string"
                },
                "title": "$filepath_list"
              }
            ],
            "branches": [
              "next"
            ],
            "input_mapping": {
              "iterated_input": "$file_diff_list"
            },
            "output_mapping": {
              "$extracted_comments": "$nested_comment_list",
              "$filename": "$filepath_list"
            },
            "flow": {
              "component_type": "Flow",
              "id": "3da67cce-b8de-40be-bb8d-e1edead178f0",
              "name": "Generate review comments flow",
              "description": "",
              "metadata": {
                "__metadata_info__": {}
              },
              "inputs": [
                {
                  "description": "\"message\" input variable for the template",
                  "title": "message"
                }
              ],
              "outputs": [
                {
                  "description": "The extracted comments content and line number",
                  "type": "array",
                  "items": {
                    "type": "object",
                    "additionalProperties": {},
                    "key_type": {
                      "type": "string"
                    }
                  },
                  "title": "$extracted_comments"
                },
                {
                  "description": "the generated text",
                  "type": "string",
                  "title": "$json_comments"
                },
                {
                  "type": "string",
                  "title": "$diff_with_lines"
                },
                {
                  "description": "the first extracted value using the regex \"diff --git a/(.+?) b/\" from the raw input",
                  "type": "string",
                  "title": "$filename",
                  "default": ""
                },
                {
                  "description": "the message added to the messages list",
                  "type": "string",
                  "title": "$diff_to_string"
                }
              ],
              "start_node": {
                "$component_ref": "e20f5870-d594-4089-9fcd-08146232910d"
              },
              "nodes": [
                {
                  "$component_ref": "f0fb3ab4-a950-43b6-a583-6f0044f18c7f"
                },
                {
                  "$component_ref": "6000ee3f-ac80-4937-b36c-94fd65cdcda4"
                },
                {
                  "$component_ref": "6f6dc822-9352-47ae-9b48-173402a334fe"
                },
                {
                  "$component_ref": "0ce752d7-3ef1-481b-bb01-c7081ef86103"
                },
                {
                  "$component_ref": "48057b9c-bee7-4286-baf5-625b6f1a6f1a"
                },
                {
                  "$component_ref": "e20f5870-d594-4089-9fcd-08146232910d"
                },
                {
                  "$component_ref": "39f36227-8910-414c-8b6b-517c0d65b0d8"
                }
              ],
              "control_flow_connections": [
                {
                  "component_type": "ControlFlowEdge",
                  "id": "becf6951-96fd-4152-97d0-4a4eff042a29",
                  "name": "format_diff_to_string_to_add_lines_on_diff_control_flow_edge",
                  "description": null,
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "from_node": {
                    "$component_ref": "f0fb3ab4-a950-43b6-a583-6f0044f18c7f"
                  },
                  "from_branch": null,
                  "to_node": {
                    "$component_ref": "6000ee3f-ac80-4937-b36c-94fd65cdcda4"
                  }
                },
                {
                  "component_type": "ControlFlowEdge",
                  "id": "c197b0d5-8002-4910-ae8d-61f97f1f8f26",
                  "name": "add_lines_on_diff_to_extract_file_path_control_flow_edge",
                  "description": null,
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "from_node": {
                    "$component_ref": "6000ee3f-ac80-4937-b36c-94fd65cdcda4"
                  },
                  "from_branch": null,
                  "to_node": {
                    "$component_ref": "6f6dc822-9352-47ae-9b48-173402a334fe"
                  }
                },
                {
                  "component_type": "ControlFlowEdge",
                  "id": "406e0670-cc49-4da4-8d15-8c1c320193e8",
                  "name": "extract_file_path_to_generate_comments_control_flow_edge",
                  "description": null,
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "from_node": {
                    "$component_ref": "6f6dc822-9352-47ae-9b48-173402a334fe"
                  },
                  "from_branch": null,
                  "to_node": {
                    "$component_ref": "0ce752d7-3ef1-481b-bb01-c7081ef86103"
                  }
                },
                {
                  "component_type": "ControlFlowEdge",
                  "id": "e54eb347-2e6c-42c4-a7d6-a42c8059bdf3",
                  "name": "generate_comments_to_extract_comments_from_json_control_flow_edge",
                  "description": null,
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "from_node": {
                    "$component_ref": "0ce752d7-3ef1-481b-bb01-c7081ef86103"
                  },
                  "from_branch": null,
                  "to_node": {
                    "$component_ref": "48057b9c-bee7-4286-baf5-625b6f1a6f1a"
                  }
                },
                {
                  "component_type": "ControlFlowEdge",
                  "id": "ebe5e60b-2724-4b51-b287-79f3e8e7fdd1",
                  "name": "__StartStep___to_format_diff_to_string_control_flow_edge",
                  "description": null,
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "from_node": {
                    "$component_ref": "e20f5870-d594-4089-9fcd-08146232910d"
                  },
                  "from_branch": null,
                  "to_node": {
                    "$component_ref": "f0fb3ab4-a950-43b6-a583-6f0044f18c7f"
                  }
                },
                {
                  "component_type": "ControlFlowEdge",
                  "id": "98e7631e-7206-4ba9-b5b0-eb308ac89c0f",
                  "name": "extract_comments_from_json_to_None End node_control_flow_edge",
                  "description": null,
                  "metadata": {},
                  "from_node": {
                    "$component_ref": "48057b9c-bee7-4286-baf5-625b6f1a6f1a"
                  },
                  "from_branch": null,
                  "to_node": {
                    "$component_ref": "39f36227-8910-414c-8b6b-517c0d65b0d8"
                  }
                }
              ],
              "data_flow_connections": [
                {
                  "component_type": "DataFlowEdge",
                  "id": "ab8ed6de-3ea7-424e-a830-bca10ac57a32",
                  "name": "format_diff_to_string_$diff_to_string_to_add_lines_on_diff_$diff_to_string_data_flow_edge",
                  "description": null,
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "source_node": {
                    "$component_ref": "f0fb3ab4-a950-43b6-a583-6f0044f18c7f"
                  },
                  "source_output": "$diff_to_string",
                  "destination_node": {
                    "$component_ref": "6000ee3f-ac80-4937-b36c-94fd65cdcda4"
                  },
                  "destination_input": "$diff_to_string"
                },
                {
                  "component_type": "DataFlowEdge",
                  "id": "3caaa171-9b4b-44df-8ebd-4d060329f91a",
                  "name": "format_diff_to_string_$diff_to_string_to_extract_file_path_$diff_to_string_data_flow_edge",
                  "description": null,
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "source_node": {
                    "$component_ref": "f0fb3ab4-a950-43b6-a583-6f0044f18c7f"
                  },
                  "source_output": "$diff_to_string",
                  "destination_node": {
                    "$component_ref": "6f6dc822-9352-47ae-9b48-173402a334fe"
                  },
                  "destination_input": "$diff_to_string"
                },
                {
                  "component_type": "DataFlowEdge",
                  "id": "cdf0945b-5a96-42ff-b410-f7c56b5f8e45",
                  "name": "add_lines_on_diff_$diff_with_lines_to_generate_comments_$diff_with_lines_data_flow_edge",
                  "description": null,
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "source_node": {
                    "$component_ref": "6000ee3f-ac80-4937-b36c-94fd65cdcda4"
                  },
                  "source_output": "$diff_with_lines",
                  "destination_node": {
                    "$component_ref": "0ce752d7-3ef1-481b-bb01-c7081ef86103"
                  },
                  "destination_input": "$diff_with_lines"
                },
                {
                  "component_type": "DataFlowEdge",
                  "id": "ca6ed62b-6f6a-405f-9f16-5e1304de6608",
                  "name": "extract_file_path_$filename_to_generate_comments_$filename_data_flow_edge",
                  "description": null,
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "source_node": {
                    "$component_ref": "6f6dc822-9352-47ae-9b48-173402a334fe"
                  },
                  "source_output": "$filename",
                  "destination_node": {
                    "$component_ref": "0ce752d7-3ef1-481b-bb01-c7081ef86103"
                  },
                  "destination_input": "$filename"
                },
                {
                  "component_type": "DataFlowEdge",
                  "id": "dec4b4bb-56c9-445a-a282-9d095ff6038e",
                  "name": "generate_comments_$json_comments_to_extract_comments_from_json_$json_comments_data_flow_edge",
                  "description": null,
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "source_node": {
                    "$component_ref": "0ce752d7-3ef1-481b-bb01-c7081ef86103"
                  },
                  "source_output": "$json_comments",
                  "destination_node": {
                    "$component_ref": "48057b9c-bee7-4286-baf5-625b6f1a6f1a"
                  },
                  "destination_input": "$json_comments"
                },
                {
                  "component_type": "DataFlowEdge",
                  "id": "611478d7-281a-4587-81e6-97e8c745da53",
                  "name": "__StartStep___message_to_format_diff_to_string_message_data_flow_edge",
                  "description": null,
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "source_node": {
                    "$component_ref": "e20f5870-d594-4089-9fcd-08146232910d"
                  },
                  "source_output": "message",
                  "destination_node": {
                    "$component_ref": "f0fb3ab4-a950-43b6-a583-6f0044f18c7f"
                  },
                  "destination_input": "message"
                },
                {
                  "component_type": "DataFlowEdge",
                  "id": "227ae098-0baf-4fe8-9615-094bb386c9a9",
                  "name": "extract_comments_from_json_$extracted_comments_to_None End node_$extracted_comments_data_flow_edge",
                  "description": null,
                  "metadata": {},
                  "source_node": {
                    "$component_ref": "48057b9c-bee7-4286-baf5-625b6f1a6f1a"
                  },
                  "source_output": "$extracted_comments",
                  "destination_node": {
                    "$component_ref": "39f36227-8910-414c-8b6b-517c0d65b0d8"
                  },
                  "destination_input": "$extracted_comments"
                },
                {
                  "component_type": "DataFlowEdge",
                  "id": "6e25b4d8-5656-471b-8ffa-1fe8cfffbc05",
                  "name": "generate_comments_$json_comments_to_None End node_$json_comments_data_flow_edge",
                  "description": null,
                  "metadata": {},
                  "source_node": {
                    "$component_ref": "0ce752d7-3ef1-481b-bb01-c7081ef86103"
                  },
                  "source_output": "$json_comments",
                  "destination_node": {
                    "$component_ref": "39f36227-8910-414c-8b6b-517c0d65b0d8"
                  },
                  "destination_input": "$json_comments"
                },
                {
                  "component_type": "DataFlowEdge",
                  "id": "fdbf1eeb-0278-4dc8-b897-c924937a1692",
                  "name": "add_lines_on_diff_$diff_with_lines_to_None End node_$diff_with_lines_data_flow_edge",
                  "description": null,
                  "metadata": {},
                  "source_node": {
                    "$component_ref": "6000ee3f-ac80-4937-b36c-94fd65cdcda4"
                  },
                  "source_output": "$diff_with_lines",
                  "destination_node": {
                    "$component_ref": "39f36227-8910-414c-8b6b-517c0d65b0d8"
                  },
                  "destination_input": "$diff_with_lines"
                },
                {
                  "component_type": "DataFlowEdge",
                  "id": "3b6bcba7-635b-45fa-b450-cf0a15dae463",
                  "name": "extract_file_path_$filename_to_None End node_$filename_data_flow_edge",
                  "description": null,
                  "metadata": {},
                  "source_node": {
                    "$component_ref": "6f6dc822-9352-47ae-9b48-173402a334fe"
                  },
                  "source_output": "$filename",
                  "destination_node": {
                    "$component_ref": "39f36227-8910-414c-8b6b-517c0d65b0d8"
                  },
                  "destination_input": "$filename"
                },
                {
                  "component_type": "DataFlowEdge",
                  "id": "2f95704b-4cc1-4983-8a20-e39c79a94e01",
                  "name": "format_diff_to_string_$diff_to_string_to_None End node_$diff_to_string_data_flow_edge",
                  "description": null,
                  "metadata": {},
                  "source_node": {
                    "$component_ref": "f0fb3ab4-a950-43b6-a583-6f0044f18c7f"
                  },
                  "source_output": "$diff_to_string",
                  "destination_node": {
                    "$component_ref": "39f36227-8910-414c-8b6b-517c0d65b0d8"
                  },
                  "destination_input": "$diff_to_string"
                }
              ],
              "$referenced_components": {
                "6000ee3f-ac80-4937-b36c-94fd65cdcda4": {
                  "component_type": "ExtendedToolNode",
                  "id": "6000ee3f-ac80-4937-b36c-94fd65cdcda4",
                  "name": "add_lines_on_diff",
                  "description": "",
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "inputs": [
                    {
                      "type": "string",
                      "title": "$diff_to_string"
                    }
                  ],
                  "outputs": [
                    {
                      "type": "string",
                      "title": "$diff_with_lines"
                    }
                  ],
                  "branches": [
                    "next"
                  ],
                  "tool": {
                    "component_type": "ServerTool",
                    "id": "e936566f-7a25-40f3-9434-3e740a7bfb02",
                    "name": "format_git_diff",
                    "description": "Formats a git diff by adding line numbers to each line except removal lines.",
                    "metadata": {
                      "__metadata_info__": {}
                    },
                    "inputs": [
                      {
                        "type": "string",
                        "title": "diff_text"
                      }
                    ],
                    "outputs": [
                      {
                        "type": "string",
                        "title": "tool_output"
                      }
                    ]
                  },
                  "input_mapping": {
                    "diff_text": "$diff_to_string"
                  },
                  "output_mapping": {
                    "tool_output": "$diff_with_lines"
                  },
                  "raise_exceptions": false,
                  "component_plugin_name": "NodesPlugin",
                  "component_plugin_version": "25.4.0.dev0"
                },
                "f0fb3ab4-a950-43b6-a583-6f0044f18c7f": {
                  "component_type": "PluginOutputMessageNode",
                  "id": "f0fb3ab4-a950-43b6-a583-6f0044f18c7f",
                  "name": "format_diff_to_string",
                  "description": "",
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "inputs": [
                    {
                      "description": "\"message\" input variable for the template",
                      "title": "message"
                    }
                  ],
                  "outputs": [
                    {
                      "description": "the message added to the messages list",
                      "type": "string",
                      "title": "$diff_to_string"
                    }
                  ],
                  "branches": [
                    "next"
                  ],
                  "expose_message_as_output": true,
                  "message": "{{ message | string }}",
                  "input_mapping": {},
                  "output_mapping": {
                    "output_message": "$diff_to_string"
                  },
                  "message_type": "AGENT",
                  "rephrase": false,
                  "llm_config": null,
                  "component_plugin_name": "NodesPlugin",
                  "component_plugin_version": "25.4.0.dev0"
                },
                "6f6dc822-9352-47ae-9b48-173402a334fe": {
                  "component_type": "PluginRegexNode",
                  "id": "6f6dc822-9352-47ae-9b48-173402a334fe",
                  "name": "extract_file_path",
                  "description": "",
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "inputs": [
                    {
                      "description": "raw text to extract information from",
                      "type": "string",
                      "title": "$diff_to_string"
                    }
                  ],
                  "outputs": [
                    {
                      "description": "the first extracted value using the regex \"diff --git a/(.+?) b/\" from the raw input",
                      "type": "string",
                      "title": "$filename",
                      "default": ""
                    }
                  ],
                  "branches": [
                    "next"
                  ],
                  "input_mapping": {
                    "text": "$diff_to_string"
                  },
                  "output_mapping": {
                    "output": "$filename"
                  },
                  "regex_pattern": "diff --git a/(.+?) b/",
                  "return_first_match_only": true,
                  "component_plugin_name": "NodesPlugin",
                  "component_plugin_version": "25.4.0.dev0"
                },
                "0ce752d7-3ef1-481b-bb01-c7081ef86103": {
                  "component_type": "ExtendedLlmNode",
                  "id": "0ce752d7-3ef1-481b-bb01-c7081ef86103",
                  "name": "generate_comments",
                  "description": "",
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "inputs": [
                    {
                      "description": "\"filename\" input variable for the template",
                      "type": "string",
                      "title": "$filename"
                    },
                    {
                      "description": "\"diff\" input variable for the template",
                      "type": "string",
                      "title": "$diff_with_lines"
                    }
                  ],
                  "outputs": [
                    {
                      "description": "the generated text",
                      "type": "string",
                      "title": "$json_comments"
                    }
                  ],
                  "branches": [
                    "next"
                  ],
                  "llm_config": {
                    "component_type": "VllmConfig",
                    "id": "fb043839-1e69-404c-a178-d8c3de0bfe20",
                    "name": "LLAMA_MODEL_ID",
                    "description": null,
                    "metadata": {
                      "__metadata_info__": {}
                    },
                    "default_generation_parameters": null,
                    "url": "LLAMA_API_URL",
                    "model_id": "LLAMA_MODEL_ID"
                  },
                  "prompt_template": "You are a very experienced code reviewer. You are given a git diff on a file: {{ filename }}\n\n## Context\nThe git diff contains all changes of a single file. All lines are prepended with their number. Lines without line number where removed from the file.\nAfter the line number, a line that was changed has a \"+\" before the code. All lines without a \"+\" are just here for context, you will not comment on them.\n\n## Input\n### Code diff\n{{ diff }}\n\n## Task\nYour task is to review these changes, according to different rules. Only comment lines that were added, so the lines that have a + just after the line number.\nThe rules are the following:\n\n\nName: TODO_WITHOUT_TICKET\nDescription: TODO comments should reference a ticket number for tracking.\nExample code:\n```python\n# TODO: Add validation here\ndef process_user_input(data):\n    return data\n```\nExample comment:\n[BOT] TODO_WITHOUT_TICKET: TODO comment should reference a ticket number for tracking (e.g., \"TODO: Add validation here (TICKET-1234)\").\n\n\n---\n\n\nName: MUTABLE_DEFAULT_ARGUMENT\nDescription: Using mutable objects as default arguments can lead to unexpected behavior.\nExample code:\n```python\ndef add_item(item, items=[]):\n    items.append(item)\n    return items\n```\nExample comment:\n[BOT] MUTABLE_DEFAULT_ARGUMENT: Avoid using mutable default arguments. Use None and initialize in the function: `def add_item(item, items=None): items = items or []`\n\n\n---\n\n\nName: NON_DESCRIPTIVE_NAME\nDescription: Variable names should clearly indicate their purpose or content.\nExample code:\n```python\ndef process(lst):\n    res = []\n    for i in lst:\n        res.append(i * 2)\n    return res\n```\nExample comment:\n[BOT] NON_DESCRIPTIVE_NAME: Use more descriptive names: 'lst' could be 'numbers', 'res' could be 'doubled_numbers', 'i' could be 'number'\n\n\n### Response Format\nYou need to return a review as a json as follows:\n```json\n[\n    {\n        \"content\": \"the comment as a text\",\n        \"suggestion\": \"if the change you propose is a single line, then put here the single line rewritten that includes your proposal change. IMPORTANT: a single line, which will erase the current line. Put empty string if no suggestion of if the suggestion is more than a single line\",\n        \"line\": \"line number where the comment applies\"\n    },\n    \u2026\n]\n```\nPlease use triple backticks ``` to delimitate your JSON list of comments. Don't output more than 5 comments, only comment the most relevant sections.\nIf there are no comments and the code seems fine, just output an empty JSON list.",
                  "input_mapping": {
                    "diff": "$diff_with_lines",
                    "filename": "$filename"
                  },
                  "output_mapping": {
                    "output": "$json_comments"
                  },
                  "prompt_template_object": null,
                  "send_message": false,
                  "component_plugin_name": "NodesPlugin",
                  "component_plugin_version": "25.4.0.dev0"
                },
                "48057b9c-bee7-4286-baf5-625b6f1a6f1a": {
                  "component_type": "PluginExtractNode",
                  "id": "48057b9c-bee7-4286-baf5-625b6f1a6f1a",
                  "name": "extract_comments_from_json",
                  "description": "",
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "inputs": [
                    {
                      "description": "raw text to extract information from",
                      "type": "string",
                      "title": "$json_comments"
                    }
                  ],
                  "outputs": [
                    {
                      "description": "The extracted comments content and line number",
                      "type": "array",
                      "items": {
                        "type": "object",
                        "additionalProperties": {},
                        "key_type": {
                          "type": "string"
                        }
                      },
                      "title": "$extracted_comments"
                    }
                  ],
                  "branches": [
                    "next"
                  ],
                  "input_mapping": {
                    "text": "$json_comments"
                  },
                  "output_mapping": {
                    "values": "$extracted_comments"
                  },
                  "output_values": {
                    "values": "[.[] | {\"content\": .[\"content\"], \"line\": .[\"line\"]}]"
                  },
                  "component_plugin_name": "NodesPlugin",
                  "component_plugin_version": "25.4.0.dev0"
                },
                "e20f5870-d594-4089-9fcd-08146232910d": {
                  "component_type": "StartNode",
                  "id": "e20f5870-d594-4089-9fcd-08146232910d",
                  "name": "__StartStep__",
                  "description": "",
                  "metadata": {
                    "__metadata_info__": {}
                  },
                  "inputs": [
                    {
                      "description": "\"message\" input variable for the template",
                      "title": "message"
                    }
                  ],
                  "outputs": [
                    {
                      "description": "\"message\" input variable for the template",
                      "title": "message"
                    }
                  ],
                  "branches": [
                    "next"
                  ]
                },
                "39f36227-8910-414c-8b6b-517c0d65b0d8": {
                  "component_type": "EndNode",
                  "id": "39f36227-8910-414c-8b6b-517c0d65b0d8",
                  "name": "None End node",
                  "description": "End node representing all transitions to None in the WayFlow flow",
                  "metadata": {},
                  "inputs": [
                    {
                      "description": "The extracted comments content and line number",
                      "type": "array",
                      "items": {
                        "type": "object",
                        "additionalProperties": {},
                        "key_type": {
                          "type": "string"
                        }
                      },
                      "title": "$extracted_comments"
                    },
                    {
                      "description": "the generated text",
                      "type": "string",
                      "title": "$json_comments"
                    },
                    {
                      "type": "string",
                      "title": "$diff_with_lines"
                    },
                    {
                      "description": "the first extracted value using the regex \"diff --git a/(.+?) b/\" from the raw input",
                      "type": "string",
                      "title": "$filename",
                      "default": ""
                    },
                    {
                      "description": "the message added to the messages list",
                      "type": "string",
                      "title": "$diff_to_string"
                    }
                  ],
                  "outputs": [
                    {
                      "description": "The extracted comments content and line number",
                      "type": "array",
                      "items": {
                        "type": "object",
                        "additionalProperties": {},
                        "key_type": {
                          "type": "string"
                        }
                      },
                      "title": "$extracted_comments"
                    },
                    {
                      "description": "the generated text",
                      "type": "string",
                      "title": "$json_comments"
                    },
                    {
                      "type": "string",
                      "title": "$diff_with_lines"
                    },
                    {
                      "description": "the first extracted value using the regex \"diff --git a/(.+?) b/\" from the raw input",
                      "type": "string",
                      "title": "$filename",
                      "default": ""
                    },
                    {
                      "description": "the message added to the messages list",
                      "type": "string",
                      "title": "$diff_to_string"
                    }
                  ],
                  "branches": [],
                  "branch_name": "next"
                }
              }
            },
            "unpack_input": {
              "message": "."
            },
            "parallel_execution": false,
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "25.4.0.dev0"
          },
          "367ae568-317d-42ec-ae70-4c41afe0dbd0": {
            "component_type": "StartNode",
            "id": "367ae568-317d-42ec-ae70-4c41afe0dbd0",
            "name": "__StartStep__",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "description": "iterated input for the map step",
                "type": "array",
                "items": {
                  "description": "\"message\" input variable for the template",
                  "title": "message"
                },
                "title": "$file_diff_list"
              }
            ],
            "outputs": [
              {
                "description": "iterated input for the map step",
                "type": "array",
                "items": {
                  "description": "\"message\" input variable for the template",
                  "title": "message"
                },
                "title": "$file_diff_list"
              }
            ],
            "branches": [
              "next"
            ]
          },
          "6f62aecf-03a1-4e38-b551-8eef0efaf4bb": {
            "component_type": "EndNode",
            "id": "6f62aecf-03a1-4e38-b551-8eef0efaf4bb",
            "name": "None End node",
            "description": "End node representing all transitions to None in the WayFlow flow",
            "metadata": {},
            "inputs": [
              {
                "type": "array",
                "items": {
                  "type": "string"
                },
                "title": "$filepath_list"
              },
              {
                "type": "array",
                "items": {},
                "title": "$nested_comment_list"
              }
            ],
            "outputs": [
              {
                "type": "array",
                "items": {
                  "type": "string"
                },
                "title": "$filepath_list"
              },
              {
                "type": "array",
                "items": {},
                "title": "$nested_comment_list"
              }
            ],
            "branches": [],
            "branch_name": "next"
          }
        }
      }
    },
    "47e367be-4d74-49dc-ac3b-89bb97ffa7df": {
      "component_type": "FlowNode",
      "id": "47e367be-4d74-49dc-ac3b-89bb97ffa7df",
      "name": "retrieve_diff_flowstep",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "string",
          "title": "$repo_dirpath_io"
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "$raw_pr_diff"
        },
        {
          "description": "the list of extracted value using the regex \"(diff --git[\\s\\S]*?)(?=diff --git|$)\" from the raw input",
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "$file_diff_list",
          "default": []
        }
      ],
      "branches": [
        "next"
      ],
      "subflow": {
        "component_type": "Flow",
        "id": "9e7aed22-876c-4c32-9d44-20ee7ceb3771",
        "name": "Retrieve PR diff flow",
        "description": "",
        "metadata": {
          "__metadata_info__": {}
        },
        "inputs": [
          {
            "type": "string",
            "title": "$repo_dirpath_io"
          }
        ],
        "outputs": [
          {
            "type": "string",
            "title": "$raw_pr_diff"
          },
          {
            "description": "the list of extracted value using the regex \"(diff --git[\\s\\S]*?)(?=diff --git|$)\" from the raw input",
            "type": "array",
            "items": {
              "type": "string"
            },
            "title": "$file_diff_list",
            "default": []
          }
        ],
        "start_node": {
          "$component_ref": "4fcb7ebe-325b-446d-a46b-59187c30e260"
        },
        "nodes": [
          {
            "$component_ref": "4fcb7ebe-325b-446d-a46b-59187c30e260"
          },
          {
            "$component_ref": "5c73da9c-6ba9-44ce-aab1-212a78d0a720"
          },
          {
            "$component_ref": "cf841053-2414-48b6-ba6d-0f0f5e11044c"
          },
          {
            "$component_ref": "dd0e56ab-1267-4345-9f59-ecc053baf2af"
          }
        ],
        "control_flow_connections": [
          {
            "component_type": "ControlFlowEdge",
            "id": "60dc14b8-d9b9-4aec-a958-9f3676848f48",
            "name": "start_step_to_get_pr_diff_control_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "from_node": {
              "$component_ref": "4fcb7ebe-325b-446d-a46b-59187c30e260"
            },
            "from_branch": null,
            "to_node": {
              "$component_ref": "5c73da9c-6ba9-44ce-aab1-212a78d0a720"
            }
          },
          {
            "component_type": "ControlFlowEdge",
            "id": "500f97de-78b1-42e0-944c-0375dfca734e",
            "name": "get_pr_diff_to_extract_into_list_of_file_diff_control_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "from_node": {
              "$component_ref": "5c73da9c-6ba9-44ce-aab1-212a78d0a720"
            },
            "from_branch": null,
            "to_node": {
              "$component_ref": "cf841053-2414-48b6-ba6d-0f0f5e11044c"
            }
          },
          {
            "component_type": "ControlFlowEdge",
            "id": "22d0cf0d-8edb-4b04-8f54-a234f5705360",
            "name": "extract_into_list_of_file_diff_to_None End node_control_flow_edge",
            "description": null,
            "metadata": {},
            "from_node": {
              "$component_ref": "cf841053-2414-48b6-ba6d-0f0f5e11044c"
            },
            "from_branch": null,
            "to_node": {
              "$component_ref": "dd0e56ab-1267-4345-9f59-ecc053baf2af"
            }
          }
        ],
        "data_flow_connections": [
          {
            "component_type": "DataFlowEdge",
            "id": "106e3740-de45-4472-8168-2873ae1dbc82",
            "name": "start_step_$repo_dirpath_io_to_get_pr_diff_$repo_dirpath_io_data_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "source_node": {
              "$component_ref": "4fcb7ebe-325b-446d-a46b-59187c30e260"
            },
            "source_output": "$repo_dirpath_io",
            "destination_node": {
              "$component_ref": "5c73da9c-6ba9-44ce-aab1-212a78d0a720"
            },
            "destination_input": "$repo_dirpath_io"
          },
          {
            "component_type": "DataFlowEdge",
            "id": "a32cbb1c-eafe-4138-80e2-2cf2e1248312",
            "name": "get_pr_diff_$raw_pr_diff_to_extract_into_list_of_file_diff_$raw_pr_diff_data_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "source_node": {
              "$component_ref": "5c73da9c-6ba9-44ce-aab1-212a78d0a720"
            },
            "source_output": "$raw_pr_diff",
            "destination_node": {
              "$component_ref": "cf841053-2414-48b6-ba6d-0f0f5e11044c"
            },
            "destination_input": "$raw_pr_diff"
          },
          {
            "component_type": "DataFlowEdge",
            "id": "3ef5dcf4-acdf-4962-8df6-07b53f249e18",
            "name": "get_pr_diff_$raw_pr_diff_to_None End node_$raw_pr_diff_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
              "$component_ref": "5c73da9c-6ba9-44ce-aab1-212a78d0a720"
            },
            "source_output": "$raw_pr_diff",
            "destination_node": {
              "$component_ref": "dd0e56ab-1267-4345-9f59-ecc053baf2af"
            },
            "destination_input": "$raw_pr_diff"
          },
          {
            "component_type": "DataFlowEdge",
            "id": "08cbca39-e591-4cf4-9057-ae67938d9557",
            "name": "extract_into_list_of_file_diff_$file_diff_list_to_None End node_$file_diff_list_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
              "$component_ref": "cf841053-2414-48b6-ba6d-0f0f5e11044c"
            },
            "source_output": "$file_diff_list",
            "destination_node": {
              "$component_ref": "dd0e56ab-1267-4345-9f59-ecc053baf2af"
            },
            "destination_input": "$file_diff_list"
          }
        ],
        "$referenced_components": {
          "5c73da9c-6ba9-44ce-aab1-212a78d0a720": {
            "component_type": "ExtendedToolNode",
            "id": "5c73da9c-6ba9-44ce-aab1-212a78d0a720",
            "name": "get_pr_diff",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "type": "string",
                "title": "$repo_dirpath_io"
              }
            ],
            "outputs": [
              {
                "type": "string",
                "title": "$raw_pr_diff"
              }
            ],
            "branches": [
              "next"
            ],
            "tool": {
              "component_type": "ServerTool",
              "id": "275aaf19-cdd4-4ed7-a436-e53f922cd740",
              "name": "local_get_pr_diff_tool",
              "description": "# docs-skiprow\nRetrieves code diff with a git command given the  # docs-skiprow\npath to the repository root folder.  # docs-skiprow",
              "metadata": {
                "__metadata_info__": {}
              },
              "inputs": [
                {
                  "type": "string",
                  "title": "repo_dirpath"
                }
              ],
              "outputs": [
                {
                  "type": "string",
                  "title": "tool_output"
                }
              ]
            },
            "input_mapping": {
              "repo_dirpath": "$repo_dirpath_io"
            },
            "output_mapping": {
              "tool_output": "$raw_pr_diff"
            },
            "raise_exceptions": true,
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "25.4.0.dev0"
          },
          "4fcb7ebe-325b-446d-a46b-59187c30e260": {
            "component_type": "StartNode",
            "id": "4fcb7ebe-325b-446d-a46b-59187c30e260",
            "name": "start_step",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "type": "string",
                "title": "$repo_dirpath_io"
              }
            ],
            "outputs": [
              {
                "type": "string",
                "title": "$repo_dirpath_io"
              }
            ],
            "branches": [
              "next"
            ]
          },
          "cf841053-2414-48b6-ba6d-0f0f5e11044c": {
            "component_type": "PluginRegexNode",
            "id": "cf841053-2414-48b6-ba6d-0f0f5e11044c",
            "name": "extract_into_list_of_file_diff",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "description": "raw text to extract information from",
                "type": "string",
                "title": "$raw_pr_diff"
              }
            ],
            "outputs": [
              {
                "description": "the list of extracted value using the regex \"(diff --git[\\s\\S]*?)(?=diff --git|$)\" from the raw input",
                "type": "array",
                "items": {
                  "type": "string"
                },
                "title": "$file_diff_list",
                "default": []
              }
            ],
            "branches": [
              "next"
            ],
            "input_mapping": {
              "text": "$raw_pr_diff"
            },
            "output_mapping": {
              "output": "$file_diff_list"
            },
            "regex_pattern": "(diff --git[\\s\\S]*?)(?=diff --git|$)",
            "return_first_match_only": false,
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "25.4.0.dev0"
          },
          "dd0e56ab-1267-4345-9f59-ecc053baf2af": {
            "component_type": "EndNode",
            "id": "dd0e56ab-1267-4345-9f59-ecc053baf2af",
            "name": "None End node",
            "description": "End node representing all transitions to None in the WayFlow flow",
            "metadata": {},
            "inputs": [
              {
                "type": "string",
                "title": "$raw_pr_diff"
              },
              {
                "description": "the list of extracted value using the regex \"(diff --git[\\s\\S]*?)(?=diff --git|$)\" from the raw input",
                "type": "array",
                "items": {
                  "type": "string"
                },
                "title": "$file_diff_list",
                "default": []
              }
            ],
            "outputs": [
              {
                "type": "string",
                "title": "$raw_pr_diff"
              },
              {
                "description": "the list of extracted value using the regex \"(diff --git[\\s\\S]*?)(?=diff --git|$)\" from the raw input",
                "type": "array",
                "items": {
                  "type": "string"
                },
                "title": "$file_diff_list",
                "default": []
              }
            ],
            "branches": [],
            "branch_name": "next"
          }
        }
      }
    },
    "020c885e-6d0b-472a-bb91-246ab70ab1db": {
      "component_type": "StartNode",
      "id": "020c885e-6d0b-472a-bb91-246ab70ab1db",
      "name": "__StartStep__",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "string",
          "title": "$repo_dirpath_io"
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "$repo_dirpath_io"
        }
      ],
      "branches": [
        "next"
      ]
    },
    "a544af64-e63b-4ccf-9ab0-8d25cdbc0b93": {
      "component_type": "EndNode",
      "id": "a544af64-e63b-4ccf-9ab0-8d25cdbc0b93",
      "name": "None End node",
      "description": "End node representing all transitions to None in the WayFlow flow",
      "metadata": {},
      "inputs": [
        {
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "$filepath_list"
        },
        {
          "type": "array",
          "items": {},
          "title": "$nested_comment_list"
        },
        {
          "type": "string",
          "title": "$raw_pr_diff"
        },
        {
          "description": "the list of extracted value using the regex \"(diff --git[\\s\\S]*?)(?=diff --git|$)\" from the raw input",
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "$file_diff_list",
          "default": []
        }
      ],
      "outputs": [
        {
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "$filepath_list"
        },
        {
          "type": "array",
          "items": {},
          "title": "$nested_comment_list"
        },
        {
          "type": "string",
          "title": "$raw_pr_diff"
        },
        {
          "description": "the list of extracted value using the regex \"(diff --git[\\s\\S]*?)(?=diff --git|$)\" from the raw input",
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "$file_diff_list",
          "default": []
        }
      ],
      "branches": [],
      "branch_name": "next"
    }
  },
  "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: Flow
id: 9c65246d-a0dd-4ec4-801d-afd640b2488e
name: PR bot flow
description: ''
metadata:
  __metadata_info__: {}
inputs:
- type: string
  title: $repo_dirpath_io
outputs:
- type: array
  items:
    type: string
  title: $filepath_list
- type: array
  items: {}
  title: $nested_comment_list
- type: string
  title: $raw_pr_diff
- description: the list of extracted value using the regex "(diff --git[\s\S]*?)(?=diff
    --git|$)" from the raw input
  type: array
  items:
    type: string
  title: $file_diff_list
  default: []
start_node:
  $component_ref: 020c885e-6d0b-472a-bb91-246ab70ab1db
nodes:
- $component_ref: 47e367be-4d74-49dc-ac3b-89bb97ffa7df
- $component_ref: 43d58c76-23a0-4d10-943d-f9c5e0835a7c
- $component_ref: 020c885e-6d0b-472a-bb91-246ab70ab1db
- $component_ref: a544af64-e63b-4ccf-9ab0-8d25cdbc0b93
control_flow_connections:
- component_type: ControlFlowEdge
  id: a5c123ff-c14c-4291-b174-61d61170f187
  name: retrieve_diff_flowstep_to_generate_comments_flowstep_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 47e367be-4d74-49dc-ac3b-89bb97ffa7df
  from_branch: null
  to_node:
    $component_ref: 43d58c76-23a0-4d10-943d-f9c5e0835a7c
- component_type: ControlFlowEdge
  id: 8a10b23a-2d0c-46c4-82ac-e66ad0b9399b
  name: __StartStep___to_retrieve_diff_flowstep_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 020c885e-6d0b-472a-bb91-246ab70ab1db
  from_branch: null
  to_node:
    $component_ref: 47e367be-4d74-49dc-ac3b-89bb97ffa7df
- component_type: ControlFlowEdge
  id: dac07720-8a5a-4a61-b1e7-50be506ed937
  name: generate_comments_flowstep_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: 43d58c76-23a0-4d10-943d-f9c5e0835a7c
  from_branch: null
  to_node:
    $component_ref: a544af64-e63b-4ccf-9ab0-8d25cdbc0b93
data_flow_connections:
- component_type: DataFlowEdge
  id: 7b12dfed-309b-46ff-8a2d-bb6f2a3154b6
  name: retrieve_diff_flowstep_$file_diff_list_to_generate_comments_flowstep_$file_diff_list_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 47e367be-4d74-49dc-ac3b-89bb97ffa7df
  source_output: $file_diff_list
  destination_node:
    $component_ref: 43d58c76-23a0-4d10-943d-f9c5e0835a7c
  destination_input: $file_diff_list
- component_type: DataFlowEdge
  id: 51122844-22d3-40a8-b652-1b020ce24945
  name: __StartStep___$repo_dirpath_io_to_retrieve_diff_flowstep_$repo_dirpath_io_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 020c885e-6d0b-472a-bb91-246ab70ab1db
  source_output: $repo_dirpath_io
  destination_node:
    $component_ref: 47e367be-4d74-49dc-ac3b-89bb97ffa7df
  destination_input: $repo_dirpath_io
- component_type: DataFlowEdge
  id: 72aa469c-98cd-4f0d-9496-0aa454373aef
  name: generate_comments_flowstep_$filepath_list_to_None End node_$filepath_list_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 43d58c76-23a0-4d10-943d-f9c5e0835a7c
  source_output: $filepath_list
  destination_node:
    $component_ref: a544af64-e63b-4ccf-9ab0-8d25cdbc0b93
  destination_input: $filepath_list
- component_type: DataFlowEdge
  id: eac1b375-1541-41f7-87f3-f3e626cc2c9c
  name: generate_comments_flowstep_$nested_comment_list_to_None End node_$nested_comment_list_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 43d58c76-23a0-4d10-943d-f9c5e0835a7c
  source_output: $nested_comment_list
  destination_node:
    $component_ref: a544af64-e63b-4ccf-9ab0-8d25cdbc0b93
  destination_input: $nested_comment_list
- component_type: DataFlowEdge
  id: 0869acb5-4d8f-4b17-b59b-3b915912b628
  name: retrieve_diff_flowstep_$raw_pr_diff_to_None End node_$raw_pr_diff_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 47e367be-4d74-49dc-ac3b-89bb97ffa7df
  source_output: $raw_pr_diff
  destination_node:
    $component_ref: a544af64-e63b-4ccf-9ab0-8d25cdbc0b93
  destination_input: $raw_pr_diff
- component_type: DataFlowEdge
  id: 9fb2ab9e-ece1-4195-8f51-ef618dcb72bb
  name: retrieve_diff_flowstep_$file_diff_list_to_None End node_$file_diff_list_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 47e367be-4d74-49dc-ac3b-89bb97ffa7df
  source_output: $file_diff_list
  destination_node:
    $component_ref: a544af64-e63b-4ccf-9ab0-8d25cdbc0b93
  destination_input: $file_diff_list
$referenced_components:
  43d58c76-23a0-4d10-943d-f9c5e0835a7c:
    component_type: FlowNode
    id: 43d58c76-23a0-4d10-943d-f9c5e0835a7c
    name: generate_comments_flowstep
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: iterated input for the map step
      type: array
      items:
        description: '"message" input variable for the template'
        title: message
      title: $file_diff_list
    outputs:
    - type: array
      items:
        type: string
      title: $filepath_list
    - type: array
      items: {}
      title: $nested_comment_list
    branches:
    - next
    subflow:
      component_type: Flow
      id: f95e0e5d-f573-4e25-9d68-8508371246f9
      name: flow_028a7dfb__auto
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - description: iterated input for the map step
        type: array
        items:
          description: '"message" input variable for the template'
          title: message
        title: $file_diff_list
      outputs:
      - type: array
        items:
          type: string
        title: $filepath_list
      - type: array
        items: {}
        title: $nested_comment_list
      start_node:
        $component_ref: 367ae568-317d-42ec-ae70-4c41afe0dbd0
      nodes:
      - $component_ref: f127a297-842d-4d17-bc89-4704019458d7
      - $component_ref: 367ae568-317d-42ec-ae70-4c41afe0dbd0
      - $component_ref: 6f62aecf-03a1-4e38-b551-8eef0efaf4bb
      control_flow_connections:
      - component_type: ControlFlowEdge
        id: 85a2cdff-6ad4-4f58-8d1c-c8deeb05880c
        name: __StartStep___to_step_0_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: 367ae568-317d-42ec-ae70-4c41afe0dbd0
        from_branch: null
        to_node:
          $component_ref: f127a297-842d-4d17-bc89-4704019458d7
      - component_type: ControlFlowEdge
        id: 396e218f-225e-4e36-a33c-a176ca77d345
        name: step_0_to_None End node_control_flow_edge
        description: null
        metadata: {}
        from_node:
          $component_ref: f127a297-842d-4d17-bc89-4704019458d7
        from_branch: null
        to_node:
          $component_ref: 6f62aecf-03a1-4e38-b551-8eef0efaf4bb
      data_flow_connections:
      - component_type: DataFlowEdge
        id: 6c8b8f78-b587-49ff-a401-6262cdafb0ee
        name: __StartStep___$file_diff_list_to_step_0_$file_diff_list_data_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        source_node:
          $component_ref: 367ae568-317d-42ec-ae70-4c41afe0dbd0
        source_output: $file_diff_list
        destination_node:
          $component_ref: f127a297-842d-4d17-bc89-4704019458d7
        destination_input: $file_diff_list
      - component_type: DataFlowEdge
        id: 84d3a783-38c8-4d53-bc0b-4205732d1fbf
        name: step_0_$filepath_list_to_None End node_$filepath_list_data_flow_edge
        description: null
        metadata: {}
        source_node:
          $component_ref: f127a297-842d-4d17-bc89-4704019458d7
        source_output: $filepath_list
        destination_node:
          $component_ref: 6f62aecf-03a1-4e38-b551-8eef0efaf4bb
        destination_input: $filepath_list
      - component_type: DataFlowEdge
        id: b7ffd4c3-4a03-47f0-95fc-0ba670010729
        name: step_0_$nested_comment_list_to_None End node_$nested_comment_list_data_flow_edge
        description: null
        metadata: {}
        source_node:
          $component_ref: f127a297-842d-4d17-bc89-4704019458d7
        source_output: $nested_comment_list
        destination_node:
          $component_ref: 6f62aecf-03a1-4e38-b551-8eef0efaf4bb
        destination_input: $nested_comment_list
      $referenced_components:
        f127a297-842d-4d17-bc89-4704019458d7:
          component_type: ExtendedMapNode
          id: f127a297-842d-4d17-bc89-4704019458d7
          name: step_0
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - description: iterated input for the map step
            type: array
            items:
              description: '"message" input variable for the template'
              title: message
            title: $file_diff_list
          outputs:
          - type: array
            items: {}
            title: $nested_comment_list
          - type: array
            items:
              type: string
            title: $filepath_list
          branches:
          - next
          input_mapping:
            iterated_input: $file_diff_list
          output_mapping:
            $extracted_comments: $nested_comment_list
            $filename: $filepath_list
          flow:
            component_type: Flow
            id: 3da67cce-b8de-40be-bb8d-e1edead178f0
            name: Generate review comments flow
            description: ''
            metadata:
              __metadata_info__: {}
            inputs:
            - description: '"message" input variable for the template'
              title: message
            outputs:
            - description: The extracted comments content and line number
              type: array
              items:
                type: object
                additionalProperties: {}
                key_type:
                  type: string
              title: $extracted_comments
            - description: the generated text
              type: string
              title: $json_comments
            - type: string
              title: $diff_with_lines
            - description: the first extracted value using the regex "diff --git a/(.+?)
                b/" from the raw input
              type: string
              title: $filename
              default: ''
            - description: the message added to the messages list
              type: string
              title: $diff_to_string
            start_node:
              $component_ref: e20f5870-d594-4089-9fcd-08146232910d
            nodes:
            - $component_ref: f0fb3ab4-a950-43b6-a583-6f0044f18c7f
            - $component_ref: 6000ee3f-ac80-4937-b36c-94fd65cdcda4
            - $component_ref: 6f6dc822-9352-47ae-9b48-173402a334fe
            - $component_ref: 0ce752d7-3ef1-481b-bb01-c7081ef86103
            - $component_ref: 48057b9c-bee7-4286-baf5-625b6f1a6f1a
            - $component_ref: e20f5870-d594-4089-9fcd-08146232910d
            - $component_ref: 39f36227-8910-414c-8b6b-517c0d65b0d8
            control_flow_connections:
            - component_type: ControlFlowEdge
              id: becf6951-96fd-4152-97d0-4a4eff042a29
              name: format_diff_to_string_to_add_lines_on_diff_control_flow_edge
              description: null
              metadata:
                __metadata_info__: {}
              from_node:
                $component_ref: f0fb3ab4-a950-43b6-a583-6f0044f18c7f
              from_branch: null
              to_node:
                $component_ref: 6000ee3f-ac80-4937-b36c-94fd65cdcda4
            - component_type: ControlFlowEdge
              id: c197b0d5-8002-4910-ae8d-61f97f1f8f26
              name: add_lines_on_diff_to_extract_file_path_control_flow_edge
              description: null
              metadata:
                __metadata_info__: {}
              from_node:
                $component_ref: 6000ee3f-ac80-4937-b36c-94fd65cdcda4
              from_branch: null
              to_node:
                $component_ref: 6f6dc822-9352-47ae-9b48-173402a334fe
            - component_type: ControlFlowEdge
              id: 406e0670-cc49-4da4-8d15-8c1c320193e8
              name: extract_file_path_to_generate_comments_control_flow_edge
              description: null
              metadata:
                __metadata_info__: {}
              from_node:
                $component_ref: 6f6dc822-9352-47ae-9b48-173402a334fe
              from_branch: null
              to_node:
                $component_ref: 0ce752d7-3ef1-481b-bb01-c7081ef86103
            - component_type: ControlFlowEdge
              id: e54eb347-2e6c-42c4-a7d6-a42c8059bdf3
              name: generate_comments_to_extract_comments_from_json_control_flow_edge
              description: null
              metadata:
                __metadata_info__: {}
              from_node:
                $component_ref: 0ce752d7-3ef1-481b-bb01-c7081ef86103
              from_branch: null
              to_node:
                $component_ref: 48057b9c-bee7-4286-baf5-625b6f1a6f1a
            - component_type: ControlFlowEdge
              id: ebe5e60b-2724-4b51-b287-79f3e8e7fdd1
              name: __StartStep___to_format_diff_to_string_control_flow_edge
              description: null
              metadata:
                __metadata_info__: {}
              from_node:
                $component_ref: e20f5870-d594-4089-9fcd-08146232910d
              from_branch: null
              to_node:
                $component_ref: f0fb3ab4-a950-43b6-a583-6f0044f18c7f
            - component_type: ControlFlowEdge
              id: 98e7631e-7206-4ba9-b5b0-eb308ac89c0f
              name: extract_comments_from_json_to_None End node_control_flow_edge
              description: null
              metadata: {}
              from_node:
                $component_ref: 48057b9c-bee7-4286-baf5-625b6f1a6f1a
              from_branch: null
              to_node:
                $component_ref: 39f36227-8910-414c-8b6b-517c0d65b0d8
            data_flow_connections:
            - component_type: DataFlowEdge
              id: ab8ed6de-3ea7-424e-a830-bca10ac57a32
              name: format_diff_to_string_$diff_to_string_to_add_lines_on_diff_$diff_to_string_data_flow_edge
              description: null
              metadata:
                __metadata_info__: {}
              source_node:
                $component_ref: f0fb3ab4-a950-43b6-a583-6f0044f18c7f
              source_output: $diff_to_string
              destination_node:
                $component_ref: 6000ee3f-ac80-4937-b36c-94fd65cdcda4
              destination_input: $diff_to_string
            - component_type: DataFlowEdge
              id: 3caaa171-9b4b-44df-8ebd-4d060329f91a
              name: format_diff_to_string_$diff_to_string_to_extract_file_path_$diff_to_string_data_flow_edge
              description: null
              metadata:
                __metadata_info__: {}
              source_node:
                $component_ref: f0fb3ab4-a950-43b6-a583-6f0044f18c7f
              source_output: $diff_to_string
              destination_node:
                $component_ref: 6f6dc822-9352-47ae-9b48-173402a334fe
              destination_input: $diff_to_string
            - component_type: DataFlowEdge
              id: cdf0945b-5a96-42ff-b410-f7c56b5f8e45
              name: add_lines_on_diff_$diff_with_lines_to_generate_comments_$diff_with_lines_data_flow_edge
              description: null
              metadata:
                __metadata_info__: {}
              source_node:
                $component_ref: 6000ee3f-ac80-4937-b36c-94fd65cdcda4
              source_output: $diff_with_lines
              destination_node:
                $component_ref: 0ce752d7-3ef1-481b-bb01-c7081ef86103
              destination_input: $diff_with_lines
            - component_type: DataFlowEdge
              id: ca6ed62b-6f6a-405f-9f16-5e1304de6608
              name: extract_file_path_$filename_to_generate_comments_$filename_data_flow_edge
              description: null
              metadata:
                __metadata_info__: {}
              source_node:
                $component_ref: 6f6dc822-9352-47ae-9b48-173402a334fe
              source_output: $filename
              destination_node:
                $component_ref: 0ce752d7-3ef1-481b-bb01-c7081ef86103
              destination_input: $filename
            - component_type: DataFlowEdge
              id: dec4b4bb-56c9-445a-a282-9d095ff6038e
              name: generate_comments_$json_comments_to_extract_comments_from_json_$json_comments_data_flow_edge
              description: null
              metadata:
                __metadata_info__: {}
              source_node:
                $component_ref: 0ce752d7-3ef1-481b-bb01-c7081ef86103
              source_output: $json_comments
              destination_node:
                $component_ref: 48057b9c-bee7-4286-baf5-625b6f1a6f1a
              destination_input: $json_comments
            - component_type: DataFlowEdge
              id: 611478d7-281a-4587-81e6-97e8c745da53
              name: __StartStep___message_to_format_diff_to_string_message_data_flow_edge
              description: null
              metadata:
                __metadata_info__: {}
              source_node:
                $component_ref: e20f5870-d594-4089-9fcd-08146232910d
              source_output: message
              destination_node:
                $component_ref: f0fb3ab4-a950-43b6-a583-6f0044f18c7f
              destination_input: message
            - component_type: DataFlowEdge
              id: 227ae098-0baf-4fe8-9615-094bb386c9a9
              name: extract_comments_from_json_$extracted_comments_to_None End node_$extracted_comments_data_flow_edge
              description: null
              metadata: {}
              source_node:
                $component_ref: 48057b9c-bee7-4286-baf5-625b6f1a6f1a
              source_output: $extracted_comments
              destination_node:
                $component_ref: 39f36227-8910-414c-8b6b-517c0d65b0d8
              destination_input: $extracted_comments
            - component_type: DataFlowEdge
              id: 6e25b4d8-5656-471b-8ffa-1fe8cfffbc05
              name: generate_comments_$json_comments_to_None End node_$json_comments_data_flow_edge
              description: null
              metadata: {}
              source_node:
                $component_ref: 0ce752d7-3ef1-481b-bb01-c7081ef86103
              source_output: $json_comments
              destination_node:
                $component_ref: 39f36227-8910-414c-8b6b-517c0d65b0d8
              destination_input: $json_comments
            - component_type: DataFlowEdge
              id: fdbf1eeb-0278-4dc8-b897-c924937a1692
              name: add_lines_on_diff_$diff_with_lines_to_None End node_$diff_with_lines_data_flow_edge
              description: null
              metadata: {}
              source_node:
                $component_ref: 6000ee3f-ac80-4937-b36c-94fd65cdcda4
              source_output: $diff_with_lines
              destination_node:
                $component_ref: 39f36227-8910-414c-8b6b-517c0d65b0d8
              destination_input: $diff_with_lines
            - component_type: DataFlowEdge
              id: 3b6bcba7-635b-45fa-b450-cf0a15dae463
              name: extract_file_path_$filename_to_None End node_$filename_data_flow_edge
              description: null
              metadata: {}
              source_node:
                $component_ref: 6f6dc822-9352-47ae-9b48-173402a334fe
              source_output: $filename
              destination_node:
                $component_ref: 39f36227-8910-414c-8b6b-517c0d65b0d8
              destination_input: $filename
            - component_type: DataFlowEdge
              id: 2f95704b-4cc1-4983-8a20-e39c79a94e01
              name: format_diff_to_string_$diff_to_string_to_None End node_$diff_to_string_data_flow_edge
              description: null
              metadata: {}
              source_node:
                $component_ref: f0fb3ab4-a950-43b6-a583-6f0044f18c7f
              source_output: $diff_to_string
              destination_node:
                $component_ref: 39f36227-8910-414c-8b6b-517c0d65b0d8
              destination_input: $diff_to_string
            $referenced_components:
              6000ee3f-ac80-4937-b36c-94fd65cdcda4:
                component_type: ExtendedToolNode
                id: 6000ee3f-ac80-4937-b36c-94fd65cdcda4
                name: add_lines_on_diff
                description: ''
                metadata:
                  __metadata_info__: {}
                inputs:
                - type: string
                  title: $diff_to_string
                outputs:
                - type: string
                  title: $diff_with_lines
                branches:
                - next
                tool:
                  component_type: ServerTool
                  id: e936566f-7a25-40f3-9434-3e740a7bfb02
                  name: format_git_diff
                  description: Formats a git diff by adding line numbers to each line
                    except removal lines.
                  metadata:
                    __metadata_info__: {}
                  inputs:
                  - type: string
                    title: diff_text
                  outputs:
                  - type: string
                    title: tool_output
                input_mapping:
                  diff_text: $diff_to_string
                output_mapping:
                  tool_output: $diff_with_lines
                raise_exceptions: false
                component_plugin_name: NodesPlugin
                component_plugin_version: 25.4.0.dev0
              f0fb3ab4-a950-43b6-a583-6f0044f18c7f:
                component_type: PluginOutputMessageNode
                id: f0fb3ab4-a950-43b6-a583-6f0044f18c7f
                name: format_diff_to_string
                description: ''
                metadata:
                  __metadata_info__: {}
                inputs:
                - description: '"message" input variable for the template'
                  title: message
                outputs:
                - description: the message added to the messages list
                  type: string
                  title: $diff_to_string
                branches:
                - next
                expose_message_as_output: True
                message: '{{ message | string }}'
                input_mapping: {}
                output_mapping:
                  output_message: $diff_to_string
                message_type: AGENT
                rephrase: false
                llm_config: null
                component_plugin_name: NodesPlugin
                component_plugin_version: 25.4.0.dev0
              6f6dc822-9352-47ae-9b48-173402a334fe:
                component_type: PluginRegexNode
                id: 6f6dc822-9352-47ae-9b48-173402a334fe
                name: extract_file_path
                description: ''
                metadata:
                  __metadata_info__: {}
                inputs:
                - description: raw text to extract information from
                  type: string
                  title: $diff_to_string
                outputs:
                - description: the first extracted value using the regex "diff --git
                    a/(.+?) b/" from the raw input
                  type: string
                  title: $filename
                  default: ''
                branches:
                - next
                input_mapping:
                  text: $diff_to_string
                output_mapping:
                  output: $filename
                regex_pattern: diff --git a/(.+?) b/
                return_first_match_only: true
                component_plugin_name: NodesPlugin
                component_plugin_version: 25.4.0.dev0
              0ce752d7-3ef1-481b-bb01-c7081ef86103:
                component_type: ExtendedLlmNode
                id: 0ce752d7-3ef1-481b-bb01-c7081ef86103
                name: generate_comments
                description: ''
                metadata:
                  __metadata_info__: {}
                inputs:
                - description: '"filename" input variable for the template'
                  type: string
                  title: $filename
                - description: '"diff" input variable for the template'
                  type: string
                  title: $diff_with_lines
                outputs:
                - description: the generated text
                  type: string
                  title: $json_comments
                branches:
                - next
                llm_config:
                  component_type: VllmConfig
                  id: fb043839-1e69-404c-a178-d8c3de0bfe20
                  name: LLAMA_MODEL_ID
                  description: null
                  metadata:
                    __metadata_info__: {}
                  default_generation_parameters: null
                  url: LLAMA_API_URL
                  model_id: LLAMA_MODEL_ID
                prompt_template: "You are a very experienced code reviewer. You are\
                  \ given a git diff on a file: {{ filename }}\n\n## Context\nThe\
                  \ git diff contains all changes of a single file. All lines are\
                  \ prepended with their number. Lines without line number where removed\
                  \ from the file.\nAfter the line number, a line that was changed\
                  \ has a \"+\" before the code. All lines without a \"+\" are just\
                  \ here for context, you will not comment on them.\n\n## Input\n\
                  ### Code diff\n{{ diff }}\n\n## Task\nYour task is to review these\
                  \ changes, according to different rules. Only comment lines that\
                  \ were added, so the lines that have a + just after the line number.\n\
                  The rules are the following:\n\n\nName: TODO_WITHOUT_TICKET\nDescription:\
                  \ TODO comments should reference a ticket number for tracking.\n\
                  Example code:\n```python\n# TODO: Add validation here\ndef process_user_input(data):\n\
                  \    return data\n```\nExample comment:\n[BOT] TODO_WITHOUT_TICKET:\
                  \ TODO comment should reference a ticket number for tracking (e.g.,\
                  \ \"TODO: Add validation here (TICKET-1234)\").\n\n\n---\n\n\nName:\
                  \ MUTABLE_DEFAULT_ARGUMENT\nDescription: Using mutable objects as\
                  \ default arguments can lead to unexpected behavior.\nExample code:\n\
                  ```python\ndef add_item(item, items=[]):\n    items.append(item)\n\
                  \    return items\n```\nExample comment:\n[BOT] MUTABLE_DEFAULT_ARGUMENT:\
                  \ Avoid using mutable default arguments. Use None and initialize\
                  \ in the function: `def add_item(item, items=None): items = items\
                  \ or []`\n\n\n---\n\n\nName: NON_DESCRIPTIVE_NAME\nDescription:\
                  \ Variable names should clearly indicate their purpose or content.\n\
                  Example code:\n```python\ndef process(lst):\n    res = []\n    for\
                  \ i in lst:\n        res.append(i * 2)\n    return res\n```\nExample\
                  \ comment:\n[BOT] NON_DESCRIPTIVE_NAME: Use more descriptive names:\
                  \ 'lst' could be 'numbers', 'res' could be 'doubled_numbers', 'i'\
                  \ could be 'number'\n\n\n### Response Format\nYou need to return\
                  \ a review as a json as follows:\n```json\n[\n    {\n        \"\
                  content\": \"the comment as a text\",\n        \"suggestion\": \"\
                  if the change you propose is a single line, then put here the single\
                  \ line rewritten that includes your proposal change. IMPORTANT:\
                  \ a single line, which will erase the current line. Put empty string\
                  \ if no suggestion of if the suggestion is more than a single line\"\
                  ,\n        \"line\": \"line number where the comment applies\"\n\
                  \    },\n    \u2026\n]\n```\nPlease use triple backticks ``` to\
                  \ delimitate your JSON list of comments. Don't output more than\
                  \ 5 comments, only comment the most relevant sections.\nIf there\
                  \ are no comments and the code seems fine, just output an empty\
                  \ JSON list."
                input_mapping:
                  diff: $diff_with_lines
                  filename: $filename
                output_mapping:
                  output: $json_comments
                prompt_template_object: null
                send_message: false
                component_plugin_name: NodesPlugin
                component_plugin_version: 25.4.0.dev0
              48057b9c-bee7-4286-baf5-625b6f1a6f1a:
                component_type: PluginExtractNode
                id: 48057b9c-bee7-4286-baf5-625b6f1a6f1a
                name: extract_comments_from_json
                description: ''
                metadata:
                  __metadata_info__: {}
                inputs:
                - description: raw text to extract information from
                  type: string
                  title: $json_comments
                outputs:
                - description: The extracted comments content and line number
                  type: array
                  items:
                    type: object
                    additionalProperties: {}
                    key_type:
                      type: string
                  title: $extracted_comments
                branches:
                - next
                input_mapping:
                  text: $json_comments
                output_mapping:
                  values: $extracted_comments
                output_values:
                  values: '[.[] | {"content": .["content"], "line": .["line"]}]'
                component_plugin_name: NodesPlugin
                component_plugin_version: 25.4.0.dev0
              e20f5870-d594-4089-9fcd-08146232910d:
                component_type: StartNode
                id: e20f5870-d594-4089-9fcd-08146232910d
                name: __StartStep__
                description: ''
                metadata:
                  __metadata_info__: {}
                inputs:
                - description: '"message" input variable for the template'
                  title: message
                outputs:
                - description: '"message" input variable for the template'
                  title: message
                branches:
                - next
              39f36227-8910-414c-8b6b-517c0d65b0d8:
                component_type: EndNode
                id: 39f36227-8910-414c-8b6b-517c0d65b0d8
                name: None End node
                description: End node representing all transitions to None in the
                  WayFlow flow
                metadata: {}
                inputs:
                - description: The extracted comments content and line number
                  type: array
                  items:
                    type: object
                    additionalProperties: {}
                    key_type:
                      type: string
                  title: $extracted_comments
                - description: the generated text
                  type: string
                  title: $json_comments
                - type: string
                  title: $diff_with_lines
                - description: the first extracted value using the regex "diff --git
                    a/(.+?) b/" from the raw input
                  type: string
                  title: $filename
                  default: ''
                - description: the message added to the messages list
                  type: string
                  title: $diff_to_string
                outputs:
                - description: The extracted comments content and line number
                  type: array
                  items:
                    type: object
                    additionalProperties: {}
                    key_type:
                      type: string
                  title: $extracted_comments
                - description: the generated text
                  type: string
                  title: $json_comments
                - type: string
                  title: $diff_with_lines
                - description: the first extracted value using the regex "diff --git
                    a/(.+?) b/" from the raw input
                  type: string
                  title: $filename
                  default: ''
                - description: the message added to the messages list
                  type: string
                  title: $diff_to_string
                branches: []
                branch_name: next
          unpack_input:
            message: .
          parallel_execution: false
          component_plugin_name: NodesPlugin
          component_plugin_version: 25.4.0.dev0
        367ae568-317d-42ec-ae70-4c41afe0dbd0:
          component_type: StartNode
          id: 367ae568-317d-42ec-ae70-4c41afe0dbd0
          name: __StartStep__
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - description: iterated input for the map step
            type: array
            items:
              description: '"message" input variable for the template'
              title: message
            title: $file_diff_list
          outputs:
          - description: iterated input for the map step
            type: array
            items:
              description: '"message" input variable for the template'
              title: message
            title: $file_diff_list
          branches:
          - next
        6f62aecf-03a1-4e38-b551-8eef0efaf4bb:
          component_type: EndNode
          id: 6f62aecf-03a1-4e38-b551-8eef0efaf4bb
          name: None End node
          description: End node representing all transitions to None in the WayFlow
            flow
          metadata: {}
          inputs:
          - type: array
            items:
              type: string
            title: $filepath_list
          - type: array
            items: {}
            title: $nested_comment_list
          outputs:
          - type: array
            items:
              type: string
            title: $filepath_list
          - type: array
            items: {}
            title: $nested_comment_list
          branches: []
          branch_name: next
  47e367be-4d74-49dc-ac3b-89bb97ffa7df:
    component_type: FlowNode
    id: 47e367be-4d74-49dc-ac3b-89bb97ffa7df
    name: retrieve_diff_flowstep
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: string
      title: $repo_dirpath_io
    outputs:
    - type: string
      title: $raw_pr_diff
    - description: the list of extracted value using the regex "(diff --git[\s\S]*?)(?=diff
        --git|$)" from the raw input
      type: array
      items:
        type: string
      title: $file_diff_list
      default: []
    branches:
    - next
    subflow:
      component_type: Flow
      id: 9e7aed22-876c-4c32-9d44-20ee7ceb3771
      name: Retrieve PR diff flow
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - type: string
        title: $repo_dirpath_io
      outputs:
      - type: string
        title: $raw_pr_diff
      - description: the list of extracted value using the regex "(diff --git[\s\S]*?)(?=diff
          --git|$)" from the raw input
        type: array
        items:
          type: string
        title: $file_diff_list
        default: []
      start_node:
        $component_ref: 4fcb7ebe-325b-446d-a46b-59187c30e260
      nodes:
      - $component_ref: 4fcb7ebe-325b-446d-a46b-59187c30e260
      - $component_ref: 5c73da9c-6ba9-44ce-aab1-212a78d0a720
      - $component_ref: cf841053-2414-48b6-ba6d-0f0f5e11044c
      - $component_ref: dd0e56ab-1267-4345-9f59-ecc053baf2af
      control_flow_connections:
      - component_type: ControlFlowEdge
        id: 60dc14b8-d9b9-4aec-a958-9f3676848f48
        name: start_step_to_get_pr_diff_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: 4fcb7ebe-325b-446d-a46b-59187c30e260
        from_branch: null
        to_node:
          $component_ref: 5c73da9c-6ba9-44ce-aab1-212a78d0a720
      - component_type: ControlFlowEdge
        id: 500f97de-78b1-42e0-944c-0375dfca734e
        name: get_pr_diff_to_extract_into_list_of_file_diff_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: 5c73da9c-6ba9-44ce-aab1-212a78d0a720
        from_branch: null
        to_node:
          $component_ref: cf841053-2414-48b6-ba6d-0f0f5e11044c
      - component_type: ControlFlowEdge
        id: 22d0cf0d-8edb-4b04-8f54-a234f5705360
        name: extract_into_list_of_file_diff_to_None End node_control_flow_edge
        description: null
        metadata: {}
        from_node:
          $component_ref: cf841053-2414-48b6-ba6d-0f0f5e11044c
        from_branch: null
        to_node:
          $component_ref: dd0e56ab-1267-4345-9f59-ecc053baf2af
      data_flow_connections:
      - component_type: DataFlowEdge
        id: 106e3740-de45-4472-8168-2873ae1dbc82
        name: start_step_$repo_dirpath_io_to_get_pr_diff_$repo_dirpath_io_data_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        source_node:
          $component_ref: 4fcb7ebe-325b-446d-a46b-59187c30e260
        source_output: $repo_dirpath_io
        destination_node:
          $component_ref: 5c73da9c-6ba9-44ce-aab1-212a78d0a720
        destination_input: $repo_dirpath_io
      - component_type: DataFlowEdge
        id: a32cbb1c-eafe-4138-80e2-2cf2e1248312
        name: get_pr_diff_$raw_pr_diff_to_extract_into_list_of_file_diff_$raw_pr_diff_data_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        source_node:
          $component_ref: 5c73da9c-6ba9-44ce-aab1-212a78d0a720
        source_output: $raw_pr_diff
        destination_node:
          $component_ref: cf841053-2414-48b6-ba6d-0f0f5e11044c
        destination_input: $raw_pr_diff
      - component_type: DataFlowEdge
        id: 3ef5dcf4-acdf-4962-8df6-07b53f249e18
        name: get_pr_diff_$raw_pr_diff_to_None End node_$raw_pr_diff_data_flow_edge
        description: null
        metadata: {}
        source_node:
          $component_ref: 5c73da9c-6ba9-44ce-aab1-212a78d0a720
        source_output: $raw_pr_diff
        destination_node:
          $component_ref: dd0e56ab-1267-4345-9f59-ecc053baf2af
        destination_input: $raw_pr_diff
      - component_type: DataFlowEdge
        id: 08cbca39-e591-4cf4-9057-ae67938d9557
        name: extract_into_list_of_file_diff_$file_diff_list_to_None End node_$file_diff_list_data_flow_edge
        description: null
        metadata: {}
        source_node:
          $component_ref: cf841053-2414-48b6-ba6d-0f0f5e11044c
        source_output: $file_diff_list
        destination_node:
          $component_ref: dd0e56ab-1267-4345-9f59-ecc053baf2af
        destination_input: $file_diff_list
      $referenced_components:
        5c73da9c-6ba9-44ce-aab1-212a78d0a720:
          component_type: ExtendedToolNode
          id: 5c73da9c-6ba9-44ce-aab1-212a78d0a720
          name: get_pr_diff
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - type: string
            title: $repo_dirpath_io
          outputs:
          - type: string
            title: $raw_pr_diff
          branches:
          - next
          tool:
            component_type: ServerTool
            id: 275aaf19-cdd4-4ed7-a436-e53f922cd740
            name: local_get_pr_diff_tool
            description: '# docs-skiprow

              Retrieves code diff with a git command given the  # docs-skiprow

              path to the repository root folder.  # docs-skiprow'
            metadata:
              __metadata_info__: {}
            inputs:
            - type: string
              title: repo_dirpath
            outputs:
            - type: string
              title: tool_output
          input_mapping:
            repo_dirpath: $repo_dirpath_io
          output_mapping:
            tool_output: $raw_pr_diff
          raise_exceptions: true
          component_plugin_name: NodesPlugin
          component_plugin_version: 25.4.0.dev0
        4fcb7ebe-325b-446d-a46b-59187c30e260:
          component_type: StartNode
          id: 4fcb7ebe-325b-446d-a46b-59187c30e260
          name: start_step
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - type: string
            title: $repo_dirpath_io
          outputs:
          - type: string
            title: $repo_dirpath_io
          branches:
          - next
        cf841053-2414-48b6-ba6d-0f0f5e11044c:
          component_type: PluginRegexNode
          id: cf841053-2414-48b6-ba6d-0f0f5e11044c
          name: extract_into_list_of_file_diff
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - description: raw text to extract information from
            type: string
            title: $raw_pr_diff
          outputs:
          - description: the list of extracted value using the regex "(diff --git[\s\S]*?)(?=diff
              --git|$)" from the raw input
            type: array
            items:
              type: string
            title: $file_diff_list
            default: []
          branches:
          - next
          input_mapping:
            text: $raw_pr_diff
          output_mapping:
            output: $file_diff_list
          regex_pattern: (diff --git[\s\S]*?)(?=diff --git|$)
          return_first_match_only: false
          component_plugin_name: NodesPlugin
          component_plugin_version: 25.4.0.dev0
        dd0e56ab-1267-4345-9f59-ecc053baf2af:
          component_type: EndNode
          id: dd0e56ab-1267-4345-9f59-ecc053baf2af
          name: None End node
          description: End node representing all transitions to None in the WayFlow
            flow
          metadata: {}
          inputs:
          - type: string
            title: $raw_pr_diff
          - description: the list of extracted value using the regex "(diff --git[\s\S]*?)(?=diff
              --git|$)" from the raw input
            type: array
            items:
              type: string
            title: $file_diff_list
            default: []
          outputs:
          - type: string
            title: $raw_pr_diff
          - description: the list of extracted value using the regex "(diff --git[\s\S]*?)(?=diff
              --git|$)" from the raw input
            type: array
            items:
              type: string
            title: $file_diff_list
            default: []
          branches: []
          branch_name: next
  020c885e-6d0b-472a-bb91-246ab70ab1db:
    component_type: StartNode
    id: 020c885e-6d0b-472a-bb91-246ab70ab1db
    name: __StartStep__
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: string
      title: $repo_dirpath_io
    outputs:
    - type: string
      title: $repo_dirpath_io
    branches:
    - next
  a544af64-e63b-4ccf-9ab0-8d25cdbc0b93:
    component_type: EndNode
    id: a544af64-e63b-4ccf-9ab0-8d25cdbc0b93
    name: None End node
    description: End node representing all transitions to None in the WayFlow flow
    metadata: {}
    inputs:
    - type: array
      items:
        type: string
      title: $filepath_list
    - type: array
      items: {}
      title: $nested_comment_list
    - type: string
      title: $raw_pr_diff
    - description: the list of extracted value using the regex "(diff --git[\s\S]*?)(?=diff
        --git|$)" from the raw input
      type: array
      items:
        type: string
      title: $file_diff_list
      default: []
    outputs:
    - type: array
      items:
        type: string
      title: $filepath_list
    - type: array
      items: {}
      title: $nested_comment_list
    - type: string
      title: $raw_pr_diff
    - description: the list of extracted value using the regex "(diff --git[\s\S]*?)(?=diff
        --git|$)" from the raw input
      type: array
      items:
        type: string
      title: $file_diff_list
      default: []
    branches: []
    branch_name: next
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    "local_get_pr_diff_tool": local_get_pr_diff_tool,
    "format_git_diff": format_git_diff,
}

assistant = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_assistant)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginOutputMessageNode`
- `PluginExtractNode`
- `PluginRegexNode`
- `ExtendedLlmNode`
- `ExtendedToolNode`
- `ExtendedMapNode`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Recap

In this tutorial you learned how to build a simple PR bot using WayFlow Flows, and learned:

- How to use core steps such as the [OutputMessageStep](../api/flows.md#outputmessagestep) and [PromptExecutionStep](../api/flows.md#promptexecutionstep).
- How to build and execute tools using the [ServerTool](../api/tools.md#servertool) and the [ToolExecutionStep](../api/flows.md#toolexecutionstep).
- How to extract information using the [RegexExtractionStep](../api/flows.md#regexextractionstep) and the [ExtractValueFromJsonStep](../api/flows.md#extractvaluefromjsonstep).
- How to apply a sub flow over an iterable data using the [MapStep](../api/flows.md#mapstep).

Finally, you learned how to structure code when building assistant as code and how to execute and combine sub flows to build complex assistant.

This is an example of the kind of fully featured tool that you can build with WayFlow.

## Next Steps

Now that you learned how to build a PR reviewing assistant, you may want to check our other guides such as:

- [Build a Simple Agent](basic_agent.md)
- [How to Catch Exceptions in Flows](../howtoguides/catching_exceptions.md)

## Full Code

Click on the card at the [top of this page](#top-simple-code-review-assistant) to download the full code
for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Tutorial - Build a Simple Code Review Assistant
# -----------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.2.0.dev0" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python usecase_prbot.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# nosec


from types import MethodType
from typing import Dict, List


# %%[markdown]
## Define the LLM

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="meta-llama/Meta-Llama-3.1-8B-Instruct",
    host_port="VLLM_HOST_PORT",
)

# %%[markdown]
## Define the tool that retrieves the PR diff

# %%
from wayflowcore.tools import tool


@tool(description_mode="only_docstring")
def local_get_pr_diff_tool(repo_dirpath: str) -> str:
    """
    Retrieves code diff with a git command given the
    path to the repository root folder.
    """
    import subprocess

    result = subprocess.run(
        ["git", "diff", "HEAD"],
        capture_output=True,
        cwd=repo_dirpath,
        text=True,
    )
    return result.stdout.strip()


# %%[markdown]
## Define a mocked PR diff

# %%
MOCK_DIFF = """
diff --git src://calculators/utils.py dst://calculators/utils.py
index 12345678..90123456 100644
--- src://calculators/utils.py
+++ dst://calculators/utils.py
@@ -10,6 +10,15 @@

 def calculate_total(data):
     # TODO: implement tax calculation
     return data

+def get_items(items=[]):
+    result = []
+    for item in items:
+        result.append(item * 2)
+    return result
+
+def process_numbers(numbers):
+    res = []
+    for x in numbers:
+        res.append(x + 1)
+    return res
+
 def calculate_average(numbers):
     return sum(numbers) / len(numbers)


diff --git src://example/utils.py dst://example/utils.py
index 000000000..123456789
--- /dev/null
+++ dst://example/utils.py
@@ -0,0 +1,20 @@
+# Copyright © 2024 Oracle and/or its affiliates.
+
+def calculate_sum(numbers=[]):
+    total = 0
+    for num in numbers:
+        total += num
+    return total
+
+
+def process_data(data):
+    # TODO: Handle exceptions here
+    result = data * 2
+    return result
+
+
+def main():
+    numbers = [1, 2, 3, 4, 5]
+    result = calculate_sum(numbers)
+    print("Sum:", result)
+    data = 10
+    processed_data = process_data(data)
+    print("Processed Data:", processed_data)
+
+
+if __name__ == "__main__":
+    main()
""".strip()



# %%[markdown]
## Create the flow that retrieves the diff of a PR

# %%
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import RegexExtractionStep, StartStep, ToolExecutionStep

# IO Variable Names
REPO_DIRPATH_IO = "$repo_dirpath_io"
PR_DIFF_IO = "$raw_pr_diff"
FILE_DIFF_LIST_IO = "$file_diff_list"

# Define the steps

start_step = StartStep(name="start_step", input_descriptors=[StringProperty(name=REPO_DIRPATH_IO)])

# Step 1: Retrieve the pull request diff using the local tool
get_pr_diff_step = ToolExecutionStep(
    name="get_pr_diff",
    tool=local_get_pr_diff_tool,
    raise_exceptions=True,
    input_mapping={"repo_dirpath": REPO_DIRPATH_IO},
    output_mapping={ToolExecutionStep.TOOL_OUTPUT: PR_DIFF_IO},
)

# Step 2: Extract the file diffs from the raw diff using a regular expression
extract_into_list_of_file_diff_step = RegexExtractionStep(
    name="extract_into_list_of_file_diff",
    regex_pattern=r"(diff --git[\s\S]*?)(?=diff --git|$)",
    return_first_match_only=False,
    input_mapping={RegexExtractionStep.TEXT: PR_DIFF_IO},
    output_mapping={RegexExtractionStep.OUTPUT: FILE_DIFF_LIST_IO},
)

# Define the sub flow
retrieve_diff_subflow = Flow(
    name="Retrieve PR diff flow",
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=get_pr_diff_step),
        ControlFlowEdge(
            source_step=get_pr_diff_step, destination_step=extract_into_list_of_file_diff_step
        ),
        ControlFlowEdge(source_step=extract_into_list_of_file_diff_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            source_step=start_step,
            source_output=REPO_DIRPATH_IO,
            destination_step=get_pr_diff_step,
            destination_input=REPO_DIRPATH_IO,
        ),
        DataFlowEdge(
            source_step=get_pr_diff_step,
            source_output=PR_DIFF_IO,
            destination_step=extract_into_list_of_file_diff_step,
            destination_input=PR_DIFF_IO,
        ),
    ],
)


# %%[markdown]
## Alternative step that retrieves the PR diff through an API call

# %%
from wayflowcore.steps import ApiCallStep

# IO Variable Names
USER_PROVIDED_TOKEN_IO = "$user_provided_token"
REPO_WORKSPACE_IO = "$repo_workspace"
REPO_SLUG_IO = "$repo_slug"
PULL_REQUEST_ID_IO = "$pull_request_id"
PR_DIFF_IO = "$raw_pr_diff"

get_pr_diff_step = ApiCallStep(
    url="https://example.com/projects/{{workspace}}/repos/{{repo_slug}}/pull-requests/{{pr_id}}.diff",
    method="GET",
    headers={"Authorization": "Bearer {{token}}"},
    ignore_bad_http_requests=False,
    num_retry_on_bad_http_request=3,
    store_response=True,
    input_mapping={
        "token": USER_PROVIDED_TOKEN_IO,
        "workspace": REPO_WORKSPACE_IO,
        "repo_slug": REPO_SLUG_IO,
        "pr_id": PULL_REQUEST_ID_IO,
    },
    output_mapping={ApiCallStep.HTTP_RESPONSE: PR_DIFF_IO},
)


# %%[markdown]
## Test the flow that retrieves the PR diff

# %%
from wayflowcore.executors.executionstatus import FinishedStatus

# Replace the path below with the path to your actual codebase sample git repository.
PATH_TO_DIR = "path/to/repository_root"

test_conversation = retrieve_diff_subflow.start_conversation(
    inputs={
        REPO_DIRPATH_IO: PATH_TO_DIR,
    }
)

execution_status = test_conversation.execute()

if not isinstance(execution_status, FinishedStatus):
    raise ValueError("Unexpected status type")

FILE_DIFF_LIST = execution_status.output_values[FILE_DIFF_LIST_IO]

print(FILE_DIFF_LIST[0])


# %%[markdown]
## Define the tool that formats the diff for the LLM

# %%
PR_BOT_CHECKS = [
    """
Name: TODO_WITHOUT_TICKET
Description: TODO comments should reference a ticket number for tracking.
Example code:
```python
# TODO: Add validation here
def process_user_input(data):
    return data
```
Example comment:
[BOT] TODO_WITHOUT_TICKET: TODO comment should reference a ticket number for tracking (e.g., "TODO: Add validation here (TICKET-1234)").
""",
    """
Name: MUTABLE_DEFAULT_ARGUMENT
Description: Using mutable objects as default arguments can lead to unexpected behavior.
Example code:
```python
def add_item(item, items=[]):
    items.append(item)
    return items
```
Example comment:
[BOT] MUTABLE_DEFAULT_ARGUMENT: Avoid using mutable default arguments. Use None and initialize in the function: `def add_item(item, items=None): items = items or []`
""",
    """
Name: NON_DESCRIPTIVE_NAME
Description: Variable names should clearly indicate their purpose or content.
Example code:
```python
def process(lst):
    res = []
    for i in lst:
        res.append(i * 2)
    return res
```
Example comment:
[BOT] NON_DESCRIPTIVE_NAME: Use more descriptive names: 'lst' could be 'numbers', 'res' could be 'doubled_numbers', 'i' could be 'number'
""",
]

CONCATENATED_CHECKS = "\n\n---\n\n".join(check for check in PR_BOT_CHECKS)

PROMPT_TEMPLATE = """You are a very experienced code reviewer. You are given a git diff on a file: {{filename}}

## Context
The git diff contains all changes of a single file. All lines are prepended with their number. Lines without line number where removed from the file.
After the line number, a line that was changed has a "+" before the code. All lines without a "+" are just here for context, you will not comment on them.

## Input
### Code diff
{{diff}}

## Task
Your task is to review these changes, according to different rules. Only comment lines that were added, so the lines that have a + just after the line number.
The rules are the following:

{{checks}}

### Response Format
You need to return a review as a json as follows:
```json
[
    {
        "content": "the comment as a text",
        "suggestion": "if the change you propose is a single line, then put here the single line rewritten that includes your proposal change. IMPORTANT: a single line, which will erase the current line. Put empty string if no suggestion of if the suggestion is more than a single line",
        "line": "line number where the comment applies"
    },
    …
]
```
Please use triple backticks ``` to delimitate your JSON list of comments. Don't output more than 5 comments, only comment the most relevant sections.
If there are no comments and the code seems fine, just output an empty JSON list."""


@tool(description_mode="only_docstring")
def format_git_diff(diff_text: str) -> str:
    """
    Formats a git diff by adding line numbers to each line except removal lines.
    """

    def pad_number(number: int, width: int) -> str:
        """Right-align a number with specified width using space padding."""
        return str(number).rjust(width)

    LINE_NUMBER_WIDTH = 5
    PADDING_WIDTH = LINE_NUMBER_WIDTH + 1
    current_line_number = 0
    formatted_lines = []

    for line in diff_text.split("\n"):
        # Handle diff header lines (e.g., "@@ -1,7 +1,6 @@")
        if line.startswith("@@"):
            try:
                # Extract the starting line number and line count
                _, position_info, _ = line.split("@@")
                new_file_info = position_info.split()[1][1:]  # Remove the '+' prefix
                start_line, line_count = map(int, new_file_info.split(","))

                current_line_number = start_line
                formatted_lines.append(line)
                continue

            except (ValueError, IndexError):
                raise ValueError(f"Invalid diff header format: {line}")

        # Handle content lines
        if current_line_number > 0 and line:
            if not line.startswith("-"):
                # Add line number for added/context lines
                line_prefix = pad_number(current_line_number, LINE_NUMBER_WIDTH)
                formatted_lines.append(f"{line_prefix} {line}")
                current_line_number += 1
            else:
                # Just add padding for removal lines
                formatted_lines.append(" " * PADDING_WIDTH + line)

    return "\n".join(formatted_lines)


# %%[markdown]
## Create the flow that generates review comments

# %%
from wayflowcore._utils._templating_helpers import render_template_partially
from wayflowcore.property import AnyProperty, DictProperty, ListProperty, StringProperty
from wayflowcore.steps import (
    ExtractValueFromJsonStep,
    MapStep,
    OutputMessageStep,
    PromptExecutionStep,
    ToolExecutionStep,
)

# IO Variable Names
DIFF_TO_STRING_IO = "$diff_to_string"
DIFF_WITH_LINES_IO = "$diff_with_lines"
FILEPATH_IO = "$filename"
JSON_COMMENTS_IO = "$json_comments"
EXTRACTED_COMMENTS_IO = "$extracted_comments"
NESTED_COMMENT_LIST_IO = "$nested_comment_list"
FILEPATH_LIST_IO = "$filepath_list"

# Define the steps

# Step 1: Format the diff to a string
format_diff_to_string_step = OutputMessageStep(
    name="format_diff_to_string",
    message_template="{{ message | string }}",
    output_mapping={OutputMessageStep.OUTPUT: DIFF_TO_STRING_IO},
)

# Step 2: Add lines on the diff using a tool
add_lines_on_diff_step = ToolExecutionStep(
    name="add_lines_on_diff",
    tool=format_git_diff,
    input_mapping={"diff_text": DIFF_TO_STRING_IO},
    output_mapping={ToolExecutionStep.TOOL_OUTPUT: DIFF_WITH_LINES_IO},
)

# Step 3: Extract the file path from the diff string using a regular expression
extract_file_path_step = RegexExtractionStep(
    name="extract_file_path",
    regex_pattern=r"diff --git src://(.+?) dst://",
    return_first_match_only=True,
    input_mapping={RegexExtractionStep.TEXT: DIFF_TO_STRING_IO},
    output_mapping={RegexExtractionStep.OUTPUT: FILEPATH_IO},
)

# Step 4: Generate comments using a prompt
generate_comments_step = PromptExecutionStep(
    name="generate_comments",
    prompt_template=render_template_partially(PROMPT_TEMPLATE, {"checks": CONCATENATED_CHECKS}),
    llm=llm,
    input_mapping={"diff": DIFF_WITH_LINES_IO, "filename": FILEPATH_IO},
    output_mapping={PromptExecutionStep.OUTPUT: JSON_COMMENTS_IO},
)

# Step 5: Extract comments from the JSON output
# Define the value type for extracted comments
comments_valuetype = ListProperty(
    name="values",
    description="The extracted comments content and line number",
    item_type=DictProperty(value_type=AnyProperty()),
    default_value=[],
)
extract_comments_from_json_step = ExtractValueFromJsonStep(
    name="extract_comments_from_json",
    output_values={comments_valuetype: '[.[] | {"content": .["content"], "line": .["line"]}]'},
    retry=True,
    llm=llm,
    input_mapping={ExtractValueFromJsonStep.TEXT: JSON_COMMENTS_IO},
    output_mapping={"values": EXTRACTED_COMMENTS_IO},
)

# Define the sub flow to generate comments for each file diff
generate_comments_subflow = Flow(
    name="Generate review comments flow",
    begin_step=format_diff_to_string_step,
    control_flow_edges=[
        ControlFlowEdge(format_diff_to_string_step, add_lines_on_diff_step),
        ControlFlowEdge(add_lines_on_diff_step, extract_file_path_step),
        ControlFlowEdge(extract_file_path_step, generate_comments_step),
        ControlFlowEdge(generate_comments_step, extract_comments_from_json_step),
        ControlFlowEdge(extract_comments_from_json_step, None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            format_diff_to_string_step, DIFF_TO_STRING_IO, add_lines_on_diff_step, DIFF_TO_STRING_IO
        ),
        DataFlowEdge(
            format_diff_to_string_step, DIFF_TO_STRING_IO, extract_file_path_step, DIFF_TO_STRING_IO
        ),
        DataFlowEdge(
            add_lines_on_diff_step, DIFF_WITH_LINES_IO, generate_comments_step, DIFF_WITH_LINES_IO
        ),
        DataFlowEdge(extract_file_path_step, FILEPATH_IO, generate_comments_step, FILEPATH_IO),
        DataFlowEdge(
            generate_comments_step,
            JSON_COMMENTS_IO,
            extract_comments_from_json_step,
            JSON_COMMENTS_IO,
        ),
    ],
)

# Use the MapStep to apply the sub flow to each file
for_each_file_step = MapStep(
    flow=generate_comments_subflow,
    unpack_input={"message": "."},
    input_mapping={MapStep.ITERATED_INPUT: FILE_DIFF_LIST_IO},
    output_descriptors=[
        ListProperty(name=NESTED_COMMENT_LIST_IO, item_type=AnyProperty()),
        ListProperty(name=FILEPATH_LIST_IO, item_type=StringProperty()),
    ],
    output_mapping={EXTRACTED_COMMENTS_IO: NESTED_COMMENT_LIST_IO, FILEPATH_IO: FILEPATH_LIST_IO},
)

generate_all_comments_subflow = Flow.from_steps([for_each_file_step])


# %%[markdown]
## Test the flow that generates review comments

# %%
# we reuse the FILE_DIFF_LIST from the previous test
test_conversation = generate_all_comments_subflow.start_conversation(
    inputs={
        FILE_DIFF_LIST_IO: FILE_DIFF_LIST,
    }
)

execution_status = test_conversation.execute()

if not isinstance(execution_status, FinishedStatus):
    raise ValueError("Unexpected status type")

NESTED_COMMENT_LIST = execution_status.output_values[NESTED_COMMENT_LIST_IO]
FILEPATH_LIST = execution_status.output_values[FILEPATH_LIST_IO]
print(NESTED_COMMENT_LIST[0])
print(FILEPATH_LIST)



# %%[markdown]
## Create tool that formats the review comments

# %%
@tool(description_mode="only_docstring")
def flatten_information(
    nested_comments_list: List[List[Dict[str, str]]], filepath_list: List[str]
) -> List[Dict[str, str]]:
    """Flattens information from comments and filepaths."""
    if len(nested_comments_list) != len(filepath_list):
        raise ValueError(
            f"Inconsistent list lengths ({len(nested_comments_list)=} and {len(filepath_list)=})"
        )

    result: List[Dict[str, str]] = []
    for comments_list, filepath in zip(nested_comments_list, filepath_list):
        for comment_dict in comments_list:
            result.append(
                {
                    **{key: str(value) for key, value in comment_dict.items()},
                    "path": filepath,
                }
            )

    return result


# %%[markdown]
## Create flow that posts review comments to bitbucket

# %%
import json

# IO Values
PR_POST_URL_IO = "$pr_post_url"
FLATTENED_COMMENT_LIST_IO = "$flattened_comment_list"
FINAL_HTTP_CODES_IO = "$http_codes"

# Define the steps

# Step 1: Flatten the generated comments into a list of comments
flatten_nested_comments_list_step = ToolExecutionStep(
    name="flatten_nested_comment_list",
    tool=flatten_information,
    input_mapping={
        "nested_comments_list": NESTED_COMMENT_LIST_IO,
        "filepath_list": FILEPATH_LIST_IO,
    },
    output_mapping={ToolExecutionStep.TOOL_OUTPUT: FLATTENED_COMMENT_LIST_IO},
)

# Step 2: Post the comments to bitbucket
post_comment_step = ApiCallStep(
    url="https://example.com/rest/api/latest/projects/{{workspace}}/repos/{{repo_slug}}/pull-requests/{{pr_id}}/comments?diffType=EFFECTIVE&markup=true&avatarSize=48",
    method="POST",
    data=json.dumps(
        {
            "text": "{{content}}",
            "severity": "NORMAL",
            "anchor": {
                "diffType": "EFFECTIVE",
                "path": "{{path}}",
                "lineType": "ADDED",
                "line": "{{line | int}}",
                "fileType": "TO",
            },
        }
    ),
    headers={"Accept": "application/json", "Authorization": "Bearer {{token}}"},
    ignore_bad_http_requests=False,
    num_retry_on_bad_http_request=3,
    store_response=True,
    input_mapping={
        "token": USER_PROVIDED_TOKEN_IO,
        "workspace": REPO_WORKSPACE_IO,
        "repo_slug": REPO_SLUG_IO,
        "pr_id": PULL_REQUEST_ID_IO,
    },
)

post_comments_mapstep = MapStep(
    name="post_comment",
    flow=Flow.from_steps([post_comment_step]),
    unpack_input={"content": ".content", "line": ".line", "path": ".path"},
    input_mapping={MapStep.ITERATED_INPUT: FLATTENED_COMMENT_LIST_IO},
    output_descriptors=[ApiCallStep.HTTP_STATUS_CODE],
    output_mapping={ApiCallStep.HTTP_STATUS_CODE: FINAL_HTTP_CODES_IO},
)

post_comments_subflow = Flow(
    name="Post comments to PR flow",
    begin_step=flatten_nested_comments_list_step,
    control_flow_edges=[
        ControlFlowEdge(flatten_nested_comments_list_step, post_comments_mapstep),
        ControlFlowEdge(post_comments_mapstep, None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            flatten_nested_comments_list_step,
            FLATTENED_COMMENT_LIST_IO,
            post_comments_mapstep,
            FLATTENED_COMMENT_LIST_IO,
        )
    ],
)
from wayflowcore.steps.step import StepResult


async def _mock_api_post_step_invoke(self, inputs, conversation):
    output_values = {ApiCallStep.HTTP_RESPONSE: MOCK_DIFF, ApiCallStep.HTTP_STATUS_CODE: 200}
    return StepResult(
        outputs=output_values,
    )


post_comment_step.invoke_async = MethodType(_mock_api_post_step_invoke, post_comment_step)


# %%[markdown]
## Test flow that posts review comments

# %%
# we reuse the NESTED_COMMENT_LIST and FILEPATH_LIST from the previous test

test_conversation = post_comments_subflow.start_conversation(
    inputs={
        USER_PROVIDED_TOKEN_IO: "MY_TOKEN",
        REPO_WORKSPACE_IO: "MY_REPO_WORKSPACE",
        REPO_SLUG_IO: "MY_REPO_SLUG",
        PULL_REQUEST_ID_IO: "MY_REPO_ID",
        NESTED_COMMENT_LIST_IO: NESTED_COMMENT_LIST,
        FILEPATH_LIST_IO: FILEPATH_LIST,
    }
)
execution_status = test_conversation.execute()

if not isinstance(execution_status, FinishedStatus):
    raise ValueError("Unexpected status type")

FINAL_HTTP_CODES = execution_status.output_values[FINAL_HTTP_CODES_IO]
print(FINAL_HTTP_CODES)


# %%[markdown]
## Create flow that performs the review

# %%
from wayflowcore.steps import FlowExecutionStep


# Steps
retrieve_diff_flowstep = FlowExecutionStep(name="retrieve_diff_flowstep", flow=retrieve_diff_subflow)
generate_all_comments_flowstep = FlowExecutionStep(
    name="generate_comments_flowstep",
    flow=generate_all_comments_subflow,
)

pr_bot = Flow(
    name="PR bot flow",
    begin_step=retrieve_diff_flowstep,
    control_flow_edges=[
        ControlFlowEdge(retrieve_diff_flowstep, generate_all_comments_flowstep),
        ControlFlowEdge(generate_all_comments_flowstep, None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            retrieve_diff_flowstep,
            FILE_DIFF_LIST_IO,
            generate_all_comments_flowstep,
            FILE_DIFF_LIST_IO,
        )
    ],
)


# %%[markdown]
## Tests flow that performs the review

# %%
# Replace the path below with the path to your actual codebase sample git repository.
PATH_TO_DIR = "path/to/repository_root"

conversation = pr_bot.start_conversation(inputs={REPO_DIRPATH_IO: PATH_TO_DIR})

execution_status = conversation.execute()

if not isinstance(execution_status, FinishedStatus):
    raise ValueError("Unexpected status type")

print(execution_status.output_values)

NESTED_COMMENT_LIST = execution_status.output_values[NESTED_COMMENT_LIST_IO]


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(pr_bot)


# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    "local_get_pr_diff_tool": local_get_pr_diff_tool,
    "format_git_diff": format_git_diff,
}

assistant = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_assistant)
```
