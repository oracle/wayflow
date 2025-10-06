Execution Interrupts
====================

We often need to interrupt the normal execution of an assistant to perform specific operations including but not limited to:

- Checking the token count
- Verifying the runtime
- Doing step by step debugging

For this reason, we provide execution interrupts, which let developers interact with the assistant's execution at specific moments.

This page presents all APIs and classes related to execution interrupts in WayFlow.

Execution Interrupt interface
-----------------------------

.. _executioninterrupt:
.. autoclass:: wayflowcore.executors.interrupts.executioninterrupt.ExecutionInterrupt

.. _interruptedexecutionstatus:
.. autoclass:: wayflowcore.executors.interrupts.executioninterrupt.InterruptedExecutionStatus


Basic Execution Interrupt classes
---------------------------------

Timeout Execution Interrupt
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _softtimeoutexecutioninterrupt:
.. autoclass:: wayflowcore.executors.interrupts.timeoutexecutioninterrupt.SoftTimeoutExecutionInterrupt

Token Limit Execution Interrupt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _softtokenlimitexecutioninterrupt:
.. autoclass:: wayflowcore.executors.interrupts.tokenlimitexecutioninterrupt.SoftTokenLimitExecutionInterrupt
