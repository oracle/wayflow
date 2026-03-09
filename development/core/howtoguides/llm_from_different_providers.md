# How to Use LLMs from Different LLM Providers

WayFlow supports several LLM API providers. The available LLMs are:

- [OpenAIModel](../api/llmmodels.md#openaimodel)
- [OpenAICompatibleModel](../api/llmmodels.md#openaicompatiblemodel)
- [OCIGenAIModel](../api/llmmodels.md#ocigenaimodel)
- [VllmModel](../api/llmmodels.md#vllmmodel)
- [OllamaModel](../api/llmmodels.md#ollamamodel)

Their configuration is specified directly to their respective class constructor.
This guide will show you how to configure LLMs from different LLM providers with examples and notes on usage.

## Basic implementation

Currently, defining a configuration dictionary and passing it to the [`LlmModelFactory.from_config()`](../api/llmmodels.md#wayflowcore.models.llmmodelfactory.LlmModelFactory.from_config) method is a convenient way to instantiate a particular LLM model in WayFlow.
However, you can also achieve this by directly instantiating the model classes, providing flexibility for more customized setups.

You can find a detailed description of each supported model type in this guide, demonstrating both methods — using the configuration dictionary and direct instantiation — for each model.

## OCI GenAI Model

[OCI GenAI Model](https://docs.oracle.com/iaas/Content/generative-ai/overview.htm) is powered by [OCI Generative AI](https://www.oracle.com/artificial-intelligence/generative-ai/generative-ai-service/).

**Parameters**

### model_id: str

Name of the model to use. A list of the available models is given in
[Oracle OCI Documentation](https://docs.oracle.com/en-us/iaas/Content/generative-ai/deprecating.htm#)
under the Model Retirement Dates (On-Demand Mode) section.

### generation_config: dict, optional

Default parameters for text generation with this model.
Example:

```python
generation_config = LlmGenerationConfig(max_tokens=256, temperature=0.8, top_p=0.95)
```

### client_config: OCIClientConfig, optional

OCI client config to authenticate the OCI service.
See the below examples and [OCI Client Config Classes for Authentication](../api/llmmodels.md#ociclientconfigclassesforauthentication) for the usage and more information.

**Examples**

```python
from wayflowcore.models import OCIGenAIModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey

if __name__ == "__main__":

    # Get the list of available models from:
    # https://docs.oracle.com/en-us/iaas/Content/generative-ai/deprecating.htm#
    # under the "Model Retirement Dates (On-Demand Mode)" section.
    OCIGENAI_MODEL_ID = "cohere.command-r-plus-08-2024"
    # e.g. <oci region> can be "us-chicago-1" and can also be found in your ~/.oci/config file
    OCIGENAI_ENDPOINT = "https://inference.generativeai.<oci region>.oci.oraclecloud.com"
    # <compartment_id> can be obtained from your personal OCI account (not the key config file).
    # Please find it under "Identity > Compartments" on the OCI console website after logging in to your user account.
    COMPARTMENT_ID = compartment_id = ("ocid1.compartment.oc1..<compartment_id>",)

    generation_config = LlmGenerationConfig(max_tokens=256, temperature=0.8, top_p=0.95)

    llm = OCIGenAIModel(
        model_id=OCIGENAI_MODEL_ID,
        client_config=OCIClientConfigWithApiKey(
            service_endpoint=OCIGENAI_ENDPOINT,
            compartment_id=COMPARTMENT_ID,
        ),
        generation_config=generation_config,
    )
```

<details>
<summary>Details</summary>

```python
if __name__ == "__main__":
    COHERE_CONFIG = {
        "model_type": "ocigenai",
        "model_id": OCIGENAI_MODEL_ID,
        "client_config": {
            "service_endpoint": OCIGENAI_ENDPOINT,
            "compartment_id": COMPARTMENT_ID,
            "auth_type": "API_KEY",
        },
    }

    llm = LlmModelFactory.from_config(COHERE_CONFIG)
```

</details>

<details>
<summary>Details</summary>

WayFlow allows users to authenticate OCI GenAI service using a user API key without relying on a local config file and a key file.

> Instead of using a config file, the values of config parameters can be specified in the [OCIUserAuthenticationConfig](../api/llmmodels.md#ociuserauthenticationconfig).

> ```python
> from wayflowcore.models.ociclientconfig import (
>     OCIClientConfigWithUserAuthentication,
>     OCIUserAuthenticationConfig,
> )

> # Assume we have an API to get credentials
> oci_genai_cred = get_oci_genai_credentials()

> user_config = OCIUserAuthenticationConfig(
>     user=oci_genai_cred["user"],
>     key_content=oci_genai_cred["key_content"],
>     fingerprint=oci_genai_cred["fingerprint"],
>     tenancy=oci_genai_cred["tenancy"],
>     region=oci_genai_cred["region"],
> )
> ```

> #### NOTE
> The user authentication config parameters are sensitive information. This information will not be included when serializing a flow (there will be just an empty dictionary instead).

> You can create a client configuration with the user authentication configuration.

> ```python
> client_config = OCIClientConfigWithUserAuthentication(
>     service_endpoint="my_service_endpoint",  # replace it with your endpoint
>     compartment_id=oci_genai_cred["compartment_id"],
>     user_config=user_config,
> )
> ```

> Then create an `OCIGenAIModel` object:

> ```python
> from wayflowcore.models.ocigenaimodel import OCIGenAIModel

> llm = OCIGenAIModel(
>     model_id="cohere.command-r-plus-08-2024",
>     client_config=client_config,
> )
> ```

> Alternatively, you can use the [`LlmModelFactory.from_config()`](../api/llmmodels.md#wayflowcore.models.llmmodelfactory.LlmModelFactory.from_config) to create an `OCIGenAIModel` object:

> ```python
> from wayflowcore.models import LlmModelFactory

> COHERE_CONFIG = {
>     "model_type": "ocigenai",
>     "model_id": "cohere.command-r-plus-08-2024",
>     "client_config": client_config,
> }
> llm = LlmModelFactory.from_config(COHERE_CONFIG)
> ```

</details>

**Notes**

- Make sure to properly set up authentication configuration.
- Make sure that you have the `oci>=2.134.0` package installed. With your WayFlow environment activated, you can install the package as follows:
  ```bash
  pip install oci>=2.134.0
  ```

#### NOTE
We recommend to encapsulate your code with `if __name__ == "__main__":` to avoid any unexpected issues.

#### IMPORTANT
If, when using the `INSTANCE_PRINCIPAL`, the response of the model returns a `404` error,
check if your instance is listed in the dynamic group and has the right privileges.
Otherwise, ask someone with administrative privileges to grant your OCI Compute instance the ability to authenticate as an Instance Principal.
You need to have a Dynamic Group that includes the instance and a policy that allows this dynamic group to manage OCI GenAI services.

<a id="subsection-api-key-gen"></a>

### Using the API_KEY authentication method

In order to use the `API_KEY` authentication method, generating and setting a new `.pem` OCI key is necessary.
The following steps will guide you through the generation and setup process:

> 1. Login to the OCI console.
> 2. In the navigation bar, select the **Profile** menu and then navigate to **User settings** or **My profile**, depending on the option that you see.
> 3. Under **Resources**, select **API Keys**, and then select **Add API Key**.
> 4. Select **Generate API Key Pair** in the Add API Key dialog.
> 5. Select **Download Private Key** and save the private key file (the  *.pem* file) in the  *~/.oci/config* directory. (If the  *~/.oci/config* directory does not exist, create it now).
> 6. Select **Add** to add the new API signing key to your user settings. The Configuration File Preview dialog is displayed, containing a configuration file snippet with basic authentication information for the profile named `DEFAULT` (including the fingerprint of the API signing key you just created).
> 7. Copy the configuration file snippet shown in the text box, and close the Configuration File Preview dialog.
> 8. In a text editor, open the  *~/.oci/config* file and paste the snippet into the file. (If the  *~/.oci/config* does not exist, create it now).
> 9. In the text editor, change the value of the `key_file` parameter of the profile to specify the path of the private key file (the  *.pem* file you downloaded earlier).
> 10. Save the changes you have made to the  *~/.oci/config* file, and close the text editor.
> 11. In a terminal window, change permissions on the private key file (the  *.pem* file) to ensure that only you can read it, by entering:
>     `chmod go-rwx ~/.oci/<private-key-file-name>.pem`

Example of defining the model parameters:
: ```python
  llm = OCIGenAIModel(
    model_id="<model ID attained from the Model Retirement Dates (On-Demand Mode) list in the OCI console website>",
    service_endpoint="https://inference.generativeai.<oci region>.oci.oraclecloud.com",
    compartment_id="ocid1.compartment.oc1..<compartment_id ID obtained from your personal OCI account (not the key config). The ID can be obtained under Identity > Compartments in the OCI console website.>",
    auth_type="API_KEY",
    auth_profile="DEFAULT",
    generation_config=generation_config,
  )
  ```

Example of the key configuration in  *.oci/config*:
: ```ini
  [DEFAULT]
  user=ocid1.user.oc1..<given in step 7>
  fingerprint=<given in step 7>
  tenancy=ocid1.tenancy.oc1..<given in step 7>
  region=<given in step 7 (region where you created your key in step 4)>
  key_file=<path of the downloaded key in step 5 (for convenience, store the key in the .oci directory and ensure it has a .pem suffix.)>
  ```
  

  This file is automatically generated and can be downloaded in step 7.

## OpenAI Model

OpenAI Model is powered by [OpenAI](https://platform.openai.com/docs/models).

**Parameters**

### model_id: str

Name of the model to use. Current supported models: `gpt-4o` and `gpt-4o-mini`.

### generation_config: dict, optional

Default parameters for text generation with this model.

### proxy: str, optional

Proxy settings to access the remote model.

### api_type: OpenAIAPIType

OpenAI API type to use. Should be one of the values from [OpenAIAPIType](../api/llmmodels.md#openaiapitype). Defaults to [Chat Completions API](https://platform.openai.com/docs/api-reference/chat)

#### IMPORTANT
Ensure that the `OPENAI_API_KEY` is set beforehand
to access this model. A list of available OpenAI models can be found at
the following link: [OpenAI Models](https://platform.openai.com/docs/models).
Among these, the supported models include `gpt-4o` and `gpt-4o-mini`.
Note that the `gpt-o1` and `gpt-o3` models are not currently supported.

**Examples**

```python
from wayflowcore.models import OpenAIModel, OpenAIAPIType

if __name__ == "__main__":

    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "DUMMY_OPENAI_KEY")

    # supported models "gpt-4o", "gpt-4o-mini".
    # We currently do not support gpt-o1 and gpt-o3 models.
    OPENAI_MODEL_ID = "gpt-5"

    generation_config = LlmGenerationConfig(max_tokens=256, temperature=0.7, top_p=0.9)

    api_type = OpenAIAPIType.RESPONSES

    llm = OpenAIModel(
        model_id=OPENAI_MODEL_ID,
        generation_config=generation_config,
        api_type=api_type,
    )
```

<details>
<summary>Details</summary>

```python
if __name__ == "__main__":
    OPENAI_CONFIG = {
        "model_type": "openai",
        "model_id": OPENAI_MODEL_ID,
        "generation_config": {"max_tokens": 256, "temperature": 0.7, "top_p": 0.9},
    }

    llm = LlmModelFactory.from_config(OPENAI_CONFIG)
```

</details>

## vLLM Model

[vLLM Model](https://docs.vllm.ai/en/latest/models/supported_models.html) is a model hosted with a vLLM server.

**Parameters**

### model_id: str

Name of the model to use.

### host_port: str

Hostname and port of the vLLM server where the model is hosted.

### generation_config: dict, optional

Default parameters for text generation with this model.

### api_type: OpenAIAPIType

OpenAI API type to use. Should be one of the values from [OpenAIAPIType](../api/llmmodels.md#openaiapitype). Defaults to [Chat Completions API](https://platform.openai.com/docs/api-reference/chat)

**Examples**

```python
from wayflowcore.models import VllmModel

if __name__ == "__main__":

    VLLM_MODEL_ID = "/storage/models/Llama-3.3-70B-Instruct"

    generation_config = LlmGenerationConfig(max_tokens=512, temperature=1.0, top_p=1.0)

    llm = VllmModel(
        model_id=VLLM_MODEL_ID,
        host_port=os.environ["VLLM_HOST_PORT"],
        generation_config=generation_config,
    )
```

<details>
<summary>Details</summary>

```python
if __name__ == "__main__":
    VLLM_CONFIG = {
        "model_type": "vllm",
        "host_port": VLLM_HOST_PORT,
        "model_id": VLLM_MODEL_ID,
    }

    llm = LlmModelFactory.from_config(VLLM_CONFIG)
```

</details>

**Notes**

Usually, vLLM models do not support tools calling.
To enable this functionality, WayFlow modifies the prompt by prepending and appending specific ReAct templates and formats tools accordingly when:

- The model is required to utilize tools.
- The list of messages contains some `tool_requests` or `tool_results`.

Be aware of this when you generate with tools or tool calls.
To disable this behavior, set `use_tools` to `False` and ensure the prompt does not contain
`tool_call` and `tool_result` messages.
See [this documentation](https://arxiv.org/abs/2210.03629) for more details on the ReAct prompting technique.

## Ollama Model

[Ollama Model](https://ollama.com/) is powered by a locally hosted Ollama server.

**Parameters**

### model_id: str

Name of the model to use. A list of model names can be found [here](https://ollama.com/search).

### host_port: str

Hostname and port of the Ollama server where the model is hosted.
By default Ollama binds port 11434.

### generation_config: dict, optional

Default parameters for text generation with this model.

**Examples**

```python
from wayflowcore.models import OllamaModel

if __name__ == "__main__":

    OLLAMA_MODEL_ID = "llama2-7b"
    OLLAMA_HOST_PORT = "localhost:11434"  # default is 11434 if omitted

    generation_config = LlmGenerationConfig(max_tokens=512, temperature=0.9, top_p=0.9)

    llm = OllamaModel(
        model_id=OLLAMA_MODEL_ID, host_port=OLLAMA_HOST_PORT, generation_config=generation_config
    )
```

<details>
<summary>Details</summary>

```python
if __name__ == "__main__":
    OLLAMA_CONFIG = {
        "model_type": "ollama",
        "model_id": OLLAMA_MODEL_ID,
        "host_port": OLLAMA_HOST_PORT,
        "generation_config": {"max_tokens": 512, "temperature": 0.9, "top_p": 0.9},
    }

    llm = LlmModelFactory.from_config(OLLAMA_CONFIG)
```

</details>

**Notes**

As of November 2025, Ollama does not support [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses). Therefore only Chat Completions API will be supported for OpenAI models.

As of November 2024, Ollama does not support tools calling with token streaming.
To enable this functionality, WayFlow modifies the prompt by prepending and appending specific ReAct templates and formats tools accordingly when:

- The model is required to utilize tools.
- The list of messages contains some `tool_requests` or `tool_results`.

Be aware of that when you generate with tools or tool calls.
To disable this behavior, set `use_tools` to `False` and ensure the prompt does not contain
`tool_call` and `tool_result` messages.
See [this documentation](https://arxiv.org/abs/2210.03629) for more details on the ReAct prompting technique.

## Troubleshooting

In certain situations, models may require messages to follow a specific order.
Message transforms such as [CanonicalizationMessageTransform](../api/prompttemplate.md#canonicalizationtransform) can
be used to enforce the correct ordering of messages (for example, when working with Google models).
For additional details on LLM prompting, refer to the [Prompt Template guide](howto_prompttemplate.md).

## Recap

This guide provides detailed descriptions of each model type supported by WayFlow, demonstrating how to use both the configuration dictionary and direct instantiation methods for each model.

<details>
<summary>Details</summary>

```python
from wayflowcore.models import OCIGenAIModel, OllamaModel, OpenAIModel, VllmModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig

OCIGENAI_MODEL_ID = "cohere.command-r-plus"
OCIGENAI_ENDPOINT = "<YOUR_SERVICE_ENDPOINT>"
COMPARTMENT_ID = "<YOUR_COMPARTMENT_ID>"

if __name__ == "__main__":

    generation_config = LlmGenerationConfig(max_tokens=256, temperature=0.8, top_p=0.95)

    llm = OCIGenAIModel(
        model_id=OCIGENAI_MODEL_ID,
        client_config=OCIClientConfigWithApiKey(
            service_endpoint=OCIGENAI_ENDPOINT,
            compartment_id=COMPARTMENT_ID,
        ),
        generation_config=generation_config,
    )

    VLLM_MODEL_ID = "/storage/models/Llama-3.3-70B-Instruct"
    VLLM_HOST_PORT = "lVLLM_HOST_PORT"

    generation_config = LlmGenerationConfig(max_tokens=512, temperature=1.0, top_p=1.0)

    llm = VllmModel(
        model_id=VLLM_MODEL_ID,
        host_port=VLLM_HOST_PORT,
        generation_config=generation_config,
    )

    # export OPENAI_API_KEY=<a_valid_open_ai_key>
    # supported models "gpt-4o", "gpt-4o-mini".
    # We currently do not support gpt-o1 and gpt-o3 models.
    OPENAI_MODEL_ID = "gpt-4o"

    generation_config = LlmGenerationConfig(max_tokens=256, temperature=0.7, top_p=0.9)

    llm = OpenAIModel(
        model_id=OPENAI_MODEL_ID,
        generation_config=generation_config,
    )

    OLLAMA_MODEL_ID = "llama2-7b"
    OLLAMA_HOST_PORT = "localhost:11434"  # default is 11434 if omitted

    generation_config = LlmGenerationConfig(max_tokens=512, temperature=0.9, top_p=0.9)

    llm = OllamaModel(
        model_id=OLLAMA_MODEL_ID, host_port=OLLAMA_HOST_PORT, generation_config=generation_config
    )
```

</details>

## Next steps

Having learned how to configure and initialize LLMs from different providers, you may now proceed to:

- [Config Generation](generation_config.md)
- [How to Build Assistants with Tools](howto_build_assistants_with_tools.md)

Some additional resources we recommend are:

- [HuggingFace - Generation with LLMs](https://huggingface.co/docs/transformers/llm_tutorial)
- [HuggingFace - Text generation strategies](https://huggingface.co/docs/transformers/generation_strategies)
