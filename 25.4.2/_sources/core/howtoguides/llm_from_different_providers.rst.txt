============================================
How to Use LLMs from Different LLM Providers
============================================

WayFlow supports several LLM API providers. The available LLMs are:

- :class:`OpenAIModel`
- :class:`OpenAICompatibleModel`
- :class:`OCIGenAIModel`
- :class:`VllmModel`
- :class:`OllamaModel`

Their configuration is specified directly to their respective class constructor.
This guide will show you how to configure LLMs from different LLM providers with examples and notes on usage.

Basic implementation
--------------------

Currently, defining a configuration dictionary and passing it to the :meth:`.LlmModelFactory.from_config` method is a convenient way to instantiate a particular LLM model in WayFlow.
However, you can also achieve this by directly instantiating the model classes, providing flexibility for more customized setups.

You can find a detailed description of each supported model type in this guide, demonstrating both methods — using the configuration dictionary and direct instantiation — for each model.

OCI GenAI Model
---------------

`OCI GenAI Model <https://docs.oracle.com/iaas/Content/generative-ai/overview.htm>`_ is powered by `OCI Generative AI <https://www.oracle.com/artificial-intelligence/generative-ai/generative-ai-service/>`_.

**Parameters**

.. option:: model_id: str

  Name of the model to use. A list of the available models is given in
  `Oracle OCI Documentation <https://docs.oracle.com/en-us/iaas/Content/generative-ai/deprecating.htm#>`_
  under the Model Retirement Dates (On-Demand Mode) section.

.. option:: generation_config: dict, optional
  Default parameters for text generation with this model.
  Example:
  .. code-block:: python

    generation_config = LlmGenerationConfig(max_tokens=256, temperature=0.8, top_p=0.95)

.. option:: client_config: OCIClientConfig, optional

  OCI client config to authenticate the OCI service.
  See the below examples and :ref:`ociclientconfigclassesforauthentication` for the usage and more information.

**Examples**

.. literalinclude:: ../code_examples/example_initialize_llms.py
    :language: python
    :start-after: .. oci-start
    :end-before: .. oci-end

.. collapse:: Equivalent code example utilizing the LlmModelFactory class.

    .. literalinclude:: ../code_examples/example_initialize_llms.py
        :language: python
        :start-after: .. oci-llmfactory-start
        :end-before: .. oci-llmfactory-end

.. collapse:: Equivalent code example utilizing the OCIUserAuthenticationConfig class (API_KEY authentication without config/key files).

  WayFlow allows users to authenticate OCI GenAI service using a user API key without relying on a local config file and a key file.

    Instead of using a config file, the values of config parameters can be specified in the :ref:`OCIUserAuthenticationConfig <OCIUserAuthenticationConfig>`.

    .. literalinclude:: ../code_examples/example_ociuserauthentication.py
        :language: python
        :start-after: .. start-userauthenticationconfig:
        :end-before: .. end-userauthenticationconfig

    .. note::

      The user authentication config parameters are sensitive information. This information will not be included when serializing a flow (there will be just an empty dictionary instead).

    You can create a client configuration with the user authentication configuration.

    .. literalinclude:: ../code_examples/example_ociuserauthentication.py
        :language: python
        :start-after: .. start-clientconfig:
        :end-before: .. end-clientconfig


    Then create an ``OCIGenAIModel`` object:

    .. literalinclude:: ../code_examples/example_ociuserauthentication.py
        :language: python
        :start-after: .. start-ocigenaimodel:
        :end-before: .. end-ocigenaimodel

    Alternatively, you can use the :meth:`.LlmModelFactory.from_config` to create an ``OCIGenAIModel`` object:

    .. literalinclude:: ../code_examples/example_ociuserauthentication.py
        :language: python
        :start-after: .. start-llmmodelfactory:
        :end-before: .. end-llmmodelfactory

**Notes**

- Make sure to properly set up authentication configuration.
- Make sure that you have the ``oci>=2.134.0`` package installed. With your WayFlow environment activated, you can install the package as follows:

  .. code-block:: bash

    pip install oci>=2.134.0

