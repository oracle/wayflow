.. :orphan:

.. :no-search:

.. tabs::

    .. tab:: OCI GenAI

        .. code-block:: python

            from wayflowcore.models import OCIGenAIModel, OCIClientConfigWithApiKey

            llm = OCIGenAIModel(
                model_id="provider.model-id",
                compartment_id="compartment-id",
                client_config=OCIClientConfigWithApiKey(
                    service_endpoint="https://url-to-service-endpoint.com",
                ),
            )

    .. tab:: vLLM

        .. code-block:: python

            from wayflowcore.models import VllmModel

            llm = VllmModel(
                model_id="model-id",
                host_port="VLLM_HOST_PORT",
            )

    .. tab:: Ollama

        .. code-block:: python

            from wayflowcore.models import OllamaModel

            llm = OllamaModel(
                model_id="model-id",
            )
