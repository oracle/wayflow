# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import warnings
from importlib.resources import files
from typing import Dict, List, Optional

import pytest

from wayflowcore.datastore import InMemoryDatastore, OracleDatabaseDatastore
from wayflowcore.datastore.entity import Entity
from wayflowcore.datastore.inmemory import _INMEMORY_USER_WARNING
from wayflowcore.embeddingmodels import VllmEmbeddingModel
from wayflowcore.property import IntegerProperty, StringProperty, VectorProperty
from wayflowcore.search import SearchConfig, VectorConfig, VectorRetrieverConfig

from ..conftest import get_oracle_connection_config


@pytest.fixture
def entity_motorcycle_schema():
    """Entity schema for motorcycles."""
    return Entity(
        description="Motorcycles in our garage",
        properties={
            "id": IntegerProperty(description="Motorcycle ID"),
            "owner_name": StringProperty(description="Name of the owner"),
            "model_name": StringProperty(description="Motorcycle model name"),
            "description": StringProperty(description="Description of the motorcycle"),
            "hp": IntegerProperty(description="Horsepower"),
        },
    )


@pytest.fixture
def motorcycle_json_data():
    """Load motorcycles from a JSON file and return as a list of dicts."""
    with open(files("tests.search.data").joinpath("motorcycle_entities.json")) as f:
        return json.load(f)


@pytest.fixture
def inmemory_motorcycle_datastore(embedding_model, entity_motorcycle_schema, motorcycle_json_data):
    """Pre-configured in-memory datastore with motorcycles and search capability."""
    search_config = SearchConfig(
        name="search_motorcycles",
        retriever=VectorRetrieverConfig(model=embedding_model, collection_name="motorcycles"),
    )

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=f"{_INMEMORY_USER_WARNING}*")
        datastore = InMemoryDatastore(
            schema={"motorcycles": entity_motorcycle_schema}, search_configs=[search_config]
        )

    datastore.create("motorcycles", motorcycle_json_data)
    return datastore


def find_search_tool(tools, collection_name="motorcycles"):
    for tool in tools:
        if f"search_{collection_name}" in tool.name:
            return tool
    return None


def get_basic_vehicle_entities():
    motorcycles = Entity(
        description="Motorcycles in our garage",
        properties={
            "owner_name": StringProperty(description="Name of the motorcycle owner"),
            "model_name": StringProperty(description="Motorcycle model and brand"),
            "hp": IntegerProperty(description="Horsepower of the motorcycle"),
            "description": StringProperty(description="Detailed description of the motorcycle"),
            "serial_text_representation": StringProperty(
                description="Concatenated String representation of each row to generate embeddings"
            ),
            "embeddings": VectorProperty(description="Embeddings for vectors"),
        },
    )

    cars = Entity(
        description="Cars in our garage",
        properties={
            "owner_name": StringProperty(description="Name of the car owner"),
            "car_model": StringProperty(description="Car model and brand"),
            "horsepower": IntegerProperty(description="Horsepower of the car"),
            "fuel_type": StringProperty(description="Type of fuel the car uses"),
            "year": IntegerProperty(description="Manufacturing year of the car"),
            "color": StringProperty(description="Color of the car"),
            "price_usd": IntegerProperty(description="Price of the car in USD"),
            "description": StringProperty(description="Detailed description of the car"),
            "registration_number": StringProperty(description="Car's registration number"),
            "previous_owners": StringProperty(
                description="List of previous owners or 'None' if it's the first owner"
            ),
            "serial_text_representation": StringProperty(
                description="Concatenated String representation of each row to generate embeddings"
            ),
            "embeddings": VectorProperty(description="Embeddings for vectors"),
        },
    )
    return {"motorcycles": motorcycles, "cars": cars}


def get_empty_table_entities():
    empty_table = Entity(
        description="Empty Table with No Data",
        properties={
            "prop_1": StringProperty(description="Name of the motorcycle owner"),
            "prop_2": StringProperty(description="Motorcycle model and brand"),
            "prop_3": IntegerProperty(description="Horsepower of the motorcycle"),
            "prop_4": VectorProperty(description="Embeddings for vectors"),
        },
    )

    return {"empty_table": empty_table}


