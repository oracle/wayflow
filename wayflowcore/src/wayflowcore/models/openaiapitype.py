# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from enum import Enum


class OpenAIAPIType(str, Enum):
    """
    Enumeration of OpenAI API Types.

    chat_completions: Chat Completions API
    responses: Responses API
    """

    CHAT_COMPLETIONS = "chat_completions"
    RESPONSES = "responses"
