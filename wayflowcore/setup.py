# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import io
import os.path

from setuptools import find_packages, setup

NAME = "wayflowcore"

# Check for an environment variable to override the version
VERSION = os.environ.get("BUILD_VERSION")
if not VERSION:
    with open("../VERSION") as version_file:
        VERSION = version_file.read().strip()


def read(file_name):
    """Read a text file and return the content as a string."""
    file_path = os.path.join(os.path.dirname(__file__), file_name)
    with io.open(file_path, encoding="utf-8") as f:
        return f.read()


setup(
    name=NAME,
    version=VERSION,
    description="Package defining the WayFlow core library and the assistant abstractions.",
    license="APACHE-2.0 OR UPL-1.0",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    url="https://github.com/oracle/wayflow",
    author="Oracle",
    author_email="",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Natural Language :: English",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="NLP, text generation, code generation, LLM, Assistant, Tool, Agent",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.10",
    install_requires=[
        "pyagentspec>=26.1.0",
        "httpx>0.28.0,<1.0.0",  # warning but no vulnerabilities
        "numpy>=1.24.3,<3.0.0",
        "pandas>=2.0.3,<3.0.0",
        "jinja2>=3.1.6,<4.0.0",
        "jq>=1.8.0,<2.0.0",
        "deprecated>=1.2.18,<2.0.0",
        "json_repair>=0.30.0,<0.45.0",
        "PyYAML>=5.4,<7.0.0",
        "pydantic>=2.7.4,<3.0.0",
        "mcp>=1.24.0,<1.25.0",
        # 4rth party dependencies version bounds, for CVE patching
        "annotated-types>=0.6.0",
        "anyio>=4.10.0,<4.12.0",
        "certifi>=2025.4.26",
        "click>=7.0",
        "h11>=0.16",
        "httpcore>=1.0.9",
        "httpx-sse>=0.4",
        "idna>=3.7",
        "opentelemetry-api>=1.33.0,<2.0.0",
        "opentelemetry-sdk>=1.33.0,<2.0.0",
        "pydantic_core>=2.33.0",  # warning but no vulnerabilities
        "pydantic-settings>=2.5.2",
        "python-dotenv>=0.21.0",
        "python-multipart>=0.0.18",
        "sniffio>=1.1",
        "sse-starlette>=1.6.1",
        "starlette>=0.47.2,<0.48.0",
        "typing_extensions>=4.12.2",
        "typing-inspection>=0.4.0",
        "exceptiongroup>=1.0.2",
        "uvicorn>=0.23.1",
        "fastapi>=0.116.2,<1.0.0",
    ],
    test_suite="tests",
    entry_points={
        "console_scripts": [
            "wayflow = wayflowcore.cli:main",
        ],
    },
    include_package_data=True,
    extras_require={
        "oci": ["oci>=2.158.2"],
        "datastore": ["sqlalchemy>=2.0.40", "oracledb>=2.2.0"],
        "a2a": ["fasta2a>=0.6.0"],
    },
)
