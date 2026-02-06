# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast

import numpy as np
import numpy.typing as npt

from wayflowcore._utils.lazy_loader import LazyLoader
from wayflowcore.datastore.entity import EntityAsDictT
from wayflowcore.exceptions import DatastoreError

from .metrics import SimilarityMetric

if TYPE_CHECKING:
    # Important: do not move these imports out of the TYPE_CHECKING
    # block so long as sqlalchemy and oracledb are optional dependencies.
    # Otherwise, importing the module when they are not installed would lead to an import error.
    import oracledb
    import sqlalchemy
    import sqlalchemy.exc

else:
    oracledb = LazyLoader("oracledb")
    sqlalchemy = LazyLoader("sqlalchemy")


class VectorIndex(ABC):
    """Abstract base class for vector indices."""

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        k: int,
        metric: SimilarityMetric = SimilarityMetric.COSINE,
        where: Optional[Dict[str, Any]] = None,
        columns_to_exclude: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for k nearest neighbors with additional filtering and exclusion options."""


class OracleDatabaseVectorIndex(VectorIndex):
    """Base class for OracleDB vector indices. Acts as an interface between the Vector Index on OracleDB and Wayflow"""

    def __init__(
        self,
        engine: "sqlalchemy.Engine",
        vector_property: str,
        table: "sqlalchemy.Table",
    ):
        """Initialize the object for the vector index built in Oracle Database.

        Parameters
        ----------
        engine
            SQLAlchemy Engine to use for connection.
        vector_property
            The column name for which the Vector Index is configured.
        table
            Database table object for the table / collection present in Oracle Database
        """
        self.engine = engine
        self.table = table

        if not hasattr(self.table.c, vector_property):
            raise ValueError(f"Column '{vector_property}' does not exist in the table.")

        self.vector_column = getattr(self.table.c, vector_property)

    def search(
        self,
        query_vector: List[float],
        k: int,
        metric: SimilarityMetric = SimilarityMetric.COSINE,
        where: Optional[Dict[str, Any]] = None,
        columns_to_exclude: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for k nearest neighbors using approximate search in Oracle Database Vector Index.
        This method works even if there is no Vector Index configured in the Oracle Database.
        It is recommended to configure an Index on Oracle Database for faster and cheaper approximate search.

        Parameters
        ----------
        query_vector
            Query vector.
        k
            Number of results to return.
        metric
            Distance metric to use to get neighbours.
            It is recommended to use the same distance metric as the one used for configuring the Vector Index
            in Oracle Database. If there is a mismatch, it will be ignored by the Oracle Database.

            Metrics currently supported:
                - l2_distance (SimilarityMetric.EUCLIDEAN)
                - cosine_distance (SimilarityMetric.COSINE)
                - inner_product (SimilarityMetric.DOT)

        where
            Filter out results by specific row/column entries.
        columns_to_exclude
            Columns to exclude while returning the final results.

        Returns
        -------
        list of dict
            List of matching items.
        """

        if not hasattr(self.vector_column, metric):
            raise ValueError(f"Invalid Distance Metric specified: {metric}")

        vector_distance = getattr(self.vector_column, metric)
        if not columns_to_exclude:
            columns_to_exclude = []

        columns_to_return = [
            col
            for col in self.table.c
            if col.name not in columns_to_exclude and col != self.vector_column
        ]
        query = sqlalchemy.select(*columns_to_return)

        if where:
            for column_name, value in where.items():
                if hasattr(self.table.c, column_name):
                    column = getattr(self.table.c, column_name)
                    query = query.filter(column == value)
                else:
                    warnings.warn(
                        f"{column_name} passed through `where` method is not present in the table {self.table}",
                        UserWarning,
                    )

        with self.engine.connect() as connection:
            try:
                results = connection.execute(
                    query.order_by(vector_distance(query_vector)).fetch(
                        k, oracle_fetch_approximate=True
                    )
                )
                result_rows = results.mappings().all()
            except sqlalchemy.exc.DatabaseError as e:
                raise DatastoreError(
                    "SQL query execution failed. See stacktrace to find out more "
                    "(note: bind variables should be provided with the :varname syntax)"
                ) from e

        def _coerce_value(value: Any) -> Any:
            # Convert driver-/library-specific wrappers to plain Python objects
            # - Oracle LOBs -> read() to get bytes/str
            try:
                lob_type = getattr(oracledb, "LOB", None)
            except Exception:
                lob_type = None
            if lob_type is not None and isinstance(value, lob_type):
                try:
                    return value.read()
                except Exception:
                    return str(value)

            # Numpy scalars -> builtin Python scalars
            if isinstance(value, np.generic):
                return value.item()

            # Keep builtin/stdlib scalar types as-is; SQLAlchemy already returns Python types for most columns
            return value

        result: List[Dict[str, Any]] = []
        for row in result_rows:
            # row is a RowMapping; ensure keys are plain strings and values are plain Python objects
            result.append({str(k): _coerce_value(v) for k, v in row.items()})
        return result


