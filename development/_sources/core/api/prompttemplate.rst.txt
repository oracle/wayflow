PromptTemplate
==============

This page presents all APIs and classes related to prompt Templates.

.. _prompttemplate:
.. autoclass:: wayflowcore.templates.template.PromptTemplate

OutputParser
------------

.. _outputparser:
.. autoclass:: wayflowcore.outputparser.OutputParser

.. _regexoutputparser:
.. autoclass:: wayflowcore.outputparser.RegexOutputParser

.. _regexpattern:
.. autoclass:: wayflowcore.outputparser.RegexPattern

.. _jsonoutputparser:
.. autoclass:: wayflowcore.outputparser.JsonOutputParser

.. _tooloutputparser:
.. autoclass:: wayflowcore.outputparser.ToolOutputParser


Message transforms
------------------

.. _messagetransform:
.. autoclass:: wayflowcore.transforms.MessageTransform

.. autoclass:: wayflowcore.transforms.CoalesceSystemMessagesTransform

.. autoclass:: wayflowcore.transforms.RemoveEmptyNonUserMessageTransform

.. autoclass:: wayflowcore.transforms.AppendTrailingSystemMessageToUserMessageTransform

.. autoclass:: wayflowcore.transforms.SplitPromptOnMarkerMessageTransform


Helpers
-------

.. _prompttemplatehelpers:
.. autofunction:: wayflowcore.templates.structuredgeneration.adapt_prompt_template_for_json_structured_generation
