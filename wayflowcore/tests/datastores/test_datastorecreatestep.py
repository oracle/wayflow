# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from typing import Any, Dict, Optional

import pytest

from wayflowcore.datastore.datastore import Datastore
from wayflowcore.flowhelpers import run_step_and_return_outputs
from wayflowcore.property import DictProperty, StringProperty
from wayflowcore.serialization.serializer import autodeserialize, serialize
from wayflowcore.steps.datastoresteps.datastorecreatestep import DatastoreCreateStep

from .conftest import check_input_output_descriptors


def insert_and_check_correctness(
    datastore: Datastore,
    step: DatastoreCreateStep,
    additional_inputs: Optional[Dict[str, Any]] = None,
) -> None:
    additional_inputs = additional_inputs or {}
    result = run_step_and_return_outputs(
        step,
        inputs={
            DatastoreCreateStep.ENTITY: {
                "ID": 34,
                "name": "Madeline Planter",
                "email": "madelineplanter@dudemuffin.com",
                "department_area": "Utica, NY",
                "department_name": "accounting",
            },
            **additional_inputs,
        },
    )

    created_entity = result[DatastoreCreateStep.CREATED_ENTITY]
    created_id = created_entity["ID"]
    assert created_entity["ID"] == 34
    assert datastore.list("employees", where={"ID": created_id})[0] == created_entity


def test_basic_create(testing_data_store_with_data):
    step = DatastoreCreateStep(testing_data_store_with_data, "employees")
    check_input_output_descriptors(
        step,
        {DatastoreCreateStep.ENTITY: DictProperty},
        {DatastoreCreateStep.CREATED_ENTITY: DictProperty},
    )
    insert_and_check_correctness(testing_data_store_with_data, step)


def test_parametrized_update_default_input_descriptors(testing_data_store_with_data):
    with pytest.raises(ValueError):
        step = DatastoreCreateStep(  # name clash with entity
            testing_data_store_with_data,
            "{{entity}}",
        )

    step = DatastoreCreateStep(
        testing_data_store_with_data,
        "{{collection_name}}",
    )
    check_input_output_descriptors(
        step,
        {DatastoreCreateStep.ENTITY: DictProperty, "collection_name": StringProperty},
        {DatastoreCreateStep.CREATED_ENTITY: DictProperty},
    )
    insert_and_check_correctness(
        testing_data_store_with_data, step, {"collection_name": "employees"}
    )


def test_datastore_step_serializable(testing_inmemory_data_store_with_data):
    step = DatastoreCreateStep(testing_inmemory_data_store_with_data, "employees")
    serialized_step = serialize(step)
    deserialized_step: DatastoreCreateStep = autodeserialize(serialized_step)
    assert deserialized_step.collection_name == step.collection_name
    assert deserialized_step.datastore is not step.datastore
    assert deserialized_step.datastore.describe() == step.datastore.describe()
