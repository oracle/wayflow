<a id="evaluation"></a>

# Evaluation APIs

## Assistant Evaluation

<a id="evaluationtask"></a>

### *class* wayflowcore.evaluation.assistantevaluator.EvaluationTask(task_id, description, scorers, task_kwargs=<factory>, scoring_kwargs=<factory>)

Class representing a Task for the LLM assistant to solve.

* **Parameters:**
  * **task_id** (`str`) – name of the task
  * **description** (`str`) – description of the task, to be provided to the LLM
  * **scorers** (`List`[[`TaskScorer`](#wayflowcore.evaluation.taskscorer.TaskScorer)]) – list of scorers to compute metrics after execution of the LLM conversation.
    Note that each scorer can compute several metrics, but these metrics
    must be unique across scorers across all tasks, otherwise an exception is raised during the evaluation.
  * **task_kwargs** (`Dict`[`str`, `Any`]) – arbitrary dict containing any additional task information for the assistant to solve
  * **scoring_kwargs** (`Dict`[`str`, `Any`]) – arbitrary dict containing any additional task information for the scoring (e.g, ground-truth answers, expected results)

#### description *: `str`*

#### score(environment, assistant, assistant_conversation)

* **Return type:**
  `Dict`[`str`, `float`]
* **Parameters:**
  * **environment** ([*EvaluationEnvironment*](#wayflowcore.evaluation.assistantevaluator.EvaluationEnvironment))
  * **assistant** ([*ConversationalComponent*](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent))
  * **assistant_conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation))

#### score_exceptional_case(environment, exception, assistant, assistant_conversation)

* **Return type:**
  `Dict`[`str`, `float`]
* **Parameters:**
  * **environment** ([*EvaluationEnvironment*](#wayflowcore.evaluation.assistantevaluator.EvaluationEnvironment))
  * **exception** (*Exception*)
  * **assistant** ([*ConversationalComponent*](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent))
  * **assistant_conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation))

#### scorers *: `List`[[`TaskScorer`](#wayflowcore.evaluation.taskscorer.TaskScorer)]*

#### scoring_kwargs *: `Dict`[`str`, `Any`]*

#### task_id *: `str`*

#### task_kwargs *: `Dict`[`str`, `Any`]*

<a id="evaluationenvironment"></a>

### *class* wayflowcore.evaluation.assistantevaluator.EvaluationEnvironment(env_id)

EvaluationEnvironment is the abstract class to provide the entry points
needed for the AssistantEvaluator. It is responsible for setting up
assistants for a given task, as well as properly setting the environment
before and after evaluating the assistant on a task.

* **Parameters:**
  **env_id** (*str*)

#### *abstract* get_assistant(task)

Creates the assistant for the task (or re-use a specific one already created by the environment)

* **Return type:**
  [`ConversationalComponent`](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent)
* **Parameters:**
  **task** ([*EvaluationTask*](#wayflowcore.evaluation.assistantevaluator.EvaluationTask))

#### *abstract* get_human_proxy(task)

Creates the human proxy for the task (or re-use a specific one already created by the environment)

* **Return type:**
  `Optional`[[`HumanProxyAssistant`](#wayflowcore.evaluation.assistantevaluator.HumanProxyAssistant)]
* **Parameters:**
  **task** ([*EvaluationTask*](#wayflowcore.evaluation.assistantevaluator.EvaluationTask))

#### *abstract* init_env(task)

Method called before the run of every task to set/reset the environment

* **Return type:**
  `None`
* **Parameters:**
  **task** ([*EvaluationTask*](#wayflowcore.evaluation.assistantevaluator.EvaluationTask))

#### *abstract* reset_env(task)

Method called after the run of every task to set/reset the environment

* **Return type:**
  `None`
* **Parameters:**
  **task** ([*EvaluationTask*](#wayflowcore.evaluation.assistantevaluator.EvaluationTask))

#### termination_check(human_conversation)

Method called within the assistant-human proxy conversation loop to determine
when the conversation should terminate, basically checking for, e.g., trigger words, in the
human_conversation (the same as the assistant conversation but switched roles, see AssistantTester).
If not overridden, the default is to check if the human proxy utters ‘<ENDED>’ or ‘<FAILED>’.

* **Return type:**
  `bool`
* **Parameters:**
  **human_conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation))

<a id="assistantevaluator"></a>

### *class* wayflowcore.evaluation.assistantevaluator.AssistantEvaluator(environment, metrics=None, max_conversation_rounds=10)

Class used to run the task evaluations

* **Parameters:**
  * **environment** (`Union`[[`EvaluationEnvironment`](#wayflowcore.evaluation.assistantevaluator.EvaluationEnvironment), `Callable`[[], [`EvaluationEnvironment`](#wayflowcore.evaluation.assistantevaluator.EvaluationEnvironment)]]) – The environment for this evaluation, or a lambda (no args) that returns a new environment instance.
    If you want to run multiple conversations in parallel, you must provide a lambda here.
  * **metrics** (`Optional`[`List`[`str`]]) – The name of the metrics that need to be provided by the scorers.
    If not provided, by default will use all metrics from all the scorers passed to the EvaluationTasks
  * **max_conversation_rounds** (`int`) – The maximum number of conversation rounds per task.

#### TASK_ATTEMPT_NO_COLUMN_NAME *= 'task_attempt_number'*

#### TASK_ID_COLUMN_NAME *= 'task_id'*

#### run_benchmark(tasks, N, raise_exceptions=False, \_max_concurrency=1)

Runs all the tasks N times, returning a dataframe with the resulting
scores for each task round. NaNs values indicate task failures.

* **Parameters:**
  * **tasks** (`List`[[`EvaluationTask`](#wayflowcore.evaluation.assistantevaluator.EvaluationTask)]) – List of tasks to run the benchmark on.
  * **N** (`int`) – Number of times to run each task
  * **raise_exceptions** (`bool`) – Whether to raise exceptions (for testing) or just mark them as errors (benchmarking)
  * **\_max_concurrency** (*int*)
* **Return type:**
  `DataFrame`

<a id="taskscorer"></a>

### *class* wayflowcore.evaluation.taskscorer.TaskScorer(scorer_id=None)

TaskScorer is an API to implement different scores and metrics to evaluate LLMs.
It needs to implement a score method to give a metric for a successful conversation
and a score_exceptional_case method to give a metric for a conversation that threw an error

* **Parameters:**
  **scorer_id** (`Optional`[`str`]) – Name of the scorer, to avoid conflicts if several scorers are named the same

#### DEFAULT_SCORER_ID *: `str`*

#### OUTPUT_METRICS *: `List`[`str`]*

#### *abstract* score(environment, task, assistant, assistant_conversation)

Retrieves relevant information from the assistants, conversations and task
to score a specific task

* **Return type:**
  `Dict`[`str`, `float`]
* **Parameters:**
  * **environment** ([*EvaluationEnvironment*](#wayflowcore.evaluation.assistantevaluator.EvaluationEnvironment))
  * **task** ([*EvaluationTask*](#wayflowcore.evaluation.assistantevaluator.EvaluationTask))
  * **assistant** ([*ConversationalComponent*](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent))
  * **assistant_conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation))

#### *abstract* score_exceptional_case(environment, exception, task, assistant, assistant_conversation)

scores a specific task that failed with an exception

* **Return type:**
  `Dict`[`str`, `float`]
* **Parameters:**
  * **environment** ([*EvaluationEnvironment*](#wayflowcore.evaluation.assistantevaluator.EvaluationEnvironment))
  * **exception** (*Exception*)
  * **task** ([*EvaluationTask*](#wayflowcore.evaluation.assistantevaluator.EvaluationTask))
  * **assistant** ([*ConversationalComponent*](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent))
  * **assistant_conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation))

<a id="runproxyconversation"></a>

### *class* wayflowcore.evaluation.assistantevaluator.run_proxy_agent_conversation(\*, assistant, max_conversation_rounds, only_agent_msg_type=True, raise_exceptions=False, assistant_conversation=None, human_conversation=None, human_proxy=None, init_human_messages=None, final_check_function=None, termination_check_function=None)

Runs a conversation once. In this implementation, the human_proxy begins the conversation first,
then the assistant, then the human_proxy, etc.

* **Parameters:**
  * **assistant** ([`ConversationalComponent`](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent)) – component on which to run the conversation
  * **max_conversation_rounds** (`int`) – max number of rounds of conversations
  * **only_agent_msg_type** (`bool`) – messages of the agent to show to the proxy
  * **raise_exceptions** (`bool`) – whether to raise exceptions or just record them
  * **assistant_conversation** (`Optional`[[`Conversation`](conversation.md#wayflowcore.conversation.Conversation)]) – potential conversation to continue for the component
  * **human_conversation** (`Optional`[[`Conversation`](conversation.md#wayflowcore.conversation.Conversation)]) – potential conversation of the proxy to continue
  * **human_proxy** (`Optional`[[`ConversationalComponent`](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent)]) – proxy to use for the conversation
  * **init_human_messages** (`Optional`[`List`[`str`]]) – scripted initial interactions for the proxy
  * **final_check_function** (`Optional`[`Callable`[[`bool`], `bool`]]) – callable to return True or False depending on if the conversation was a success or not
  * **termination_check_function** (`Optional`[`Callable`[[[`Conversation`](conversation.md#wayflowcore.conversation.Conversation)], `bool`]]) – callable to find out if the conversation should be stopped or not
* **Return type:**
  `List`[`Dict`[`str`, `Any`]]

<a id="assistantevaluationresult"></a>

### *class* wayflowcore.evaluation.assistantevaluator.AssistantEvaluationResult(task_id, task_attempt_number, messages, metrics_dict)

* **Parameters:**
  * **task_id** (*str*)
  * **task_attempt_number** (*int*)
  * **messages** (*List* *[*[*Message*](conversation.md#wayflowcore.messagelist.Message) *]*  *|* *None*)
  * **metrics_dict** (*Dict* *[**str* *,* *float* *]*)

#### messages *: `Optional`[`List`[[`Message`](conversation.md#wayflowcore.messagelist.Message)]]*

#### metrics_dict *: `Dict`[`str`, `float`]*

#### task_attempt_number *: `int`*

#### task_id *: `str`*

<a id="humanproxyassistant"></a>

### *class* wayflowcore.evaluation.assistantevaluator.HumanProxyAssistant(\*, llm, system_prompt=None, full_task_description='', short_task_description='', assistant_role='', user_role='', extra_instructions='')

HumanProxyAssistant is a WayFlow Assistant LLM for interacting with other assistants in place of a human developer.

Build a new HumanProxyAssistant.

* **Parameters:**
  * **llm** ([`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)) – model config for the LLM
  * **system_prompt** (`Optional`[`str`]) – The system prompt to control the behavior of the Human Proxy. It should at least provide the context of the task of the
    other assistant the proxy is interacting with. It should also instruct the proxy to generate <ENDED> if the task is completed.
    If the system prompt is not provided, the other arguments below need to be provided to render a pre-defined system prompt template.
  * **full_task_description** (`str`) – the detailed description of the task of the assistant (e.g. help the human build an app for the plumbing store)
  * **short_task_description** (`str`) – the brief description of the task (e.g. build an app)
  * **assistant_role** (`str`) – the persona of the assistant (e.g. a software engineer)
  * **user_role** (`str`) – the persona of the human user, of which the LLM is a proxy (e.g. a busy manager of a plumbing store)
  * **extra_instructions** (`str`) – extra instructions to the LLM, usually to tell it to only respond in certain ways like only yes/no
    will be inserted to the system prompt at the end

### Example

```pycon
>>> from wayflowcore.evaluation import HumanProxyAssistant
>>> human_proxy = HumanProxyAssistant(
...     llm=llm,
...     full_task_description="to provide you with the current general weather (breezy, warm, snowy, etc.) in the largest city of Switzerland (don't tell me which one).",
...     short_task_description="get the weather in the largest city of Switzerland",
...     assistant_role="a weather reporter",
...     user_role="a news viewer"
... )
```

## Conversation Evaluation

<a id="conversationevaluator"></a>

### *class* wayflowcore.evaluation.conversationevaluator.ConversationEvaluator(scorers)

Class used to run the conversation evaluation given a list of conversation scorers.

* **Parameters:**
  **scorers** (`Union`[[`ConversationScorer`](#wayflowcore.evaluation.conversationscorer.ConversationScorer), `List`[[`ConversationScorer`](#wayflowcore.evaluation.conversationscorer.ConversationScorer)]]) – Scorers to be used to evaluate the conversation.

### Examples

```pycon
>>> from wayflowcore.messagelist import MessageList
>>> from wayflowcore.evaluation import ConversationEvaluator, UsefulnessScorer
>>>
>>> conversation = MessageList()
>>> conversation.append_user_message("What is the capital of France")
>>> conversation.append_agent_message("The capital of France is Paris")
>>> usefulness_scorer = UsefulnessScorer("usefulness_scorer1", llm=llm)
>>>
>>> evaluator = ConversationEvaluator(scorers=[usefulness_scorer])
>>> evaluation_results = evaluator.run_evaluations([conversation])
```

#### run_evaluations(conversations, output_raw_evaluation=False)

Evaluates the conversations using the list of scorers.

* **Parameters:**
  * **conversations** (`List`[[`MessageList`](conversation.md#wayflowcore.messagelist.MessageList)]) – The list of conversations to evaluate
  * **output_raw_evaluation** (`bool`) – Whether to output the raw evaluation results
* **Returns:**
  A DataFrame with the conversation id [int] and the different scores [float] (columns)
  for each conversation (rows)
* **Return type:**
  pandas.DataFrame

#### *async* run_evaluations_async(conversations, output_raw_evaluation=False)

Evaluates the conversations using the list of scorers.

* **Parameters:**
  * **conversations** (`List`[[`MessageList`](conversation.md#wayflowcore.messagelist.MessageList)]) – The list of conversations to evaluate
  * **output_raw_evaluation** (`bool`) – Whether to output the raw evaluation results
* **Returns:**
  A DataFrame with the conversation id [int] and the different scores [float] (columns)
  for each conversation (rows)
* **Return type:**
  pandas.DataFrame

<a id="conversationscorer"></a>

### *class* wayflowcore.evaluation.conversationscorer.ConversationScorer(scorer_id, llm)

Base Scorer class to evaluate a conversation trace.

* **Parameters:**
  * **scorer_id** (`str`) – The scorer identifier. Is used in the column name for the output evaluation DataFrame
  * **llm** ([`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)) – The model to use to evaluate the conversation

#### *abstract* score(conversation_messages, output_raw_evaluation=False)

* **Return type:**
  `Dict`[`str`, `float`]
* **Parameters:**
  * **conversation_messages** ([*MessageList*](conversation.md#wayflowcore.messagelist.MessageList))
  * **output_raw_evaluation** (*bool*)

#### *async* score_async(conversation_messages, output_raw_evaluation=False)

* **Return type:**
  `Dict`[`str`, `float`]
* **Parameters:**
  * **conversation_messages** ([*MessageList*](conversation.md#wayflowcore.messagelist.MessageList))
  * **output_raw_evaluation** (*bool*)

<a id="usefullnessscorer"></a>

### *class* wayflowcore.evaluation.usefulnessscorer.UsefulnessScorer(scorer_id, llm, scorer_theme=None, criteria_names=None, criteria_descriptions=None, llm_score_to_final_score_map=None, score_aggregation='mean')

Scorer to evaluate the conversation trace given a set of criteria. The default score map
is: [DEFAULT_SCORE_MAP](#defaultscoremap)

* **Parameters:**
  * **scorer_id** (`str`) – The scorer identifier. Is used in the column name for the output evaluation DataFrame
  * **llm** ([`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)) – The model to use to evaluate the conversation
  * **scorer_theme** (`Optional`[`str`]) – The score theme for the scorer (e.g. user frustration, assistant helpfulness, …)
    Is used in the evaluation prompt.
  * **criteria_names** (`Optional`[`List`[`str`]]) – The list of criteria names. Is used in the output parsing.
  * **criteria_descriptions** (`Optional`[`List`[`str`]]) – The list of criteria descriptions. Is used in the evaluation prompt.
  * **llm_score_to_final_score_map** (`Optional`[`Dict`[`str`, `Optional`[`float`]]]) – Optional, the mapping from the evaluations to numbers (e.g. {‘bad’: 0, ‘good’: 1})
  * **score_aggregation** (`Optional`[`Literal`[`'mean'`, `'min'`, `'max'`]]) – Optional, must be used with llm_score_to_final_score_map to produce an aggregated
    score output. Defaults to None (no aggregation).

#### CRITERIA_DESCRIPTIONS *: List[str]* *= ['\\n- Task Completion Efficiency\\nExplanation: [Technical explanation here]\\nScore: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]\\n\\nStrongly Disagree: The AI consistently fails to complete tasks or requires an excessive number of turns, severely impacting efficiency.\\nDisagree: The AI often struggles to complete tasks, requiring more turns than expected and showing limited efficiency.\\nNeither Agree nor Disagree: The AI completes tasks with average efficiency, neither excelling nor failing noticeably.\\nAgree: The AI generally completes tasks efficiently, often requiring fewer turns than expected.\\nStrongly Agree: The AI consistently completes tasks with exceptional efficiency, minimizing the number of turns and maximizing productivity.\\n', '\\n- Proactive Assistance\\nExplanation: [Technical explanation here]\\nScore: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]\\n\\nStrongly Disagree: The AI never anticipates user needs or offers additional relevant information beyond direct responses.\\nDisagree: The AI rarely provides proactive assistance, mostly responding reactively to user queries.\\nNeither Agree nor Disagree: The AI occasionally offers proactive assistance but is primarily reactive in its approach.\\nAgree: The AI frequently anticipates user needs and provides relevant information or suggestions unprompted.\\nStrongly Agree: The AI consistently demonstrates high-level proactive assistance, anticipating complex user needs and offering valuable insights.\\n', '\\n-. Clarification and Elaboration\\nExplanation: [Technical explanation here]\\nScore: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]\\n\\nStrongly Disagree: The AI consistently seeks clarification when appropriate and provides comprehensive, insightful elaboration on all responses.\\nDisagree: The AI frequently asks for clarification when needed and often provides detailed elaboration on its responses.\\nNeither Agree nor Disagree: The AI sometimes seeks clarification and provides basic elaboration when necessary.\\nAgree: The AI rarely asks for clarification or elaborates on its responses, often leading to misunderstandings.\\nStrongly Agree: The AI never seeks clarification when needed and provides minimal or no elaboration on its responses.\\n']*

#### CRITERIA_NAMES *: List[str]* *= ['Task Completion Efficiency', 'Proactive Assistance', 'Clarification and Elaboration']*

#### SCORER_THEME *: str* *= 'User Helpfulness'*

<a id="userhappinessscorer"></a>

### *class* wayflowcore.evaluation.userhappinessscorer.UserHappinessScorer(scorer_id, llm, scorer_theme=None, criteria_names=None, criteria_descriptions=None, llm_score_to_final_score_map=None, score_aggregation='mean')

Scorer to evaluate the conversation trace given a set of criteria. The default score map
is: [DEFAULT_SCORE_MAP](#defaultscoremap)

* **Parameters:**
  * **scorer_id** (`str`) – The scorer identifier. Is used in the column name for the output evaluation DataFrame
  * **llm** ([`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)) – The model to use to evaluate the conversation
  * **scorer_theme** (`Optional`[`str`]) – The score theme for the scorer (e.g. user frustration, assistant helpfulness, …)
    Is used in the evaluation prompt.
  * **criteria_names** (`Optional`[`List`[`str`]]) – The list of criteria names. Is used in the output parsing.
  * **criteria_descriptions** (`Optional`[`List`[`str`]]) – The list of criteria descriptions. Is used in the evaluation prompt.
  * **llm_score_to_final_score_map** (`Optional`[`Dict`[`str`, `Optional`[`float`]]]) – Optional, the mapping from the evaluations to numbers (e.g. {‘bad’: 0, ‘good’: 1})
  * **score_aggregation** (`Optional`[`Literal`[`'mean'`, `'min'`, `'max'`]]) – Optional, must be used with llm_score_to_final_score_map to produce an aggregated
    score output. Defaults to None (no aggregation).

#### CRITERIA_DESCRIPTIONS *: List[str]* *= ["\\n- Query Repetition Frequency\\nExplanation: [Technical explanation here]\\nScore: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]\\n\\nStrongly Disagree: The user consistently needs to repeat queries multiple times, indicating severe communication issues with the AI.\\nDisagree: The user frequently needs to repeat queries due to the AI's misunderstanding or inadequate responses.\\nNeither Agree nor Disagree: The user occasionally needs to repeat queries, but it doesn't significantly impact the conversation flow.\\nAgree: The user rarely needs to repeat queries; the AI generally understands and addresses requests effectively.\\nStrongly Agree: The user never needs to repeat queries; the AI understands and addresses all requests on the first attempt.\\n", "\\n- Misinterpretation of User Intent\\nExplanation: [Technical explanation here]\\nScore: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]\\n\\nStrongly Disagree: The AI consistently misinterprets user intent, repeatedly failing to understand or address the user's true goals.\\nDisagree: The AI frequently misinterprets user intent, often providing responses that don't align with the user's actual needs.\\nNeither Agree nor Disagree: The AI occasionally misinterprets user intent, but usually corrects itself or seeks clarification.\\nAgree: The AI rarely misinterprets user intent, generally providing responses aligned with the user's goals.\\nStrongly Agree: The AI never misinterprets user intent, consistently understanding and addressing the user's actual needs.\\n", '\\n- Conversation Flow Disruption\\nExplanation: [Technical explanation here]\\nScore: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]\\n\\nStrongly Disagree: The conversation is severely disrupted throughout; the AI consistently loses context, introduces irrelevant information, or abruptly changes topics.\\nDisagree: The conversation is frequently disrupted; the AI often loses context or introduces irrelevant information.\\nNeither Agree nor Disagree: The conversation has occasional disruptions, but the AI usually recovers and maintains adequate flow.\\nAgree: The conversation generally flows well with minimal disruptions; the AI maintains good continuity and context.\\nStrongly Agree: The conversation flows seamlessly with no disruptions; the AI maintains perfect continuity and context.\\n']*

#### CRITERIA_NAMES *: List[str]* *= ['Query Repetition Frequency', 'Misinterpretation of User Intent', 'Conversation Flow Disruption']*

#### SCORER_THEME *: str* *= 'User Frustration / Happiness'*

<a id="criteriascorer"></a>

### *class* wayflowcore.evaluation.criteriascorer.CriteriaScorer(scorer_id, llm, scorer_theme=None, criteria_names=None, criteria_descriptions=None, llm_score_to_final_score_map=None, score_aggregation='mean')

Scorer to evaluate the conversation trace given a set of criteria. The default score map
is: [DEFAULT_SCORE_MAP](#defaultscoremap)

* **Parameters:**
  * **scorer_id** (`str`) – The scorer identifier. Is used in the column name for the output evaluation DataFrame
  * **llm** ([`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)) – The model to use to evaluate the conversation
  * **scorer_theme** (`Optional`[`str`]) – The score theme for the scorer (e.g. user frustration, assistant helpfulness, …)
    Is used in the evaluation prompt.
  * **criteria_names** (`Optional`[`List`[`str`]]) – The list of criteria names. Is used in the output parsing.
  * **criteria_descriptions** (`Optional`[`List`[`str`]]) – The list of criteria descriptions. Is used in the evaluation prompt.
  * **llm_score_to_final_score_map** (`Optional`[`Dict`[`str`, `Optional`[`float`]]]) – Optional, the mapping from the evaluations to numbers (e.g. {‘bad’: 0, ‘good’: 1})
  * **score_aggregation** (`Optional`[`Literal`[`'mean'`, `'min'`, `'max'`]]) – Optional, must be used with llm_score_to_final_score_map to produce an aggregated
    score output. Defaults to None (no aggregation).

#### CRITERIA_DESCRIPTIONS *: `List`[`str`]*

#### CRITERIA_NAMES *: `List`[`str`]*

#### SCORER_THEME *: `str`*

#### score(conversation_messages, output_raw_evaluation=False)

Scores the conversation, focusing on the criteria described in the criteria descriptions

* **Parameters:**
  * **conversation_messages** ([`MessageList`](conversation.md#wayflowcore.messagelist.MessageList)) – Messages to score
  * **output_raw_evaluation** (`bool`) – Whether to output the raw evaluation results or not
* **Return type:**
  `Dict`[`str`, `float`]

#### *async* score_async(conversation_messages, output_raw_evaluation=False)

Scores the conversation, focusing on the criteria described in the criteria descriptions

* **Parameters:**
  * **conversation_messages** ([`MessageList`](conversation.md#wayflowcore.messagelist.MessageList)) – Messages to score
  * **output_raw_evaluation** (`bool`) – Whether to output the raw evaluation results or not
* **Return type:**
  `Dict`[`str`, `float`]

<a id="defaultscoremap"></a>

### wayflowcore.evaluation.criteriascorer.DEFAULT_SCORE_MAP

alias of {‘N/A’: None, ‘agree’: 3.0, ‘disagree’: 1.0, ‘neither agree nor disagree’: 2.0, ‘not applicable’: None, ‘strongly agree’: 4.0, ‘strongly disagree’: 0.0}

## Evaluation Metrics

<a id="calculate-set-metrics"></a>

### wayflowcore.evaluation.evaluation_metrics.calculate_set_metrics(ground_truth, predicted)

Calculate precision, recall, and F1 for set-based comparisons (where order doesn’t matter)

This function implements the following rules and behaviors:

**Input Handling:**
- Accepts pandas Series containing sets, JSON strings of lists, or single values
- JSON string representations of lists are parsed and converted to sets
- Invalid JSON strings fall back to single-element sets containing the original value
- Non-iterable values (strings, numbers) are wrapped in single-element sets
- NaN/None values are treated as empty sets
- Both series must have the same length (raises ValueError otherwise)

**Metric Calculations:**
- Precision = intersection_size / predicted_set_size (0.0 if predicted set is empty)
- Recall = intersection_size / ground_truth_set_size (0.0 if ground truth set is empty)
- F1 = 2 \* (precision \* recall) / (precision + recall) (0.0 if both precision and recall are 0)
- Final metrics are averages across all items in the series

**Type Conversions:**
- Sets remain as sets
- JSON strings like ‘[“a”, “b”]’ are parsed to sets
- Single values like “apple” become {“apple”}
- Invalid JSON becomes single-element sets
- NaN/None becomes empty set

* **Parameters:**
  * **ground_truth** (`Series`) – Series containing ground truth values (can be JSON strings of lists)
  * **predicted** (`Series`) – Series containing predicted values (can be JSON strings of lists)
* **Return type:**
  `Dict`[`str`, `float`]
* **Returns:**
  Dictionary with precision, recall, and f1 scores (all float values between 0.0 and 1.0)
* **Raises:**
  **ValueError** – If the series have different lengths

### Examples

```pycon
>>> import pandas as pd
>>> from wayflowcore.evaluation.evaluation_metrics import calculate_set_metrics
>>> ground_truth_series = pd.Series([{"a","b","c"}, set(), {"a", "b"}])
>>> predicted_series = pd.Series([{"a"}, {"a"}, {"a", "b"}])
>>> metrics = calculate_set_metrics(ground_truth_series, predicted_series)
>>> # metrics should be {"precision": 0.6667, "recall": 0.4444, "f1": 0.5333}
```

<a id="calculate-accuracy"></a>

### wayflowcore.evaluation.evaluation_metrics.calculate_accuracy(ground_truth, predicted)

Calculate accuracy for exact matches (where order matters)

This function implements the following rules and behaviors:

**Preprocessing Rules:**
- All values are converted to strings using astype(str)
- All strings are converted to lowercase using str.lower() (case-insensitive matching)
- Leading and trailing whitespace is stripped using str.strip()
- NaN/None values are replaced with empty strings using fillna(“”)

**Type Conversions:**
- Numbers: 42 → “42”, 3.14 → “3.14”
- Booleans: True → “true”, False → “false” (after lowercase conversion)
- Strings: “APPLE” → “apple”, “ Hello “ → “hello”
- NaN/None: → “” (empty string)

**Matching Rules:**
- Performs exact string matching after all preprocessing
- Case-insensitive: “APPLE” matches “apple”
- Whitespace-insensitive: “ hello “ matches “hello”
- Type-flexible: 42 matches “42”, True matches “true”

**Calculation:**
- Accuracy = (number of exact matches) / (total number of items)
- Returns value between 0.0 (no matches) and 1.0 (all matches)
- Empty series returns 0.0

* **Parameters:**
  * **ground_truth** (`Series`) – Series containing ground truth values
  * **predicted** (`Series`) – Series containing predicted values
* **Return type:**
  `Dict`[`str`, `float`]
* **Returns:**
  Dictionary with accuracy score (float between 0.0 and 1.0)
* **Raises:**
  **ValueError** – If the series have different lengths

### Examples

```pycon
>>> import pandas as pd
>>> from wayflowcore.evaluation.evaluation_metrics import calculate_accuracy
>>> ground_truth_series = pd.Series(["apple", "banana", "cherry"])
>>> predicted_series = pd.Series(["apple", "banana", "orange"])
>>> metrics = calculate_accuracy(ground_truth_series, predicted_series)
>>> # metrics should be {"accuracy": 0.6667}
```
