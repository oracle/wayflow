# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import numpy as np


class Faker:
    @staticmethod
    def seed(seed):
        np.random.seed(seed)

    def seed_instance(self, seed):
        np.random.seed(seed)

    def name(self):
        return np.random.choice(
            [
                "Norma Fisher",
                "Jorge Sullivan",
                "Elizabeth Woods",
                "Susan Wagner",
                "Peter Montgomery",
                "Theodore Mcgrath",
                "Stephanie Collins",
                "Brian Hamilton",
                "Sean Green",
                "Kimberly Smith",
            ]
        )

    def company(self):
        return np.random.choice(
            [
                "Cook Inc",
                "Williams PLC",
                "Matthews-Rogers",
                "Hinton LLC",
                "Morales Ltd",
            ]
        )
