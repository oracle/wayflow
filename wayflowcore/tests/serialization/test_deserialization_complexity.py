# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import time

from wayflowcore import Agent
from wayflowcore.serialization.serializer import autodeserialize, serialize
from wayflowcore.swarm import Swarm


def test_deserialization_complexity(remotely_hosted_llm):
    agents = [
        Agent(llm=remotely_hosted_llm, name=f"agent_{i}", description="some agent")
        for i in range(10)
    ]
    swarm = Swarm(
        first_agent=agents[0],
        relationships=[(agent_1, agent_2) for agent_1 in agents for agent_2 in agents],
    )
    conversation = swarm.start_conversation()

    serialized_conv = serialize(conversation)
    start = time.time()
    autodeserialize(serialized_conv)
    duration = time.time() - start

    # we previously had bug in the deserialization taken several seconds
    # it takes 33 seconds without import_module cached
    # takes <1 otherwise
    assert duration < 5  # we check much longer to ensure stability
