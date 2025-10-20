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
from wayflowcore.property import Property
from wayflowcore.steps.datastoresteps._utils import (
    check_no_reserved_names,
    get_entity_as_dict_property,
    validate_collection_name,
)
from wayflowcore.steps.step import Step, StepResult

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


class DatastoreCreateStep(Step):
    """Step that can create a new entity in a ``Datastore``."""

    ENTITY = "entity"
    """str: Input key for the entity to be created."""

    CREATED_ENTITY = "created_entity"
    """str: Output key for the newly created entity."""

    def __init__(
        self,
        datastore: Datastore,
        collection_name: str,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """Initialize a new ``DatastoreCreateStep``.

        Note
        ----

        A step has input and output descriptors, describing what values
        the step requires to run and what values it produces.

        **Input descriptors**

        By default, this step has a single input descriptor, the new
        entity object to be created (``DatastoreCreateStep.ENTITY``).
        Additionally, the ``collection_name`` parameter may contain
        jinja-style variables that can be used to dynamically configure
        which entity is being created by the step.

        **Output descriptors**

        This step has a single output descriptor: ``DatastoreCreateStep.CREATED_ENTITY``,
        a dictionary representing the newly created entity

        Parameters
        ----------
        datastore:
            Datastore this step operates on
        collection_name:
            Collection in the datastore manipulated by this step. Can be
            parametrized using jinja variables, and the resulting input
            descriptors will be inferred by the step.
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
        >>> from wayflowcore.steps.datastoresteps import DatastoreCreateStep

        To use this step, you need first need to create a ``Datastore``:

        >>> document = Entity(
        ...     properties={ "id": IntegerProperty(), "content": StringProperty(default_value="Empty...") }
        ... )
        >>> datastore = InMemoryDatastore({"documents": document})

        Now you can use this ``Datastore`` in a ``DatastoreCreateStep``

        >>> datastore_create_flow = create_single_step_flow(DatastoreCreateStep(datastore, "documents"))
        >>> conversation = datastore_create_flow.start_conversation({"entity": {'content': 'The rat the cat the dog bit chased escaped.', 'id': 0}})
        >>> execution_status = conversation.execute()

        Since not all properties of documents are required, we can let the Datastore fill in the rest:

        >>> datastore_create_flow = create_single_step_flow(DatastoreCreateStep(datastore, "documents"))
        >>> conversation = datastore_create_flow.start_conversation({"entity": {'id': 1}})
        >>> execution_status = conversation.execute()

        You can then finally verify that the entities were indeed created:

        >>> datastore.list("documents")
        [{'content': 'The rat the cat the dog bit chased escaped.', 'id': 0}, {'content': 'Empty...', 'id': 1}]

        """
        validate_collection_name(collection_name, datastore)
        self.datastore = datastore
        self.collection_name = collection_name
        super().__init__(
            step_static_configuration=dict(datastore=datastore, collection_name=collection_name),
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
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        datastore: Datastore,
        collection_name: str,
    ) -> List[Property]:
        input_properties = get_variables_names_and_types_from_template(collection_name)
        check_no_reserved_names(input_properties, [cls.ENTITY])
        input_properties.append(get_entity_as_dict_property(cls.ENTITY))
        return input_properties

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        datastore: Datastore,
        collection_name: str,
    ) -> List[Property]:
        return [get_entity_as_dict_property(cls.CREATED_ENTITY)]

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        collection_name = render_template(self.collection_name, inputs)
        updated_entities = self.datastore.create(collection_name, inputs[self.ENTITY])
        return StepResult(outputs={self.CREATED_ENTITY: updated_entities})
