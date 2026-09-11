.. _top-howtoconversationevaluation:

=======================================
How to Evaluate Assistant Conversations
=======================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_conversation_evaluation.py
        :link-alt: Conversation Evaluation how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Agents <../tutorials/basic_agent>`

Evaluating the robustness and performance of assistants requires careful conversation assessment.
The :ref:`ConversationEvaluator <conversationevaluator>` API in WayFlow enables evaluation of conversations
using LLM-powered criteria—helping you find weaknesses and improve your assistants.

This guide demonstrates the process of constructing, scoring, and evaluating a conversation.

.. image:: ../_static/howto/conversation_evaluator.png
    :align: center
    :scale: 40%

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Basic implementation
====================

Assume you want to evaluate the following assistant conversation, which purposefully exhibits poor assistant performance.

.. literalinclude:: ../code_examples/howto_conversation_evaluation.py
    :language: python
    :start-after: .. start-##_Define_the_conversation
    :end-before: .. end-##_Define_the_conversation

The conversation alternates user and assistant messages, simulating a scenario with misunderstandings and wrong information.

In a production context, you system would be collecting conversations, and you would evaluate
then offline. You can use serialization to serialize conversations easily in your production
environment, and reload them later for offline evaluation:

.. literalinclude:: ../code_examples/howto_conversation_evaluation.py
    :language: python
    :start-after: .. start-##_Serialize_and_Deserialize_the_conversation
    :end-before: .. end-##_Serialize_and_Deserialize_the_conversation


Defining the LLM to use as a judge
==================================

We will need a LLM to judge the conversations. The first step is to instantiate an LLM supported by WayFlow.

.. literalinclude:: ../code_examples/howto_conversation_evaluation.py
    :language: python
    :start-after: .. start-##_Define_the_llm
    :end-before: .. end-##_Define_the_llm

Defining scoring criteria
=========================

The :ref:`ConversationScorer <conversationscorer>` is the component responsible for scoring the conversation according to specific criteria.
Currently, two scorers are supported in ``wayflowcore``:

- The :ref:`UsefulnessScorer <usefullnessscorer>` score estimates the overall usefulness of the assistant from the conversation. It uses criteria such as:
   - The task completion efficiency: does it seem like the assistant is able to complete the tasks?
   - The level of proactiveness: is the assistant able to anticipate the user needs?
   - The ambiguity detection capability: does the assistant often requires clarification or is more autonomous?
- The :ref:`UserHappinessScorer <userhappinessscorer>` score estimates the level of happiness / frustration of the user from the conversation. It uses criteria such as:
   - The query repetition frequency: does the user need to repeat their questions?
   - The misinterpretation of user intent: is there misinterpretation from the assistant?
   - The conversation flow disruption: does the conversation flow seamlessly or is severely disrupted?

.. literalinclude:: ../code_examples/howto_conversation_evaluation.py
    :language: python
    :start-after: .. start-##_Define_the_scorers
    :end-before: .. end-##_Define_the_scorers

You can, or course, implement your own versions for your specific use-case, by respecting the
:ref:`ConversationScorer <conversationscorer>` APIs.

Setting up the evaluator
========================

The :ref:`ConversationEvaluator <conversationevaluator>` combines scorers and applies them to the provided conversation(s):

.. literalinclude:: ../code_examples/howto_conversation_evaluation.py
    :language: python
    :start-after: .. start-##_Define_the_conversation_evaluator
    :end-before: .. end-##_Define_the_conversation_evaluator

Running the evaluation
======================

Trigger the evaluation and inspect the scoring DataFrame as output:

.. literalinclude:: ../code_examples/howto_conversation_evaluation.py
    :language: python
    :start-after: .. start-##_Execute_the_evaluation
    :end-before: .. end-##_Execute_the_evaluation

The result is a table where each scorer provides a score for each conversation.


Next steps
==========

After learning to use ``ConversationEvaluator`` to assess conversations, proceed to :doc:`Perform Assistant Evaluation <howto_evaluation>` for more advanced evaluation techniques.


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoconversationevaluation>` to download the full code for this guide, or view it below.

.. literalinclude:: ../end_to_end_code_examples/howto_conversation_evaluation.py
    :language: python
    :linenos:
