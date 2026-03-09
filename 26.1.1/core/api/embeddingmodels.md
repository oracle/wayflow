# Embedding Models

This page presents all APIs and classes related to LLM Embedding models.

## EmbeddingModel

<a id="id1"></a>

### *class* wayflowcore.embeddingmodels.embeddingmodel.EmbeddingModel(\_\_metadata_info_\_, id=None, name=None, description=None)

Abstract base class for embedding models.

Implementations should define the ‘embed’ method which returns a list of
vector embeddings (each embedding is a list of floats) given a list of text strings.

* **Parameters:**
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)

#### *abstract* embed(data)

Generate embeddings for the given list of text strings.

* **Parameters:**
  **data** (`List`[`str`]) – A list of text strings for which to generate embeddings.
* **Returns:**
  A list where each element is a list of floats representing the embedding
  of the corresponding text.
* **Return type:**
  List[List[float]]

## All models

### OpenAI Compatible Embedding Models

<a id="openaicompatibleembeddingmodel"></a>

### *class* wayflowcore.embeddingmodels.openaicompatiblemodel.OpenAICompatibleEmbeddingModel(model_id, base_url, \_\_metadata_info_\_=None, id=None, name=None, description=None)

Base class for OpenAI-compatible embedding models.

* **Parameters:**
  * **model_id** (`str`) – The name of the model to use for generating embeddings.
  * **base_url** (`str`) – The base URL for the embedding API. Both HTTP and HTTPS protocols are supported.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)

#### embed(data)

Generate embeddings for the given list of text strings.

* **Parameters:**
  **data** (`List`[`str`]) – A list of text strings for which to generate embeddings.
* **Returns:**
  A list where each element is a list of floats representing the embedding
  of the corresponding text.
* **Return type:**
  List[List[float]]

#### *async* embed_async(data)

* **Return type:**
  `List`[`List`[`float`]]
* **Parameters:**
  **data** (*List* *[**str* *]*)

### OpenAI Embedding Models

<a id="openaiembeddingmodel"></a>

### *class* wayflowcore.embeddingmodels.openaimodel.OpenAIEmbeddingModel(model_id, api_key=None, \_\_metadata_info_\_=None, id=None, name=None, description=None, \_validate_api_key=True)

Embedding model for OpenAI’s embedding API using the requests library.

* **Parameters:**
  * **model_id** (`str`) – The name of the OpenAI model to use for generating embeddings.
  * **api_key** (`Optional`[`str`]) – The API key for the service. If not provided, the value of the
    OPENAI_API_KEY environment variable will be used, if set.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)
  * **\_validate_api_key** (*bool*)

### Examples

```pycon
>>> from wayflowcore.embeddingmodels.openaimodel import OpenAIEmbeddingModel  
>>> model = OpenAIEmbeddingModel(model_id="text-embedding-3-small", api_key="<your API key>")  
>>> embeddings = model.embed(["WayFlow is a framework to develop and run LLM-based assistants."])  
>>> # Update API key after initialization
>>> model.api_key = "<your new API key>"  
>>> # If no key is provided, it will try to use the OPENAI_API_KEY environment variable
>>> model.api_key = None  # Will use environment variable if available  
```

### Notes

OPENAI_API_KEY is the default API key used for authentication with the embedding service when `api_key` is not explicitly provided.
If the API key is not provided and the environment variable OPENAI_API_KEY is not set, a ValueError is raised.

