# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import copy

import pytest
import yaml

from wayflowcore._threading import get_threadpool
from wayflowcore.datastore import Datastore, InMemoryDatastore, nullable
from wayflowcore.datastore.entity import Entity
from wayflowcore.datastore.oracle import OracleDatabaseDatastore, TlsOracleDatabaseConnectionConfig
from wayflowcore.exceptions import (
    DatastoreConstraintViolationError,
    DatastoreEntityError,
    DatastoreError,
    DatastoreKeyError,
    DatastoreTypeError,
)
from wayflowcore.property import DictProperty, FloatProperty, IntegerProperty, StringProperty
from wayflowcore.serialization.serializer import autodeserialize, serialize
from wayflowcore.warnings import SecurityWarning

from .conftest import (
    cleanup_oracle_datastore,
    get_basic_office_entities,
    get_default_datastore_content,
    get_oracle_datastore_with_schema,
)


@pytest.fixture(
    scope="function", params=["testing_inmemory_data_store", "testing_oracle_data_store"]
)
def testing_data_store(request):
    # https://stackoverflow.com/questions/42014484/pytest-using-fixtures-as-arguments-in-parametrize
    return request.getfixturevalue(request.param)


EMPLOYEE_0 = {
    # This used to be 0, but that is not good practice:
    # https://docs.oracle.com/cd/E17952_01/mysql-5.7-en/sql-mode.html#sqlmode_no_auto_value_on_zero
    "ID": 45,
    "name": "Dwayne Chute",
    "email": "dwayne@dudemuffin.com",
    "department_area": "Utica, NY",
    "department_name": "sales",
    "salary": 120000.0,
}


def test_basic_operations(testing_data_store: Datastore):
    assert len(testing_data_store.list("employees")) == 0
    assert len(testing_data_store.list("departments")) == 0

    new_joiner = testing_data_store.create("employees", EMPLOYEE_0)
    assert new_joiner == EMPLOYEE_0

    joe = {
        "ID": 1,
        "name": "Joe Happens",
        "email": "joe@dudemuffin.com",
        "department_area": "Utica, NY",
        "department_name": "sales",
    }
    pam = {
        "ID": 2,
        "name": "Pamela Beefly",
        "email": "pam@dudemuffin.com",
        "department_area": "Utica, NY",
        "department_name": "reception",
    }

    more_new_joiners = testing_data_store.create("employees", [joe, pam])
    joe_salary, pam_salary = [person.pop("salary") for person in more_new_joiners]
    assert joe_salary == 0.1 and pam_salary == 0.1
    assert more_new_joiners == [joe, pam]

    # We want to ensure results are JSON serializable to be able to return
    # these as tool results
    json_serialized_result = yaml.safe_dump(more_new_joiners)
    assert "!!" not in json_serialized_result

    promoted_employees = testing_data_store.update(
        "employees", where={"salary": 0.1}, update={"salary": 100000.0}
    )
    joe_salary, pam_salary = [person.pop("salary") for person in promoted_employees]
    assert joe_salary == 100000.0 and pam_salary == 100000.0
    assert promoted_employees == [joe, pam], "The entities have changed other properties?"
    json_serialized_result = yaml.safe_dump(promoted_employees)
    assert "!!" not in json_serialized_result

    promoted_employees = testing_data_store.update(
        "employees", where={"ID": 5}, update={"salary": 100000.0}
    )
    assert promoted_employees == []

    testing_data_store.delete("employees", where={"ID": 1})
    current_employees = testing_data_store.list("employees")
    assert len(current_employees) == 2
    json_serialized_result = yaml.safe_dump(current_employees)
    assert "!!" not in json_serialized_result

    mike = {  # this is just for historical accuracy
        "ID": 3,
        "name": "Mike Swat",
        "email": "mikeswat@dudemuffin.com",
        "department_area": "Utica, NY",
        "department_name": "sales",
        "salary": 150000.0,
    }
    testing_data_store.create("employees", mike)
    testing_data_store.create(
        "departments",
        {
            "department_name": "sales",
            "area": "Utica, NY",
            "regional_manager": 3,
            "assistant_to_the_regional_manager": 45,
        },
    )


