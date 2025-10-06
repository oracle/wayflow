# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore._utils._templating_helpers import (
    get_variables_names_and_types_from_template,
    render_template,
)
from wayflowcore.datastore.datastore import Datastore
from wayflowcore.property import ListProperty, Property
from wayflowcore.steps.datastoresteps._utils import (
    check_no_reserved_names,
    compute_input_descriptors_from_where_dict,
    get_entity_as_dict_property,
    set_values_on_templated_where,
    validate_collection_name,
)
from wayflowcore.steps.step import Step, StepResult

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


class DatastoreUpdateStep(Step):
    """Step that can update entities in a ``Datastore``."""

    ENTITIES = "entities"
    """str: Output key for the entities listed by this step."""

    UPDATE = "update"
    """str: Input key for the dictionary of the updates to be made."""

    def __init__(
        self,
        datastore: Datastore,
        collection_name: str,
        where: Dict[str, Any],
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """Initialize a new ``DatastoreUpdateStep``.

        Note
        ----

        A step has input and output descriptors, describing what values
        the step requires to run and what values it produces.

        **Input descriptors**

        By default, this step has a single input descriptor, the
        dictionary of updates to be made to the entities
        (``DatastoreUpdateStep.UPDATE``).
        Additionally, the ``collection_name`` and keys and values in the ``where``
        dictionary can be parametrized with jinja-style variables.
        Use this construct sparingly, as there is no special validation
        performed on update.
        By default, the inferred input descriptors will be of type string,
        but this can be overriden with the ``input_descriptors`` parameter.

        **Output descriptors**

        This step has a single output descriptor: ``DatastoreCreateStep.ENTITIES``,
        a list of dictionaries representing the newly updated entities.


        Parameters
        ----------
        datastore:
            Datastore this step operates on
        collection_name:
            Collection in the datastore manipulated by this step. Can be
            parametrized using jinja variables, and the resulting input
            descriptors will be inferred by the step.
        where:
            Filtering to be applied when updating entities. The dictionary
            is composed of property name and value pairs to filter by
            with exact matches. Only entities matching all conditions in
            the dictionary will be updated. For example, `{"name": "Fido",
            "breed": "Golden Retriever"}` will match all ``Golden Retriever``
            dogs with name ``Fido``.

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
        >>> from wayflowcore.steps.datastoresteps import DatastoreUpdateStep

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

        Now you can use this ``Datastore`` in a ``DatastoreUpdateStep``

        >>> datastore_update_flow = create_single_step_flow(DatastoreUpdateStep(datastore, "documents", where={"id": 2}))
        >>> conversation = datastore_update_flow.start_conversation({"update": {"content": "A brand new sentence"}})
        >>> execution_status = conversation.execute()

        The output of this step will provide all the entities that were updated during the execution:

        >>> execution_status.output_values
        {'entities': [{'content': 'A brand new sentence', 'id': 2}]}

        You can parametrize inputs to the step if required; this is done via variable templating.
        Note that by default, all variables you define here are assumed to be of type string; specify
        the exact type you need via the `input_descriptors` parameter:

        >>> datastore_update_flow = create_single_step_flow(
        ...     DatastoreUpdateStep(
        ...         datastore,
        ...         collection_name="{{entity_to_list}}",
        ...         where={"id": "{{target_id}}"},
        ...         input_descriptors=[IntegerProperty("target_id")]
        ...     )
        ... )
        >>> conversation = datastore_update_flow.start_conversation({
        ...     "entity_to_list": "documents",
        ...     "target_id": 2,
        ...     "update": {"content": "Yet another content"},
        ... })
        >>> execution_status = conversation.execute()
        >>> execution_status.output_values
        {'entities': [{'content': 'Yet another content', 'id': 2}]}

        """
        validate_collection_name(collection_name, datastore)
        self.datastore = datastore
        self.collection_name = collection_name
        # Filtering keys are validated at step execution time, they may contain jinja variables
        self.where = where
        super().__init__(
            step_static_configuration=dict(
                datastore=datastore, collection_name=collection_name, where=where
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
            # Only method where this isn't None by default
            "where": Dict[str, Any],
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        datastore: Datastore,
        collection_name: str,
        where: Optional[Dict[str, Any]],
    ) -> List[Property]:
        input_properties = get_variables_names_and_types_from_template(collection_name)
        input_properties.extend(compute_input_descriptors_from_where_dict(where))
        check_no_reserved_names(input_properties, [cls.UPDATE])
        input_properties.append(get_entity_as_dict_property(cls.UPDATE))
        return input_properties

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        datastore: Datastore,
        collection_name: str,
        where: Optional[Dict[str, Any]],
    ) -> List[Property]:
        return [ListProperty(name=cls.ENTITIES, item_type=get_entity_as_dict_property())]

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        collection_name = render_template(self.collection_name, inputs)
        where = set_values_on_templated_where(self.where, inputs, self.input_descriptors)
        updated_entities = self.datastore.update(
            collection_name, where, inputs[DatastoreUpdateStep.UPDATE]
        )
        return StepResult(outputs={self.ENTITIES: updated_entities})
