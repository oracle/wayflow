:orphan:

.. ^ REMOVE THIS AND ADD THE HOW-TO GUIDE TO index.rst file

================================
How to {specific task/goal here}
================================


.. Title Guidelines:
.. - Capitalize each word in the main title, except for articles or prepositions
.. - Start with "How to" followed by an action verb
.. - Be specific and action-oriented
.. - Use present tense
.. - Examples of good titles:
..     - How to create stateful tools
..     - How to use a datastore to retrieve data


.. admonition:: Prerequisites

    This guide assumes familiarity with the following concepts:

    - {Prerequisite 1 with link to documentation}
    - {Prerequisite 2 with link to documentation}
    - {Additional prerequisites as needed}

.. Prerequisites should:
.. - Link to relevant documentation
.. - Be specific and minimal
.. - Only include truly necessary knowledge
.. See at the end of the document for common admonition to use


.. warning::
    {Include any version requirements, dependencies, or critical setup information}

{Brief introduction to the problem and solution}

This guide will show you how to:

- {Specific outcome 1}
- {Specific outcome 2}
- {Specific outcome 3}

.. Describe clearly the problem or task that the guide shows the user how to solve.
.. The overview should:
.. - Be 2-3 paragraphs maximum
.. - Clearly state what problem this guide solves
.. - (when required) Explain why this solution is useful
.. - (when required) Mention any important limitations or considerations

.. note::
    {Important contextual information or key considerations}

.. .. To uncomment for actual use
.. .. image:: ../_static/path/to/image.svg
..     :align: center
..     :scale: 70%
..     :alt: {Descriptive alt text for accessibility}

.. Try to include visual elements whenever possible (e.g. diagrams made with diagram.net)
.. Image Guidelines:
.. - Use SVG format for diagrams (can directly export from draw.io (aka diagrams.net))
.. - Always include alt text
.. - Use scale between 40-100%
.. - Center align most images

.. For main content of the how-to guide:
.. - Maximum 2 levels of headings (sections and sub-sections)
.. - Write all subheadings in sentence case
.. - The content can be sequential (e.g. Setup -> Step 1 -> Step 2),
..   or can be an enumeration of different ways to achieve a similar outcome
.. - Keep the section name simple (with as few words as possible)
.. - Each example should be focused and achievable
.. - Encapsulate all function / class / variables with double backticks, e.g. ``Agent``
.. - Use :doc:`Name <path/to/doc>` for linking to different parts of the documentation
.. - Use :ref:`ClassName <classname>` for linking to the API reference
.. - Alternative to :ref: is :meth:`.LlmModelFactory.from_config`
..   or :meth:`~wayflowcore.models.llmmodelfactory.LlmModelFactory.from_config`
.. - Use `text <url>`_ for external links
.. - check https://docutils.sourceforge.io/docs/user/rst/quickref.html for more information


.. Note: Choose section name that make sense for the how-to guide.
.. If using verbs, use imperative mood (e.g. Define flow, Add Y, ...)

Basic implementation
=====================

.. - Start with the simplest working example
.. - Break into clear, logical steps
.. - Use concrete, runnable code
.. - Explain only what's necessary, refer to conceptual guides otherwise
.. - Link to related documentation frequently

.. Code blocks can be used, but prefer the use of literalinclude directives

.. code-block:: python

    {Basic implementation code}

.. Imports should be done little by little and not everything in the beginning
.. For every new import, add a clickable link to the API reference as follows:

API Reference: :ref:`LlmModelFactory <llmmodelfactory>` | :ref:`Agent <agent>`

.. .. To uncomment for actual use
.. .. literalinclude:: ../code_examples/example.py
..     :language: python
..     :start-after: .. start-code_snippet:
..     :end-before: .. end-code_snippet

.. the same should be done for literal include

API Reference: :ref:`LlmModelFactory <llmmodelfactory>` | :ref:`Agent <agent>`

.. note::
    {Important details about the implementation}

.. - Explain key parts of the code
.. - Use Python code blocks sparingly, prefer the use of literalinclude
.. - Link to the relevant API documentation


.. If multiple options exist, use tabs

.. tabs::

    .. tab:: Option 1

        .. code-block:: python

            # code for option 1

    .. tab:: Option 2

        .. code-block:: python

            # code for option 2

.. with additional references after the tabs

API Reference: :ref:`LlmModelFactory <llmmodelfactory>` | :ref:`Agent <agent>`


.. danger::
    .. Use directives inside the how-to guide to give addition information when needed

    Never commit sensitive information like API keys. Use environment variables:

    .. code-block:: python

        import os
        from dotenv import load_dotenv

        load_dotenv()
        API_KEY = os.getenv("API_KEY")


(OPTIONAL) Alternative Approaches
==================================

.. Only use when necessary, remove the (Optional) when using
.. - Show different ways to accomplish the same task
.. - Explain when to use each approach
.. - Keep focused on the specific task

Method 1: {Approach name}
-------------------------

.. .. To uncomment for actual use
.. .. literalinclude:: ../code_examples/example.py
..     :language: python
..     :start-after: .. start-code_snippet:
..     :end-before: .. end-code_snippet

