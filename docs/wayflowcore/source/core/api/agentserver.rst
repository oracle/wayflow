Agent Server
============

This page covers the components used to expose WayFlow agents through an OpenAI Responses-compatible
server.


Server application
------------------

.. _openairesponsesserver:
.. autoclass:: wayflowcore.agentserver.server.OpenAIResponsesServer
    :members: __init__, get_app, run

.. _serverstorageconfig:
.. autoclass:: wayflowcore.agentserver.serverstorageconfig.ServerStorageConfig
    :members: to_schema

.. autofunction:: wayflowcore.agentserver.app.create_server_app


Service interfaces
------------------

.. autoclass:: wayflowcore.agentserver.services.service.OpenAIResponsesService
    :members:

.. autoclass:: wayflowcore.agentserver.services.wayflowservice.WayFlowOpenAIResponsesService
    :members:


CLI Reference
-------------

.. _cliwayflowreference:
.. argparse::
   :module: wayflowcore.cli
   :func: build_parser
   :prog: wayflow
