# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.


from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flowhelpers import run_step_and_return_outputs
from wayflowcore.property import DictProperty, FloatProperty, ListProperty, StringProperty
from wayflowcore.serialization.serializer import autodeserialize, serialize
from wayflowcore.steps.datastoresteps.datastoreliststep import DatastoreListStep
from wayflowcore.steps.datastoresteps.datastoreupdatestep import DatastoreUpdateStep

from .conftest import check_input_output_descriptors


def _check_sales_got_promoted(result: FinishedStatus) -> None:
    assert len(result[DatastoreListStep.ENTITIES]) == 3
    assert all([entity["salary"] == 125500.0 for entity in result[DatastoreListStep.ENTITIES]])


def test_basic_update(testing_data_store_with_data):
    step = DatastoreUpdateStep(
        testing_data_store_with_data, "employees", where={"department_name": "sales"}
    )
    check_input_output_descriptors(
        step,
        {DatastoreUpdateStep.UPDATE: DictProperty},
        {DatastoreUpdateStep.ENTITIES: ListProperty},
    )
    result = run_step_and_return_outputs(
        step, inputs={DatastoreUpdateStep.UPDATE: {"salary": 125500.0}}
    )
    _check_sales_got_promoted(result)


def test_parametrized_update_default_input_descriptors(testing_data_store_with_data):
    step = DatastoreUpdateStep(
        testing_data_store_with_data,
        "{{entity}}",
        where={"{{stringcol}}": "{{somevalue}}"},
    )
    check_input_output_descriptors(
        step,
        {
            DatastoreUpdateStep.UPDATE: DictProperty,
            "entity": StringProperty,
            "stringcol": StringProperty,
            "somevalue": StringProperty,
        },
        {DatastoreUpdateStep.ENTITIES: ListProperty},
    )
    result = run_step_and_return_outputs(
        step,
        inputs={
            "entity": "employees",
            "stringcol": "department_name",
            "somevalue": "sales",
            DatastoreUpdateStep.UPDATE: {"salary": 125500.0},
        },
    )
    _check_sales_got_promoted(result)


def test_parametrized_update_custom_input_descriptors(testing_data_store_with_data):
    step = DatastoreUpdateStep(
        testing_data_store_with_data,
        "{{entity}}",
        where={"{{numericalcol}}": "{{somevalue}}"},
        input_descriptors=[FloatProperty("somevalue")],
    )
    check_input_output_descriptors(
        step,
        {
            DatastoreUpdateStep.UPDATE: DictProperty,
            "entity": StringProperty,
            "numericalcol": StringProperty,
            "somevalue": FloatProperty,
        },
        {DatastoreUpdateStep.ENTITIES: ListProperty},
    )
    result = run_step_and_return_outputs(
        step,
        inputs={
            "entity": "employees",
            "numericalcol": "salary",
            "somevalue": 150000.0,
            DatastoreUpdateStep.UPDATE: {"department_name": "accounting"},
        },
    )
    updated_entities = result[DatastoreUpdateStep.ENTITIES]
    assert len(updated_entities) == 1
    assert updated_entities[0]["name"] == "Mike Swat"
    assert updated_entities[0]["department_name"] == "accounting"


def test_no_entities_updated(testing_data_store_with_data):
    step = DatastoreUpdateStep(
        testing_data_store_with_data, "employees", where={"department_name": "warehouse"}
    )
    result = run_step_and_return_outputs(
        step, inputs={DatastoreUpdateStep.UPDATE: {"salary": 125500.0}}
    )
    assert len(result[DatastoreUpdateStep.ENTITIES]) == 0


def test_datastore_step_serializable(testing_inmemory_data_store_with_data):
    step = DatastoreUpdateStep(
        testing_inmemory_data_store_with_data, "employees", {"department_name": "warehouse"}
    )
    serialized_step = serialize(step)
    deserialized_step: DatastoreUpdateStep = autodeserialize(serialized_step)
    assert deserialized_step.collection_name == step.collection_name
    assert deserialized_step.datastore is not step.datastore
    assert deserialized_step.datastore.describe() == step.datastore.describe()
    assert deserialized_step.where == step.where
