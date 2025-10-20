# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict

from wayflowcore.property import Property, StringProperty

from .chathistorycontextprovider import ChatHistoryContextProvider
from .contextprovider import ContextProvider


def get_default_context_providers() -> Dict[Property, ContextProvider]:
    """
    Returns a list of pairs of Property with corresponding context providers.
    This includes:
    - short_history
    - full_history
    - plan
    - data (optional)
    """
    return {
        StringProperty(
            "short_history", "The truncated history of messages"
        ): ChatHistoryContextProvider(n=5, output_name="short_history"),
        StringProperty("full_history", "The full history of messages"): ChatHistoryContextProvider(
            n=int(1e9), output_name="full_history"
        ),
    }
