Installation
============

.. only:: stable

  You can find all versions and supported platforms of |project| in the :package_index:`\ `.

  For example, if you want to install |package_name| |stable_release|:

  .. code-block:: bash
      :substitutions:

      pip install "|package_name|==|stable_release|"

  Installing with ``pip`` pulls prebuilt binary wheels on supported platforms.

  .. only:: builder_html

      The list below shows the package versions used in the CI environment, with Business Approval requests filed for each as part of the release process.
      :download:`constraints.txt <../../../../wayflowcore/constraints/constraints.txt>`

      If you want to install |project| with exactly these package versions, download the file and run:

      .. code-block:: bash
          :substitutions:

          pip install "|package_name|==|stable_release|"  -c constraints.txt

.. only:: dev

  1. Clone the `repository <https://github.com/oracle/wayflow>`_.

    .. code-block:: bash
      :substitutions:

      git clone git@github.com:oracle/wayflow.git

  .. tip::
      If you face any problem, check with the WayFlow team.

  Next, install WayFlow directly from source.

  1. Create a fresh Python environment for building and running WayFlow assistants:

    .. code-block:: bash
      :substitutions:

        python3.10 -m venv <venv_name>
        source <venv_name>/bin/activate

  2. Move to the *wayflowcore/wayflowcore* directory:

    .. code-block:: bash
      :substitutions:

        cd wayflowcore/wayflowcore

  3. Install ``wayflowcore``:

    .. code-block:: bash
      :substitutions:

        bash install-dev.sh

  .. note::
    This removes any previous Python environment named ``venv-wayflowcore`` in order to create a new one.

Supported Platforms
-------------------

|project| strives for compatibility with major platforms and environments, where it is possible.

Operation systems and CPU architectures
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 50 30 30
   :header-rows: 1

   * - OS / CPU Architecture
     - x86-64 Support
     - ARM64 Support
   * - Linux
     - Supported
     - Untested
   * - MacOS
     - Supported
     - Supported


Python version
~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 30
   :header-rows: 1

   * - Python version
     - Support
   * - Python 3.9
     - Unsupported
   * - Python 3.10
     - Supported
   * - Python 3.11
     - Supported
   * - Python 3.12
     - Supported
   * - Python 3.13
     - Supported
   * - Python 3.14
     - Supported


Package manager
~~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 30
   :header-rows: 1

   * - Package Manager
     - Support
   * - pip
     - Supported
   * - conda
     - Untested


Python implementation
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 30
   :header-rows: 1

   * - Implementation
     - Support
   * - CPython
     - Supported
   * - PyPy
     - Untested

What do *Supported*, *Untested* and *Unsupported* mean?

* *Unsupported*: The package or one of its dependencies is not compatible with the Python version.
* *Untested*: The package and its dependencies are compatible with the Python version, but they are not tested.
* *Supported*: The package and its dependencies are compatible with the Python version, and the package is tested on that version.