.. note::
  We recommend to encapsulate your code with ``if __name__ == "__main__":`` to avoid any unexpected issues.

.. important::
  If, when using the ``INSTANCE_PRINCIPAL``, the response of the model returns a ``404`` error,
  check if your instance is listed in the dynamic group and has the right privileges.
  Otherwise, ask someone with administrative privileges to grant your OCI Compute instance the ability to authenticate as an Instance Principal.
  You need to have a Dynamic Group that includes the instance and a policy that allows this dynamic group to manage OCI GenAI services.

.. _subsection-api-key-gen:

Using the API_KEY authentication method
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to use the ``API_KEY`` authentication method, generating and setting a new ``.pem`` OCI key is necessary.
The following steps will guide you through the generation and setup process:

  1. Login to the OCI console.
  2. In the navigation bar, select the **Profile** menu and then navigate to **User settings** or **My profile**, depending on the option that you see.
  3. Under **Resources**, select **API Keys**, and then select **Add API Key**.
  4. Select **Generate API Key Pair** in the Add API Key dialog.
  5. Select **Download Private Key** and save the private key file (the *.pem* file) in the *~/.oci/config* directory. (If the *~/.oci/config* directory does not exist, create it now).
  6. Select **Add** to add the new API signing key to your user settings. The Configuration File Preview dialog is displayed, containing a configuration file snippet with basic authentication information for the profile named ``DEFAULT`` (including the fingerprint of the API signing key you just created).
  7. Copy the configuration file snippet shown in the text box, and close the Configuration File Preview dialog.
  8. In a text editor, open the *~/.oci/config* file and paste the snippet into the file. (If the *~/.oci/config* does not exist, create it now).
  9. In the text editor, change the value of the ``key_file`` parameter of the profile to specify the path of the private key file (the *.pem* file you downloaded earlier).
  10. Save the changes you have made to the *~/.oci/config* file, and close the text editor.
  11. In a terminal window, change permissions on the private key file (the *.pem* file) to ensure that only you can read it, by entering:
      ``chmod go-rwx ~/.oci/<private-key-file-name>.pem``

Example of defining the model parameters:
  .. code-block:: python

    llm = OCIGenAIModel(
      model_id="<model ID attained from the Model Retirement Dates (On-Demand Mode) list in the OCI console website>",
      service_endpoint="https://inference.generativeai.<oci region>.oci.oraclecloud.com",
      compartment_id="ocid1.compartment.oc1..<compartment_id ID obtained from your personal OCI account (not the key config). The ID can be obtained under Identity > Compartments in the OCI console website.>",
      auth_type="API_KEY",
      auth_profile="DEFAULT",
      generation_config=generation_config,
    )

Example of the key configuration in *.oci/config*:
  .. code-block:: ini

    [DEFAULT]
    user=ocid1.user.oc1..<given in step 7>
    fingerprint=<given in step 7>
    tenancy=ocid1.tenancy.oc1..<given in step 7>
    region=<given in step 7 (region where you created your key in step 4)>
    key_file=<path of the downloaded key in step 5 (for convenience, store the key in the .oci directory and ensure it has a .pem suffix.)>

  This file is automatically generated and can be downloaded in step 7.

OpenAI Model
------------

OpenAI Model is powered by `OpenAI <https://platform.openai.com/docs/models>`_.

**Parameters**

- **model_id** : str
  Name of the model to use. Current supported models: ``gpt-4o`` and ``gpt-4o-mini``.

- **generation_config** : dict, optional
  Default parameters for text generation with this model.

- **proxy** : str, optional
  Proxy settings to access the remote model.

.. important::
   Ensure that the ``OPENAI_API_KEY`` is set beforehand
   to access this model. A list of available OpenAI models can be found at
   the following link: `OpenAI Models <https://platform.openai.com/docs/models>`_.
   Among these, the supported models include ``gpt-4o`` and ``gpt-4o-mini``.
   Note that the ``gpt-o1`` and ``gpt-o3`` models are not currently supported.

**Examples**

