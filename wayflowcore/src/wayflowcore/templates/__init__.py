# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from .llamatemplates import LLAMA_AGENT_TEMPLATE, LLAMA_CHAT_TEMPLATE
from .nativetemplates import NATIVE_AGENT_TEMPLATE, NATIVE_CHAT_TEMPLATE
from .pythoncalltemplates import PYTHON_CALL_AGENT_TEMPLATE, PYTHON_CALL_CHAT_TEMPLATE
from .reacttemplates import REACT_AGENT_TEMPLATE, REACT_CHAT_TEMPLATE
from .template import PromptTemplate

__all__ = [
    "NATIVE_CHAT_TEMPLATE",
    "NATIVE_AGENT_TEMPLATE",
    "REACT_CHAT_TEMPLATE",
    "REACT_AGENT_TEMPLATE",
    "LLAMA_CHAT_TEMPLATE",
    "LLAMA_AGENT_TEMPLATE",
    "PYTHON_CALL_CHAT_TEMPLATE",
    "PYTHON_CALL_AGENT_TEMPLATE",
    "PromptTemplate",
]