def test_nullable_property(testing_data_store: Datastore):
    _ = testing_data_store.create("employees", EMPLOYEE_0)
    department_without_optional_manager = {
        "department_name": "reception",
        "area": "Utica, NY",
        "regional_manager": 45,
    }
    new_department = testing_data_store.create("departments", department_without_optional_manager)
    assert new_department["assistant_to_the_regional_manager"] is None


def test_multiple_datastores_in_same_process():
    datastore_1 = InMemoryDatastore(
        get_basic_office_entities(),
    )

    datastore_2 = InMemoryDatastore(
        get_basic_office_entities(),
    )

    employee = {
        "ID": 432,
        "name": "Oscar the Grouch",
        "email": "oscarthegrouch@dudemuffin.com",
        "department_area": "Utica, NY",
        "department_name": "accounting",
    }

    _ = datastore_1.create("employees", employee)

    assert len(datastore_1.list("employees")) == 1
    assert len(datastore_2.list("employees")) == 0

    dept = {
        "department_name": "accounting",
        "area": "Utica, NY",
        "regional_manager": 1,
    }

    employee = {
        "ID": 1,  # verify no PK violation
        "name": "Devin DaPone",
        "email": "DevinDaPone@dudemuffin.com",
        "department_area": "Utica, NY",
        "department_name": "accounting",
    }

    _ = datastore_2.create("employees", employee)
    _ = datastore_2.create("departments", dept)


def test_in_memory_serialization_deserialization(testing_inmemory_data_store):
    test_basic_operations(testing_inmemory_data_store)
    datastore_as_str = serialize(testing_inmemory_data_store)

    reloaded_datastore = autodeserialize(datastore_as_str)
    test_basic_operations(reloaded_datastore)


def test_oracle_serialization_deserialization(testing_oracle_data_store):
    test_basic_operations(testing_oracle_data_store)
    with pytest.warns(SecurityWarning):
        datastore_as_str = serialize(testing_oracle_data_store)
    assert "user" not in datastore_as_str
    assert "password" not in datastore_as_str

    with pytest.raises(
        TypeError, match="OracleDatabaseConnectionConfig is a security sensitive configuration"
    ):
        autodeserialize(datastore_as_str)


@pytest.mark.parametrize("salary_value", ["N/A", 4, {"huh?|"}])
def test_data_type_validation(salary_value, testing_data_store: Datastore):
    if salary_value == 4 and isinstance(testing_data_store, OracleDatabaseDatastore):
        pytest.skip("Oracle Database supports casting of integer to float")
    with pytest.raises(DatastoreEntityError):
        employee_with_broken_salary = copy.copy(EMPLOYEE_0) | {"salary": salary_value}
        testing_data_store.create("employees", employee_with_broken_salary)


def test_missing_data_validation(testing_data_store: Datastore):
    with pytest.raises(ValueError):
        # TODO: This error is hard to debug because validation on properties is a boolean method
        emp = copy.copy(EMPLOYEE_0)
        emp.pop("ID")  # For oracle DB this is an auto-increment ID
        emp.pop("department_name")
        testing_data_store.create("employees", emp)


def test_invalid_entities_in_update_and_create(testing_data_store: Datastore):
    with pytest.raises(DatastoreEntityError):
        testing_data_store.update("employees", where={"ID": 4}, update={"huh": 32})
    with pytest.raises(DatastoreEntityError):
        testing_data_store.update("employees", where={"ID": 4}, update={"salary": "thirtytwo"})
    # InMemoryDatastore will say "this entity is not valid given what you defined it should be"
    # Database will say: constraint violation error because ID cannot be NULL
    with pytest.raises((DatastoreEntityError, DatastoreConstraintViolationError)):
        testing_data_store.create("employees", entities={"salary": 32})


def test_invalid_entities_in_update_and_create_where_db_does_not_raise(
    testing_inmemory_data_store: InMemoryDatastore,
):
    with pytest.raises(DatastoreEntityError):
        testing_inmemory_data_store.create(
            "employees", entities=copy.copy(EMPLOYEE_0) | {"huh": 32}
        )
    with pytest.raises(DatastoreEntityError):
        # Property validation is stricter in WayFlow than it is in the DB (Integers can be cast up to Float)
        testing_inmemory_data_store.update("employees", where={"ID": 4}, update={"salary": 4})


