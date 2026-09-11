.. _evaluation:

Evaluation APIs
===============


Assistant Evaluation
--------------------

.. _evaluationtask:
.. autoclass:: wayflowcore.evaluation.assistantevaluator.EvaluationTask

.. _evaluationenvironment:
.. autoclass:: wayflowcore.evaluation.assistantevaluator.EvaluationEnvironment

.. _assistantevaluator:
.. autoclass:: wayflowcore.evaluation.assistantevaluator.AssistantEvaluator

.. _taskscorer:
.. autoclass:: wayflowcore.evaluation.taskscorer.TaskScorer

.. _runproxyconversation:
.. autoclass:: wayflowcore.evaluation.assistantevaluator.run_proxy_agent_conversation

.. _assistantevaluationresult:
.. autoclass:: wayflowcore.evaluation.assistantevaluator.AssistantEvaluationResult

.. _humanproxyassistant:
.. autoclass:: wayflowcore.evaluation.assistantevaluator.HumanProxyAssistant

Conversation Evaluation
-----------------------

.. _conversationevaluator:
.. autoclass:: wayflowcore.evaluation.conversationevaluator.ConversationEvaluator

.. _conversationscorer:
.. autoclass:: wayflowcore.evaluation.conversationscorer.ConversationScorer

.. _usefullnessscorer:
.. autoclass:: wayflowcore.evaluation.usefulnessscorer.UsefulnessScorer

.. _userhappinessscorer:
.. autoclass:: wayflowcore.evaluation.userhappinessscorer.UserHappinessScorer

.. _criteriascorer:
.. autoclass:: wayflowcore.evaluation.criteriascorer.CriteriaScorer

.. _defaultscoremap:
.. autoclass:: wayflowcore.evaluation.criteriascorer.DEFAULT_SCORE_MAP

Evaluation Metrics
------------------

.. _calculate_set_metrics:
.. autofunction:: wayflowcore.evaluation.evaluation_metrics.calculate_set_metrics

.. _calculate_accuracy:
.. autofunction:: wayflowcore.evaluation.evaluation_metrics.calculate_accuracy
