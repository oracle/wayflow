# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict, Type

from .constantcontextprovider import ConstantContextProvider
from .contextprovider import ContextProvider
from .flowcontextprovider import FlowContextProvider
from .toolcontextprovider import ToolContextProvider

__all__ = [
    "ContextProvider",
    "FlowContextProvider",
    "ToolContextProvider",
    "ConstantContextProvider",
]

_SUPPORTED_CONTEXT_PROVIDER_TYPES: Dict[str, Type[ContextProvider]] = {
    "flow": FlowContextProvider,
    "tool": ToolContextProvider,
    "constant": ConstantContextProvider,
}