.. with additional references

API Reference: :ref:`LlmModelFactory <llmmodelfactory>` | :ref:`Agent <agent>`

.. important::
    {Critical information about this approach}

Method 2: {Alternative approach}
--------------------------------

.. .. To uncomment for actual use
.. .. literalinclude:: ../code_examples/example.py
..     :language: python
..     :start-after: .. start-code_snippet:
..     :end-before: .. end-code_snippet

.. with additional references

API Reference: :ref:`LlmModelFactory <llmmodelfactory>` | :ref:`Agent <agent>`

.. tip::
    {When to use one approach over another}


(Optional) Advanced Usage
==========================

.. - Only include if necessary, remove the (Optional) when using
.. - Focus on practical applications
.. - Keep examples concrete

.. .. To uncomment for actual use
.. .. literalinclude:: ../code_examples/example.py
..     :language: python
..     :start-after: .. start-code_snippet:
..     :end-before: .. end-code_snippet

.. warning::
    {Important caveats or limitations}


(Optional) Common Patterns and Best Practices
==============================================

.. (Only include when relevant), remove the (Optional) when using
.. This section should:
.. - Highlight recommended approaches
.. - Warn about anti-patterns
.. - Provide real-world usage examples
.. - Link to related patterns in documentation

Pattern 1: {Pattern Name}
-------------------------

.. .. To uncomment for actual use
.. .. literalinclude:: ../code_examples/example.py
..     :language: python
..     :start-after: .. start-code_snippet:
..     :end-before: .. end-code_snippet

.. tip::
    {Why and when to use this pattern}


(Optional) Troubleshooting
==========================

.. (Only include when relevant), remove the (Optional) when using
.. Troubleshooting section should:
.. - Address common issues
.. - Provide clear solutions
.. - Include error messages
.. - Link to relevant documentation


{Name of Common Problem no.1}
-----------------------------

**Symptom**

.. Add 1-2 sentences to explain when such a problem may occur

.. code-block:: text

    {Error message or problem description}

.. Explain briefly if necessary why the problem happens
.. (create a ticket if the error message is not clear enough)

**Solution**

.. Explain how to solve the encountered problem and potentially give some
.. hints on how to better do things next time not to encounter it anymore

.. warning::
    {Important cautions related to the solution}


Recap
=====

.. Mandatory section. The recap should:
.. - Summarize what was learned in 1-2 sentences
.. - Add a full code block for easy user access to executable code

In this how-to guide, we covered how to [...]

You can find below the full code to run the example shown in this how-to guide.

.. .. To uncomment for actual use
.. .. collapse:: full code

..    .. literalinclude:: ../code_examples/how_to_guide.py
..       :language: python
..       :linenos:
..       :start-after: .. full-code:
..       :end-before: .. end-full-code

.. Note: In the future the full code collapsible will be replaced by buttons
.. at the top of the guide. In the meantime, simply add the full code that can
.. be copy-pasted by the user and executed.

Next Steps
==========

.. Next steps should:
.. - Suggest related topics
.. - Link to advanced guides
.. - Provide resources for further learning (optional)

Now that you've learned {main topic}, you might want to explore:

.. .. To uncomment for actual use
.. - :doc:`Related Guide 1 <../path/to/guide>`
.. - :doc:`Related Guide 2 <../path/to/guide>`
.. - :doc:`Advanced Topic <../path/to/advanced>`

(Optional) Additional Resources
-------------------------------

- `External Resource 1 <url>`_
- `External Resource 2 <url>`_
- `Community Forum <url>`_


.. Quick Reference for RST Directives:
.. - .. warning:: - Important cautionary notes
.. - .. danger:: - Critical warnings
.. - .. tip:: - Helpful suggestions
.. - .. note:: - Additional information
.. - .. important:: - Key points
.. - .. seealso:: - other elements the user might be interested in
.. - .. versionadded:: - New feature annotations
.. - .. deprecated:: - Deprecation notices
.. - .. admonition:: - Custom callouts
..    (e.g. Prerequisites, you should not have to write new ones)

.. General Writing Style Guidelines:
.. - Use active voice: "Configure the assistant" not "The assistant should be configured"
.. - Present tense: "The function returns" not "The function will return"
.. - Be concise: Avoid unnecessary words
.. - Use consistent terminology
.. - Link liberally to other documentation
.. - Keep paragraphs short (3-4 sentences maximum)

.. Accessibility Guidelines:
.. - Include alt text for all images
.. - Maintain good color contrast in diagrams, use thin lines sparingly
.. - Provide text alternatives for complex diagrams

.. Cross-linking Strategy:
.. - Link to prerequisite concepts in introduction
.. - Link to API reference for mentioned classes/functions
.. - Link to related how-to guides in Next Steps
.. - Link to tutorials for broader learning
.. - Link to explanation docs for deep dives into concepts
.. - Use :doc:`Name <path/to/doc>` for linking to different parts of the documentation
.. - Use :ref:`ClassName <classname>` for linking to API reference
.. - Use `text <url>`_ for external links