def test_invalid_where_clause(testing_inmemory_data_store_with_data: Datastore):
    with pytest.raises(DatastoreEntityError):
        testing_inmemory_data_store_with_data.update(
            "employees", where={"huh": 4}, update={"ID": 32}
        )
    with pytest.raises(DatastoreEntityError):
        testing_inmemory_data_store_with_data.list("employees", where={"huh": 4})
    with pytest.raises(DatastoreEntityError):
        testing_inmemory_data_store_with_data.delete("employees", where={"huh": 4})
    with pytest.raises(DatastoreEntityError):
        testing_inmemory_data_store_with_data.update(
            "employees", where={"ID": "hihi"}, update={"salary": 32}
        )
    with pytest.raises(DatastoreEntityError):
        testing_inmemory_data_store_with_data.list("employees", where={"ID": "hihi"})
    with pytest.raises(DatastoreEntityError):
        testing_inmemory_data_store_with_data.delete("employees", where={"ID": "hihi"})


def test_methods_when_no_matches(testing_inmemory_data_store_with_data: Datastore):
    list_before = testing_inmemory_data_store_with_data.list("employees")
    testing_inmemory_data_store_with_data.delete("employees", {})
    assert list_before == testing_inmemory_data_store_with_data.list("employees")

    testing_inmemory_data_store_with_data.update("employees", {}, {"salary": 3.4})
    assert list_before == testing_inmemory_data_store_with_data.list("employees")

    assert testing_inmemory_data_store_with_data.list("employees", {"ID": -1}) == []


def test_access_to_nonexistent_collection(testing_inmemory_data_store_with_data: Datastore):
    with pytest.raises(DatastoreKeyError):
        testing_inmemory_data_store_with_data.list("products")
    with pytest.raises(DatastoreKeyError):
        testing_inmemory_data_store_with_data.delete("products", where={})
    with pytest.raises(DatastoreKeyError):
        testing_inmemory_data_store_with_data.update("product", where={}, update={})
    with pytest.raises(DatastoreKeyError):
        testing_inmemory_data_store_with_data.create("product", entities={})


def test_database_with_threadpool(testing_data_store: Datastore):
    """This test ensures we can run the datastore operations in a map step.

    Consistency and validation of order of operations is left to the database.
    """

    entities = get_default_datastore_content()

    def create(entity):
        return testing_data_store.create("employees", entity)

    all_outputs = get_threadpool().execute(func=create, items=entities["employees"])
    assert all_outputs == entities["employees"]


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM EMPLOYEES WHERE",  # Simple syntax error
        "SELECT ID AS :bindvar FROM EMPLOYEES",  # Illegal use of bind variables
        "SELECT {{bindvar}} FROM EMPLOYEES",
        "SELECT {bindvar} FROM EMPLOYEES",
        "SELECT * FROM EMPLOYEES WHERE ID = @bindvar",
        "SELECT * FROM EMPLOYEES WHERE ID = ${bindvar}",
        "SELECT * FROM EMPLOYEES WHERE ID = `bindvar`",
    ],
)
def test_invalid_query_patterns(query, testing_oracle_data_store: OracleDatabaseDatastore):
    with pytest.raises(DatastoreError):
        testing_oracle_data_store.query(query, bind={"bindvar": "; DROP TABLE EMPLOYEES; --"})


def test_any_type_in_bind_var(testing_oracle_data_store: OracleDatabaseDatastore):
    query = "SELECT * FROM EMPLOYEES WHERE ID = :bindvar"

    with pytest.raises(DatastoreError):
        # This fails because of not supported type (dictionary)
        testing_oracle_data_store.query(query, bind={"bindvar": {"bla": "I am an object"}})

    class MyCustomID:
        def __init__(self, id: int) -> None:
            self.id = id

    with pytest.raises(DatastoreError):
        # This fails because of not supported type (custom class)
        testing_oracle_data_store.query(query, bind={"bindvar": MyCustomID(1)})

    with pytest.raises(DatastoreError):
        # This fails because the bound variable is supposed to be number, not binary
        testing_oracle_data_store.query(query, bind={"bindvar": b"4352345q3wtsdfcvd"})


