# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
# mypy: ignore-errors
# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html


import logging
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath("_ext"))
from python_example_parser import parse_and_write_scripts

import wayflowcore

# ^ this script from _ext/python_example_parser.py parses the docs code_examples and
# automatically generates the end-to-end code examples for guides and tutorials.


# -- Project information -----------------------------------------------------
project = "wayflowcore"
package_name = "wayflowcore"
copyright = "2025, Oracle and/or its affiliates."
author = "Oracle Labs"

html_static_path = ["_static"]

# The last stable release we want users to install
version_file = wayflowcore.__version__

# Tag for building the right version with `make html`
# The tags can be `dev` or `stable`. See  https://www.sphinx-doc.org/en/master/usage/configuration.html#conf-tags
# BUILD_ID is the id of the regression build.
# USE_BUILD_ID indicates if the BUILD should be used or not.
use_build_id_str = os.getenv("USE_BUILD_ID")
build_id = os.getenv("BUILD_ID")
exclude_patterns = []
visibility = "external"

if os.getenv("DOC_VERSION") == "dev":
    tags.add("dev")
else:
    tags.add("stable")

# The short X.Y version.
version = ".".join(wayflowcore.__version__.split(".")[:2])

# The full version, including alpha/beta/rc tags.
release = wayflowcore.__version__

# The last stable release we want users to install
version_file = wayflowcore.__version__

# Use STABLE_RELEASE if it's set, otherwise use version_file
stable_release = os.getenv("STABLE_RELEASE") or version_file
if stable_release is None:
    raise Exception("Error: STABLE_RELEASE environment variable is not set.")

WARNINGS_TO_FILTER_OUT = []


class SphinxWarningFilter(logging.Filter):
    def filter(self, record):
        if record.name.startswith("sphinx"):
            record_message = record.getMessage()
            if any(warning_message in record_message for warning_message in WARNINGS_TO_FILTER_OUT):
                return False
        return True


logging.getLogger("sphinx").addFilter(SphinxWarningFilter())
# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.mathjax",
    "sphinx_substitution_extensions",
    "sphinx.ext.extlinks",
    "sphinx_toolbox.collapse",
    "sphinx_tabs.tabs",
    "sphinx.ext.doctest",
    "sphinx_copybutton",
    "sphinx_design",
]

# Set the variables that should be replaced in the substitution-extensions directives
rst_prolog = f"""
.. |release| replace:: {release}
.. |stable_release| replace:: {stable_release}
.. |author| replace:: {author}
.. |copyright| replace:: {copyright}
.. |project| replace:: {project}
.. |package_name| replace:: {package_name}
"""

extlinks = {
    "package_index": (
        f"https://pypi.org/simple/{package_name}/%s",
        "Package Index %s",
    ),
    "issue": ("https://github.com/org/repo/issues/%s", "issue "),
    "pr": ("https://github.com/org/repo/pull/%s", "PR #"),
}


source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

autodoc_default_options = {
    "members": True,
    "inherited-members": False,
    "undoc-members": True,
}

# Use __init__ method docstring.
autoclass_content = "both"

# Add type hints to parameter description, not to signature.
autodoc_typehints = "description"

# -- Options for HTML output -------------------------------------------------

# Ignore the components dir. This is where reusable doc components, such as LLM Config tabs, are kept.
exclude_patterns.append("_components/*.rst")

# The theme to use for HTML and HTML Help pages. See the documentation for
# a list of builtin themes.
html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "logo": {
        "text": "WayFlow",
    },
    "show_toc_level": 1,
    "header_links_before_dropdown": 4,
    "navbar_align": "left",
    "navbar_center": ["navbar-nav"],
    "show_prev_next": False,
    "pygments_light_style": "xcode",  # for light mode
    "pygments_dark_style": "monokai",  # for dark mode
    "navbar_start": ["navbar-logo"],
    "navbar_center": ["navbar-nav"] if "internal" in tags else [],
    "logo": {
        "image_light": "logo-light.svg",
        "image_dark": "logo-dark.svg",
    },
}

html_sidebars = {"**": ["sidebar-nav-bs"], "core/changelog": []}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_css_files = ["css-style.css", "core.css"]
html_js_files = []

html_favicon = "_static/favicon.png"

# to remove the `View page source` link
html_show_sourcelink = False

# -- Options for Copy button -------------------------------------------------
# Remove >>> and ... prompts from code blocks
# https://sphinx-copybutton.readthedocs.io/en/latest/use.html#using-regexp-prompt-identifiers
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
# enables the copy prevention of the above patterns when they match.
copybutton_prompt_is_regexp = True


def on_builder_inited(app):
    """
    Hook to process Python files before the HTML build is completed.
    """
    # Define source and destination folders
    source_dir = Path(__file__).parent
    source_raw_examples = source_dir / "core/code_examples"
    source_parsed_examples = source_dir / "core/end_to_end_code_examples"
    html_destination_folder = os.path.join(app.outdir, "core/end_to_end_code_examples")

    # 1. Raw code examples are parsed for internal consumption
    parse_and_write_scripts(
        source_folder=source_raw_examples,
        destination_folder=source_parsed_examples,
        version=version,
    )
    # 2. Parsed code examples are copied to the built docs folder
    shutil.copytree(source_parsed_examples, html_destination_folder, dirs_exist_ok=True)
    print(f"Code snippets processed and copied to: {html_destination_folder}")


def on_build_finished(app, exception):
    """
    Hook to process Python files after the HTML build is complete.
    """
    source_dir = Path(__file__).parent
    source_parsed_examples = source_dir / "core/end_to_end_code_examples"

    if exception is None and os.path.exists(
        source_parsed_examples
    ):  # Only run if the build succeeded
        shutil.rmtree(source_parsed_examples)


# Connect the hook to the Sphinx "build-finished" event
def setup(app):
    app.connect("builder-inited", on_builder_inited)
    app.connect("build-finished", on_build_finished)
