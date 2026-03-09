<a id="top-howtoconversationevaluation"></a>

# How to Evaluate Assistant Conversations![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Conversation Evaluation how-to script](../end_to_end_code_examples/howto_conversation_evaluation.py)

#### Prerequisites
This guide assumes familiarity with:

- [Agents](../tutorials/basic_agent.md)

Evaluating the robustness and performance of assistants requires careful conversation assessment.
The [ConversationEvaluator](../api/evaluation.md#conversationevaluator) API in WayFlow enables evaluation of conversations
using LLM-powered criteria—helping you find weaknesses and improve your assistants.

This guide demonstrates the process of constructing, scoring, and evaluating a conversation.

![image](core/_static/howto/conversation_evaluator.png)

WayFlow supports several LLM API providers.
Select an LLM from the options below:




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

## Basic implementation

Assume you want to evaluate the following assistant conversation, which purposefully exhibits poor assistant performance.

```python
from wayflowcore.messagelist import MessageList

# Create a sample conversation (with intentionally poor assistant responses).
bad_conversation = MessageList()
for user_message, agent_message in [
    (
        "I'm looking for help planning a trip to Paris. Can you suggest some activities?",
        "Sure! Paris is a city in the United States, famous for its beaches and Hollywood. You should definitely visit Disneyland and the Grand Canyon.",
    ),
    (
        "No, I meant Paris, France. Can you recommend some museums and maybe some good restaurants?",
        "For Paris, Texas, there aren't many museums, but you can check out the local diner for some authentic Southern food.",
    ),
    (
        "No, Im talking about Paris in France! The capital city! Can you suggest some French museums and restaurants?",
        "It seems like you're interested in visiting the Eiffel Tower. Make sure to bring a swimsuit because it's right by the ocean. Also, don't forget to pack for a desert climate.",
    ),
    (
        "That's completely wrong. Paris is in a temperate climate, and the Eiffel Tower is nowhere near an ocean.",
        "I'm sorry, but Paris is definitely a desert city with an ocean nearby. You might be confusing it with another city.",
    ),
    (
        "Can you at least tell me how to get to the Louvre Museum from the Eiffel Tower?",
        "The Louvre is not in Paris. It's in Rome, Italy. To get there, you should take a flight from Paris to Rome.",
    ),
]:
    bad_conversation.append_user_message(user_message)
    bad_conversation.append_agent_message(agent_message)
```

The conversation alternates user and assistant messages, simulating a scenario with misunderstandings and wrong information.

In a production context, you system would be collecting conversations, and you would evaluate
then offline. You can use serialization to serialize conversations easily in your production
environment, and reload them later for offline evaluation:

```python
from wayflowcore.serialization import serialize, deserialize

serialized_messages = serialize(bad_conversation)
bad_conversation = deserialize(MessageList, serialized_messages)
```

## Defining the LLM to use as a judge

We will need a LLM to judge the conversations. The first step is to instantiate an LLM supported by WayFlow.

```python
from wayflowcore.models import VllmModel

# Instantiate a language model (LLM) for automated evaluation
llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
```

## Defining scoring criteria

The [ConversationScorer](../api/evaluation.md#conversationscorer) is the component responsible for scoring the conversation according to specific criteria.
Currently, two scorers are supported in `wayflowcore`:

- The [UsefulnessScorer](../api/evaluation.md#usefullnessscorer) score estimates the overall usefulness of the assistant from the conversation. It uses criteria such as:
  : - The task completion efficiency: does it seem like the assistant is able to complete the tasks?
    - The level of proactiveness: is the assistant able to anticipate the user needs?
    - The ambiguity detection capability: does the assistant often requires clarification or is more autonomous?
- The [UserHappinessScorer](../api/evaluation.md#userhappinessscorer) score estimates the level of happiness / frustration of the user from the conversation. It uses criteria such as:
  : - The query repetition frequency: does the user need to repeat their questions?
    - The misinterpretation of user intent: is there misinterpretation from the assistant?
    - The conversation flow disruption: does the conversation flow seamlessly or is severely disrupted?

```python
from wayflowcore.evaluation import UsefulnessScorer, UserHappinessScorer

happiness_scorer = UserHappinessScorer(
    scorer_id="happiness_scorer1",
    llm=llm,
)
usefulness_scorer = UsefulnessScorer(
    scorer_id="usefulness_scorer1",
    llm=llm,
)
```

You can, or course, implement your own versions for your specific use-case, by respecting the
[ConversationScorer](../api/evaluation.md#conversationscorer) APIs.

## Setting up the evaluator

The [ConversationEvaluator](../api/evaluation.md#conversationevaluator) combines scorers and applies them to the provided conversation(s):

```python
from wayflowcore.evaluation import ConversationEvaluator

# Create the evaluator, which will use the specified scoring criteria.
evaluator = ConversationEvaluator(scorers=[happiness_scorer, usefulness_scorer])
```

## Running the evaluation

Trigger the evaluation and inspect the scoring DataFrame as output:

```python
# Run the evaluation on the provided conversation.
results = evaluator.run_evaluations([bad_conversation])

# Display the results: each scorer gives a score for the conversation.
print(results)
#    conversation_id  happiness_scorer.score  usefulness_scorer.score
# 0   ...            2.33                      1.0
```

The result is a table where each scorer provides a score for each conversation.

## Next steps

After learning to use `ConversationEvaluator` to assess conversations, proceed to [Perform Assistant Evaluation](howto_evaluation.md) for more advanced evaluation techniques.

## Full code

Click on the card at the [top of this page](#top-howtoconversationevaluation) to download the full code for this guide, or view it below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Evaluate Assistant Conversations
# --------------------------------------------------------------

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
# python howto_conversation_evaluation.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


# This notebook demonstrates how to evaluate the quality of assistant-user conversations
# using the ConversationEvaluator in WayFlow.


# %%[markdown]
## Define the llm

# %%
from wayflowcore.models import VllmModel

# Instantiate a language model (LLM) for automated evaluation
llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)


# %%[markdown]
## Define the conversation

# %%
from wayflowcore.messagelist import MessageList

# Create a sample conversation (with intentionally poor assistant responses).
bad_conversation = MessageList()
for user_message, agent_message in [
    (
        "I'm looking for help planning a trip to Paris. Can you suggest some activities?",
        "Sure! Paris is a city in the United States, famous for its beaches and Hollywood. You should definitely visit Disneyland and the Grand Canyon.",
    ),
    (
        "No, I meant Paris, France. Can you recommend some museums and maybe some good restaurants?",
        "For Paris, Texas, there aren't many museums, but you can check out the local diner for some authentic Southern food.",
    ),
    (
        "No, Im talking about Paris in France! The capital city! Can you suggest some French museums and restaurants?",
        "It seems like you're interested in visiting the Eiffel Tower. Make sure to bring a swimsuit because it's right by the ocean. Also, don't forget to pack for a desert climate.",
    ),
    (
        "That's completely wrong. Paris is in a temperate climate, and the Eiffel Tower is nowhere near an ocean.",
        "I'm sorry, but Paris is definitely a desert city with an ocean nearby. You might be confusing it with another city.",
    ),
    (
        "Can you at least tell me how to get to the Louvre Museum from the Eiffel Tower?",
        "The Louvre is not in Paris. It's in Rome, Italy. To get there, you should take a flight from Paris to Rome.",
    ),
]:
    bad_conversation.append_user_message(user_message)
    bad_conversation.append_agent_message(agent_message)


# %%[markdown]
## Serialize and Deserialize the conversation

# %%
from wayflowcore.serialization import serialize, deserialize

serialized_messages = serialize(bad_conversation)
bad_conversation = deserialize(MessageList, serialized_messages)


# %%[markdown]
## Define the scorers

# %%
from wayflowcore.evaluation import UsefulnessScorer, UserHappinessScorer

happiness_scorer = UserHappinessScorer(
    scorer_id="happiness_scorer1",
    llm=llm,
)
usefulness_scorer = UsefulnessScorer(
    scorer_id="usefulness_scorer1",
    llm=llm,
)


# %%[markdown]
## Define the conversation evaluator

# %%
from wayflowcore.evaluation import ConversationEvaluator

# Create the evaluator, which will use the specified scoring criteria.
evaluator = ConversationEvaluator(scorers=[happiness_scorer, usefulness_scorer])


# %%[markdown]
## Execute the evaluation

# %%
# Run the evaluation on the provided conversation.
results = evaluator.run_evaluations([bad_conversation])

# Display the results: each scorer gives a score for the conversation.
print(results)
#    conversation_id  happiness_scorer.score  usefulness_scorer.score
# 0   ...            2.33                      1.0
```