class BaseInMemoryVectorIndex(VectorIndex):
    """Base class for in-memory vector indices with common functionality."""

    # Memory limit for batched computations prevents OOM errors on large datasets
    _MAX_SIMILARITY_MEMORY_CONSUMPTION_BYTES = 100000000  # 100MB

    def __init__(self, dimension: int, metric: SimilarityMetric = SimilarityMetric.COSINE):
        """Initialize the vector index.

        Parameters
        ----------
        dimension
            Dimension of the vectors.
        metric
            Distance metric to use (SimilarityMetric.COSINE, SimilarityMetric.EUCLIDEAN, SimilarityMetric.DOT).
            Must be one of the SimilarityMetric enum values.
            Default: SimilarityMetric.COSINE.
        """
        self.dimension = dimension
        self.metric = metric
        self.vectors: Optional[npt.NDArray[Any]] = None
        self.vectors_arr_size = 0
        self.items: List[Dict[str, Any]] = []  # General storage for entities
        self.num_vectors = 0

    def search(
        self,
        query_vector: List[float],
        k: int,
        metric: Optional[SimilarityMetric] = None,
        where: Optional[Dict[str, Any]] = None,
        columns_to_exclude: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for k nearest neighbors using efficient batched computation.

        Parameters
        ----------
        query_vector
            Query vector.
        k
            Number of results to return.
        metric
            Distance metric to use for search (will temporarily override the instance metric for this search call).
        where
            Filter out results by specific row/column entries.
        columns_to_exclude
            Columns to exclude while returning the final results.

        Returns
        -------
        results: List[Dict[str, Any]]
            List of matching items with scores.
        """
        # Early exit for empty index avoids unnecessary computation
        if self.vectors is None or self.num_vectors == 0 or len(self.items) == 0:
            return []

        orig_metric = self.metric

        # Compatibility: override self.metric if requested for this search only
        if metric:
            self.metric = metric

        # Convert query to numpy array
        query = np.array(query_vector, dtype=np.float32).reshape(1, -1)
        query = self._safe_normalize_vectors(query)

        # Cap k to available vectors to avoid unnecessary work
        k = min(k, self.num_vectors)

        # Compute distances based on metric using batched approach
        distances, get_highest_distances = self._compute_distances(query)

        # Use argpartition for O(n) average complexity instead of O(n log n) sort
        # Only partially sorts to find the k best elements
        if k >= self.num_vectors:
            # Return all vectors
            indices = np.arange(self.num_vectors)
        else:
            # argpartition finds k largest values without full sort
            # Get the actual distances for these indices
            # Sort only the k results
            if get_highest_distances:
                indices = np.argpartition(distances, -k)[-k:]
                top_distances = distances[indices]
                sorted_order = np.argsort(-top_distances)
                indices = indices[sorted_order]
            else:
                indices = np.argpartition(distances, k)[:k]
                top_distances = distances[indices]
                sorted_order = np.argsort(top_distances)
                indices = indices[sorted_order]

        results = self._build_results(indices, distances, columns_to_exclude=columns_to_exclude)

        # Restore original metric
        self.metric = orig_metric

        # Apply filter if there are any
        if where:
            results = [r for r in results if self._matches_filters(r, where)]

        return results

    def _matches_filters(self, entity: EntityAsDictT, where: Dict[str, Any]) -> bool:
        """Check if an entity matches the given filter criteria."""
        for key, value in where.items():
            if key not in entity or entity[key] != value:
                return False
        return True

    def _safe_normalize_vectors(self, vectors: npt.NDArray[Any]) -> np.ndarray:  # type: ignore
        """Normalize vectors for cosine similarity.

        Pre-normalizing vectors for cosine similarity allows using
        simple dot product instead of computing dot(a,b)/(||a||*||b||) at search time.
        This converts O(n*d) normalization operations to just O(d) at search time.
        """

        if self.metric == SimilarityMetric.COSINE:
            norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
            # Add small epsilon to avoid division by zero without if-checks
            return cast(npt.NDArray[np.float32], vectors / (norms + 1e-12))
        return vectors

    def _initialize_or_resize_vectors(self, num_new_vectors: int) -> None:
        """Initialize or resize the vector array with amortized growth strategy."""
        if self.vectors is None:
            # Pre-allocate 1.5x space to reduce future reallocations
            # This amortizes the cost of array growth over multiple insertions
            self.vectors_arr_size = int(num_new_vectors * 1.5)
            self.vectors = np.empty((self.vectors_arr_size, self.dimension), dtype=np.float32)
        elif self.num_vectors + num_new_vectors > self.vectors_arr_size:
            # Amortized doubling strategy for array growth
            # Ensures O(1) amortized insertion time and minimizes memory copies
            new_size = self.vectors_arr_size
            while new_size < self.num_vectors + num_new_vectors:
                new_size *= 2
            self.vectors_arr_size = new_size
            new_vectors = np.empty((self.vectors_arr_size, self.dimension), dtype=np.float32)
            new_vectors[: self.num_vectors] = self.vectors[: self.num_vectors]
            self.vectors = new_vectors

    def _compute_distances(self, query: npt.NDArray[Any]) -> Tuple[npt.NDArray[Any], bool]:
        """Compute distances between query and indexed vectors."""
        if self.vectors is None:
            raise ValueError(
                "Vectors are not initialized properly. Make sure the index build function is called to initialize the vectors"
            )
        if self.metric == SimilarityMetric.COSINE:
            # Single matrix multiplication for all distances
            # Leverages highly optimized BLAS routines in numpy
            # Since vectors are pre-normalized, dot product = cosine similarity
            # Batch size calculation to limit memory usage
            batch_size = max(
                1,
                int(
                    self._MAX_SIMILARITY_MEMORY_CONSUMPTION_BYTES
                    / (4 * self.num_vectors * self.dimension)
                ),
            )
            distances = np.matmul(
                query, self.vectors[: self.num_vectors].T, dtype=np.float32
            ).flatten()
            return distances, True  # get_highest_distances = True

        elif self.metric == SimilarityMetric.EUCLIDEAN:
            # Compute squared distances to avoid expensive sqrt operations
            # For ranking, squared distances preserve order
            # Process in batches to control memory usage for large datasets
            batch_size = max(
                1, int(self._MAX_SIMILARITY_MEMORY_CONSUMPTION_BYTES / (4 * self.dimension))
            )

            distances = np.zeros(self.num_vectors, dtype=np.float32)
            for start_idx in range(0, self.num_vectors, batch_size):
                end_idx = min(self.num_vectors, start_idx + batch_size)
                batch_vectors = self.vectors[start_idx:end_idx]
                # Efficient squared distance using vectorized operations
                diff = query - batch_vectors
                distances[start_idx:end_idx] = np.sum(diff * diff, axis=1)

            return distances, False  # get_highest_distances = False

        elif self.metric == SimilarityMetric.DOT:
            distances = np.matmul(
                query, self.vectors[: self.num_vectors].T, dtype=np.float32
            ).flatten()
            return distances, True  # get_highest_distances = True
        else:
            raise ValueError(f"Unknown metric: {self.metric}")

    def _build_results(
        self,
        indices: npt.NDArray[np.intp],
        distances: npt.NDArray[Any],
        columns_to_exclude: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Build search results from indices and distances.

        Parameters
        ----------
        indices
            Indices of matching items.
        distances
            Distance/similarity scores.
        columns_to_exclude
            Columns (keys) to exclude from the returned results.
        """
        results = []
        exclude_set = set(columns_to_exclude) if columns_to_exclude else set()
        for idx in indices:
            idx = int(idx)
            item_copy = self.items[idx].copy()

            # Remove excluded columns, but keep _score
            for key in exclude_set:
                item_copy.pop(key, None)

            # Simple score computation without expensive transformations
            # For cosine/dot: higher = more similar (no transformation needed)
            # For Euclidean: negate to convert distance to similarity
            score: float
            if self.metric == SimilarityMetric.COSINE:
                score = float(distances[idx])
            elif self.metric == SimilarityMetric.EUCLIDEAN:
                # Convert distance to similarity score
                score = -float(distances[idx])
            elif self.metric == SimilarityMetric.DOT:
                score = float(distances[idx])
            else:
                raise ValueError(
                    f"Received Unknown metric: {self.metric}, List of available metrics: {[metric for metric in SimilarityMetric]}"
                )

            # _score: Similarity score added to search results
            item_copy["_score"] = score
            results.append(item_copy)

        return results

    @abstractmethod
    def build(self, data: List[Dict[str, Any]], vector_field: Optional[str] = None) -> None:
        """Build index from data. Must be implemented by subclasses.

        Parameters
        ----------
        data
            List of items to index (entities).
        vector_field
            Field name containing vectors (required for entities).
        """

    @property
    def entities(self) -> List[Dict[str, Any]]:
        """Entities getter for accessing items."""
        return self.items

    @entities.setter
    def entities(self, value: List[Dict[str, Any]]) -> None:
        """Entities setter."""
        self.items = value


class EntityVectorIndex(BaseInMemoryVectorIndex):
    """Vector index for entity-based indexing."""

    def build(self, data: List[Dict[str, Any]], vector_field: Optional[str] = None) -> None:
        """Build index from entities with vectors.

        Parameters
        ----------
        data
            List of entities containing vectors.
        vector_field
            Name of the field containing vectors (required).

        Raises
        ------
        ValueError
            If vector_field is not provided.
        """
        if vector_field is None:
            raise ValueError("vector_field is required for EntityVectorIndex")

        # Extract vectors and filter entities that have them
        valid_items = []
        vectors_list = []

        for i, entity in enumerate(data):
            if vector_field in entity and entity[vector_field] is not None:
                vector = entity[vector_field]
                if isinstance(vector, list) and len(vector) == self.dimension:
                    valid_items.append(entity)
                    vectors_list.append(vector)

        if vectors_list:
            self.items = valid_items

            # Initialize or resize vector array
            num_new_vectors = len(vectors_list)
            self._initialize_or_resize_vectors(num_new_vectors)

            # Use float32 instead of float64 - reduces memory by 50%
            # while maintaining sufficient precision for similarity search
            vectors_array = np.array(vectors_list, dtype=np.float32)

            # Normalize vectors once during indexing for cosine similarity
            vectors_array = self._safe_normalize_vectors(vectors_array)

            if self.vectors is not None:
                self.vectors[:num_new_vectors] = vectors_array
            self.num_vectors = num_new_vectors

        else:
            self.items = []
            self.vectors = None
            self.num_vectors = 0
