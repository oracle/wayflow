.. :orphan:

.. :no-search:

.. tabs::

    .. tab:: OCI GenAI

        .. code-block:: python

            from wayflowcore.models import OCIGenAIModel

            if __name__ == "__main__":

                llm = OCIGenAIModel(
                    model_id="provider.model-id",
                    service_endpoint="https://url-to-service-endpoint.com",
                    compartment_id="compartment-id",
                    auth_type="API_KEY",
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