ORACLE_DB_DDL = [
    "DROP TABLE IF EXISTS motorcycles cascade constraints",
    "DROP TABLE IF EXISTS cars cascade constraints",
    "DROP TABLE IF EXISTS empty_table cascade constraints",
    """\
    CREATE TABLE motorcycles (
    owner_name VARCHAR2(255),
    model_name VARCHAR2(255),
    description VARCHAR2(255),
    hp INTEGER,
    serial_text_representation VARCHAR2(1023),
    embeddings VECTOR
)
""",
    """\
CREATE TABLE cars (
        owner_name VARCHAR2(255),
        car_model VARCHAR2(255),
        horsepower INTEGER,
        fuel_type VARCHAR2(50),
        year INTEGER,
        color VARCHAR2(50),
        price_usd INTEGER,
        description VARCHAR2(1000),
        registration_number VARCHAR2(100),
        previous_owners VARCHAR2(1000),
        serial_text_representation VARCHAR2(10000),
        embeddings VECTOR
)
""",
    """\
    CREATE TABLE empty_table (
    prop_1 VARCHAR2(255),
    prop_2 VARCHAR2(255),
    prop_3 INTEGER,
    prop_4 VECTOR
)
""",
]

ORACLE_DB_DDL_2 = [
    "DROP TABLE IF EXISTS motorcycles cascade constraints",
    "DROP TABLE IF EXISTS cars cascade constraints",
    "DROP TABLE IF EXISTS empty_table cascade constraints",
    """\
    CREATE TABLE motorcycles (
    owner_name VARCHAR2(255),
    model_name VARCHAR2(255),
    description VARCHAR2(255),
    hp INTEGER,
    serial_text_representation VARCHAR2(1023),
    embeddings VECTOR,
    embeddings_2 VECTOR
)
""",
    """\
CREATE TABLE cars (
        owner_name VARCHAR2(255),
        car_model VARCHAR2(255),
        horsepower INTEGER,
        fuel_type VARCHAR2(50),
        year INTEGER,
        color VARCHAR2(50),
        price_usd INTEGER,
        description VARCHAR2(1000),
        registration_number VARCHAR2(100),
        previous_owners VARCHAR2(1000),
        serial_text_representation VARCHAR2(10000),
        embeddings VECTOR,
        embeddings_2 VECTOR
)
""",
    """\
    CREATE TABLE empty_table (
    prop_1 VARCHAR2(255),
    prop_2 VARCHAR2(255),
    prop_3 INTEGER,
    prop_4 VECTOR
)
""",
]


def get_oracle_datastore_with_schema(ddl: List[str], entities: Dict[str, Entity], embedding_model):
    connection_config = get_oracle_connection_config()
    conn = connection_config.get_connection()
    for stmt in ddl:
        conn.cursor().execute(stmt)
    conn.close()
    if "motorcycles" in entities:
        search_config = SearchConfig(
            name="search_motorcycles",
            retriever=VectorRetrieverConfig(
                model=embedding_model,
                collection_name="motorcycles",
                distance_metric="cosine_distance",
            ),
        )
    else:
        search_config = SearchConfig(
            name="search_empty",
            retriever=VectorRetrieverConfig(
                model=embedding_model,
                collection_name="empty_table",
                distance_metric="cosine_distance",
            ),
        )
    return OracleDatabaseDatastore(
        entities, connection_config=connection_config, search_configs=[search_config]
    )


def get_oracle_datastore_with_multiple_search_configs_and_schema(
    ddl: List[str], entities: Dict[str, Entity], embedding_model
):
    connection_config = get_oracle_connection_config()
    conn = connection_config.get_connection()
    for stmt in ddl:
        conn.cursor().execute(stmt)
    conn.close()

    return OracleDatabaseDatastore(
        entities,
        connection_config=connection_config,
        search_configs=get_search_configs(embedding_model),
    )


def get_oracle_datastore_with_multiple_search_and_vector_configs(
    ddl: List[str], entities: Dict[str, Entity], embedding_model
):
    connection_config = get_oracle_connection_config()
    conn = connection_config.get_connection()
    for stmt in ddl:
        conn.cursor().execute(stmt)
    conn.close()

    search_configs = get_search_configs(embedding_model)
    vector_config1 = VectorConfig(model=embedding_model, collection_name="motorcycles")
    vector_config2 = VectorConfig(
        model=embedding_model, collection_name="motorcycles", vector_property="embeddings_2"
    )
    vector_config3 = VectorConfig(model=embedding_model, vector_property="embeddings")
    vector_config4 = VectorConfig(
        model=embedding_model, collection_name="cars", vector_property="embeddings"
    )
    vector_configs = [vector_config1, vector_config2, vector_config3, vector_config4]
    search_config_5 = SearchConfig(
        name="specific_search_motor_embeddings_2",
        retriever=VectorRetrieverConfig(
            vectors=vector_config2,
            model=embedding_model,
            collection_name="motorcycles",
            distance_metric="cosine_distance",
        ),
    )
    search_config_6 = SearchConfig(
        name="specific_search_cars_embeddings_2",
        retriever=VectorRetrieverConfig(
            vectors=vector_config3,
            model=embedding_model,
            collection_name="cars",
            distance_metric="cosine_distance",
        ),
    )
    search_config_7 = SearchConfig(
        name="specific_search_car_embeddings",
        retriever=VectorRetrieverConfig(
            vectors="embeddings",
            model=embedding_model,
            collection_name="cars",
            distance_metric="cosine_distance",
        ),
    )
    search_configs += [search_config_5, search_config_6, search_config_7]
    return OracleDatabaseDatastore(
        entities,
        connection_config=connection_config,
        search_configs=search_configs,
        vector_configs=vector_configs,
    )


