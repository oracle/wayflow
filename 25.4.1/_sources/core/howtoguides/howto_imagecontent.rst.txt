.. _top-howtoimagecontent:

=====================================
How to Send Images to LLMs and Agents
=====================================


.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_imagecontent.py
        :link-alt: Tutorial on using Images with WayFlow models

        Python script/notebook for this guide.


.. admonition:: Prerequisites

    - Familiarity with :doc:`basic agent and prompt workflows <../tutorials/basic_agent>`.

Overview
========

Some Large Language Models (LLMs) can handle images in addition to text.
WayFlow supports passing images alongside text in both direct prompt requests and full agent conversations
using the `ImageContent` API.

This guide will show you:

- How to create `ImageContent` in code.
- How to run a prompt with image input directly with the model.
- How to send image+text messages in an Agent conversation.
- How to inspect and use model/agent outputs with image reasoning.

What is ``ImageContent``?
-------------------------

`ImageContent` is a type of message content that stores image bytes and format metadata.
You can combine an image with additional `TextContent` in a single message.


Basic implementation
====================

First import what is needed for this guide:

.. literalinclude:: ../code_examples/howto_imagecontent.py
   :language: python
   :linenos:
   :start-after: .. start-##_Imports
   :end-before: .. end-##_Imports

To follow this guide, you will need access to a **Multimodal** large language model (LLM).
WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst


Step 1: Creating a prompt with ImageContent
===========================================

Before sending requests to your vision-capable LLMs or agents, you need to construct a prompt containing both the image and text content. The example below demonstrates:

- Downloading an image (here, the Oracle logo) via HTTP request
- Creating an `ImageContent` object from the image bytes
- Adding a `TextContent` question
- Packing both into a `Message`, then into a `Prompt`

.. literalinclude:: ../code_examples/howto_imagecontent.py
   :language: python
   :start-after: .. start-##_Create_prompt
   :end-before: .. end-##_Create_prompt

Step 2: Sending image input to a vision-capable model
=====================================================

You can send images directly to your LLM by constructing a prompt with both `ImageContent` and `TextContent`.
The example below downloads the Oracle logo PNG and queries the LLM for recognition.

.. literalinclude:: ../code_examples/howto_imagecontent.py
    :language: python
    :start-after: .. start-##_Generate_completion_with_an_image_as_input
    :end-before: .. end-##_Generate_completion_with_an_image_as_input


**Expected output:** The model should identify the company (e.g. "Oracle Corporation" or equivalent).
If your model does not support images, you will get an error.

Step 3: Using images in Agent conversations
===========================================

You can pass images in an Agent-driven chat workflow.
This allows assistants to process visual information alongside user dialog.

.. literalinclude:: ../code_examples/howto_imagecontent.py
    :language: python
    :start-after: .. start-##_Pass_an_image_to_an_agent_as_input
    :end-before: .. end-##_Pass_an_image_to_an_agent_as_input

**Expected output:** The agent response should mention "Oracle Corporation".

API Reference and Practical Information
=======================================

- :class:`wayflowcore.messagelist.ImageContent`
- :class:`wayflowcore.messagelist.TextContent`
- :class:`wayflowcore.agent.Agent`

Supported Image Formats
-----------------------

Most vision LLMs support PNG, JPG, JPEG, GIF, or WEBP.
Always specify the correct format for ImageContent.



Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_imagecontent.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_imagecontent.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_imagecontent.yaml
            :language: yaml


You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_imagecontent.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config


Next steps
==========

Having learned how to send images to LLMs and Agents, you may now proceed to:

- :doc:`../tutorials/basic_agent`


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoimagecontent>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_imagecontent.py
    :language: python
    :linenos:
