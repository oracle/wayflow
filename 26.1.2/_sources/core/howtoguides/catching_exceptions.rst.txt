.. _top-catchingexceptions:

================================
How to Catch Exceptions in Flows
================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_catchingexceptions.py
        :link-alt: Catching exceptions how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with :doc:`Flows <../tutorials/basic_flow>`.

Exception handling is a crucial aspect of building robust and reliable software applications.
It allows a program to gracefully handle unexpected issues without crashing.
In WayFlow, exception handling can be achieved using the :ref:`CatchExceptionStep <CatchExceptionStep>` API.

This guide shows you how to use this step to catch and process exceptions in a sub-flow:

.. image:: ../_static/howto/catchexceptionstep.svg
    :align: center
    :scale: 100%
    :alt: Simple Flow using a catch exception step

.. seealso::
    The :ref:`RetryStep <RetryStep>` can be used to retry a sub-flow on specific criteria. See API documentation for more information.


Basic implementation
====================

To catch exceptions in a sub-flow, WayFlow offers the :ref:`CatchExceptionStep <CatchExceptionStep>` class.
This step is configured to run a flow and catches any exceptions that occur during its execution.

The following example demonstrates the use of the ``CatchExceptionStep``.
Assuming you want to catch only ``ValueError`` exceptions. Specify them in the ``except_on`` parameter and define the branch name to which the flow will continue upon catching such exceptions.

.. literalinclude:: ../code_examples/howto_catchingexceptions.py
    :language: python
    :start-after: .. start-##_Define_Catch_Exception_Step
    :end-before: .. end-##_Define_Catch_Exception_Step

Once this is done, create the main flow and map each branch of the catch exception step to the next step.
In this example, the catch exception step has one branch for when a ``ValueError`` is caught (named ``VALUE_ERROR_BRANCH``),
and one default branch when no exception is raised (``Step.BRANCH_NEXT``, which is the only branch of the sub-flow).

You can check the branch name of a step using the ``step.get_branches()`` function.

.. literalinclude:: ../code_examples/howto_catchingexceptions.py
    :language: python
    :start-after: .. start-##_Build_Exception_Handling_Flow
    :end-before: .. end-##_Build_Exception_Handling_Flow

Now you have a complete flow that takes different transitions depending on whether an exception was raised or not:

.. literalinclude:: ../code_examples/howto_catchingexceptions.py
    :language: python
    :start-after: .. start-##_Execute_Flow_With_Exceptions
    :end-before: .. end-##_Execute_Flow_With_Exceptions

.. tip::
    When developing flows, similarly to try-catch best practices in Python, we recommended to wrap only the steps that are likely to raise errors.
    This approach helps to keep the flow organized and easier to maintain.
    By wrapping only the error-prone steps, you can catch and handle specific exceptions more effectively, reducing the likelihood of masking other unexpected issues.


Common patterns
===============

Catching all exceptions
-----------------------

To catch all exceptions and redirect to a shared branch, use the ``catch_all_exceptions`` parameter of the ``CatchExceptionStep`` class, and specify the transition of the branch ``CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH`` as shown below:

.. literalinclude:: ../code_examples/howto_catchingexceptions.py
    :language: python
    :start-after: .. start-##_Catch_All_Exceptions
    :end-before: .. end-##_Catch_All_Exceptions


Catching OCI model errors
-------------------------

OCI models may raise a ``ServiceError`` when used (for example, when an inappropriate content is detected).
You can directly wrap the :ref:`PromptExecutionStep <PromptExecutionStep>` using the ``CatchExceptionStep`` and the helper method ``Flow.from_steps``, as follows:

.. literalinclude:: ../code_examples/howto_catchingexceptions.py
    :language: python
    :start-after: .. start-##_Handle_OCI_Service_Error
    :end-before: .. end-##_Handle_OCI_Service_Error


Agent Spec Exporting/Loading
============================

You can export the flow configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_catchingexceptions.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_catchingexceptions.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_catchingexceptions.yaml
            :language: yaml


You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_catchingexceptions.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginCatchExceptionNode``
    - ``PluginOutputMessageNode``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


Next steps
==========

In this guide, you learned how to do exception handling in WayFlow using the ``CatchExceptionStep`` class to:

- catch specific exceptions with the ``except_on`` parameter;
- catch all exceptions with the ``catch_all_exceptions`` parameter.

By following these steps and best practices, you can build more robust and reliable software applications using Flows.

Having learned how to handle exceptions in flows, you may now proceed to :doc:`How to Create Conditional Transitions in Flows <conditional_flows>`.


Full code
=========

Click on the card at the :ref:`top of this page <top-catchingexceptions>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_catchingexceptions.py
    :language: python
    :linenos:
