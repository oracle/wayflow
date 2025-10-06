# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.


import pytest

from wayflowcore.flowhelpers import run_step_and_return_outputs
from wayflowcore.property import DictProperty, FloatProperty, ListProperty, StringProperty
from wayflowcore.steps.datastoresteps.datastoreliststep import DatastoreListStep

from .conftest import check_input_output_descriptors


def _check_sales_people_in_result(result: dict, all_entities_in_store) -> None:
    sales_people = [
        e for e in all_entities_in_store["employees"] if e["department_name"] == "sales"
    ]
    assert all(
        [
            # Entity has additional auto-increment IDs and default values
            expected.items() <= entity.items()
            for entity, expected in zip(
                result[DatastoreListStep.ENTITIES],
                sales_people,
            )
        ]
    )


def test_list_all(testing_data_store_with_data, default_datastore_content):
    step = DatastoreListStep(testing_data_store_with_data, "employees")
    check_input_output_descriptors(step, {}, {DatastoreListStep.ENTITIES: ListProperty})
    result = run_step_and_return_outputs(step)
    assert all(
        [
            # Entity has additional auto-increment IDs and default values
            expected.items() <= entity.items()
            for entity, expected in zip(
                result[DatastoreListStep.ENTITIES],
                default_datastore_content["employees"],
            )
        ]
    )


def test_list_with_filtering(testing_data_store_with_data, default_datastore_content):
    step = DatastoreListStep(
        testing_data_store_with_data, "employees", where={"department_name": "sales"}
    )
    check_input_output_descriptors(step, {}, {DatastoreListStep.ENTITIES: ListProperty})
    result = run_step_and_return_outputs(step)
    _check_sales_people_in_result(result, default_datastore_content)


def test_list_with_limit(testing_data_store_with_data):
    LIMIT = 2
    step = DatastoreListStep(testing_data_store_with_data, "employees", limit=LIMIT)
    check_input_output_descriptors(step, {}, {DatastoreListStep.ENTITIES: ListProperty})
    result = run_step_and_return_outputs(step)
    assert len(result[DatastoreListStep.ENTITIES]) <= LIMIT


def test_list_with_error_on_unpack(testing_data_store_with_data):
    with pytest.raises(
        ValueError, match="Set limit to 1 when using unpack_single_entity_from_list .*"
    ):
        DatastoreListStep(
            testing_data_store_with_data, "employees", unpack_single_entity_from_list=True
        )

    with pytest.raises(
        ValueError, match="Set limit to 1 when using unpack_single_entity_from_list .*"
    ):
        DatastoreListStep(
            testing_data_store_with_data,
            "employees",
            limit=3,
            unpack_single_entity_from_list=True,
        )


def test_parametrized_list_default_input_descriptors(
    testing_data_store_with_data, default_datastore_content
):
    step = DatastoreListStep(
        testing_data_store_with_data,
        "{{entity}}",
        where={"{{stringcol}}": "{{somevalue}}"},
    )
    check_input_output_descriptors(
        step,
        {"entity": StringProperty, "stringcol": StringProperty, "somevalue": StringProperty},
        {DatastoreListStep.ENTITIES: ListProperty},
    )
    result = run_step_and_return_outputs(
        step,
        inputs={
            "entity": "employees",
            "stringcol": "department_name",
            "somevalue": "sales",
        },
    )
    _check_sales_people_in_result(result, default_datastore_content)


def test_unpack_single_entity_from_list(testing_data_store_with_data, default_datastore_content):
    step = DatastoreListStep(
        testing_data_store_with_data,
        "employees",
        where={"name": "{{somevalue}}"},
        limit=1,
        unpack_single_entity_from_list=True,
    )
    check_input_output_descriptors(
        step, {"somevalue": StringProperty}, {DatastoreListStep.ENTITIES: DictProperty}
    )
    result = run_step_and_return_outputs(
        step,
        inputs={
            "somevalue": "Mike Swat",
        },
    )
    assert result[DatastoreListStep.ENTITIES]["name"] == "Mike Swat"

    with pytest.raises(RuntimeError):
        run_step_and_return_outputs(
            step,
            inputs={
                "somevalue": "Nonexistent employee",
            },
        )


def test_parametrized_list_custom_input_descriptors(
    testing_data_store_with_data, default_datastore_content
):
    step = DatastoreListStep(
        testing_data_store_with_data,
        "{{entity}}",
        where={"{{numericalcol}}": "{{somevalue}}"},
        input_descriptors=[FloatProperty("somevalue")],
        limit=1,
        unpack_single_entity_from_list=True,
    )
    check_input_output_descriptors(
        step,
        {"entity": StringProperty, "numericalcol": StringProperty, "somevalue": FloatProperty},
        {DatastoreListStep.ENTITIES: DictProperty},
    )
    result = run_step_and_return_outputs(
        step,
        inputs={
            "entity": "employees",
            "numericalcol": "salary",
            "somevalue": 150000.0,
        },
    )
    assert result[DatastoreListStep.ENTITIES]["name"] == "Mike Swat"


def test_error_on_templated_where_with_multiple_variables(testing_data_store_with_data):
    with pytest.raises(
        ValueError,
        match="Dictionary values in where dictionary can only contain one jinja variable at a time.*",
    ):
        DatastoreListStep(
            testing_data_store_with_data,
            "employees",
            where={"{{numericalcol}}": "{{somevalue}} {{anothervar}}"},
            input_descriptors=[FloatProperty("somevalue")],
            limit=1,
            unpack_single_entity_from_list=True,
        )


def test_list_on_numeric_where(testing_data_store_with_data):
    step = DatastoreListStep(
        testing_data_store_with_data,
        "employees",
        where={"salary": 100000.0},
    )

    # Ensures this doesn't break when where has non-string keys or values
    run_step_and_return_outputs(step)
