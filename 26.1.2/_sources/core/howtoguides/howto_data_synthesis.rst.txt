========================================
How to Perform Data Synthesis in WayFlow
========================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_data_synthesis.py
        :link-alt: Data Synthesis how-to script

        Python script/notebook for this guide.

This guide provides practical and adaptable methods for generating synthetic datasets tailored to a range of real-world use cases. Use it when you need to create evaluation datasets for model testing, sample data for demonstrations, or address data privacy requirements. You will find reproducible workflows and techniques that you can flexibly adapt to your own data schema and constraints.

Each synthesis approach is presented in relation to specific feature requirements. Most examples start from a seed dataset to capture authentic data characteristics. However, you can also apply these methods without real data by specifying a target schema and using tools such as *Faker*. With this guide, you can generate synthetic data that balances statistical realism with project flexibility.

Prerequisites and setup
=======================

- **Desired output schema:** Define the fields and features your synthetic dataset should contain. Specify each field's type and any necessary constraints.

- **Seed dataset (optional, recommended):**

  - Use a seed dataset if you want to preserve real-world distributional properties, such as means, variances, or category frequencies.

  - A seed dataset is also essential if you need to interpolate or generate synthetic values conditioned on, or resembling, existing feature values (for example, generating synthetic ages based on a real distribution).

- **No seed dataset?**

  If you do not have real data to start with, you can use the *Faker* package (`Faker <https://faker.readthedocs.io/>`__). *Faker* provides many generators for structured data such as names, addresses, dates, countries, and phone numbers. Use this to quickly create dummy datasets with any schema, though the values will not reflect empirical sources.

.. note::
   Choosing whether to use a seed dataset or a synthetic generator depends on your use case.

   - For data realism and statistical fidelity, start from a seed dataset.
   - For flexible or arbitrary data structures without statistical constraints, use *Faker* or similar tools.

Target schema and feature properties
====================================

The following table summarizes the type, synthesis method, and key properties or constraints for each feature:

+-----------------------+--------+---------------------+-------------------------------------------+----------------------+
| Feature               | Type   | Interp./Extrap.     | Method or constraint                      | Distribution target  |
+=======================+========+=====================+===========================================+======================+
| customer_type         | cat    | Interpolation       | Sampled with empirical (seed) univariate  | Preserve univariate  |
|                       |        |                     | distribution                              |                      |
+-----------------------+--------+---------------------+-------------------------------------------+----------------------+
| customer_name         | string | Extrapolation       | Use ``fake.name()`` if individual, else   | /                    |
|                       |        |                     | ``fake.company()``                        |                      |
+-----------------------+--------+---------------------+-------------------------------------------+----------------------+
| region                | cat    | Interpolation       | Choice among [EMEA, JAPAC, LAD, NA]       | /                    |
+-----------------------+--------+---------------------+-------------------------------------------+----------------------+
| country               | cat    | Interpolation       | Based on mapping from region; randomly    | Coherency: region    |
|                       |        |                     | select among possible countries in region |                      |
+-----------------------+--------+---------------------+-------------------------------------------+----------------------+
| customer_net_worth    | num    | Interpolation       | Sampled from joint empirical distribution | Joint: region        |
|                       |        |                     | with region                               |                      |
+-----------------------+--------+---------------------+-------------------------------------------+----------------------+
| loan_value            | num    | Interpolation       | Sampled from joint empirical distribution | Joint: region        |
|                       |        |                     | with region                               |                      |
+-----------------------+--------+---------------------+-------------------------------------------+----------------------+
| loan_proposed_interest| num    | Interpolation       | Sampled from joint empirical distribution | Joint: region        |
|                       |        |                     | with region                               |                      |
+-----------------------+--------+---------------------+-------------------------------------------+----------------------+
| loan_reason           | cat    | Interpolation       | Sampled with empirical (seed) univariate  | Preserve univariate  |
|                       |        |                     | distribution                              |                      |
+-----------------------+--------+---------------------+-------------------------------------------+----------------------+
| justification         | string | Extrapolation       | Long text generation                      | Coherency with other |
|                       |        |                     |                                           | fields               |
+-----------------------+--------+---------------------+-------------------------------------------+----------------------+

- **Interp./Extrap.:** Indicates if the feature is synthesized from existing (seed) values (interpolation) or from new, plausible values (extrapolation).
- **Method or constraint:** Specifies any specialized synthesis function or logic, including use of *Faker*.

Load and inspect the seed data
==============================

Begin by loading your seed dataset. This data provides distributions, feature values, and coherency patterns for synthetic data generation. For demonstration, the following example defines a small seed dataset matching the target schema above, but you can use your own data.

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-data:
    :end-before: .. end-data

Data synthesis
==============

