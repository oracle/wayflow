# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from enum import Enum


class SimilarityMetric(str, Enum):
    """
    Enumeration of similarity metrics.

    COSINE: Cosine similarity
    EUCLIDEAN: Euclidean distance
    DOT: Dot product similarity
    """

    COSINE = "cosine_distance"
    EUCLIDEAN = "l2_distance"
    DOT = "inner_product"