def create_oracle_datastore_with_vector_config(
    ddl: List[str], entities: Dict[str, Entity], embedding_model
):
    connection_config = get_oracle_connection_config()
    conn = connection_config.get_connection()
    for stmt in ddl:
        conn.cursor().execute(stmt)
    conn.close()

    vector_config = VectorConfig(
        name="vector_config1", collection_name="motorcycles", vector_property="embeddings"
    )

    search_config_1 = SearchConfig(
        name="default_search",
        retriever=VectorRetrieverConfig(
            model=embedding_model,
            distance_metric="cosine_distance",
            vectors=vector_config,
        ),
    )

    return OracleDatabaseDatastore(
        entities,
        connection_config=connection_config,
        search_configs=[search_config_1],
        vector_configs=[vector_config],
    )


def cleanup_oracle_datastore(ddl: Optional[List[str]] = None):
    stmts = ddl if ddl is not None else ORACLE_DB_DDL[:3]
    connection_config = get_oracle_connection_config()
    conn = connection_config.get_connection()
    for stmt in stmts:
        conn.cursor().execute(stmt)
    conn.close()


def cleanup_datastore_content(oracle_datastore: OracleDatabaseDatastore):
    for entity in get_basic_vehicle_entities():
        oracle_datastore.delete(entity, where={})


@pytest.fixture(scope="function")
def oracle_vehicle_datastore(embedding_model):
    cleanup_oracle_datastore()
    yield get_oracle_datastore_with_schema(
        ORACLE_DB_DDL, get_basic_vehicle_entities(), embedding_model
    )
    cleanup_oracle_datastore()


@pytest.fixture(scope="function")
def oracle_empty_table_datastore(embedding_model):
    cleanup_oracle_datastore()
    yield get_oracle_datastore_with_schema(
        ORACLE_DB_DDL, get_empty_table_entities(), embedding_model
    )
    cleanup_oracle_datastore()


@pytest.fixture(scope="function")
def oracle_vehicle_multi_search_config_datastore(embedding_model):
    cleanup_oracle_datastore()
    yield get_oracle_datastore_with_multiple_search_configs_and_schema(
        ORACLE_DB_DDL, get_basic_vehicle_entities(), embedding_model
    )
    cleanup_oracle_datastore()


@pytest.fixture(scope="function")
def oracle_vehicle_multi_search_and_vector_config_datastore(embedding_model):
    cleanup_oracle_datastore()
    entities = get_basic_vehicle_entities()
    new_entities = {}
    for collection_name, entity in entities.items():
        new_properties = entity.properties.copy()
        new_properties["embeddings_2"] = VectorProperty(
            name="embeddings_2",
            description="Second column of embedding vectors",
            default_value=[],
        )
        new_entity = Entity(
            name=entity.name,
            description=entity.description,
            default_value=entity.default_value,
            properties=new_properties,
        )
        new_entities[collection_name] = new_entity

    yield get_oracle_datastore_with_multiple_search_and_vector_configs(
        ORACLE_DB_DDL_2, new_entities, embedding_model
    )
    cleanup_oracle_datastore()


@pytest.fixture(scope="function")
def oracle_vehicle_vector_config_datastore(embedding_model):
    cleanup_oracle_datastore()
    yield create_oracle_datastore_with_vector_config(
        ORACLE_DB_DDL, get_basic_vehicle_entities(), embedding_model
    )
    cleanup_oracle_datastore()


@pytest.fixture(scope="function")
def populated_oracle_vehicle_vector_config_datastore(
    oracle_vehicle_vector_config_datastore: OracleDatabaseDatastore,
    embedding_model: VllmEmbeddingModel,
):
    cleanup_datastore_content(oracle_vehicle_vector_config_datastore)
    populate_oracledb_with_basic_entities(oracle_vehicle_vector_config_datastore, embedding_model)
    yield oracle_vehicle_vector_config_datastore
    cleanup_datastore_content(oracle_vehicle_vector_config_datastore)


