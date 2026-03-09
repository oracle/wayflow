# How to Use Embedding Models from Different Providers

WayFlow supports several embedding model providers. The available embedding models are:

- [OCIGenAIEmbeddingModel](../api/embeddingmodels.md#ocigenaiembeddingmodel)
- [OpenAIEmbeddingModel](../api/embeddingmodels.md#openaiembeddingmodel)
- [VllmEmbeddingModel](../api/embeddingmodels.md#vllmembeddingmodel)
- [OllamaEmbeddingModel](../api/embeddingmodels.md#ollamaembeddingmodel)

Their configuration is specified directly to their respective class constructor.
This guide will show you how to configure embedding models from different providers with examples and notes on usage.

## Basic Implementation

WayFlow provides multiple ways to work with embedding models. You can directly instantiate embedding model classes for maximum flexibility and control, which is the approach demonstrated in this guide. Each embedding model class extends the abstract `EmbeddingModel` base class and implements the required embed method.

For the embedding models shown in this guide:

- All models implement a consistent interface through the abstract `EmbeddingModel` base class
- Models generally require provider-specific configuration for authentication and endpoint access
- Security best practices are followed, with sensitive authentication data never being serialized
- The `SerializableObject` interface allows for saving and loading model configurations

The following sections provide detailed information about each supported embedding model type, with examples showing how to instantiate and use them.

## OCI GenAI Embedding Model

[OCI GenAI Embedding Model](https://docs.oracle.com/iaas/Content/generative-ai/overview.htm) is powered by [OCI Generative AI](https://www.oracle.com/artificial-intelligence/generative-ai/generative-ai-service/).

**Parameters**

### model_id: str

Name of the model to use. A list of the available models is given in
[Oracle OCI Documentation](https://docs.oracle.com/en-us/iaas/Content/generative-ai/deprecating.htm#)
under the Model Retirement Dates (Embedding Models) section.

### config: OCIClientConfig

OCI client config to authenticate the OCI service.
See the below examples and [OCI Client Config Classes for Authentication](../api/llmmodels.md#ociclientconfigclassesforauthentication) for the usage and more information.

**Examples**

```python
from wayflowcore.embeddingmodels import OCIGenAIEmbeddingModel
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey

if __name__ == "__main__":

    # Get the list of available embedding models from OCI documentation
    OCIGENAI_MODEL_ID = "cohere.embed-english-light-v3.0"
    # e.g. <oci region> can be "us-phoenix-1" and can also be found in your ~/.oci/config file
    OCIGENAI_ENDPOINT = "https://path.to.your.ocigenai.endpoint.com"
    # <compartment_id> can be obtained from your personal OCI account (not the key config file).
    # Please find it under "Identity > Compartments" on the OCI console website after logging in to your user account.
    COMPARTMENT_ID = "ocid1.compartment.oc1..example"

    oci_embedding_model = OCIGenAIEmbeddingModel(
        model_id=OCIGENAI_MODEL_ID,
        config=OCIClientConfigWithApiKey(
            service_endpoint=OCIGENAI_ENDPOINT,
            compartment_id=COMPARTMENT_ID,
        ),
    )

    # Generate embeddings
    text_list = [
        "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
    ]
    # embeddings = oci_embedding_model.embed(text_list)
    # print(f"OCI GenAI embeddings dimension: {len(embeddings[0])}")
```

<details>
<summary>Details</summary>

WayFlow allows users to authenticate OCI GenAI service using a user API key without relying on a local config file and a key file.

> Instead of using a config file, the values of config parameters can be specified in the [OCIUserAuthenticationConfig](../api/llmmodels.md#ociuserauthenticationconfig).

> ```python
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
> # Create client configuration with user authentication
> client_config = OCIClientConfigWithUserAuthentication(
>     service_endpoint="my_service_endpoint",  # replace it with your endpoint
>     compartment_id=oci_genai_cred["compartment_id"],
>     user_config=user_config,
> )
> ```

> Then create an `OCIGenAIEmbeddingModel` object:

> ```python
> # Create the OCIGenAIEmbeddingModel with the client configuration
> oci_embedding_model = OCIGenAIEmbeddingModel(
>     model_id="cohere.embed-english-light-v3.0",
>     config=client_config,
> )

> # Generate embeddings
> text_list = [
>     "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
> ]
> # embeddings = oci_embedding_model.embed(text_list)
> ```

</details>

**Notes**

- Make sure to properly set up authentication configuration.
- Make sure that you have the `oci>=2.134.0` package installed. With your WayFlow environment activated, you can install the package as follows:
  ```bash
  pip install oci>=2.134.0
  ```

#### IMPORTANT
If, when using the `INSTANCE_PRINCIPAL`, the response of the model returns a `404` error,
check if your instance is listed in the dynamic group and has the right privileges.
Otherwise, ask someone with administrative privileges to grant your OCI Compute instance the ability to authenticate as an Instance Principal.
You need to have a Dynamic Group that includes the instance and a policy that allows this dynamic group to manage OCI GenAI services.

## OpenAI Embedding Model

OpenAI Embedding Model is powered by [OpenAI](https://platform.openai.com/docs/guides/embeddings).

**Parameters**

- **model_id** : str
  Name of the model to use. Current supported models: `text-embedding-3-small`, `text-embedding-3-large`, and `text-embedding-ada-002`
  (legacy model).
- **api_key** : str, optional
  The API key for authentication with OpenAI. If not provided, the value of the
  `OPENAI_API_KEY` environment variable will be used, if set.

**Examples**

```python
from wayflowcore.embeddingmodels import OpenAIEmbeddingModel

if __name__ == "__main__":

    # For the sake of this example, we set the API key in the environment
    # In production, use a secure method to store and access the key
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "DUMMY_OPENAI_KEY")

    OPENAI_MODEL_ID = "text-embedding-3-small"

    openai_embedding_model = OpenAIEmbeddingModel(
        model_id=OPENAI_MODEL_ID,
    )

    # Generate embeddings
    text_list = [
        "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
    ]
    # embeddings = openai_embedding_model.embed(text_list)
    # print(f"OpenAI embeddings dimension: {len(embeddings[0])}")
```

## vLLM Embedding Model

[vLLM Embedding Model](https://docs.vllm.ai/en/latest/models/supported_models.html) is a model hosted with a vLLM server.

**Parameters**

- **url** : str
  The complete URL of the vLLM server where the model is hosted (e.g., “[http://localhost:8000](http://localhost:8000)” or “[https://secure-vllm.example.com](https://secure-vllm.example.com)”).
  Both HTTP and HTTPS protocols are supported.
- **model_id** : str
  Name of the model to use.

**Examples**

```python
from wayflowcore.embeddingmodels import VllmEmbeddingModel

if __name__ == "__main__":

    VLLM_MODEL_ID = "mistralai/mistral-embed"
    VLLM_BASE_URL = "http://your.ip:port"

    vllm_embedding_model = VllmEmbeddingModel(
        base_url=VLLM_BASE_URL,
        model_id=VLLM_MODEL_ID,
    )

    # Generate embeddings
    text_list = [
        "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
    ]
    # embeddings = vllm_embedding_model.embed(text_list)
    # print(f"vLLM embeddings dimension: {len(embeddings[0])}")
```

**Notes**

The vLLM embedding model makes HTTP/HTTPS POST requests to the /v1/embeddings endpoint of the specified URL,
following the OpenAI API format. When using HTTPS, certificate verification is performed by default.
For self-signed certificates, additional configuration may be needed at the application level.

## Ollama Embedding Model

[Ollama Embedding Model](https://ollama.com/) is powered by a locally hosted Ollama server.

**Parameters**

- **url** : str
  The complete URL of the Ollama server where the model is hosted (e.g., “[http://localhost:11434](http://localhost:11434)” or “[https://ollama.example.com](https://ollama.example.com)”).
  Both HTTP and HTTPS protocols are supported.
- **model_id** : str
  Name of the model to use. A list of model names can be found [here](https://ollama.com/search).

**Examples**

```python
from wayflowcore.embeddingmodels import OllamaEmbeddingModel

if __name__ == "__main__":

    OLLAMA_MODEL_ID = "nomic-embed-text"
    OLLAMA_BASE_URL = "http://your.ip:port"

    ollama_embedding_model = OllamaEmbeddingModel(
        base_url=OLLAMA_BASE_URL,
        model_id=OLLAMA_MODEL_ID,
    )

    # Generate embeddings
    text_list = [
        "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
    ]
    # embeddings = ollama_embedding_model.embed(text_list)
    # print(f"Ollama embeddings dimension: {len(embeddings[0])}")
```

**Notes**

The Ollama embedding model makes HTTP/HTTPS POST requests to the /v1/embeddings endpoint of the specified URL,
following the OpenAI API format. Ensure your Ollama server is properly configured with models that support embedding generation.
When using HTTPS, certificate verification is performed by default. For self-signed certificates,
additional configuration may be needed at the application level.

## Recap

This guide provides detailed descriptions of each embedding model type supported by WayFlow, demonstrating how to use both the configuration dictionary and direct instantiation methods for each model.
You can find below the complete code example presented in this guide:

<details>
<summary>Details</summary>

```python
from wayflowcore.embeddingmodels import (
    OCIGenAIEmbeddingModel,
    OllamaEmbeddingModel,
    OpenAIEmbeddingModel,
    VllmEmbeddingModel,
)
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey

if __name__ == "__main__":
    text_list = [
        "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
    ]

    # OCI GenAI Embedding Model
    OCIGENAI_MODEL_ID = "cohere.embed-english-light-v3.0"
    OCIGENAI_ENDPOINT = "https://path.to.your.ocigenai.endpoint.com"
    COMPARTMENT_ID = "ocid1.compartment.oc1..example"

    oci_embedding_model = OCIGenAIEmbeddingModel(
        model_id=OCIGENAI_MODEL_ID,
        config=OCIClientConfigWithApiKey(
            service_endpoint=OCIGENAI_ENDPOINT,
            compartment_id=COMPARTMENT_ID,
        ),
    )

    # oci_embeddings = oci_embedding_model.embed(text_list)
    # print(f"OCI GenAI embeddings dimension: {len(oci_embeddings[0])}")

    # OpenAI Embedding Model
    OPENAI_MODEL_ID = "text-embedding-3-small"

    openai_embedding_model = OpenAIEmbeddingModel(
        model_id=OPENAI_MODEL_ID,
    )

    # openai_embeddings = openai_embedding_model.embed(text_list)
    # print(f"OpenAI embeddings dimension: {len(openai_embeddings[0])}")

    # vLLM Embedding Model
    VLLM_MODEL_ID = "mistralai/mistral-embed"
    VLLM_BASE_URL = "http://your.ip:port"

    vllm_embedding_model = VllmEmbeddingModel(
        base_url=VLLM_BASE_URL,
        model_id=VLLM_MODEL_ID,
    )

    # vllm_embeddings = vllm_embedding_model.embed(text_list)
    # print(f"vLLM embeddings dimension: {len(vllm_embeddings[0])}")

    # Ollama Embedding Model
    OLLAMA_MODEL_ID = "nomic-embed-text"
    OLLAMA_BASE_URL = "http://your.ip:port"

    ollama_embedding_model = OllamaEmbeddingModel(
        base_url=OLLAMA_BASE_URL,
        model_id=OLLAMA_MODEL_ID,
    )

    # ollama_embeddings = ollama_embedding_model.embed(text_list)
    # print(f"Ollama embeddings dimension: {len(ollama_embeddings[0])}")
```

</details>

## Next steps

Having learned how to configure and initialize embedding models from different providers, you may now proceed to:

- [Datastores](howto_datastores.md)
