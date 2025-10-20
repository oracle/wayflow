# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore._utils._templating_helpers import get_variables_names_and_types_from_template
from wayflowcore.datastore._relational import RelationalDatastore
from wayflowcore.datastore.datastore import Datastore
from wayflowcore.property import AnyProperty, DictProperty, ListProperty, Property, StringProperty
from wayflowcore.steps.step import Step, StepResult

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


class DatastoreQueryStep(Step):
    """Step to execute a parameterized SQL query on a relational ``Datastore``
    (``OracleDatabaseDatastore``), that supports SQL queries (the specific
    SQL dialect depends on the database backing the datastore).

    This step enables safe, flexible querying of datastores using
    parameterized SQL.  Queries must use bind variables (e.g., `:customer_id`).
    String templating within queries is forbidden for security reasons;
    any such usage raises an error.
    """

    RESULT = "result"
    """str: Output key for the query result (list of dictionaries, one per row)."""

    def __init__(
        self,
        datastore: RelationalDatastore,
        query: str,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """Initialize a new ``DatastoreQueryStep``.

        Note
        ----

        A step has input and output descriptors, describing what values
        the step requires to run and what values it produces.

        **Input descriptors**

        By default, this step has a single input descriptor.
        ``bind_variables`` is a dictionary mapping variable names in the
        SQL query to their value at execution time.

        **Output descriptors**

        This step has a single output descriptor: ``DatastoreQueryStep.RESULT``,
        the query result rows, with each row represented as a dictionary
        mapping column names to their values.

        .. warning::

            While the input descriptor maps the bound variable name to a
            type AnyProperty to offer maximum flexibility, runtime
            validation will be performed to assess if the provided values
            are valid bind variables, and whether they match the expected
            type in the query.
            You may override the default input descriptor to specialize
            it to the bind variables in your query, to benefit from
            additional static validation (see example below).

        Parameters
        ----------
        datastore:
            The ``Datastore`` to execute the query against.
        query:
            SQL query string using bind variables (e.g., ``SELECT * FROM table WHERE id = :val``).
            String templating/interpolation is forbidden and will raise an exception.

            .. important::

                The provided query will be executed with the session user's privileges
                (the user configured in the datastore's connection config). SQL queries should be
                designed carefully, to ensure their correctness prior to execution.

        input_descriptors:
            Input descriptors of the step. ``None`` means the step will resolve the input
            descriptors automatically.
        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically
            using its static configuration in a best effort manner.
        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in
            the conversation input/output dictionary.
        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in
            the conversation input/output dictionary.
        name:
            Name of the step.

        Notes
        -----
        - Bind variable values are passed in the input as a dictionary with key "bind_variables".
        - Output is always a list of dictionaries (row-oriented).

        Examples
        --------
        >>> from wayflowcore.datastore import OracleDatabaseDatastore, MTlsOracleDatabaseConnectionConfig
        >>> from wayflowcore.steps.datastoresteps import DatastoreQueryStep
        >>> from wayflowcore.datastore import Entity
        >>> from wayflowcore.flowhelpers import create_single_step_flow
        >>> from wayflowcore.property import FloatProperty, ObjectProperty, StringProperty, IntegerProperty

        We start by defining the entity of interest in the datastore. We assume here that an employees table
        already exists in the target database:

        >>> employees = Entity(
        ...     properties={
        ...         "ID": IntegerProperty(),
        ...         "name": StringProperty(),
        ...         "email": StringProperty(),
        ...         "department_name": StringProperty(),
        ...         "department_area": StringProperty(),
        ...         "salary": FloatProperty(default_value=0.1),
        ...     },
        ... )

        Next, we can connect to the Oracle Database. For connection configuration options see
        ``OracleDatabaseConnectionConfig``:

        >>> datastore = OracleDatabaseDatastore({"employees": employees}, database_connection_config)

        We can create the ``DatastoreQueryStep`` to execute a query structure that cannot
        be modelled, for example, by a ``DatastoreListStep``:

        >>> datastore_query_flow = create_single_step_flow(
        ...     DatastoreQueryStep(
        ...         datastore,
        ...         "SELECT email, salary FROM employees WHERE department_name = :department OR salary < :salary"
        ...     )
        ... )
        >>> conversation = datastore_query_flow.start_conversation({"bind_variables": {"salary": 100000, "department": "reception"}})
        >>> execution_status = datastore_query_flow.execute(conversation)
        >>> execution_status.output_values
        {'result': [{'email': 'pam@dudemuffin.com', 'salary': 95000.0}]}

        To ensure the bind variables will not create any issues at runtime, we may specialize
        the default input descriptor to exactly match the types and values of bound variables in
        the query:

        >>> datastore_query_flow = create_single_step_flow(
        ...     DatastoreQueryStep(
        ...         testing_oracle_data_store_with_data,
        ...         "SELECT email, salary FROM employees WHERE department_name = :depname OR salary < :salary",
        ...         input_descriptors=[
        ...             ObjectProperty(
        ...                 "bind_variables",
        ...                 properties={
        ...                     "salary": FloatProperty(),
        ...                     "depname": StringProperty()
        ...                 }
        ...             )
        ...         ]
        ...     )
        ... )

        Inputs to this step can now be validated before the step is executed:

        >>> conversation = datastore_query_flow.start_conversation(
        ...     {"bind_variables": {"salary": "1", "depname": "sales"}}
        ... )  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        TypeError: The input passed: `{'salary': '1', 'depname': 'sales'}` of type `dict` is not of the expected type ...

        """
        super().__init__(
            step_static_configuration=dict(datastore=datastore, query=query),
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )

        self.datastore = datastore
        if get_variables_names_and_types_from_template(query):
            raise ValueError(
                "String templating in SQL queries is a security risk. Use bind variables instead."
            )
        self.query = query

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {
            "datastore": Datastore,
            "query": str,
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        datastore: Datastore,
        query: str,
    ) -> List[Property]:
        # Accept all bind variables as a single dictionary input to prevent potential
        # issues with regex identifying the bind variable names
        return [
            DictProperty(
                name="bind_variables",
                key_type=StringProperty(),
                value_type=AnyProperty(),
            )
        ]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        datastore: Datastore,
        query: str,
    ) -> List[Property]:
        return [
            ListProperty(
                cls.RESULT,
                item_type=DictProperty(key_type=StringProperty(), value_type=AnyProperty()),
            )
        ]

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        result = self.datastore.query(self.query, bind=inputs["bind_variables"])
        return StepResult(outputs={self.RESULT: result})