def test_oracle_connection_error():
    connection_config = TlsOracleDatabaseConnectionConfig("myuser", "42", "mydatabase")
    with pytest.raises(DatastoreError):
        OracleDatabaseDatastore({"planet": Entity(properties={})}, connection_config)


def test_oracle_column_type_mapping():
    """This test ensures that the Oracle DB datastore can correctly map
    WayFlow property types to Oracle column types (VARCHAR, CLOB, NUMBER),
    and that non-supported types (e.g., BLOB) that are not specified in
    the Entity do not raise an error.
    """
    ddl = [
        "DROP TABLE IF EXISTS PRODUCTS cascade constraints",
        """
        CREATE TABLE PRODUCTS (
            ID NUMBER PRIMARY KEY,
            TITLE NVARCHAR2(255) NOT NULL,
            DESCRIPTION CLOB,
            PRICE NUMBER(10,2) DEFAULT 0.1 NOT NULL,
            CATEGORY CHAR(3) NULL,
            RESTOCK DATE NULL,
            CREATED TIMESTAMP NULL,
            UPDATED TIMESTAMP WITH TIME ZONE NULL,
            BINARYCOL BLOB NULL
        ) \
    """,
    ]
    product = Entity(
        properties={
            "ID": IntegerProperty(description="Unique product identifier"),
            "title": StringProperty(description="Brief summary of the product"),
            "description": StringProperty(),
            "price": FloatProperty(default_value=0.1),
            "category": nullable(StringProperty()),
        },
    )
    try:
        datastore = get_oracle_datastore_with_schema(ddl, {"products": product})
        assert datastore.list("products") == []
    finally:
        cleanup_oracle_datastore(ddl=["DROP TABLE IF EXISTS PRODUCTS cascade constraints"])


def test_oracle_json_columns(caplog):
    """This test verifies that we gracefully handle scenarios that SQLalchemy does not support
    (i.e., JSON columns).

    We already raise an appropriate error if users try to configure a JSON column via a DictProprty,
    or some other property that doesn't fit the JSON type itself.

    We also need to additionally ensure that the schema validation does not raise errors/warnings if
    other columns in the schema (not mapped by the user's Entity are referenced)
    """
    ddl = [
        "DROP TABLE IF EXISTS PRODUCTS cascade constraints",
        """
        CREATE TABLE PRODUCTS (
            ID NUMBER PRIMARY KEY,
            TITLE NVARCHAR2(255) NOT NULL,
            DETAILS JSON
        ) \
    """,
    ]
    product = Entity(
        properties={
            "ID": IntegerProperty(description="Unique product identifier"),
            "title": StringProperty(description="Brief summary of the product"),
            "details": DictProperty(description="A JSON with all the product details"),
        },
    )

    product_slim = Entity(
        properties={
            "ID": IntegerProperty(description="Unique product identifier"),
            "title": StringProperty(description="Brief summary of the product"),
        },
    )

    product_with_json_as_str = Entity(
        properties={
            "ID": IntegerProperty(description="Unique product identifier"),
            "title": StringProperty(description="Brief summary of the product"),
            "details": StringProperty(description="A JSON with all the product details"),
        },
    )
    try:
        with pytest.raises(
            DatastoreTypeError,
            match="is not supported as a column type for the Datastore. Supported property types are",
        ):
            _ = get_oracle_datastore_with_schema(ddl, {"products": product})
            assert (
                "Suppressed warning during database inspection: Did not recognize type 'JSON' of column 'details'"
                in caplog.text
            )

        with pytest.raises(
            DatastoreTypeError, match="Mismatching types found in property definition and database."
        ):
            _ = get_oracle_datastore_with_schema(ddl, {"products": product_with_json_as_str})
            assert (
                "Suppressed warning during database inspection: Did not recognize type 'JSON' of column 'details'"
                in caplog.text
            )

        # If the datastore schema doesn't reference any JSON column, then this should work without warnings
        _ = get_oracle_datastore_with_schema(ddl, {"products": product_slim})
        assert (
            "Suppressed warning during database inspection: Did not recognize type 'JSON' of column 'details'"
            in caplog.text
        )
    finally:
        cleanup_oracle_datastore(ddl=["DROP TABLE IF EXISTS PRODUCTS cascade constraints"])
