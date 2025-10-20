# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict, List

from wayflowcore.datastore.entity import Entity, EntityAsDictT
from wayflowcore.exceptions import DatastoreEntityError, DatastoreKeyError


def check_collection_name(schema: Dict[str, Entity], collection_name: str) -> None:
    """Raise an error if the collection_name is not valid in the schema.

    Parameters
    ----------
    schema :
        schema to validate against
    collection_name :
        collection name to check

    Raises
    ------
    DatastoreKeyError
        If the collection name is not part of the schema
    """
    if collection_name not in schema:
        # NOTE: do not add available collections to the error to avoid data leakage
        raise DatastoreKeyError(f"Collection name {collection_name} not found in Datastore")


def validate_entities(entity_description: Entity, entities: List[EntityAsDictT]) -> None:
    """Validate entity dictionaries provided as input to a Datastore.

    Parameters
    ----------
    entity_description : Entity
        Entity descriptor to validate against
    entities : List[EntityAsDictT]
        Entities to validate

    Raises
    ------
    DatastoreEntityError
        If any of the entities fails validation
    """
    for entity in entities:
        validate_partial_entity(entity_description, entity)
        if not entity_description.is_value_of_expected_type(entity):
            raise DatastoreEntityError(f"Invalid value found in entity {entity}")


def validate_partial_entity(entity_description: Entity, entity: EntityAsDictT) -> None:
    """Validate a partial entity dictionary composed of a subset of an
    Entity's properties.

    Parameters
    ----------
    entity_description :
        Entity descriptor to validate against
    entities :
        (Partial) entity to validate

    Raises
    ------
    DatastoreEntityError
        If the entity fails validation
    """
    for property_name, value in entity.items():
        if property_name not in entity_description.properties:
            raise DatastoreEntityError(
                f"Property name {property_name} not found in entity {entity_description.name}"
            )
        elif not entity_description.properties[property_name].is_value_of_expected_type(value):
            raise DatastoreEntityError(
                f"Value {value} ({type(value)}) invalid for property {property_name}"
            )
