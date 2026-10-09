================
For Contributors
================

WayFlow is an open-source project from Oracle, and developers from around the world are welcome to contribute.

There are several ways to collaborate:

- By submitting a `GitHub issue <https://github.com/oracle/wayflow/issues>`_ for bug reports or questions.
- By submitting a Request for Comments (RFC) for a new feature request or enhancement.
- By submitting a `GitHub pull request <https://github.com/oracle/wayflow/pulls>`_.

As a contributor, we expect you to abide by the WayFlow :doc:`Contributor Code of Conduct <conduct>`, which outlines the standards for respectful and constructive collaboration.


Submitting a GitHub Issue
-------------------------

Use GitHub's issue tracking system to report problems (bugs) or ask questions related to the project.
You can submit a GitHub issue for WayFlow `here <https://github.com/oracle/wayflow/issues>`_.

When submitting a bug, provide a clear description of the issue.
We encourage you to:

- Include steps to reproduce the bug, so project developers can replicate the problem.
- Attach error messages, logs, or screenshots to give more context to the issue.
- Mention the environment (operating system, version, etc.) where the bug occurs.


Submitting a Request for Comments (RFC)
---------------------------------------

To propose a new feature or enhancement, submit a Request for Comments (RFC).
This RFC is basically a design proposal where you can share a detailed description of what change you want to make,
why it is needed, and how you propose to implement it.
The RFC gives core maintainers an opportunity to suggest refinements before you start coding.

Follow these instructions to submit an RFC.

I. Create an RFC
~~~~~~~~~~~~~~~~

Fork the `WayFlow repository <https://github.com/oracle/wayflow>`_.
Fill out your proposal using the :doc:`provided template <rfcs-template>`.
Rename the template file to **RFC-your-feature-name.rst** and push it to your fork.
Submit a pull request titled **RFC-your-feature-name**.
Before your RFC is ready for review, give it the draft label.

II. Get Feedback on the RFC
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once your RFC ready for review, remove the draft label.
File a GitHub issue against the `WayFlow repository <https://github.com/oracle/wayflow>`_ with request to review your proposal.
In the description, include a short summary of your feature and a link to your RFC pull request.

The core developers will review your PR RFC and offer feedback.
Revise your proposal as needed until everyone agrees on a path forward.

III. Implement Your Proposal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your RFC pull request is accepted, you can begin working on the implementation.
The next step is to submit a pull request (PR) with your code changes.
This takes the form of a regular PR review.
Be sure to link your PR to the accepted RFC so reviewers can easily catch up on the context and design decisions behind your proposal.


Submitting a Pull Request
-------------------------

For smaller changes, such as bug fixes, you can proceed directly and `create a pull request (PR) <https://github.com/oracle/wayflow/pulls>`_.
This process is similar for implementing your RFC, except in this case, the PR will include the code changes.

I. Create a Pull Request
~~~~~~~~~~~~~~~~~~~~~~~~

The common process is forking the `WayFlow repository <https://github.com/oracle/wayflow>`_, pushing a change, and creating a PR.
When creating a PR, make sure to include a clear description of the intention of the change.
Describe why (1) the change is needed, (2) how it is implemented, and, optionally, (3) what further implications it may have.
You can either use the PR request description field or the commit message.
It is recommended to address one fix or feature per PR request.

Once you have `created a pull
request <https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/creating-a-pull-request-from-a-fork>`_,
the CI service will run some sanity checks on your change.
Be sure to address any obvious issues caught by these checks (for example, formatting violation).

II. Sign the Oracle Contributor Agreement
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To allow your pull request to be accepted, you need to sign the `Oracle Contributor Agreement (OCA) <https://oca.opensource.oracle.com/>`_.
Sign it online, and once your name appears on the OCA signatory list, your pull request will be authorized.
If you signed the agreement, but the bot leaves a message that you have not signed the OCA, leave a comment on the pull request.
If it appears to be a delay, please send an email to *oracle-ca_us@oracle.com*.

III. Review and Merge
~~~~~~~~~~~~~~~~~~~~~

An Oracle employee will review the proposed change and, once it is in a mergeable state, will take responsibility for merging it into the main branch.


Contributing to Documentation
-----------------------------

The WayFlow documentation is open source and anyone can contribute to make it perfect and comprehensive.
If you consider contributing to the documentation, read our :doc:`writing guidelines <style_guide>` beforehand to ensure consistency and quality.

The end
-------

WayFlow welcomes contributions from both users and developers!

The WayFlow team
