Flows
=====

This page presents all APIs and classes related to flows and steps in WayFlow.


.. |agentspec-icon| image:: ../../_static/icons/agentspec-icon.svg
   :width: 100px

.. grid:: 1

    .. grid-item-card:: |agentspec-icon|
        :link: https://oracle.github.io/agent-spec/api/flows.html
        :link-alt: Agent Spec - Flows API Reference

        Visit the Agent Spec API Documentation to learn more about Flow Components.


.. tip::

    Click the button above ↑ to visit the `Agent Spec Documentation <https://oracle.github.io/agent-spec/index.html>`_


Flows & Steps
-------------

.. _flow:
.. autoclass:: wayflowcore.flow.Flow
    :exclude-members: execute

.. _assistantstep:
.. autoclass:: wayflowcore.steps.step.Step


.. _dataflowedge:
.. autoclass:: wayflowcore.dataconnection.DataFlowEdge

.. _controlflowedge:
.. autoclass:: wayflowcore.controlconnection.ControlFlowEdge

.. _presentstep:

Task steps
----------

.. _agentexecutionstep:
.. autoclass:: wayflowcore.steps.agentexecutionstep.AgentExecutionStep

.. _promptexecutionstep:
.. autoclass:: wayflowcore.steps.promptexecutionstep.PromptExecutionStep

.. _templaterenderingstep:
.. autoclass:: wayflowcore.steps.templaterenderingstep.TemplateRenderingStep

.. _toolexecutionstep:
.. autoclass:: wayflowcore.steps.toolexecutionstep.ToolExecutionStep

.. _extractvaluefromjsonstep:
.. autoclass:: wayflowcore.steps.textextractionstep.extractvaluefromjsonstep.ExtractValueFromJsonStep

.. _regexextractionstep:
.. autoclass:: wayflowcore.steps.textextractionstep.regexextractionstep.RegexExtractionStep

.. autoclass:: wayflowcore.steps.promptexecutionstep.StructuredGenerationMode

.. _datastoresteps:

Datastore tasks
~~~~~~~~~~~~~~~

.. admonition:: On the transactional consistency of datastore tasks

    When executing Datastore tasks in a flow, each step will execute one
    atomic operation on the datastore (that is, one transaction in
    database-backed datastores). Therefore, rolling-back a sequence of
    operations in case one or more steps fail during execution is not
    supported. Please keep this in mind when designing flows using these
    steps.

.. _datastoreliststep:
.. autoclass:: wayflowcore.steps.datastoresteps.DatastoreListStep

.. _datastorecreatestep:
.. autoclass:: wayflowcore.steps.datastoresteps.DatastoreCreateStep

.. _datastoreupdatestep:
.. autoclass:: wayflowcore.steps.datastoresteps.DatastoreUpdateStep

.. _datastoredeletestep:
.. autoclass:: wayflowcore.steps.datastoresteps.DatastoreDeleteStep

.. _datastorequerystep:
.. autoclass:: wayflowcore.steps.datastoresteps.DatastoreQueryStep

IO steps
--------

.. _inputmessagestep:
.. autoclass:: wayflowcore.steps.inputmessagestep.InputMessageStep

.. _outputmessagestep:
.. autoclass:: wayflowcore.steps.outputmessagestep.OutputMessageStep

.. _getchathistorystep:
.. autoclass:: wayflowcore.steps.getchathistorystep.GetChatHistoryStep

.. _variablestep:
.. autoclass:: wayflowcore.steps.variablesteps.variablestep.VariableStep

.. _variablereadstep:
.. autoclass:: wayflowcore.steps.variablesteps.variablereadstep.VariableReadStep

.. _variablewritestep:
.. autoclass:: wayflowcore.steps.variablesteps.variablewritestep.VariableWriteStep

.. _constantvaluesstep:
.. autoclass:: wayflowcore.steps.ConstantValuesStep

.. autoclass::  wayflowcore.steps.getchathistorystep.MessageSlice

Flow steps
----------

.. _retrystep:
.. autoclass:: wayflowcore.steps.retrystep.RetryStep

.. _catchexceptionstep:
.. autoclass:: wayflowcore.steps.catchexceptionstep.CatchExceptionStep

.. _flowexecutionstep:
.. autoclass:: wayflowcore.steps.flowexecutionstep.FlowExecutionStep

.. _parallelflowexecutionstep:
.. autoclass:: wayflowcore.steps.parallelflowexecutionstep.ParallelFlowExecutionStep

.. _mapstep:
.. autoclass:: wayflowcore.steps.mapstep.MapStep

.. _parallelmapstep:
.. autoclass:: wayflowcore.steps.mapstep.ParallelMapStep

.. _branchingstep:
.. autoclass:: wayflowcore.steps.branchingstep.BranchingStep

.. _choiceselectionstep:
.. autoclass:: wayflowcore.steps.choiceselectionstep.ChoiceSelectionStep

.. _completestep:
.. autoclass:: wayflowcore.steps.completestep.CompleteStep

.. _startstep:
.. autoclass:: wayflowcore.steps.startstep.StartStep

.. _apicallstep:
.. autoclass:: wayflowcore.steps.apicallstep.ApiCallStep

.. autoclass:: wayflowcore.stepdescription.StepDescription

Classes for the IO system properties
------------------------------------

.. _property:
.. autoclass:: wayflowcore.property.Property

.. _booleanproperty:
.. autoclass:: wayflowcore.property.BooleanProperty

.. _floatproperty:
.. autoclass:: wayflowcore.property.FloatProperty

.. _messageproperty:
.. autoclass:: wayflowcore.property.MessageProperty

.. _integerproperty:
.. autoclass:: wayflowcore.property.IntegerProperty

.. _stringproperty:
.. autoclass:: wayflowcore.property.StringProperty

.. _anyproperty:
.. autoclass:: wayflowcore.property.AnyProperty

.. _listproperty:
.. autoclass:: wayflowcore.property.ListProperty

.. _dictproperty:
.. autoclass:: wayflowcore.property.DictProperty

.. _objectproperty:
.. autoclass:: wayflowcore.property.ObjectProperty

.. _unionproperty:
.. autoclass:: wayflowcore.property.UnionProperty

.. _nullproperty:
.. autoclass:: wayflowcore.property.NullProperty

.. autoclass:: wayflowcore.property._empty_default

.. autoclass:: wayflowcore.property.JsonSchemaParam

Other classes and helpers used in fixed flows
---------------------------------------------

.. _assistantstepresult:
.. autoclass:: wayflowcore.steps.step.StepResult

.. autoclass:: wayflowcore.steps.step.StepExecutionStatus

.. autoclass:: wayflowcore.flowhelpers.run_step_and_return_outputs

.. autoclass:: wayflowcore.flowhelpers.run_flow_and_return_outputs

.. autoclass:: wayflowcore.flowhelpers.create_single_step_flow



Flow Builder
------------

The Flow Builder provides a concise, chainable API to assemble WayFlow Flows programmatically.
It helps wire control and data edges, use conditional branching, set entry/finish points,
and serialize flows to JSON/YAML.

See code examples in the :ref:`Reference Sheet <flowbuilder_ref_sheet>`.

.. _flowbuilder:
.. autoclass:: wayflowcore.flowbuilder.FlowBuilder