Available embedding models: [https://platform.openai.com/docs/guides/embeddings#embedding-models](https://platform.openai.com/docs/guides/embeddings#embedding-models)

### VLLM Embedding Models

<a id="vllmembeddingmodel"></a>

### *class* wayflowcore.embeddingmodels.vllmmodel.VllmEmbeddingModel(model_id, base_url, \_\_metadata_info_\_=None, id=None, name=None, description=None)

Embedding model for self-hosted models via vLLM.

* **Parameters:**
  * **base_url** (`str`) – The complete URL of the vLLM server (e.g., “[http://localhost:8000](http://localhost:8000)” or “[https://secure-vllm.example.com](https://secure-vllm.example.com)”).
    Both HTTP and HTTPS protocols are supported.
  * **model_id** (`str`) – The name of the model to use on the server.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)

### Examples

```pycon
>>> from wayflowcore.embeddingmodels.vllmmodel import VllmEmbeddingModel  
>>> # Using HTTP
>>> model = VllmEmbeddingModel(url="http://localhost:8000", model_id="hosted-model-name")  
>>> # Using HTTPS
>>> secure_model = VllmEmbeddingModel(url="https://secure-vllm.example.com", model_id="hosted-model-name")  
>>> embeddings = model.embed(["WayFlow is a framework to develop and run LLM-based assistants."])  
```

### Notes

This provider makes HTTP/HTTPS POST requests to the /v1/embeddings endpoint of the specified URL.
When using HTTPS, certificate verification is performed by default. For self-signed certificates,
additional configuration may be needed at the application level.

### OCI GenAI Embedding Models

<a id="ocigenaiembeddingmodel"></a>

### *class* wayflowcore.embeddingmodels.ocigenaimodel.OCIGenAIEmbeddingModel(model_id, config, compartment_id=None, \_\_metadata_info_\_=None, id=None, name=None, description=None)

Embedding model for Oracle OCI Generative AI service.

* **Parameters:**
  * **model_id** (`str`) – The model identifier (e.g., ‘cohere.embed-english-light-v3.0’).
  * **config** ([`OCIClientConfig`](llmmodels.md#wayflowcore.models.ociclientconfig.OCIClientConfig)) – OCI client configuration with authentication details.
  * **compartment_id** (`Optional`[`str`]) – The compartment OCID
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)

### Examples

The following examples show how to configure the OCIGenAIEmbeddingModel.
In actual use, replace the placeholder values with your real credentials.

# Option 1: User Authentication Config
>>> from wayflowcore.models.ociclientconfig import OCIUserAuthenticationConfig, OCIClientConfigWithUserAuthentication  # doctest: +SKIP
>>> oci_user_config = OCIUserAuthenticationConfig(  # doctest: +SKIP
…     user=”<my_user_ocid>”,
…     key_content=”<my_key_content>”,
…     fingerprint=”<fingerprint_of_my_public_key>”,
…     tenancy=”<my_tenancy_ocid>”,
…     region=”<my_oci_region>”,
… )
>>> client_config = OCIClientConfigWithUserAuthentication(  # doctest: +SKIP
…     service_endpoint=”[https://inference.generativeai.us](https://inference.generativeai.us)-<your key’s region>.oci.oraclecloud.com”,
…     compartment_id=”<Please read the ‘Using the API_KEY authentication method’ subsection in the ‘How to Use LLM from Different LLM Sources/Providers’ how-to guide>”,
…     user_config=oci_user_config
… )

# Option 2: Instance Principal
>>> from wayflowcore.models.ociclientconfig import OCIClientConfigWithInstancePrincipal  # doctest: +SKIP
>>> client_config = OCIClientConfigWithInstancePrincipal(  # doctest: +SKIP
…     service_endpoint=”[https://inference.generativeai.us](https://inference.generativeai.us)-<your key’s region>.oci.oraclecloud.com”,
…     compartment_id=”<Please read the ‘Using the API_KEY authentication method’ subsection in the ‘How to Use LLM from Different LLM Sources/Providers’ how-to guide>”,
… )

# Option 3: API Key from the default config file
>>> from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey  # doctest: +SKIP
>>> client_config = OCIClientConfigWithApiKey(  # doctest: +SKIP
…     service_endpoint=”[https://inference.generativeai.us](https://inference.generativeai.us)-<your key’s region>.oci.oraclecloud.com”,
…     compartment_id=”<Please read the ‘Using the API_KEY authentication method’ subsection in the ‘How to Use LLM from Different LLM Sources/Providers’ how-to guide>”,
… )

# Using the configured client with the embedding model
>>> from wayflowcore.embeddingmodels.ocigenaimodel import OCIGenAIEmbeddingModel
>>> model = OCIGenAIEmbeddingModel(  # doctest: +SKIP
…     model_id=”cohere.embed-english-light-v3.0”,
…     config=client_config,  # Use whichever client_config option you prefer
… )
>>> embeddings = model.embed([“WayFlow is a framework to develop and run LLM-based assistants.”])  # doctest: +SKIP

### Notes

The OCI SDK must be installed.
For generating the OCI config file, please follow the WayFlow documentation.

Available embedding models: [https://docs.oracle.com/en-us/iaas/Content/generative-ai/pretrained-models.htm](https://docs.oracle.com/en-us/iaas/Content/generative-ai/pretrained-models.htm)

#### embed(data)

Generate embeddings for the given list of text strings.

* **Parameters:**
  **data** (`List`[`str`]) – A list of text strings for which to generate embeddings.
* **Returns:**
  A list where each element is a list of floats representing the embedding
  of the corresponding text.
* **Return type:**
  List[List[float]]

### Ollama Embedding Models

<a id="ollamaembeddingmodel"></a>

### *class* wayflowcore.embeddingmodels.ollamamodel.OllamaEmbeddingModel(model_id, base_url, \_\_metadata_info_\_=None, id=None, name=None, description=None)

Embedding model for self-hosted models via Ollama.

* **Parameters:**
  * **base_url** (`str`) – The complete URL of the Ollama server (e.g., “[http://localhost:11434](http://localhost:11434)” or “[https://ollama.example.com](https://ollama.example.com)”).
    Both HTTP and HTTPS protocols are supported.
  * **model_id** (`str`) – The name of the model to use on the Ollama server.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)

### Examples

```pycon
>>> from wayflowcore.embeddingmodels.ollamamodel import OllamaEmbeddingModel  
>>> # Using HTTP
>>> model = OllamaEmbeddingModel(url="http://localhost:11434", model_id="nomic-embed-text")  
>>> # Using HTTPS
>>> secure_model = OllamaEmbeddingModel(url="https://ollama.example.com", model_id="nomic-embed-text")  
>>> embeddings = model.embed(["WayFlow is a framework to develop and run LLM-based assistants."])  
```

### Notes

This provider makes HTTP/HTTPS POST requests to the /v1/embeddings endpoint of the specified URL.
When using HTTPS, certificate verification is performed by default. For self-signed certificates,
additional configuration may be needed at the application level.
