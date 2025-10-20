# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore._utils._templating_helpers import (
    get_variables_names_and_types_from_template,
    render_template,
)
from wayflowcore.datastore.datastore import Datastore
from wayflowcore.property import ListProperty, Property
from wayflowcore.steps.datastoresteps._utils import (
    compute_input_descriptors_from_where_dict,
    get_entity_as_dict_property,
    set_values_on_templated_where,
    validate_collection_name,
)
from wayflowcore.steps.step import Step, StepResult

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


class DatastoreListStep(Step):
    """Step that can list entities in a ``Datastore``."""

    ENTITIES = "entities"
    """str: Output key for the entities listed by this step."""

    def __init__(
        self,
        datastore: Datastore,
        collection_name: str,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        unpack_single_entity_from_list: Optional[bool] = False,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """Initialize a new ``DatastoreListStep``.

        Note
        ----

        A step has input and output descriptors, describing what values
        the step requires to run and what values it produces.

        **Input descriptors**

        By default, this step has no input descriptor.
        However, the ``collection_name`` and keys and values in the ``where``
        dictionary can be parametrized with jinja-style variables.
        By default, the inferred input descriptors will be of type string,
        but this can be overridden with the ``input_descriptors`` parameter.

        **Output descriptors**

        This step has a single output descriptor: ``DatastoreCreateStep.ENTITIES``,
        a list of dictionaries representing the retrieved entities.

        Parameters
        ----------
        datastore:
            Datastore this step operates on
        collection_name:
            Collection in the datastore manipulated by this step. Can be
            parametrized using jinja variables, and the resulting input
            descriptors will be inferred by the step.
        where:
            Filtering to be applied when retrieving entities. The dictionary
            is composed of property name and value pairs to filter by
            with exact matches. Only entities matching all conditions in
            the dictionary will be retrieved. For example, `{"name": "Fido",
            "breed": "Golden Retriever"}` will match all ``Golden Retriever``
            dogs named ``Fido``.
        limit:
            Maximum number of entities to list. By default retrieves all entities.
        unpack_single_entity_from_list:
            When limit is set to `1`, one may optionally decide to unpack
            the single entity in the list and only return a the
            dictionary representing the retrieved entity. This can be
            useful when, e.g., reading a single entity by its ID.
        input_descriptors:
            Input descriptors of the step. ``None`` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically using its static
            configuration in a best effort manner.
        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
        name:
            Name of the step.

        Examples
        --------
        >>> from wayflowcore.datastore import Entity
        >>> from wayflowcore.datastore.inmemory import InMemoryDatastore
        >>> from wayflowcore.flowhelpers import create_single_step_flow
        >>> from wayflowcore.property import StringProperty, IntegerProperty
        >>> from wayflowcore.steps.datastoresteps import DatastoreListStep

        To use this step, you need first need to create a ``Datastore``. Here, we populate it with dummy data:

        >>> document = Entity(
        ...     properties={ "id": IntegerProperty(), "content": StringProperty(default_value="Empty...") }
        ... )
        >>> datastore = InMemoryDatastore({"documents": document})
        >>> dummy_data = [
        ...     {"id": 2, "content": "The rat the cat the dog bit chased escaped."},
        ...     {"id": 3, "content": "More people have been to Russia than I have."}
        ... ]
        >>> datastore.create("documents", dummy_data)
        [{'content': 'The rat the cat the dog bit chased escaped.', 'id': 2}, {'content': 'More people have been to Russia than I have.', 'id': 3}]

        Now you can use this ``Datastore`` in a ``DatastoreListStep``

        >>> datastore_list_flow = create_single_step_flow(DatastoreListStep(datastore, "documents"))
        >>> conversation = datastore_list_flow.start_conversation()
        >>> execution_status = conversation.execute()
        >>> execution_status.output_values
        {'entities': [{'content': 'The rat the cat the dog bit chased escaped.', 'id': 2}, {'content': 'More people have been to Russia than I have.', 'id': 3}]}

        You can parametrize inputs to the step if required; this is done via variable templating.
        Other configurations allow you to control the size and type of the output. Note that by
        default, all variables you define here are assumed to be of type string; specify the exact
        type you need via the `input_descriptors` parameter:

        >>> datastore_list_flow = create_single_step_flow(
        ...     DatastoreListStep(
        ...         datastore,
        ...         collection_name="{{entity_to_list}}",
        ...         where={"id": "{{target_id}}"},
        ...         limit=1,
        ...         unpack_single_entity_from_list=True,
        ...         input_descriptors=[IntegerProperty("target_id")]
        ...     )
        ... )
        >>> conversation = datastore_list_flow.start_conversation({"entity_to_list": "documents", "target_id": 2})
        >>> execution_status = conversation.execute()
        >>> execution_status.output_values
        {'entities': {'content': 'The rat the cat the dog bit chased escaped.', 'id': 2}}

        """
        validate_collection_name(collection_name, datastore)
        self.datastore = datastore
        self.collection_name = collection_name
        # Filtering keys are validated at step execution time, they may contain jinja variables
        self.where = where
        if unpack_single_entity_from_list and limit != 1:
            raise ValueError(
                "Set limit to 1 when using unpack_single_entity_from_list to ensure a single "
                "entity is retrieved on execution of this step."
            )
        self.limit = limit
        self.unpack_single_entity_from_list = unpack_single_entity_from_list

        super().__init__(
            step_static_configuration=dict(
                datastore=datastore,
                collection_name=collection_name,
                where=where,
                limit=limit,
                unpack_single_entity_from_list=unpack_single_entity_from_list,
            ),
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        return {
            "datastore": Datastore,
            "collection_name": str,
            "where": Optional[Dict[str, Any]],  # type: ignore
            "limit": int,
            "unpack_single_entity_from_list": int,
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        datastore: Datastore,
        collection_name: str,
        where: Optional[Dict[str, Any]],
        limit: Optional[int],
        unpack_single_entity_from_list: bool,
    ) -> List[Property]:
        input_properties = get_variables_names_and_types_from_template(collection_name)
        input_properties.extend(compute_input_descriptors_from_where_dict(where))

        return input_properties

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        datastore: Datastore,
        collection_name: str,
        where: Optional[Dict[str, Any]],
        limit: Optional[int],
        unpack_single_entity_from_list: bool,
    ) -> List[Property]:
        if unpack_single_entity_from_list:
            return [get_entity_as_dict_property(cls.ENTITIES)]
        else:
            return [ListProperty(name=cls.ENTITIES, item_type=get_entity_as_dict_property())]

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        collection_name = render_template(self.collection_name, inputs)
        if self.where is not None:
            where = set_values_on_templated_where(self.where, inputs, self.input_descriptors)
        else:
            where = None
        listed_entities = self.datastore.list(collection_name, where, self.limit)
        if getattr(self, "unpack_single_entity_from_list", False):
            if len(listed_entities) == 0:
                raise RuntimeError(
                    "Expected list operation to return a single item, but got zero items instead."
                    "Verify step configuration and inputs to ensure the correct collection is "
                    "being searched and the correct `where` filter is being applied."
                )
            result: Any = listed_entities[0]
        else:
            result = listed_entities
        return StepResult(outputs={self.ENTITIES: result})
