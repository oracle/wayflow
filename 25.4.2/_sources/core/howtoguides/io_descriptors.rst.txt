.. _top-howiodescriptors:

========================================================
How to Change Input and Output Descriptors of Components
========================================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_io_descriptors.py
        :link-alt: IO descriptors how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with :doc:`Flows <../tutorials/basic_flow>`.

WayFlow components such as :ref:`Agents <agent>`, :ref:`Flows <flow>`, and :ref:`Steps <assistantstep>` accept inputs and produce outputs.
These inputs and outputs allow you to pass values to be used, and return some new values.
You can inspect the input/output descriptors on classes that inherit from ``ComponentWithInputsOutputs`` by accessing the ``input_descriptors`` and ``output_descriptors`` attributes, respectively.
See the :ref:`Property <property>` API documentation to learn more about the IO typing system operations.

Sometimes, it is helpful to change their description, either because the type is not specific enough, or if you want
to specify a default value.

This guide will show you how to **override the default input and output descriptions of Agents, Flows, or Steps**.

Basic implementation
====================

When creating a step, input and output descriptors are automatically detected based on the step's configuration.

.. literalinclude:: ../code_examples/howto_io_descriptors.py
    :language: python
    :start-after: .. start-##_Auto_IO_detection
    :end-before: .. end-##_Auto_IO_detection

In this case, the input descriptor ``service`` does not have a default value, and the description is not very informative.
To improve the user experience, you can provide a more informative description and set a default value by overriding the input descriptors:

.. literalinclude:: ../code_examples/howto_io_descriptors.py
    :language: python
    :start-after: .. start-##_Specify_input_descriptor
    :end-before: .. end-##_Specify_input_descriptor

.. note::

    Since a step requires specific variables to work well, the overriding descriptor must have the same ``name`` as the original descriptor.

The same process can be applied to output descriptors.

Refining a type
===============

In certain situations, the automatic detection of input and output types may not determine the appropriate type for a variable.
For example, consider the following step where an ``AnyProperty`` input is detected:

.. literalinclude:: ../code_examples/howto_io_descriptors.py
    :language: python
    :start-after: .. start-##_Default_any_descriptor
    :end-before: .. end-##_Default_any_descriptor

Here, the service input is expected to be a list.
To improve clarity, you can override the ``AnyProperty`` descriptor to specify the expected type:

.. literalinclude:: ../code_examples/howto_io_descriptors.py
    :language: python
    :start-after: .. start-##_List_descriptor
    :end-before: .. end-##_List_descriptor

.. note::

    Currently, type validation is not implemented. When overriding a descriptor's type, make sure to specify the correct type to prevent runtime crashes during step execution.


Changing the name of a descriptor
=================================

Sometimes, the default name of an input or output descriptor can be complex or unclear.

In this case, you can not just modify the names of the ``input_descriptors`` or ``output_descriptors``, as these names are integral to mapping between new and default descriptors.

You can still rename the input or output descriptor of a ``Step`` by using ``input_mapping`` or ``output_mapping``.
These mappings associate the default descriptor names (keys) with the desired new names (values).
The associated ``input_descriptors`` and ``output_descriptors`` need to reflect these new names accordingly.

.. literalinclude:: ../code_examples/howto_io_descriptors.py
    :language: python
    :start-after: .. start-##_Rename_a_descriptor
    :end-before: .. end-##_Rename_a_descriptor

Without providing the ``input_mapping`` value, the step will not recognize the input descriptor name and will raise an error.

.. code-block:: python

    step = InputMessageStep(
        message_template="Hi {{unclear_var_name}}. How are you doing?",
        input_descriptors=[StringProperty(name="username", description="name of the current user")],
    )
    # ValueError: Unknown input descriptor specified: StringProperty(name='username', description='name of the current user'). Make sure there is no misspelling.
    # Expected input descriptors are: [StringProperty(name='unclear_var_name', description='"unclear_var_name" input variable for the template')]


Agent Spec Exporting/Loading
============================

You can export the step configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_io_descriptors.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_io_descriptors.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_io_descriptors.yaml
            :language: yaml


You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_io_descriptors.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginInputMessageNode``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


Next steps
==========

Having learned how to override the default input and output descriptions of a component, you may now proceed to:

- :doc:`How to Do Structured LLM Generation in Flows <promptexecutionstep>`
- :doc:`How to Use Agents in Flows <howto_agents_in_flows>`


Full code
=========

Click on the card at the :ref:`top of this page <top-howiodescriptors>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_io_descriptors.py
    :language: python
    :linenos:
