# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


import pytest

from wayflowcore.datastore._relational import RelationalDatastore
from wayflowcore.exceptions import DatastoreError
from wayflowcore.flowhelpers import create_single_step_flow, run_step_and_return_outputs
from wayflowcore.property import FloatProperty, ObjectProperty, StringProperty
from wayflowcore.serialization.serializer import autodeserialize, serialize
from wayflowcore.steps.datastoresteps.datastorequerystep import DatastoreQueryStep
from wayflowcore.warnings import SecurityWarning


def test_basic_query(testing_oracle_data_store_with_data: RelationalDatastore):
    QUERY = "SELECT * FROM EMPLOYEES"
    step = DatastoreQueryStep(testing_oracle_data_store_with_data, query=QUERY)
    # One input descriptor, always a bind_variables dictionary
    assert len(step.input_descriptors) == 1
    assert step.input_descriptors[0].name == "bind_variables"
    # Pass empty bind_variables dict for non-parametrized
    result = run_step_and_return_outputs(step, {"bind_variables": {}})
    assert result[DatastoreQueryStep.RESULT] == testing_oracle_data_store_with_data.query(QUERY)


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM EMPLOYEES WHERE salary > :empsalary",
        # use a raw string to avoid escaping issues
        r"SELECT * FROM EMPLOYEES WHERE salary > :empsalary OR name = 'some random\:thing that: isn''t a:: var'",
    ],
)
def test_parametrized_query_with_default_descriptors(
    query: str,
    testing_oracle_data_store_with_data: RelationalDatastore,
):
    step = DatastoreQueryStep(testing_oracle_data_store_with_data, query=query)
    assert len(step.input_descriptors) == 1
    assert step.input_descriptors[0].name == "bind_variables"
    bind = {"empsalary": 150000}
    result = run_step_and_return_outputs(step, {"bind_variables": bind})
    assert result[DatastoreQueryStep.RESULT] == testing_oracle_data_store_with_data.query(
        query, bind
    )


def test_error_on_jinja_in_query(testing_oracle_data_store_with_data: RelationalDatastore):
    QUERY = "SELECT * FROM EMPLOYEES WHERE {{column}} > :empsalary"
    with pytest.raises(ValueError):
        DatastoreQueryStep(
            testing_oracle_data_store_with_data,
            query=QUERY,
        )


@pytest.mark.parametrize(
    "query", ["SELECT * FROM employees", "SELECT * FROM EMPLOYEES WHERE salary > :empsalary"]
)
def test_datastore_step_serializable(
    query: str, testing_oracle_data_store_with_data: RelationalDatastore
):
    step = DatastoreQueryStep(testing_oracle_data_store_with_data, query)
    with pytest.warns(SecurityWarning):
        serialized_step = serialize(step)
    with pytest.raises(TypeError):
        autodeserialize(serialized_step)


def test_custom_descriptor_for_bind_variables(testing_oracle_data_store_with_data):
    datastore_query_flow = create_single_step_flow(
        DatastoreQueryStep(
            testing_oracle_data_store_with_data,
            "SELECT email, salary FROM employees WHERE department_name = :depname OR salary < :salary",
        )
    )
    conversation = datastore_query_flow.start_conversation(
        {"bind_variables": {"salary": 100000, "depname": "reception"}}
    )
    execution_status = conversation.execute()
    assert len(execution_status.output_values[DatastoreQueryStep.RESULT]) == 1

    # Second part of the example
    datastore_query_flow = create_single_step_flow(
        DatastoreQueryStep(
            testing_oracle_data_store_with_data,
            "SELECT email, salary FROM employees WHERE department_name = :depname OR salary < :salary",
            input_descriptors=[
                ObjectProperty(
                    "bind_variables",
                    properties={"salary": FloatProperty(), "depname": StringProperty()},
                )
            ],
        )
    )
    conversation = datastore_query_flow.start_conversation(
        {"bind_variables": {"salary": 1000.0, "depname": "reception"}}
    )

    with pytest.raises(TypeError):
        conversation = datastore_query_flow.start_conversation(
            {"bind_variables": {"salary": "mysalary", "depname": "reception"}}
        )
    with pytest.raises(TypeError):
        conversation = datastore_query_flow.start_conversation(
            {"bind_variables": {"bla": "mysalary", "depname": "reception"}}
        )


@pytest.mark.parametrize(
    "query",
    [
        # NOTE: Specific error on jinja query is already tested above
        "SELECT * FROM EMPLOYEES WHERE",  # Simple syntax error
        "SELECT ID AS :bindvar FROM EMPLOYEES",  # Illegal use of bind variables
        "SELECT {bindvar} FROM EMPLOYEES",
        "SELECT * FROM EMPLOYEES WHERE ID = @bindvar",
        "SELECT * FROM EMPLOYEES WHERE ID = ${bindvar}",
        "SELECT * FROM EMPLOYEES WHERE ID = `bindvar`",
    ],
)
def test_invalid_query_errors_are_propagated(query, testing_oracle_data_store_with_data):
    datastore_query_flow = create_single_step_flow(
        DatastoreQueryStep(
            testing_oracle_data_store_with_data,
            query,
        )
    )
    conversation = datastore_query_flow.start_conversation(
        {"bind_variables": {"bindvar": "; DROP TABLE EMPLOYEES; --"}}
    )
    with pytest.raises(DatastoreError):
        conversation.execute()
