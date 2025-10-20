# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from wayflowcore.datastore.datastore import Datastore
from wayflowcore.flowhelpers import run_step_and_return_outputs
from wayflowcore.property import FloatProperty, StringProperty
from wayflowcore.serialization.serializer import autodeserialize, serialize
from wayflowcore.steps.datastoresteps.datastoredeletestep import DatastoreDeleteStep

from .conftest import check_input_output_descriptors


def _check_sales_got_deleted(datastore: Datastore) -> None:
    assert datastore.list("employees", where={"department_name": "sales"}) == []


def test_basic_delete(testing_data_store_with_data):
    step = DatastoreDeleteStep(
        testing_data_store_with_data, "employees", where={"department_name": "sales"}
    )
    check_input_output_descriptors(step, {}, {})
    run_step_and_return_outputs(step)
    _check_sales_got_deleted(testing_data_store_with_data)


def test_parametrized_delete_default_input_descriptors(testing_data_store_with_data):
    step = DatastoreDeleteStep(
        testing_data_store_with_data,
        "{{entity}}",
        where={"{{stringcol}}": "{{somevalue}}"},
    )
    check_input_output_descriptors(
        step,
        {"entity": StringProperty, "stringcol": StringProperty, "somevalue": StringProperty},
        {},
    )
    run_step_and_return_outputs(
        step,
        inputs={"entity": "employees", "stringcol": "department_name", "somevalue": "sales"},
    )
    _check_sales_got_deleted(testing_data_store_with_data)


def test_parametrized_delete_custom_input_descriptors(testing_data_store_with_data):
    step = DatastoreDeleteStep(
        testing_data_store_with_data,
        "{{entity}}",
        where={"{{numericalcol}}": "{{somevalue}}"},
        input_descriptors=[FloatProperty("somevalue")],
    )
    check_input_output_descriptors(
        step,
        {"entity": StringProperty, "numericalcol": StringProperty, "somevalue": FloatProperty},
        {},
    )
    run_step_and_return_outputs(
        step,
        inputs={
            "entity": "employees",
            "numericalcol": "salary",
            "somevalue": 150000.0,
        },
    )
    remaining_employees = testing_data_store_with_data.list("employees")
    assert all(e["name"] != "Mike Swat" for e in remaining_employees)


def test_no_entities_deleted(testing_data_store_with_data):
    employees_before = testing_data_store_with_data.list("employees")
    step = DatastoreDeleteStep(
        testing_data_store_with_data, "employees", where={"department_name": "warehouse"}
    )
    run_step_and_return_outputs(step)
    employees_after = testing_data_store_with_data.list("employees")
    assert employees_before == employees_after


def test_datastore_step_serializable(testing_inmemory_data_store_with_data):
    step = DatastoreDeleteStep(
        testing_inmemory_data_store_with_data, "employees", {"department_name": "warehouse"}
    )
    serialized_step = serialize(step)
    deserialized_step: DatastoreDeleteStep = autodeserialize(serialized_step)
    assert deserialized_step.collection_name == step.collection_name
    assert deserialized_step.datastore is not step.datastore
    assert deserialized_step.datastore.describe() == step.datastore.describe()
    assert deserialized_step.where == step.where