Synthesis functions
^^^^^^^^^^^^^^^^^^^

Define Python functions to generate feature values according to empirical distributions and project-specific constraints.

1. ``fake_categorical``: Sample a categorical column by seed frequency
   It uses NumPy to reproduce marginal distributions.

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-fake_categorical:
    :end-before: .. end-fake_categorical

2. ``fake_joint_numerical``: Sample a numerical feature by joint distribution
   It samples values for a numerical feature conditional on one or more categorical features (for example, ``customer_net_worth`` conditioned on region).

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-fake_joint_numerical:
    :end-before: .. end-fake_joint_numerical

Structured data generation
==========================

Each section below demonstrates how to synthesize features while upholding a specific property. After each example, synthesize all other features by specification.

Reproducibility
^^^^^^^^^^^^^^^

Set seeds for all relevant random number generators to make synthesis repeatable.

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-seeds:
    :end-before: .. end-seeds

Generation configuration
^^^^^^^^^^^^^^^^^^^^^^^^

Configure the synthetic data generation process.

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-generation_configuration:
    :end-before: .. end-generation_configuration

Univariate distribution preservation example (region)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sample the ``region`` column according to the frequency distribution in the seed dataset.

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-univariate_distribution:
    :end-before: .. end-univariate_distribution

Coherency constraint example (region vs. country)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``country`` and ``region`` must be coherent: each country should map to its correct business region.

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-coherency_constraint:
    :end-before: .. end-coherency_constraint

Joint distribution example (customer_net_worth | region)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Synthesize ``customer_net_worth`` values respecting the empirical joint distribution over ``region``.

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-joint_distribution:
    :end-before: .. end-joint_distribution

Extrapolation (new values) example (customer_name)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use *Faker* to synthesize new individual names or company names, even if not present in the seed.

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-extrapolation:
    :end-before: .. end-extrapolation

Synthesizing remaining structured features according to property table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

With each property demonstrated, now synthesize the remaining structured features as specified above.

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-full_synthesis:
    :end-before: .. end-full_synthesis

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-full_synthesis_flow:
    :end-before: .. end-full_synthesis_flow

Verification: sanity checks and distribution comparison
=======================================================

Compare value counts and distributions for select features, and compare them to the original seed dataset.

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-verification:
    :end-before: .. end-verification

Long text generation
====================
To generate realistic business justifications for each record, you will use a language model (LLM) as part of your synthesis workflow. This section explains the configuration of the LLM, describes the prompts and parsing logic, outlines the flow definition, and demonstrates parallelized generation and validation.

LLM selection and initialization
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
For long text generation, you need to use an LLM.
WayFlow supports several LLM providers. Select and configure your LLM below:

.. include:: ../_components/llm_config_tabs.rst

Prompt and I/O constants
^^^^^^^^^^^^^^^^^^^^^^^^
Begin by defining the necessary output constants and prompts used to instruct the LLM and structure the flow:

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-long_text_generation:
    :end-before: .. end-long_text_generation

Parsing functions
^^^^^^^^^^^^^^^^^
Parsing functions are responsible for extracting and normalizing the LLM outputs produced during justification and validation steps:

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-parsing_functions:
    :end-before: .. end-parsing_functions

Justification generation flow definition
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This flow defines a multi-step pipeline for generation, parsing, validation, and conditional retry of business justifications:

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-justification_generation_flow:
    :end-before: .. end-justification_generation_flow

Batch justification generation and validation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Finally, apply the justification generation flow in parallel over your dataset using a `MapStep` (for more information see :doc:`How to Do Map and Reduce Operations in Flows <howto_mapstep>`). This enables efficient batch generation and validation:

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-justification_generation:
    :end-before: .. end-justification_generation

Synthetic dataset export
========================

Save the synthesized dataset for downstream use.

.. literalinclude:: ../code_examples/howto_data_synthesis.py
    :language: python
    :start-after: .. start-exporting_synthetic_dataset:
    :end-before: .. end-exporting_synthetic_dataset

Recap
=====

This guide demonstrated property-respecting structured data synthesis, including logic for univariate, joint, interpolated, extrapolated, and coherent features. It also described long text generation and validation with a language model as a judge, including conditional retries. By following these workflows and recommendations, you can create realistic, flexible synthetic datasets to support your WayFlow projects.


Next steps
==========

Having learned how to synthesize data in WayFlow, you may now proceed to :doc:`How to Connect Assistants to Your Data <howto_datastores>` to learn how to integrate your synthesized datasets with your assistants for downstream applications and enhanced testing.


Full code
=========

You can copy the full code for this guide below.

.. literalinclude:: ../end_to_end_code_examples/howto_data_synthesis.py
    :language: python
    :linenos:
