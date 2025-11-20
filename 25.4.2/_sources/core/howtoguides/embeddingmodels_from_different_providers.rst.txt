====================================================
How to Use Embedding Models from Different Providers
====================================================

WayFlow supports several embedding model providers. The available embedding models are:

- :class:`OCIGenAIEmbeddingModel`
- :class:`OpenAIEmbeddingModel`
- :class:`VllmEmbeddingModel`
- :class:`OllamaEmbeddingModel`

Their configuration is specified directly to their respective class constructor.
This guide will show you how to configure embedding models from different providers with examples and notes on usage.

Basic Implementation
--------------------

WayFlow provides multiple ways to work with embedding models. You can directly instantiate embedding model classes for maximum flexibility and control, which is the approach demonstrated in this guide. Each embedding model class extends the abstract ``EmbeddingModel`` base class and implements the required `embed` method.

For the embedding models shown in this guide:

- All models implement a consistent interface through the abstract ``EmbeddingModel`` base class
- Models generally require provider-specific configuration for authentication and endpoint access
- Security best practices are followed, with sensitive authentication data never being serialized
- The ``SerializableObject`` interface allows for saving and loading model configurations

The following sections provide detailed information about each supported embedding model type, with examples showing how to instantiate and use them.

OCI GenAI Embedding Model
-------------------------

`OCI GenAI Embedding Model <https://docs.oracle.com/iaas/Content/generative-ai/overview.htm>`_ is powered by `OCI Generative AI <https://www.oracle.com/artificial-intelligence/generative-ai/generative-ai-service/>`_.

**Parameters**

.. option:: model_id: str

  Name of the model to use. A list of the available models is given in
  `Oracle OCI Documentation <https://docs.oracle.com/en-us/iaas/Content/generative-ai/deprecating.htm#>`_
  under the Model Retirement Dates (Embedding Models) section.

.. option:: config: OCIClientConfig

  OCI client config to authenticate the OCI service.
  See the below examples and :ref:`ociclientconfigclassesforauthentication` for the usage and more information.

**Examples**

.. literalinclude:: ../code_examples/example_initialize_embedding_models.py
    :language: python
    :start-after: .. oci-embedding-start
    :end-before: .. oci-embedding-end

.. collapse:: Equivalent code example utilizing the OCIUserAuthenticationConfig class (API_KEY authentication without config/key files).

  WayFlow allows users to authenticate OCI GenAI service using a user API key without relying on a local config file and a key file.

    Instead of using a config file, the values of config parameters can be specified in the :ref:`OCIUserAuthenticationConfig <OCIUserAuthenticationConfig>`.

    .. literalinclude:: ../code_examples/example_oci_embeddings_userauthentication.py
        :language: python
        :start-after: .. start-embeddings-userauthenticationconfig:
        :end-before: .. end-embeddings-userauthenticationconfig

    .. note::

      The user authentication config parameters are sensitive information. This information will not be included when serializing a flow (there will be just an empty dictionary instead).

    You can create a client configuration with the user authentication configuration.

    .. literalinclude:: ../code_examples/example_oci_embeddings_userauthentication.py
        :language: python
        :start-after: .. start-embeddings-clientconfig:
        :end-before: .. end-embeddings-clientconfig


    Then create an ``OCIGenAIEmbeddingModel`` object:

    .. literalinclude:: ../code_examples/example_oci_embeddings_userauthentication.py
        :language: python
        :start-after: .. start-ocigenaiembeddingmodel:
        :end-before: .. end-ocigenaiembeddingmodel

**Notes**

- Make sure to properly set up authentication configuration.
- Make sure that you have the ``oci>=2.134.0`` package installed. With your WayFlow environment activated, you can install the package as follows:

  .. code-block:: bash

    pip install oci>=2.134.0

.. important::
  If, when using the ``INSTANCE_PRINCIPAL``, the response of the model returns a ``404`` error,
  check if your instance is listed in the dynamic group and has the right privileges.
  Otherwise, ask someone with administrative privileges to grant your OCI Compute instance the ability to authenticate as an Instance Principal.
  You need to have a Dynamic Group that includes the instance and a policy that allows this dynamic group to manage OCI GenAI services.

OpenAI Embedding Model
----------------------

OpenAI Embedding Model is powered by `OpenAI <https://platform.openai.com/docs/guides/embeddings>`_.

**Parameters**

- **model_id** : str
  Name of the model to use. Current supported models: ``text-embedding-3-small``, ``text-embedding-3-large``, and ``text-embedding-ada-002``
  (legacy model).

- **api_key** : str, optional
  The API key for authentication with OpenAI. If not provided, the value of the
  ``OPENAI_API_KEY`` environment variable will be used, if set.

**Examples**

.. literalinclude:: ../code_examples/example_initialize_embedding_models.py
    :language: python
    :start-after: .. openai-embedding-start
    :end-before: .. openai-embedding-end

vLLM Embedding Model
--------------------

`vLLM Embedding Model <https://docs.vllm.ai/en/latest/models/supported_models.html>`_ is a model hosted with a vLLM server.

**Parameters**

- **url** : str
  The complete URL of the vLLM server where the model is hosted (e.g., "http://localhost:8000" or "https://secure-vllm.example.com").
  Both HTTP and HTTPS protocols are supported.

- **model_id** : str
  Name of the model to use.

**Examples**

.. literalinclude:: ../code_examples/example_initialize_embedding_models.py
    :language: python
    :start-after: .. vllm-embedding-start
    :end-before: .. vllm-embedding-end

**Notes**

The vLLM embedding model makes HTTP/HTTPS POST requests to the /v1/embeddings endpoint of the specified URL,
following the OpenAI API format. When using HTTPS, certificate verification is performed by default.
For self-signed certificates, additional configuration may be needed at the application level.

Ollama Embedding Model
----------------------

`Ollama Embedding Model <https://ollama.com/>`_ is powered by a locally hosted Ollama server.

**Parameters**

- **url** : str
  The complete URL of the Ollama server where the model is hosted (e.g., "http://localhost:11434" or "https://ollama.example.com").
  Both HTTP and HTTPS protocols are supported.

- **model_id** : str
  Name of the model to use. A list of model names can be found `here <https://ollama.com/search>`_.

**Examples**

.. literalinclude:: ../code_examples/example_initialize_embedding_models.py
    :language: python
    :start-after: .. ollama-embedding-start
    :end-before: .. ollama-embedding-end

**Notes**

The Ollama embedding model makes HTTP/HTTPS POST requests to the /v1/embeddings endpoint of the specified URL,
following the OpenAI API format. Ensure your Ollama server is properly configured with models that support embedding generation.
When using HTTPS, certificate verification is performed by default. For self-signed certificates,
additional configuration may be needed at the application level.

Recap
-----

This guide provides detailed descriptions of each embedding model type supported by WayFlow, demonstrating how to use both the configuration dictionary and direct instantiation methods for each model.
You can find below the complete code example presented in this guide:

.. collapse:: Full Code

    .. literalinclude:: ../code_examples/example_initialize_embedding_models.py
        :language: python
        :start-after: .. recap:
        :end-before: .. end-recap


Next steps
----------

Having learned how to configure and initialize embedding models from different providers, you may now proceed to:

- :doc:`Datastores <howto_datastores>`
