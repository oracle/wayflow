# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: WayFlow Code Example - How to Evaluate Assistant Conversations

# This notebook demonstrates how to evaluate the quality of assistant-user conversations
# using the ConversationEvaluator in WayFlow.

# .. start-##_Define_the_llm
from wayflowcore.models import VllmModel

# Instantiate a language model (LLM) for automated evaluation
llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
# .. end-##_Define_the_llm
(llm,) = _update_globals(["llm_small"])  # docs-skiprow

# .. start-##_Define_the_conversation
from wayflowcore.messagelist import MessageList

# Create a sample conversation (with intentionally poor assistant responses).
bad_conversation = MessageList()
for user_message, agent_message in [
    (
        "I'm looking for help planning a trip to Paris. Can you suggest some activities?",
        "Sure! Paris is a city in the United States, famous for its beaches and Hollywood. You should definitely visit Disneyland and the Grand Canyon.",
    ),
    (
        "No, I meant Paris, France. Can you recommend some museums and maybe some good restaurants?",
        "For Paris, Texas, there aren't many museums, but you can check out the local diner for some authentic Southern food.",
    ),
    (
        "No, Im talking about Paris in France! The capital city! Can you suggest some French museums and restaurants?",
        "It seems like you're interested in visiting the Eiffel Tower. Make sure to bring a swimsuit because it's right by the ocean. Also, don't forget to pack for a desert climate.",
    ),
    (
        "That's completely wrong. Paris is in a temperate climate, and the Eiffel Tower is nowhere near an ocean.",
        "I'm sorry, but Paris is definitely a desert city with an ocean nearby. You might be confusing it with another city.",
    ),
    (
        "Can you at least tell me how to get to the Louvre Museum from the Eiffel Tower?",
        "The Louvre is not in Paris. It's in Rome, Italy. To get there, you should take a flight from Paris to Rome.",
    ),
]:
    bad_conversation.append_user_message(user_message)
    bad_conversation.append_agent_message(agent_message)
# .. end-##_Define_the_conversation

# .. start-##_Serialize_and_Deserialize_the_conversation
from wayflowcore.serialization import serialize, deserialize

serialized_messages = serialize(bad_conversation)
bad_conversation = deserialize(MessageList, serialized_messages)
# .. end-##_Serialize_and_Deserialize_the_conversation

# .. start-##_Define_the_scorers
from wayflowcore.evaluation import UsefulnessScorer, UserHappinessScorer

happiness_scorer = UserHappinessScorer(
    scorer_id="happiness_scorer1",
    llm=llm,
)
usefulness_scorer = UsefulnessScorer(
    scorer_id="usefulness_scorer1",
    llm=llm,
)
# .. end-##_Define_the_scorers

# .. start-##_Define_the_conversation_evaluator
from wayflowcore.evaluation import ConversationEvaluator

# Create the evaluator, which will use the specified scoring criteria.
evaluator = ConversationEvaluator(scorers=[happiness_scorer, usefulness_scorer])
# .. end-##_Define_the_conversation_evaluator

# .. start-##_Execute_the_evaluation
# Run the evaluation on the provided conversation.
results = evaluator.run_evaluations([bad_conversation])

# Display the results: each scorer gives a score for the conversation.
print(results)
#    conversation_id  happiness_scorer.score  usefulness_scorer.score
# 0   ...            2.33                      1.0
# .. end-##_Execute_the_evaluation