.. literalinclude:: ../code_examples/example_initialize_llms.py
    :language: python
    :start-after: .. openai-start
    :end-before: .. openai-end

.. collapse:: Equivalent code example utilizing the LlmModelFactory class.

    .. literalinclude:: ../code_examples/example_initialize_llms.py
        :language: python
        :start-after: .. openai-llmfactory-start
        :end-before: .. openai-llmfactory-end

vLLM Model
----------

`vLLM Model <https://docs.vllm.ai/en/latest/models/supported_models.html>`_ is a model hosted with a vLLM server.

**Parameters**

- **model_id** : str
  Name of the model to use.
- **host_port** : str
  Hostname and port of the vLLM server where the model is hosted.
- **generation_config** : dict, optional
  Default parameters for text generation with this model.

**Examples**

.. literalinclude:: ../code_examples/example_initialize_llms.py
    :language: python
    :start-after: .. vllm-start
    :end-before: .. vllm-end

.. collapse:: Equivalent code example utilizing the LlmModelFactory class.

    .. literalinclude:: ../code_examples/example_initialize_llms.py
        :language: python
        :start-after: .. vllm-llmfactory-start
        :end-before: .. vllm-llmfactory-end

**Notes**

Usually, vLLM models do not support tools calling.
To enable this functionality, WayFlow modifies the prompt by prepending and appending specific ReAct templates and formats tools accordingly when:

- The model is required to utilize tools.
- The list of messages contains some ``tool_requests`` or ``tool_results``.

Be aware of this when you generate with tools or tool calls.
To disable this behavior, set ``use_tools`` to ``False`` and ensure the prompt does not contain
``tool_call`` and ``tool_result`` messages.
See `this documentation <https://arxiv.org/abs/2210.03629>`_ for more details on the ReAct prompting technique.


Ollama Model
------------

`Ollama Model <https://ollama.com/>`_ is powered by a locally hosted Ollama server.

**Parameters**

- **model_id** : str
  Name of the model to use. A list of model names can be found `here <https://ollama.com/search>`_.

- **host_port** : str
  Hostname and port of the Ollama server where the model is hosted.
  By default Ollama binds port 11434.

- **generation_config** : dict, optional
  Default parameters for text generation with this model.

**Examples**

.. literalinclude:: ../code_examples/example_initialize_llms.py
    :language: python
    :start-after: .. ollama-start
    :end-before: .. ollama-end

.. collapse:: Equivalent code example utilizing the LlmModelFactory class.

    .. literalinclude:: ../code_examples/example_initialize_llms.py
        :language: python
        :start-after: .. ollama-llmfactory-start
        :end-before: .. ollama-llmfactory-end

**Notes**

As of November 2024, Ollama does not support tools calling with token streaming.
To enable this functionality, WayFlow modifies the prompt by prepending and appending specific ReAct templates and formats tools accordingly when:

- The model is required to utilize tools.
- The list of messages contains some ``tool_requests`` or ``tool_results``.

Be aware of that when you generate with tools or tool calls.
To disable this behavior, set ``use_tools`` to ``False`` and ensure the prompt does not contain
``tool_call`` and ``tool_result`` messages.
See `this documentation <https://arxiv.org/abs/2210.03629>`_ for more details on the ReAct prompting technique.


Recap
-----

This guide provides detailed descriptions of each model type supported by WayFlow, demonstrating how to use both the configuration dictionary and direct instantiation methods for each model.

.. collapse:: Below is the complete code from this guide.

    .. literalinclude:: ../code_examples/example_initialize_llms.py
        :language: python
        :start-after: .. recap:
        :end-before: .. end-recap


Next steps
----------

Having learned how to configure and initialize LLMs from different providers, you may now proceed to:

- :doc:`Config Generation <generation_config>`
- :doc:`How to Build Assistants with Tools <howto_build_assistants_with_tools>`

Some additional resources we recommend are:

- `HuggingFace - Generation with LLMs <https://huggingface.co/docs/transformers/llm_tutorial>`_
- `HuggingFace - Text generation strategies <https://huggingface.co/docs/transformers/generation_strategies>`_
