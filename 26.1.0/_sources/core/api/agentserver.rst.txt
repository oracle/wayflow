Agent Server
============

This page covers the components used to expose WayFlow agents through different protocols.


Server application
------------------

.. _openairesponsesserver:
.. autoclass:: wayflowcore.agentserver.server.OpenAIResponsesServer
    :members: __init__, get_app, run

.. _a2aserver:
.. autoclass:: wayflowcore.agentserver.server.A2AServer
    :members: __init__, get_app, run

.. _serverstorageconfig:
.. autoclass:: wayflowcore.agentserver.serverstorageconfig.ServerStorageConfig
    :members: to_schema

.. autofunction:: wayflowcore.agentserver.app.create_server_app


CLI Reference
-------------

.. _cliwayflowreference:
.. argparse::
   :module: wayflowcore.cli
   :func: build_parser
   :prog: wayflow
