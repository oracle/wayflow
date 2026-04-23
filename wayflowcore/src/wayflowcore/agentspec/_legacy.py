# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


def _resolve_legacy_configurations(serialized_config: str) -> str:
    """
    Normalize legacy Agent Spec component names before deserialization.
    """
    return serialized_config.replace(
        "PluginSwarmToolRequestAndCallsTransform",
        "PluginToolRequestAndCallsTransform",
    )
