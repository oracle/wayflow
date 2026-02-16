:orphan:

=========================
Documentation Style Guide
=========================

This style guide is short but specific to the project documentation, and aligns with the writing guidelines of the Oracle Documentation Style Guide
and `Chicago Manual of Style <https://www.chicagomanualofstyle.org/home.html>`_.
These recommendations apply universally across all documentation types—be it reference materials, guides, or release notes.
We do not enforce these recommendations, but following them will improve content readability and ensure consistency across all pages.

I. Naming conventions
---------------------

-  The project name is **WayFlow**. It is a proper name; no article is required upfront. Example: *WayFlow is an open source project. You can find the source code in the WayFlow project repository on GitHub*.
-  Use **Agent** and **Flow** with initial letters capitalized when referencing to the concept or a class name. As an alternative, you can write **WayFlow Agent**, **WayFlow Flow**.
-  There is no class/API such as **Assistant**. You can create intelligent assistants with WayFlow. Example: *Create a next-generation powerful assistant with WayFlow Agents*.

II. Verb tense
--------------

In technical documentation, the verb tense depends on the context, but the general guidelines are:

-  Present tense – Most common, recommended, used for describing facts, or how a system behaves. Example: *The user inputs their question to the assistant*.
-  Future tense – Used typically when describing planned features or expected behavior. Example: *The next release will include support for Windows*.
-  Past tense – Rarely used, except when documenting historical changes or past events. Example: *Version 1.1 introduced support for Windows platform.*

For WayFlow documentation, the present tense is best for describing how flows, steps, and agents behave.

III. Style and tone
-------------------

Be conversational and yet keep some level of formality.

-  Avoid marketing pitch language in the technical documentation.
-  Use the second-person singular, *you*. Try to use *we* only when referring to developers. Example: *We are still working on implementing*; *We recommend*.
-  Avoid using passive voice extensively, and rewrite the sentence to active voice. Instead of writing *It is recommended*, use *We recommend*.
-  Avoid phrasing in terms of *Let’s do something*.
-  Avoid using phrases such as *It’s simple*, *It’s easy*.
-  Avoid using contractions such as *it’s*, *you’ll*, *you’re*.
-  Avoid the use of gender-specific, third-person pronouns such as *he*, *she*, *his*, and *hers*. If possible, rewrite to use a neutral plural subject, such as *developers* or *users*.
-  Try to avoid using *get*. Instead of writing *To check which classes got included*, use *To check which classes were included*.

Be clear:

-  The introduction to a how-to guide can be as simple as *In this guide you will learn how to…*
-  Consider including an introduction and a summary for the whole document.
-  Consider a closing sentence summing the section up.
-  When the page is long (requires a lot of scrolling down), consider including quick links to subsections right below the introduction so readers can skip to the section relevant to them.
-  Double check the logical flow of the chapter outline.
-  Avoid redundancy or content duplication.
-  Always proofread and when proofreading, read it out loud. It will help you find passages that may be too long or bulky.
-  Try not to let sentences get too long and serpentine. When in doubt, make it two sentences.
-  If one sentence goes to three lines, consider breaking it up.

IV. Formatting rules
--------------------

The following inconsistencies are important, common, and worth paying special attention to.

Page titles and subtitles
~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Main page title should have the first letter of each word capitalized**, except for articles or prepositions. If a title contains a hyphenated term, each word should be capitalized, unless it is a preposition or article. Example: *How-to Guides*.
-  **All subheadings should be sentence case**.
-  If you write a user tutorial or a how-to guide, start with an **action verb**. Example: *Build a Simple Fixed-flow Assistant with Flows*.
-  If you write a reference documentation, it should start with a **noun or gerund**. Example: *Testing Inference with LLMs*.

Spacing
~~~~~~~

-  Break the line if the sentence is getting long.
-  Strive not to have code (lowercase) start sentences.

Referring to a file name or path
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To refer to a file name or repository path inside the text, italicize it. Example: "Save this code to a file named *File.py* in the current working directory."

Button names in the text
~~~~~~~~~~~~~~~~~~~~~~~~

-  When documenting the UI or API, match the terminology. Example: *To stop the process, click Abort*.
-  Capitalize the button name (as it is onscreen).

Action names in the text
~~~~~~~~~~~~~~~~~~~~~~~~

When documenting the UI, match the terminology and wrap the actions in quotation marks (“”). Example: *Upon completion, invoke the “Set as Default Java” action*.

Referring to file formats
~~~~~~~~~~~~~~~~~~~~~~~~~

-  When referring to a typical file format in the text, capitalize each letter. Example: JAR and JSON, not jar and json.
-  Do not italicize types of files.

Oxford comma
~~~~~~~~~~~~

The **Oxford comma** is the comma before words such as “and” or “or” in a list of three or more items.
Example: *The flag is red, white, and blue*.

**We suggest using the Oxford comma** to keep sentences as clear and intelligible.

British English vs American English spelling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As a convention, Oracle Corporation uses American English spelling rather than British English spelling.
Use **American English spelling**.

-  Example: Instead of "…our", use "…or". Write *behavior*, not *behaviour*.
-  Example: Instead of "…ise", use "…ize". Write *organize* and *organization*, not *organise* and *organisation*.

How to become a contributor
---------------------------

The WayFlow documentation is open source and anyone can contribute to make it perfect and comprehensive.
If you consider contributing to the documentation, please read our :doc:`contributing guidelines <contributing>`.

The end
~~~~~~~

We thank you for taking the time to read this style guide.

The WayFlow team
