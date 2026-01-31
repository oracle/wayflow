# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import doctest
import glob
import os
from pathlib import Path

import pytest

from wayflowcore.datastore.inmemory import _INMEMORY_USER_WARNING
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.serialization.serializer import serialize
from wayflowcore.steps import OutputMessageStep
from wayflowcore.transforms.summarization import _SUMMARIZATION_WARNING_MESSAGE

from .datastores.conftest import (  # noqa
    ORACLE_DB_DDL,
    get_basic_office_entities,
    get_oracle_datastore_with_schema,
    populate_with_basic_entities,
)

CONFIGS_DIR = Path(os.path.dirname(__file__)).parent


def get_all_src_files():
    return glob.glob(str(CONFIGS_DIR) + "/src/**/*.py", recursive=True)


def create_assistant() -> Flow:
    return create_single_step_flow(
        step=OutputMessageStep(
            message_template="some_output",
        ),
        step_name="gen_step",
    )


ONLY_FILE_VAR = "ONLY_FILE"
FILES_REQUIRE_DATASTORE = ["datastorequerystep.py"]


@pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")
@pytest.mark.filterwarnings(f"ignore:{_SUMMARIZATION_WARNING_MESSAGE}:UserWarning")
@pytest.mark.parametrize("file_path", get_all_src_files())
def test_examples_in_docstrings_can_be_successfully_ran(
    remotely_hosted_llm: VllmModel,
    remote_gemma_llm: VllmModel,
    test_with_llm_fixture,
    file_path: str,
    with_mcp_enabled,
) -> None:
    if ONLY_FILE_VAR in os.environ and os.environ[ONLY_FILE_VAR] not in file_path:
        pytest.skip(f"Skipping because we only want to run {os.environ[ONLY_FILE_VAR]}")
        # We don't parametrize w/ the fixture to avoid useless work for tests that don't require this
    testing_oracle_data_store_with_data = None
    if Path(file_path).name in FILES_REQUIRE_DATASTORE:
        testing_oracle_data_store_with_data = get_oracle_datastore_with_schema(
            ORACLE_DB_DDL, get_basic_office_entities()
        )
        populate_with_basic_entities(testing_oracle_data_store_with_data)

    LLAMA70BV33_API_URL = os.environ.get("LLAMA70BV33_API_URL")
    if not LLAMA70BV33_API_URL:
        raise Exception("LLAMA70BV33_API_URL is not set in the environment")
    # Check the docs at https://docs.python.org/3/library/doctest.html#doctest.testfile
    # if you want to understand how this test works.
    assistant = create_assistant()
    doctest.testfile(
        filename=file_path,
        module_relative=False,
        globs={
            "llm": remotely_hosted_llm,
            "assistant": assistant,
            "config_file_path": CONFIGS_DIR / "tests/configs/docstring_assistant.yaml",
            "serialized_assistant_as_str": serialize(assistant),
            "LLAMA70B_API_ENDPOINT": LLAMA70BV33_API_URL,
            # Note: the docstring of the datastore query step instantiates a new datastore,
            # but we use this so that we create a new datastore in the test that connects to the
            # existing database with the data already there
            "testing_oracle_data_store_with_data": testing_oracle_data_store_with_data,
            "database_connection_config": (
                testing_oracle_data_store_with_data.connection_config
                if testing_oracle_data_store_with_data
                else None
            ),
            "multimodal_llm": remote_gemma_llm,
        },
        raise_on_error=True,
        verbose=True,
    )
