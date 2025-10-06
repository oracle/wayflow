# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.


import json
import os
from importlib.resources import files
from typing import Dict, List, Optional, Type

import pytest

from wayflowcore.datastore import MTlsOracleDatabaseConnectionConfig, OracleDatabaseDatastore
from wayflowcore.datastore.datastore import Datastore
from wayflowcore.datastore.entity import Entity, nullable
from wayflowcore.datastore.inmemory import InMemoryDatastore
from wayflowcore.datastore.oracle import TlsOracleDatabaseConnectionConfig
from wayflowcore.property import FloatProperty, IntegerProperty, Property, StringProperty
from wayflowcore.steps.step import Step


def get_basic_office_entities():
    employees = Entity(
        properties={
            "ID": IntegerProperty(),
            "name": StringProperty(),
            "email": StringProperty(),
            "department_name": StringProperty(),
            "department_area": StringProperty(),
            "salary": FloatProperty(default_value=0.1),
        },
    )

    departments = Entity(
        properties={
            "department_name": StringProperty("department_name"),
            "area": StringProperty("area"),
            "regional_manager": nullable(IntegerProperty("regional_manager")),
            "assistant_to_the_regional_manager": nullable(
                IntegerProperty("assistant_to_the_regional_manager")
            ),
        },
    )
    return {"employees": employees, "departments": departments}


@pytest.fixture(scope="function")
def testing_inmemory_data_store():
    return InMemoryDatastore(get_basic_office_entities())


ORACLE_DB_DDL = [
    "DROP TABLE IF EXISTS departments cascade constraints",
    "DROP TABLE IF EXISTS employees cascade constraints",
    """\
CREATE TABLE employees (
    "ID" INTEGER,
    name VARCHAR(400) NOT NULL,
    email VARCHAR(400) NOT NULL,
    department_name VARCHAR(400) NOT NULL,
    department_area VARCHAR(400) NOT NULL,
    salary FLOAT DEFAULT '0.1' NOT NULL,
    PRIMARY KEY ("ID")
)
""",
    """\
CREATE TABLE departments (
    department_name VARCHAR(400) NOT NULL,
    area VARCHAR(400) NOT NULL,
    regional_manager INTEGER NOT NULL,
    assistant_to_the_regional_manager INTEGER,
    PRIMARY KEY (department_name, area),
    FOREIGN KEY(regional_manager) REFERENCES employees (id) ON DELETE CASCADE,
    FOREIGN KEY(assistant_to_the_regional_manager) REFERENCES employees (id) ON DELETE CASCADE
)""",
]


def get_oracle_connection_config():
    mtls_connection_args = [
        "ADB_CONFIG_DIR",
        "ADB_DB_USER",
        "ADB_DB_PASSWORD",
        "ADB_DSN",
        "ADB_WALLET_DIR",
        "ADB_WALLET_SECRET",
    ]
    tls_connection_args = ["ADB_DB_USER", "ADB_DB_PASSWORD", "ADB_DSN"]
    if all([arg in os.environ for arg in mtls_connection_args]):
        return MTlsOracleDatabaseConnectionConfig(
            config_dir=os.environ["ADB_CONFIG_DIR"],
            user=os.environ["ADB_DB_USER"],
            password=os.environ["ADB_DB_PASSWORD"],
            dsn=os.environ["ADB_DSN"],
            wallet_location=os.environ["ADB_WALLET_DIR"],
            wallet_password=os.environ["ADB_WALLET_SECRET"],
        )
    elif all([arg in os.environ for arg in tls_connection_args]):
        return TlsOracleDatabaseConnectionConfig(
            user=os.environ["ADB_DB_USER"],
            password=os.environ["ADB_DB_PASSWORD"],
            dsn=os.environ["ADB_DSN"],
        )
    else:
        pytest.skip(
            "No database connection arguments configured in enviroment. "
            "Skipping Oracle DB tests..."
        )


def get_oracle_datastore_with_schema(ddl: List[str], entities: Dict[str, Entity]):
    connection_config = get_oracle_connection_config()
    conn = connection_config.get_connection()
    for stmt in ddl:
        conn.cursor().execute(stmt)
    conn.close()
    return OracleDatabaseDatastore(entities, connection_config=connection_config)


def cleanup_oracle_datastore(ddl: Optional[List[str]] = None):
    stmts = ddl if ddl is not None else ORACLE_DB_DDL[:2]
    connection_config = get_oracle_connection_config()
    conn = connection_config.get_connection()
    for stmt in stmts:
        conn.cursor().execute(stmt)
    conn.close()


def cleanup_datastore_content(oracle_datastore: OracleDatabaseDatastore):
    for entity in get_basic_office_entities():
        oracle_datastore.delete(entity, where={})


@pytest.fixture(scope="session")
def oracle_datastore():
    yield get_oracle_datastore_with_schema(ORACLE_DB_DDL, get_basic_office_entities())
    cleanup_oracle_datastore()


@pytest.fixture(scope="function")
def testing_oracle_data_store(oracle_datastore: OracleDatabaseDatastore):
    yield oracle_datastore
    cleanup_datastore_content(oracle_datastore)


def get_default_datastore_content():
    with open(files("tests.datastores").joinpath("entities.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def default_datastore_content():
    return get_default_datastore_content()


def populate_with_basic_entities(datastore: Datastore):
    entities_json = get_default_datastore_content()
    datastore.create("employees", entities_json["employees"])
    datastore.create("departments", entities_json["departments"])


@pytest.fixture(scope="function")
def testing_inmemory_data_store_with_data():
    datastore = InMemoryDatastore(get_basic_office_entities())
    populate_with_basic_entities(datastore)
    return datastore


@pytest.fixture(scope="function")
def testing_oracle_data_store_with_data(oracle_datastore: OracleDatabaseDatastore):
    populate_with_basic_entities(oracle_datastore)
    yield oracle_datastore
    cleanup_datastore_content(oracle_datastore)


@pytest.fixture(
    scope="function",
    params=["testing_inmemory_data_store_with_data", "testing_oracle_data_store_with_data"],
)
def testing_data_store_with_data(request):
    # https://stackoverflow.com/questions/42014484/pytest-using-fixtures-as-arguments-in-parametrize
    return request.getfixturevalue(request.param)


def check_input_output_descriptors(
    step: Step,
    expected_inputs: Dict[str, Type[Property]],
    expected_outputs: Dict[str, Type[Property]],
):
    assert len(step.input_descriptors) == len(expected_inputs)
    for input_descriptor in step.input_descriptors:
        assert input_descriptor.name in expected_inputs
        assert isinstance(input_descriptor, expected_inputs[input_descriptor.name])

    assert len(step.output_descriptors) == len(expected_outputs)
    for input_descriptor in step.output_descriptors:
        assert input_descriptor.name in expected_outputs
        assert isinstance(input_descriptor, expected_outputs[input_descriptor.name])
