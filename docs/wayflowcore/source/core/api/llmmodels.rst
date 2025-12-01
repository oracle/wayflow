LLMs
====

This page presents all APIs and classes related to LLM models.


.. |agentspec-icon| image:: ../../_static/icons/agentspec-icon.svg
   :width: 100px

.. grid:: 1

    .. grid-item-card:: |agentspec-icon|
        :link: https://oracle.github.io/agent-spec/api/llmmodels.html
        :link-alt: Agent Spec - LLMs API Reference

        Visit the Agent Spec API Documentation to learn more about LLMs Components.


.. tip::

    Click the button above ↑ to visit the `Agent Spec Documentation <https://oracle.github.io/agent-spec/index.html>`_



LlmModel
-----------------

.. _llmmodel:
.. autoclass:: wayflowcore.models.llmmodel.LlmModel


LlmModelFactory
------------------------

.. _llmmodelfactory:
.. autoclass:: wayflowcore.models.llmmodelfactory.LlmModelFactory


Token Usage
-----------

Class that is used to gather all token usage information.

.. _tokenusage:
.. autoclass:: wayflowcore.tokenusage.TokenUsage


LLM Generation Config
---------------------

Parameters for LLM generation (``max_tokens``, ``temperature``, ``top_p``).

.. _llmgenerationconfig:
.. autoclass:: wayflowcore.models.llmgenerationconfig.LlmGenerationConfig

API Type
-----------

Class that is used to select the OpenAI API Type to use.

.. _openaiapitype:
.. autoclass:: wayflowcore.models.openaiapitype.OpenAIAPIType

.. _allllms:

All models
----------

OpenAI Compatible Models
~~~~~~~~~~~~~~~~~~~~~~~~

.. _openaicompatiblemodel:
.. autoclass:: wayflowcore.models.openaicompatiblemodel.OpenAICompatibleModel

OpenAI Models
~~~~~~~~~~~~~

.. _openaimodel:
.. autoclass:: wayflowcore.models.openaimodel.OpenAIModel

Ollama Models
~~~~~~~~~~~~~

.. _ollamamodel:
.. autoclass:: wayflowcore.models.ollamamodel.OllamaModel

VLLM Models
~~~~~~~~~~~

.. _vllmmodel:
.. autoclass:: wayflowcore.models.vllmmodel.VllmModel

OCI GenAI Models
~~~~~~~~~~~~~~~~

.. _ocigenaimodel:
.. autoclass:: wayflowcore.models.ocigenaimodel.OCIGenAIModel

.. _ociclientconfigclassesforauthentication:

OCI Client Config Classes for Authentication
********************************************

.. _ociclientconfigwithapikey:
.. autoclass:: wayflowcore.models.ociclientconfig.OCIClientConfigWithApiKey

.. _ociclientconfigwithsecuritytoken:
.. autoclass:: wayflowcore.models.ociclientconfig.OCIClientConfigWithSecurityToken

.. _ociclientconfigwithinstanceprincipal:
.. autoclass:: wayflowcore.models.ociclientconfig.OCIClientConfigWithInstancePrincipal

.. _ociclientconfigwithresourceprincipal:
.. autoclass:: wayflowcore.models.ociclientconfig.OCIClientConfigWithResourcePrincipal

.. _ociclientconfigwithuserauthentication:
.. autoclass:: wayflowcore.models.ociclientconfig.OCIClientConfigWithUserAuthentication

.. important::
    ``OCIClientConfigWithUserAuthentication`` supports the same authentication type as ``OCIClientConfigWithApiKey`` but without a config file.
    Values in the config file are passed directly through ``OCIUserAuthenticationConfig`` below.

.. _ociuserauthenticationconfig:
.. autoclass:: wayflowcore.models.ociclientconfig.OCIUserAuthenticationConfig

.. important::
    The serialization of this class is currently not supported since the values are sensitive information.