def get_default_datastore_content_vehicles():
    with open(files("tests.search.data").joinpath("vehicle_entities.json")) as f:
        return json.load(f)


def compute_serial_text_and_embeddings(embedding_model):
    entities_json = get_default_datastore_content_vehicles()
    for dataset_name, dataset in entities_json.items():
        for entity in dataset:
            concat_str = []
            for key, value in entity.items():
                concat_str.append(f"{key}: {value}")
            serial_text = ",".join(concat_str)
            entity["serial_text_representation"] = serial_text
            entity["embeddings"] = embedding_model.embed(
                data=[entity["serial_text_representation"]]
            )[0]
    return entities_json


def populate_with_basic_entities(datastore: InMemoryDatastore, embedding_model: VllmEmbeddingModel):
    entities_json = compute_serial_text_and_embeddings(embedding_model)
    datastore.create("motorcycles", entities_json["motorcycles"])
    datastore.create("cars", entities_json["cars"])


def populate_oracledb_with_basic_entities(
    datastore: OracleDatabaseDatastore, embedding_model: VllmEmbeddingModel
):
    entities_json = compute_serial_text_and_embeddings(embedding_model)
    datastore.create("motorcycles", entities_json["motorcycles"])
    datastore.create("cars", entities_json["cars"])


@pytest.fixture(scope="function")
def populated_oracle_vehicle_datastore(
    oracle_vehicle_datastore: OracleDatabaseDatastore,
    embedding_model: VllmEmbeddingModel,
):
    cleanup_datastore_content(oracle_vehicle_datastore)
    populate_oracledb_with_basic_entities(oracle_vehicle_datastore, embedding_model)
    yield oracle_vehicle_datastore
    cleanup_datastore_content(oracle_vehicle_datastore)


@pytest.fixture(scope="function")
def populated_oracle_vehicle_multi_search_config_datastore(
    oracle_vehicle_multi_search_config_datastore: OracleDatabaseDatastore,
    embedding_model: VllmEmbeddingModel,
):
    cleanup_datastore_content(oracle_vehicle_multi_search_config_datastore)
    populate_oracledb_with_basic_entities(
        oracle_vehicle_multi_search_config_datastore,
        embedding_model,
    )
    yield oracle_vehicle_multi_search_config_datastore
    cleanup_datastore_content(oracle_vehicle_multi_search_config_datastore)


def get_search_configs(embedding_model):
    search_config_1 = SearchConfig(
        name="default_search",
        retriever=VectorRetrieverConfig(model=embedding_model, distance_metric="cosine_distance"),
    )

    search_config_2 = SearchConfig(
        name="specific_search_motor",
        retriever=VectorRetrieverConfig(
            model=embedding_model, collection_name="motorcycles", distance_metric="cosine_distance"
        ),
    )

    search_config_3 = SearchConfig(
        name="specific_search_car_cosine",
        retriever=VectorRetrieverConfig(
            model=embedding_model, collection_name="cars", distance_metric="cosine_distance"
        ),
    )

    search_config_4 = SearchConfig(
        name="specific_search_car_l2",
        retriever=VectorRetrieverConfig(
            model=embedding_model, collection_name="cars", distance_metric="l2_distance"
        ),
    )
    return [search_config_1, search_config_2, search_config_3, search_config_4]


@pytest.fixture
def populated_inmemory_vehicle_datastore(embedding_model):
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=f"{_INMEMORY_USER_WARNING}*")
        datastore = InMemoryDatastore(
            get_basic_vehicle_entities(), search_configs=get_search_configs(embedding_model)
        )
    populate_with_basic_entities(datastore, embedding_model)
    return datastore


@pytest.fixture(scope="function")
def populated_oracle_vehicle_multi_search_and_vector_config_datastore(
    oracle_vehicle_multi_search_and_vector_config_datastore: OracleDatabaseDatastore,
    embedding_model: VllmEmbeddingModel,
):
    cleanup_datastore_content(oracle_vehicle_multi_search_and_vector_config_datastore)
    entities_json = compute_serial_text_and_embeddings(embedding_model)
    for dataset_name, dataset in entities_json.items():
        for entity in dataset:
            entity["embeddings_2"] = embedding_model.embed(
                data=[entity["serial_text_representation"]]
            )[0]

    oracle_vehicle_multi_search_and_vector_config_datastore.create(
        "motorcycles", entities_json["motorcycles"]
    )
    oracle_vehicle_multi_search_and_vector_config_datastore.create("cars", entities_json["cars"])

    yield oracle_vehicle_multi_search_and_vector_config_datastore
    cleanup_datastore_content(oracle_vehicle_multi_search_and_vector_config_datastore)
