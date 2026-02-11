# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
from typing import Any, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.datastore.datastore import _DEFAULT_K, Datastore
from wayflowcore.flowconversation import FlowConversation
from wayflowcore.property import AnyProperty, DictProperty, ListProperty, Property, StringProperty
from wayflowcore.steps.step import Step, StepResult

logger = logging.getLogger(__name__)


class SearchStep(Step):
    """Step to search for entities in a collection in a datastore."""

    QUERY = "query"
    """str: Input key for the query to be used to search the rows in the datastore."""
    DOCUMENTS = "retrieved_documents"
    """str: Output key for the list of retrieved documents from the ``SearchStep``."""

    def __init__(
        self,
        datastore: Datastore,
        collection_name: str,
        k: int = _DEFAULT_K,
        where: Optional[Dict[str, Any]] = None,
        columns_to_exclude: Optional[List[str]] = None,
        search_config: Optional[str] = None,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Note
        ----

        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        **Input descriptors**

        This step has a single input descriptor:

        * ``SearchStep.QUERY``: ``StringProperty()``, input query for the search.

        **Output descriptors**

        This step has a single output descriptor:

        * ``SearchStep.DOCUMENTS``: ``ListProperty(DictProperty())``, documents retrieved by the search

        Parameters
        ----------
        datastore:
            Searchable instance that contains collections with search capability.
        collection_name:
            Name of the collection within the datastore that is to be searched on.
        k:
            Upper limit on the number of records to retrieve.
        search_config:
            Optional name of the search configuration to use. If None, uses default.
        input_descriptors:
            Input descriptors of the step. ``None`` means the step will resolve the input descriptors automatically.
        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically.
        name:
            Name of the step.
        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.

        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
        Examples
        --------
        >>> import os
        >>> from wayflowcore.flowhelpers import create_single_step_flow
        >>> from wayflowcore.datastore import Entity, InMemoryDatastore
        >>> from wayflowcore.embeddingmodels import VllmEmbeddingModel
        >>> from wayflowcore.property import StringProperty
        >>> from wayflowcore.search import SearchConfig, VectorRetrieverConfig
        >>> from wayflowcore.steps.searchstep import SearchStep

        >>> e5largev2_api_url = "http://" + os.environ.get("E5largev2_EMBEDDING_API_URL")
        >>> # Configure embedding model for vector search
        >>> embedding_model = VllmEmbeddingModel(base_url=e5largev2_api_url , model_id="intfloat/e5-large-v2")

        >>> # Define entity
        >>> hr_benefits = Entity(
        ...     name="HR Benefits",
        ...     description="Benefits offered by our company",
        ...     properties={
        ...         "BenefitId": StringProperty(),
        ...         "BenefitDescription": StringProperty()
        ...     }
        ... )

        >>> # Create datastore with search capability
        >>> datastore = InMemoryDatastore(
        ...     schema={"HR Benefits": hr_benefits},
        ...     search_configs=[
        ...         SearchConfig(
        ...             retriever=VectorRetrieverConfig(
        ...                 model=embedding_model,
        ...                 collection_name="HR Benefits"
        ...             )
        ...         )
        ...     ]
        ... )

        >>> # Add data
        >>> dummy_data = [
        ...     {
        ...         "BenefitId": "SALARY",
        ...         "BenefitDescription": "The yearly salary in our company. The base salary is $100,000.",
        ...     },
        ...     {
        ...         "BenefitId": "VACATION BENEFIT",
        ...         "BenefitDescription": "Our company has an Unlimited Paid-time-off (PTO) policy.",
        ...     },
        ... ]
        >>> created_table = datastore.create("HR Benefits", dummy_data)

        >>> # Create search step
        >>> step = SearchStep(
        ...     datastore=datastore,
        ...     collection_name="HR Benefits",
        ...     k=2,
        ... )

        """
        # Check if collection exists
        if hasattr(datastore, "describe"):
            schema = datastore.describe()
            if collection_name not in schema:
                raise ValueError(
                    f"Collection '{collection_name}' not found in datastore. Available collections: {list(schema.keys())}"
                )

        super().__init__(
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(
                datastore=datastore,
                collection_name=collection_name,
                k=k,
                search_config=search_config,
            ),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )
        self.datastore = datastore
        self.collection_name = collection_name
        self.k = k
        self.where = where
        self.columns_to_exclude = columns_to_exclude
        self.search_config = search_config

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, Any]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {
            "datastore": Datastore,
            "collection_name": str,
            "k": int,
            "search_config": Optional[str],
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        datastore: Datastore,
        collection_name: str,
        k: int,
        search_config: Optional[str],
    ) -> List[Property]:
        return [StringProperty(name=cls.QUERY, description="query for the retrieval")]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        datastore: Datastore,
        collection_name: str,
        k: int,
        search_config: Optional[str],
    ) -> List[Property]:
        return [
            ListProperty(
                name=cls.DOCUMENTS,
                description="retrieved documents",
                item_type=DictProperty(
                    name="inner_dict",
                    key_type=StringProperty("inner_key"),
                    value_type=AnyProperty("inner_value"),
                ),
            )
        ]

    @classmethod
    def _compute_internal_branches_from_static_config(
        cls,
        datastore: Datastore,
        collection_name: str,
        k: int,
        search_config: Optional[str],
    ) -> List[str]:
        return [cls.BRANCH_NEXT]

    @property
    def might_yield(self) -> bool:
        return False

    async def _invoke_step_async(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        """
        Invokes the ``SearchStep`` with the given inputs and conversation context.

        Parameters
        ----------
        inputs:
            Dictionary of input values to be used by the step.
        conversation:
            The current conversation context.

        Returns
        -------
        StepResult
            The result of the step invocation.
        """
        query = inputs[self.QUERY]

        documents = await self.datastore.search_async(
            collection_name=self.collection_name,
            query=query,
            search_config=self.search_config,
            k=self.k,
            where=self.where,
            columns_to_exclude=self.columns_to_exclude,
        )

        logger.debug(f"SearchStep found {len(documents)} documents for query: {query}")

        return StepResult(
            outputs={self.DOCUMENTS: documents},
            branch_name=self.BRANCH_NEXT,
        )
