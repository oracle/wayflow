# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from wayflowcore.templates.template import PromptTemplate
from wayflowcore.transforms import RemoveEmptyNonUserMessageTransform

NATIVE_CHAT_TEMPLATE = PromptTemplate(
    messages=[PromptTemplate.CHAT_HISTORY_PLACEHOLDER],
    post_rendering_transforms=[RemoveEmptyNonUserMessageTransform()],
)

NATIVE_AGENT_TEMPLATE = PromptTemplate(
    messages=[
        {
            "role": "system",
            "content": "{% if custom_instruction %}{{custom_instruction}}{% endif %}",
        },
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
        {
            "role": "system",
            "content": "{% if __PLAN__ %}The current plan you should follow is the following: \n{{__PLAN__}}{% endif %}",
        },
    ],
    post_rendering_transforms=[RemoveEmptyNonUserMessageTransform()],
)
