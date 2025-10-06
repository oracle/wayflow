# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# Tutorial - Build a Simple Code Review Assistant
# -----------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python usecase_prbot.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

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

### Reponse Format
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
    regex_pattern=r"diff --git a/(.+?) b/",
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
    json_body=json.dumps(
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
