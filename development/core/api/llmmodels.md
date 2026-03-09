# LLMs

This page presents all APIs and classes related to LLM models.

![agentspec-icon](_static/icons/agentspec-icon.svg)

Visit the Agent Spec API Documentation to learn more about LLMs Components.

[Agent Spec - LLMs API Reference](https://oracle.github.io/agent-spec/api/llmmodels.html)

#### TIP
Click the button above ↑ to visit the [Agent Spec Documentation](https://oracle.github.io/agent-spec/index.html)

## LlmModel

<a id="id1"></a>

### *class* wayflowcore.models.llmmodel.LlmModel(model_id, generation_config, chat_template=None, agent_template=None, supports_structured_generation=None, supports_tool_calling=None, \_\_metadata_info_\_=None, id=None, name=None, description=None)

Base class for LLM models.

* **Parameters:**
  * **model_id** (`str`) – ID of the model.
  * **generation_config** (`Optional`[[`LlmGenerationConfig`](#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig)]) – Parameters for LLM generation.
  * **chat_template** (`Optional`[[`PromptTemplate`](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)]) – Default template for chat completion.
  * **agent_template** (`Optional`[[`PromptTemplate`](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)]) – Default template for agents using this model.
  * **supports_structured_generation** (`Optional`[`bool`]) – Whether the model supports structured generation or not. When set to None,
    the model will be prompted with a response format and it will check it can use
    structured generation.
  * **supports_tool_calling** (`Optional`[`bool`]) – Whether the model supports tool calling or not. When set to None,
    the model will be prompted with a tool and it will check it can use
    the tool.
  * **id** (`Optional`[`str`]) – ID of the component.
  * **name** (`Optional`[`str`]) – Name of the component.
  * **description** (`Optional`[`str`]) – Description of the component.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### *abstract property* config *: Dict[str, Any]*

Get the configuration dictionary for the {VLlm/OpenAI/…} model

#### *property* default_agent_template *: [PromptTemplate](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)*

#### *property* default_chat_template *: [PromptTemplate](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)*

#### generate(prompt, \_conversation=None)

Generates a new message based on a prompt using a LLM

* **Parameters:**
  * **prompt** (`Union`[`str`, [`Prompt`](#wayflowcore.models.Prompt)]) – Prompt that contains the messages and other arguments to send to the LLM
  * **\_conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation) *|* *None*)
* **Return type:**
  [`LlmCompletion`](#wayflowcore.models.LlmCompletion)

### Examples

```pycon
>>> from wayflowcore.messagelist import Message
>>> from wayflowcore.models import Prompt
>>> prompt = Prompt(messages=[Message('What is the capital of Switzerland?')])
>>> completion = llm.generate(prompt)
>>> # LlmCompletion(message=Message(content='The capital of Switzerland is Bern'))
```

#### *async* generate_async(prompt, \_conversation=None)

* **Return type:**
  [`LlmCompletion`](#wayflowcore.models.LlmCompletion)
* **Parameters:**
  * **prompt** (*str* *|* [*Prompt*](#wayflowcore.models.Prompt))
  * **\_conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation) *|* *None*)

#### get_total_token_consumption(conversation_id)

Calculate and return the total token consumption for a given conversation.

This method computes the aggregate token usage for the specified conversation
by summing the token usages.

* **Parameters:**
  **conversation_id** (`str`) – The unique identifier for the conversation whose token consumption is to be calculated.
* **Returns:**
  A TokenUsage object that gathers all token usage information.
* **Return type:**
  [TokenUsage](#wayflowcore.tokenusage.TokenUsage)

#### stream_generate(prompt, \_conversation=None)

* **Return type:**
  `Iterable`[`Tuple`[[`StreamChunkType`](#wayflowcore.models._requesthelpers.StreamChunkType), `Optional`[[`Message`](conversation.md#wayflowcore.messagelist.Message)]]]
* **Parameters:**
  * **prompt** (*str* *|* [*Prompt*](#wayflowcore.models.Prompt))
  * **\_conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation) *|* *None*)

#### *async* stream_generate_async(prompt, \_conversation=None)

Returns an async iterator of message chunks

* **Parameters:**
  * **prompt** (`Union`[`str`, [`Prompt`](#wayflowcore.models.Prompt)]) – Prompt that contains the messages and other arguments to send to the LLM
  * **\_conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation) *|* *None*)
* **Return type:**
  `AsyncIterable`[`Tuple`[[`StreamChunkType`](#wayflowcore.models._requesthelpers.StreamChunkType), `Optional`[[`Message`](conversation.md#wayflowcore.messagelist.Message)]]]

### Examples

```pycon
>>> import asyncio
>>> from wayflowcore.messagelist import Message, MessageType
>>> from wayflowcore.models import Prompt
>>> message = Message(content="What is the capital of Switzerland?", message_type=MessageType.USER)
>>> llm_stream = llm.stream_generate(
...     prompt=Prompt(messages=[message])
... )
>>> for chunk_type, chunk in llm_stream:
...     print(chunk)   
>>> # Bern
>>> #  is the
>>> # capital
>>> #  of
>>> #  Switzerland
>>> # Message(content='Bern is the capital of Switzerland', message_type=MessageType.AGENT)
```

### *class* wayflowcore.models._requesthelpers.StreamChunkType(value)

An enumeration.

#### END_CHUNK *= 2*

#### IGNORED *= 0*

#### START_CHUNK *= 3*

#### TEXT_CHUNK *= 1*

## LlmModelFactory

<a id="id2"></a>

### *class* wayflowcore.models.llmmodelfactory.LlmModelFactory

Factory class that creates `LlmModel` instances from configuration dictionaries.

Supports vLLM, Ollama, OpenAI and OCIGenAI models.

#### *static* from_config(model_config)

* **Return type:**
  [`LlmModel`](#wayflowcore.models.llmmodel.LlmModel)
* **Parameters:**
  **model_config** (*Dict* *[**str* *,* *Any* *]*)

## LlmCompletion

<a id="llmmodelcompletion"></a>

### *class* wayflowcore.models.LlmCompletion(message, token_usage)

* **Parameters:**
  * **message** ([*Message*](conversation.md#wayflowcore.messagelist.Message))
  * **token_usage** ([*TokenUsage*](#wayflowcore.tokenusage.TokenUsage) *|* *None*)

#### message *: Message*

Message generated by the LLM

#### token_usage *: `Optional`[[`TokenUsage`](#wayflowcore.tokenusage.TokenUsage)]*

Token usage for this completion

## Prompt

<a id="id3"></a>

### *class* wayflowcore.models.Prompt(messages, tools=None, response_format=None, output_parser=None, generation_config=None)

Dataclass containing all information needed for LLM completion + potential post-processing

* **Parameters:**
  * **messages** (*List* *[*[*Message*](conversation.md#wayflowcore.messagelist.Message) *]*)
  * **tools** (*List* *[*[*Tool*](tools.md#wayflowcore.tools.tools.Tool) *]*  *|* *None*)
  * **response_format** ([*Property*](flows.md#wayflowcore.property.Property) *|* *None*)
  * **output_parser** ([*OutputParser*](prompttemplate.md#wayflowcore.outputparser.OutputParser) *|* *List* *[*[*OutputParser*](prompttemplate.md#wayflowcore.outputparser.OutputParser) *]*  *|* *None*)
  * **generation_config** ([*LlmGenerationConfig*](#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig) *|* *None*)

#### copy(\*\*kwargs)

Makes a copy of the prompt and changes some given attributes.

* **Return type:**
  [`Prompt`](#wayflowcore.models.Prompt)
* **Parameters:**
  **kwargs** (*Any*)

#### generation_config *: `Optional`[[`LlmGenerationConfig`](#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig)]* *= None*

Optional parameters for the llm generation.

#### messages *: `List`[Message]*

List of messages to use for chat generation.

#### output_parser *: `Union`[OutputParser, `List`[OutputParser], `None`]* *= None*

Optional parser to transform the raw output of the LLM.

#### parse_output(message)

* **Return type:**
  [`Message`](conversation.md#wayflowcore.messagelist.Message)
* **Parameters:**
  **message** ([*Message*](conversation.md#wayflowcore.messagelist.Message))

#### response_format *: `Optional`[[`Property`](flows.md#wayflowcore.property.Property)]* *= None*

Optional response format to use for structured generation.

#### tools *: `Optional`[`List`[Tool]]* *= None*

Optional tools to use for native tool calling.

## Token Usage

Class that is used to gather all token usage information.

<a id="tokenusage"></a>

### *class* wayflowcore.tokenusage.TokenUsage(input_tokens=0, output_tokens=0, cached_tokens=0, reasoning_tokens=0, total_tokens=0, exact_count=False)

Gathers all token usage information.

* **Parameters:**
  * **input_tokens** (`int`) – Number of tokens used as input/context.
  * **cached_tokens** (`int`) – Number of tokens in prompt that were cached.
  * **output_tokens** (`int`) – Number of tokens generated by the model.
  * **reasoning_tokens** (`int`) – Number of reasoning tokens generated by the model
  * **exact_count** (`bool`) – Whether these numbers are exact or were estimated using the 1 token ≈ 3/4 word rule
  * **total_tokens** (*int*)

#### cached_tokens *: `int`* *= 0*

#### exact_count *: `bool`* *= False*

#### input_tokens *: `int`* *= 0*

#### output_tokens *: `int`* *= 0*

#### reasoning_tokens *: `int`* *= 0*

#### total_tokens *: `int`* *= 0*

## LLM Generation Config

Parameters for LLM generation (`max_tokens`, `temperature`, `top_p`).

<a id="llmgenerationconfig"></a>

### *class* wayflowcore.models.llmgenerationconfig.LlmGenerationConfig(max_tokens=None, temperature=None, top_p=None, stop=None, frequency_penalty=None, extra_args=<factory>, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Parameters for LLM generation

* **Parameters:**
  * **max_tokens** (`Optional`[`int`]) – Maximum number of tokens to generate as output.
  * **temperature** (`Optional`[`float`]) – What sampling temperature to use, between 0 and 2. Higher values like 0.8 will make the output more random,
    while lower values like 0.2 will make it more focused and deterministic.
    We generally recommend altering this or `top_p` but not both.
  * **top_p** (`Optional`[`float`]) – An alternative to sampling with temperature, called nucleus sampling, where the model considers the results
    of the tokens with top_p probability mass. So 0.1 means only the tokens comprising the top 10% probability
    mass are considered.
    We generally recommend altering this or temperature but not both.
  * **stop** (`Optional`[`List`[`str`]]) – List of stop words to indicate the LLM to stop generating when encountering one of these words. This helps
    reducing hallucinations, when using templates like ReAct. Some reasoning models (o3, o4-mini…) might
    not support it.
  * **frequency_penalty** (`Optional`[`float`]) – float between -2.0 and 2.0 that penalizes new tokens based on their frequency in the generated text so far.
    Values > 0 encourage the model to use new tokens, while values < 0 encourage the model to repeat tokens.
  * **extra_args** (`Dict`[`str`, `Any`]) – 

    dictionary of extra arguments that can be used by specific model providers
    > For OpenAI Responses API:

    > max_tool_calls:
    > : The maximum number of total calls to built-in tools that can be processed in a response.
    >   This maximum number applies across all built-in tool calls, not per individual tool.
    >   Any further attempts to call a tool by the model will be ignored.

    > reasoning:
    > : gpt-5 and o-series models only.
    >   

    >   If the config contains “reasoning”, adds the “reasoning.encrypted_content” key in “include” automatically to preserve reasoning traces.
    >   ([https://platform.openai.com/docs/api-reference/responses/create#responses_create-include](https://platform.openai.com/docs/api-reference/responses/create#responses_create-include))
    >   

    >   effort:
    >   : Constrains effort on reasoning for reasoning models. Currently supported values are “minimal”, “low”, “medium”, and “high”.
    >     Reducing reasoning effort can result in faster responses and fewer tokens used on reasoning in a response.
    >   

    >   summary:
    >   : A summary of the reasoning performed by the model. This can be useful for debugging and understanding the model’s reasoning process. One of “auto”, “concise”, or “detailed”.
    >     If the config contains “reasoning” and the “summary” parameter is not set, defaults to “auto”.

    The full list of parameters for Responses API can be found here:
    [https://platform.openai.com/docs/api-reference/responses/create](https://platform.openai.com/docs/api-reference/responses/create)

    #### NOTE
    The extra parameters should never include sensitive information.
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### extra_args *: `Dict`[`str`, `Any`]*

#### frequency_penalty *: `Optional`[`float`]* *= None*

#### *static* from_dict(config)

* **Return type:**
  [`LlmGenerationConfig`](#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig)
* **Parameters:**
  **config** (*Dict* *[**str* *,* *Any* *]*)

#### max_tokens *: `Optional`[`int`]* *= None*

#### merge_config(overriding_config)

* **Return type:**
  [`LlmGenerationConfig`](#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig)
* **Parameters:**
  **overriding_config** ([*LlmGenerationConfig*](#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig) *|* *None*)

#### stop *: `Optional`[`List`[`str`]]* *= None*

#### temperature *: `Optional`[`float`]* *= None*

#### to_dict()

* **Return type:**
  `Dict`[`str`, `Any`]

#### top_p *: `Optional`[`float`]* *= None*

## API Type

Class that is used to select the OpenAI API Type to use.

<a id="openaiapitype"></a>

### *class* wayflowcore.models.openaiapitype.OpenAIAPIType(value)

Enumeration of OpenAI API Types.

chat_completions: Chat Completions API
responses: Responses API

#### CHAT_COMPLETIONS *= 'chat_completions'*

#### RESPONSES *= 'responses'*

<a id="allllms"></a>

## All models

### OpenAI Compatible Models

<a id="openaicompatiblemodel"></a>

### *class* wayflowcore.models.openaicompatiblemodel.OpenAICompatibleModel(model_id, base_url, proxy=None, api_key=None, generation_config=None, supports_structured_generation=True, supports_tool_calling=True, api_type=OpenAIAPIType.CHAT_COMPLETIONS, \_\_metadata_info_\_=None, id=None, name=None, description=None)

Model to use remote LLM endpoints that use OpenAI-compatible chat APIs.

* **Parameters:**
  * **model_id** (`str`) – Name of the model to use
  * **base_url** (`str`) – Hostname and port of the vllm server where the model is hosted. If you specify a url
    ending with /completions or /responses it will be used as-is, otherwise the url path
    v1/chat/completions or v1/responses will be appended to the base url depending on the API
    type specified.
  * **proxy** (`Optional`[`str`]) – Proxy to use to connect to the remote LLM endpoint
  * **api_key** (`Optional`[`str`]) – API key to use for the request if needed. It will be formatted in the OpenAI format.
    (as “Bearer API_KEY” in the request header)
    If not provided, will attempt to read from the environment variable OPENAI_API_KEY
  * **generation_config** (`Optional`[[`LlmGenerationConfig`](#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig)]) – default parameters for text generation with this model
  * **supports_structured_generation** (`Optional`[`bool`]) – Whether the model supports structured generation or not. When set to None,
    the model will be prompted with a response format and it will check it can use
    structured generation.
  * **supports_tool_calling** (`Optional`[`bool`]) – Whether the model supports tool calling or not. When set to None,
    the model will be prompted with a tool and it will check it can use
    the tool.
  * **api_type** ([`OpenAIAPIType`](#wayflowcore.models.openaiapitype.OpenAIAPIType)) – OpenAI API type to use. Currently supports Responses and Chat Completions API.
    Uses Chat Completions API if not specified
  * **id** (`Optional`[`str`]) – ID of the component.
  * **name** (`Optional`[`str`]) – Name of the component.
  * **description** (`Optional`[`str`]) – Description of the component.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.models import OpenAICompatibleModel
>>> llm = OpenAICompatibleModel(
...     model_id="<MODEL_NAME>",
...     base_url="<ENDPOINT_URL>",
...     api_key="<API_KEY_FOR_REMOTE_ENDPOINT>",
... )
```

#### *property* config *: Dict[str, Any]*

Get the configuration dictionary for the {VLlm/OpenAI/…} model

### OpenAI Models

<a id="openaimodel"></a>

### *class* wayflowcore.models.openaimodel.OpenAIModel(model_id='gpt-4o-mini', api_key=None, generation_config=None, proxy=None, api_type=OpenAIAPIType.CHAT_COMPLETIONS, \_\_metadata_info_\_=None, id=None, name=None, description=None)

Model powered by OpenAI.

* **Parameters:**
  * **model_id** (`str`) – Name of the model to use
  * **api_key** (`Optional`[`str`]) – API key for the OpenAI endpoint. Overrides existing `OPENAI_API_KEY` environment variable.
  * **generation_config** (`Optional`[[`LlmGenerationConfig`](#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig)]) – default parameters for text generation with this model
  * **proxy** (`Optional`[`str`]) – proxy to access the remote model under VPN
  * **api_type** ([`OpenAIAPIType`](#wayflowcore.models.openaiapitype.OpenAIAPIType)) – OpenAI API type to use. Currently supports Responses and Chat Completions API.
    Uses Completions API if not specified
  * **id** (`Optional`[`str`]) – ID of the component.
  * **name** (`Optional`[`str`]) – Name of the component.
  * **description** (`Optional`[`str`]) – Description of the component.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### IMPORTANT
When running under Oracle VPN, the connection to the OCIGenAI service requires to run the model without any proxy.
Therefore, make sure not to have any of `http_proxy` or `HTTP_PROXY` environment variables setup,
or unset them with `unset http_proxy HTTP_PROXY`. Please also ensure that the `OPENAI_API_KEY` is set beforehand
to access this model. A list of available OpenAI models can be found at the following
link: [OpenAI Models](https://platform.openai.com/docs/models)

### Examples

```pycon
>>> from wayflowcore.models import LlmModelFactory
>>> OPENAI_CONFIG = {
...     "model_type": "openai",
...     "model_id": "gpt-4o-mini",
... }
>>> llm = LlmModelFactory.from_config(OPENAI_CONFIG)  
```

### Notes

When running with Oracle VPN, you need to specify a https proxy, either globally or at the model level:

```pycon
>>> OPENAI_CONFIG = {
...    "model_type": "openai",
...    "model_id": "gpt-4o-mini",
...    "proxy": "<PROXY_ADDRESS>",
... }  
```

#### *property* config *: Dict[str, Any]*

Get the configuration dictionary for the {VLlm/OpenAI/…} model

### Ollama Models

<a id="ollamamodel"></a>

### *class* wayflowcore.models.ollamamodel.OllamaModel(model_id, host_port='localhost:11434', proxy=None, generation_config=None, supports_structured_generation=True, supports_tool_calling=True, \_\_metadata_info_\_=None, id=None, name=None, description=None)

Model powered by a locally hosted Ollama server.

* **Parameters:**
  * **model_id** (`str`) – Name of the model to use. List of model names can be found here:
    [https://ollama.com/search](https://ollama.com/search)
  * **host_port** (`str`) – Hostname and port of the vllm server where the model is hosted.
    By default Ollama binds port 11434.
  * **proxy** (`Optional`[`str`]) – Proxy to use to connect to the remote LLM endpoint
  * **generation_config** (`Optional`[[`LlmGenerationConfig`](#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig)]) – default parameters for text generation with this model
  * **supports_structured_generation** (`Optional`[`bool`]) – Whether the model supports structured generation or not. When set to None,
    the model will be prompted with a response format and it will check it can use
    structured generation.
  * **supports_tool_calling** (`Optional`[`bool`]) – Whether the model supports tool calling or not. When set to None,
    the model will be prompted with a tool and it will check it can use
    the tool.
  * **id** (`Optional`[`str`]) – ID of the component.
  * **name** (`Optional`[`str`]) – Name of the component.
  * **description** (`Optional`[`str`]) – Description of the component.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.models import LlmModelFactory
>>> OLLAMA_CONFIG = {
...     "model_type": "ollama",
...     "model_id": "<MODEL_NAME>",
... }
>>> llm = LlmModelFactory.from_config(OLLAMA_CONFIG)
```

### Notes

As of November 2024, Ollama does not support tool calling with token streaming. To enable this functionality,
we prepend and append some specific REACT prompts and format tools with the REACT prompting template when:

* the model should use tools
* the list of message contains some tool_requests or tool_results

Be aware of that when you generate with tools or tool calls. To disable this behaviour, set use_tools to False
and make sure the prompt doesn’t contain tool_call and tool_result messages.
See [https://arxiv.org/abs/2210.03629](https://arxiv.org/abs/2210.03629) for learning more about the REACT prompting techniques.

#### *property* config *: Dict[str, Any]*

Get the configuration dictionary for the {VLlm/OpenAI/…} model

#### *property* default_agent_template *: [PromptTemplate](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)*

#### *property* default_chat_template *: [PromptTemplate](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)*

### VLLM Models

<a id="vllmmodel"></a>

### *class* wayflowcore.models.vllmmodel.VllmModel(model_id, host_port, proxy=None, generation_config=None, supports_structured_generation=True, supports_tool_calling=True, api_type=OpenAIAPIType.CHAT_COMPLETIONS, api_key='<[EMPTY#KEY]>', \_\_metadata_info_\_=None, id=None, name=None, description=None)

Model powered by a model hosted with VLLM server.

* **Parameters:**
  * **model_id** (`str`) – Name of the model to use
  * **host_port** (`str`) – Hostname and port of the vllm server where the model is hosted
  * **proxy** (`Optional`[`str`]) – Proxy to use to connect to the remote LLM endpoint
  * **generation_config** (`Optional`[[`LlmGenerationConfig`](#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig)]) – default parameters for text generation with this model
  * **supports_structured_generation** (`Optional`[`bool`]) – Whether the model supports structured generation or not. When set to None,
    the model will be prompted with a response format and it will check it can use
    structured generation.
  * **supports_tool_calling** (`Optional`[`bool`]) – Whether the model supports tool calling or not. When set to None,
    the model will be prompted with a tool and it will check it can use
    the tool.
  * **api_type** ([`OpenAIAPIType`](#wayflowcore.models.openaiapitype.OpenAIAPIType)) – OpenAI API type to use. Currently supports Responses and Chat Completions API.
    Uses Completions API if not specified.
    As of November 2025, Reponses support with VLLM is limited for certain models.
    Responses API has been tested on vLLM with OpenAI GPT-OSS.
  * **api_key** (`Optional`[`str`]) – API key to use for the request if needed. It will be formatted in the OpenAI format.
    (as “Bearer API_KEY” in the request header)
    If not provided, will attempt to read from the environment variable OPENAI_API_KEY
  * **id** (`Optional`[`str`]) – ID of the component.
  * **name** (`Optional`[`str`]) – Name of the component.
  * **description** (`Optional`[`str`]) – Description of the component.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.models import LlmModelFactory
>>> VLLM_CONFIG = {
...     "model_type": "vllm",
...     "host_port": "<HOSTNAME>",
...     "model_id": "<MODEL_NAME>",
... }
>>> llm = LlmModelFactory.from_config(VLLM_CONFIG)
```

### Notes

Usually, VLLM models do not support tool calling. To enable this, we prepend and append some specific REACT
prompts and format tools with the REACT prompting template when:

* the model should use tools
* the list of message contains some tool_requests or tool_results

Be aware of that when you generate with tools or tool calls. To disable this behaviour, set use_tools to False
and make sure the prompt doesn’t contain tool_call and tool_result messages.
See [https://arxiv.org/abs/2210.03629](https://arxiv.org/abs/2210.03629) for learning more about the REACT prompting techniques.

### Notes

When running under Oracle VPN, the connection to the OCIGenAI service requires to run the model without any proxy.
Therefore, make sure not to have any of http_proxy or HTTP_PROXY environment variables setup, or unset them with unset http_proxy HTTP_PROXY

#### *property* config *: Dict[str, Any]*

Get the configuration dictionary for the {VLlm/OpenAI/…} model

#### *property* default_agent_template *: [PromptTemplate](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)*

#### *property* default_chat_template *: [PromptTemplate](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)*

### OCI GenAI Models

<a id="ocigenaimodel"></a>

### *class* wayflowcore.models.ocigenaimodel.OCIGenAIModel(\*, model_id, compartment_id=None, client_config=None, serving_mode=None, provider=None, generation_config=None, id=None, name=None, description=None, \_\_metadata_info_\_=None, service_endpoint=None, auth_type=None, auth_profile='DEFAULT', api_type=OciAPIType.OCI, conversation_store_id=None)

Model powered by OCIGenAI.

* **Parameters:**
  * **model_id** (`str`) – Name of the model to use.
  * **compartment_id** (`Optional`[`str`]) – The compartment OCID. Can be also configured in the OCI_GENAI_COMPARTMENT env variable.
  * **client_config** (`Optional`[[`OCIClientConfig`](#wayflowcore.models.ociclientconfig.OCIClientConfig)]) – OCI client config to authenticate the OCI service.
  * **serving_mode** (`Optional`[[`ServingMode`](#wayflowcore.models.ocigenaimodel.ServingMode)]) – OCI serving mode for the model. Either `ServingMode.ON_DEMAND` or `ServingMode.DEDICATED`.
    When set to None, it will be auto-detected based on the `model_id`.
  * **provider** (`Optional`[[`ModelProvider`](#wayflowcore.models.ocigenaimodel.ModelProvider)]) – Name of the provider of the underlying model, to adapt the request.
    Needs to be specified in `ServingMode.DEDICATED`. Is auto-detected when in `ServingMode.ON_DEMAND`
    based on the `model_id`.
  * **api_type** ([`OciAPIType`](#wayflowcore.models.ocigenaimodel.OciAPIType)) – API type to use to call the OCI LLM provider.
  * **conversation_store_id** (`Optional`[`str`]) – Optional store ID to use to store conversations from turn to turn.
  * **generation_config** (`Optional`[[`LlmGenerationConfig`](#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig)]) – default parameters for text generation with this model
  * **id** (`Optional`[`str`]) – ID of the component.
  * **name** (`Optional`[`str`]) – Name of the component.
  * **description** (`Optional`[`str`]) – Description of the component.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **service_endpoint** (*str* *|* *None*)
  * **auth_type** (*str* *|* *None*)
  * **auth_profile** (*str* *|* *None*)

### Examples

```pycon
>>> from wayflowcore.models.ocigenaimodel import OCIGenAIModel
>>> from wayflowcore.models.ociclientconfig import (
...     OCIClientConfigWithInstancePrincipal,
...     OCIClientConfigWithApiKey,
... )
>>> ## Example 1. Instance Principal
>>> client_config = OCIClientConfigWithInstancePrincipal(
...     service_endpoint="my_service_endpoint",
... )
>>> ## Example 2. API Key from a config file (~/.oci/config)
>>> client_config = OCIClientConfigWithApiKey(
...     service_endpoint="my_service_endpoint",
...     auth_profile="DEFAULT",
...     _auth_file_location="~/.oci/config"
... )
>>> llm = OCIGenAIModel(
...     model_id="xai.grok-4",
...     client_config=client_config,
...     compartment_id="my_compartment_id",
... )  
```

### Notes

When running under Oracle VPN, the connection to the OCIGenAI service requires to run the model without any proxy.
Therefore, make sure not to have any of http_proxy or HTTP_PROXY environment variables setup, or unset them with unset http_proxy HTTP_PROXY

#### WARNING
If when using `INSTANCE_PRINCIPAL` authentication, the response of the model returns a `404` error, please check if the machine is listed in the dynamic group and has the right privileges. Otherwise, please ask someone with administrative privileges.
To grant an OCI Compute instance the ability to authenticate as an Instance Principal, one needs to define a Dynamic Group that includes the instance and create a policy that allows this dynamic group to manage OCI GenAI services.

#### *property* config *: Dict[str, Any]*

Get the configuration dictionary for the {VLlm/OpenAI/…} model

#### *property* default_agent_template *: [PromptTemplate](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)*

#### *property* default_chat_template *: [PromptTemplate](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)*

### *class* wayflowcore.models.ocigenaimodel.ServingMode(value)

The serving mode in which the model is hosted

#### DEDICATED *= 'DEDICATED'*

#### ON_DEMAND *= 'ON_DEMAND'*

### *class* wayflowcore.models.ocigenaimodel.ModelProvider(value)

Provider of the model. It is used to ensure the requests to this model respect
the format expected by the provider.

#### COHERE *= 'COHERE'*

#### GOOGLE *= 'GOOGLE'*

#### GROK *= 'GROK'*

#### META *= 'META'*

#### OTHER *= 'OTHER'*

#### XAI *= 'XAI'*

### *class* wayflowcore.models.ocigenaimodel.OciAPIType(value)

Enumeration of API Types.

#### OCI *= 'oci'*

Use the original oci SDK endpoint

#### OPENAI_CHAT_COMPLETIONS *= 'openai_chat_completions'*

Use the chat completion endpoint from OCI GenAI

#### OPENAI_RESPONSES *= 'openai_responses'*

Use the responses endpoint form OCI GenAI

<a id="ociclientconfigclassesforauthentication"></a>

#### OCI Client Config Classes for Authentication

### *class* wayflowcore.models.ociclientconfig.OCIClientConfig(service_endpoint, auth_type, compartment_id=None)

Base abstract class for OCI client config

* **Parameters:**
  * **service_endpoint** (*str*)
  * **auth_type** ( [*\_OCIAuthType*](#wayflowcore.models.ociclientconfig._OCIAuthType))
  * **compartment_id** (*str* *|* *None*)

#### auth_type *: [`_OCIAuthType`](#wayflowcore.models.ociclientconfig._OCIAuthType)*

#### compartment_id *: `Optional`[`str`]* *= None*

#### *classmethod* from_dict(input_dict)

* **Return type:**
  [`OCIClientConfig`](#wayflowcore.models.ociclientconfig.OCIClientConfig)
* **Parameters:**
  **input_dict** (*Dict* *[**str* *,* *str* *|* *Dict* *[**str* *,* *str* *]* *]*)

#### service_endpoint *: `str`*

#### to_dict()

* **Return type:**
  `Dict`[`str`, `Union`[`str`, `Dict`[`str`, `Any`]]]

<a id="ociclientconfigwithapikey"></a>

### *class* wayflowcore.models.ociclientconfig.OCIClientConfigWithApiKey(service_endpoint, compartment_id=None, auth_profile=None, \_auth_file_location=None)

OCI client config class for authentication using API_KEY.

* **Parameters:**
  * **service_endpoint** (`str`) – the endpoint of the OCI GenAI service.
  * **compartment_id** (`Optional`[`str`]) – compartment id to use.
  * **auth_profile** (`Optional`[`str`]) – name of the profile to use in the config file. Defaults to “DEFAULT”.
  * **\_auth_file_location** (*str* *|* *None*)

#### to_dict()

* **Return type:**
  `Dict`[`str`, `Union`[`str`, `Dict`[`str`, `str`]]]

<a id="ociclientconfigwithsecuritytoken"></a>

### *class* wayflowcore.models.ociclientconfig.OCIClientConfigWithSecurityToken(service_endpoint, compartment_id=None, auth_profile=None, \_auth_file_location=None)

OCI client config class for authentication using SECURITY_TOKEN.

* **Parameters:**
  * **service_endpoint** (`str`) – the endpoint of the OCI GenAI service.
  * **compartment_id** (`Optional`[`str`]) – compartment id to use.
  * **auth_profile** (`Optional`[`str`]) – name of the profile to use in the config file. Defaults to “DEFAULT”.
  * **\_auth_file_location** (*str* *|* *None*)

#### to_dict()

* **Return type:**
  `Dict`[`str`, `Union`[`str`, `Dict`[`str`, `str`]]]

<a id="ociclientconfigwithinstanceprincipal"></a>

### *class* wayflowcore.models.ociclientconfig.OCIClientConfigWithInstancePrincipal(service_endpoint, compartment_id=None)

OCI client config class for authentication using INSTANCE_PRINCIPAL.

* **Parameters:**
  * **service_endpoint** (`str`) – the endpoint of the OCI GenAI service.
  * **compartment_id** (`Optional`[`str`]) – compartment id to use.

<a id="ociclientconfigwithresourceprincipal"></a>

### *class* wayflowcore.models.ociclientconfig.OCIClientConfigWithResourcePrincipal(service_endpoint, compartment_id=None)

OCI client config class for authentication using RESOURCE_PRINCIPAL.

* **Parameters:**
  * **service_endpoint** (`str`) – the endpoint of the OCI GenAI service.
  * **compartment_id** (`Optional`[`str`]) – compartment id to use.

<a id="ociclientconfigwithuserauthentication"></a>

### *class* wayflowcore.models.ociclientconfig.OCIClientConfigWithUserAuthentication(service_endpoint, user_config, compartment_id=None)

* **Parameters:**
  * **service_endpoint** (*str*)
  * **user_config** ([*OCIUserAuthenticationConfig*](#wayflowcore.models.ociclientconfig.OCIUserAuthenticationConfig))
  * **compartment_id** (*str* *|* *None*)

#### to_dict()

* **Return type:**
  `Dict`[`str`, `Union`[`str`, `Dict`[`str`, `Any`]]]

### *class* wayflowcore.models.ociclientconfig.\_OCIAuthType(value)

An enumeration.

#### API_KEY *= 'API_KEY'*

#### INSTANCE_PRINCIPAL *= 'INSTANCE_PRINCIPAL'*

#### RESOURCE_PRINCIPAL *= 'RESOURCE_PRINCIPAL'*

#### SECURITY_TOKEN *= 'SECURITY_TOKEN'*

#### IMPORTANT
`OCIClientConfigWithUserAuthentication` supports the same authentication type as `OCIClientConfigWithApiKey` but without a config file.
Values in the config file are passed directly through `OCIUserAuthenticationConfig` below.

<a id="ociuserauthenticationconfig"></a>

### *class* wayflowcore.models.ociclientconfig.OCIUserAuthenticationConfig(user, key_content, fingerprint, tenancy, region)

Create an OCI user authentication config, which can be passed to the OCIClientConfigWithUserAuthentication class in order to authenticate the OCI service.

This class provides a way to authenticate the OCI service without relying on a config file.
In other words, it is equivalent to saving the config in a file and passing the file using OCIClientConfigWithApiKey class.

* **Parameters:**
  * **user** (`str`) – user OCID
  * **key_content** (`str`) – content of the private key
  * **fingerprint** (`str`) – fingerprint of your public key
  * **tenancy** (`str`) – tenancy OCID
  * **region** (`str`) – OCI region

#### WARNING
This class contains sensitive information. Please make sure that the contents are not printed or logged.

#### *classmethod* from_dict(client_config)

* **Return type:**
  [`OCIUserAuthenticationConfig`](#wayflowcore.models.ociclientconfig.OCIUserAuthenticationConfig)
* **Parameters:**
  **client_config** (*Dict* *[**str* *,* *str* *]*)

#### to_dict()

* **Return type:**
  `Dict`[`str`, `str`]

#### IMPORTANT
The serialization of this class is currently not supported since the values are sensitive information.
