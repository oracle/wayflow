# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from collections import Counter

from wayflowcore.agentspec.components import all_deserialization_plugin, all_serialization_plugin


def test_serialization_plugins_all_have_unique_names():
    name_counter = Counter(p.plugin_name for p in all_serialization_plugin)

    most_common_name_pair = name_counter.most_common(1)
    assert len(most_common_name_pair) == 1
    most_common_name_count = most_common_name_pair[0][1]
    assert most_common_name_count == 1


def test_deserialization_plugins_all_have_unique_names():
    name_counter = Counter(p.plugin_name for p in all_deserialization_plugin)

    most_common_name_pair = name_counter.most_common(1)
    assert len(most_common_name_pair) == 1
    most_common_name_count = most_common_name_pair[0][1]
    assert most_common_name_count == 1


def test_plugins_all_have_matching_ser_deser_names():
    ser_plugin_names = {p.plugin_name for p in all_serialization_plugin}
    deser_plugin_names = {p.plugin_name for p in all_deserialization_plugin}

    assert ser_plugin_names == deser_plugin_names
