# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - Build a ManagerWorkers of Agents

from typing import Annotated, Dict, Optional, Union

from wayflowcore.agent import Agent
from wayflowcore.models import VllmModel
from wayflowcore.tools import tool

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)

llm: VllmModel # docs-skiprow
(llm, ) = _update_globals(["llm_small"]) # docs-skiprow

# .. start-##_Helper_method_for_printing_conversation_messages
def print_messages(messages):
    from wayflowcore.messagelist import MessageType

    for message in messages:
        message_type = message.message_type
        prefix = (
            f"{message_type}"
            if message_type == MessageType.USER
            else f"{message_type} ({message.sender})"
        )
        content = (
            f"{message.content}"
            if message_type != MessageType.TOOL_REQUEST
            else f"{message.content.strip()}\n{message.tool_requests}"
        )
        print(f"{prefix} >>> {content}")


# .. end-##_Helper_method_for_printing_conversation_messages

# .. start-##_Specialist_tools
from wayflowcore.tools import tool

@tool
def check_refund_eligibility(
    order_id: Annotated[str, "The unique identifier for the order."],
    customer_id: Annotated[str, "The unique identifier for the customer."],
) -> Dict[str, Union[bool, float, str]]:
    """
    Checks if a given order is eligible for a refund based on company policy.

    Returns:
        A dictionary containing eligibility status and details.
        Example: {"eligible": True, "max_refundable_amount": 50.00, "reason": "Within return window"}
                 {"eligible": False, "reason": "Order past 30-day return window"}
    """
    # Simulate checking eligibility (e.g., database lookup, policy check)
    # In a real system, this would interact with backend systems.
    if "123" in order_id:  # Simulate eligible order
        return {
            "eligible": True,
            "max_refundable_amount": 50.00,
            "reason": "Within 30-day return window and item is returnable.",
        }
    elif "999" in order_id:  # Simulate ineligible order
        return {"eligible": False, "reason": "Order past 30-day return window."}
    else:  # Simulate item not found or other issue
        return {"eligible": False, "reason": "Order ID not found or invalid."}

@tool
def process_refund(
    order_id: Annotated[str, "The unique identifier for the order to be refunded."],
    amount: Annotated[float, "The amount to be refunded."],
    reason: Annotated[str, "The reason for the refund."],
) -> Dict[str, Union[bool, str]]:
    """
    Processes a refund for a specific order and amount.

    Returns:
        A dictionary confirming the refund status.
        Example: {"success": True, "refund_id": "REF_789XYZ", "message": "Refund processed successfully."}
                 {"success": False, "message": "Refund processing failed due to payment gateway error."}
    """
    # Simulate refund processing (e.g., calling a payment gateway API)
    # In a real system, this would trigger financial transactions.
    if float(amount) > 0:
        refund_id = f"REF_{order_id[:3]}{int(amount * 100)}"  # Generate a pseudo-unique ID
        return {
            "success": True,
            "refund_id": refund_id,
            "message": f"Refund of ${amount:.2f} processed successfully.",
        }
    else:
        return {"success": False, "message": "Refund amount must be greater than zero."}

# .. end-##_Specialist_tools

# .. start-##_Specialist_prompt
REFUND_SPECIALIST_SYSTEM_PROMPT = """
You are a Refund Specialist agent whose objective is to process customer refund requests accurately and efficiently based on company policy.

# Instructions
- Receive the refund request details (e.g., order ID, customer ID, reason) from the 'CustomerServiceManager'.
- Use the `check_refund_eligibility` tool to verify if the request meets the refund policy criteria using the provided order and customer IDs.
- If the check indicates eligibility, determine the correct refund amount (up to the maximum allowed from the eligibility check).
- If eligible, use the `process_refund` tool to execute the refund for the determined amount, providing order ID and reason.
- If ineligible based on the check, clearly note the reason provided by the tool.
- Report the final outcome (e.g., "Refund processed successfully, Refund ID: [ID], Amount: [Amount]", or "Refund denied: [Reason from eligibility check]") back to the 'CustomerServiceManager'.
- Do not engage in general conversation; focus solely on the refund process.
""".strip()
# .. end-##_Specialist_prompt

# .. start-##_Specialist_agent
from wayflowcore.agent import Agent

refund_specialist_agent = Agent(
    name="RefundSpecialist",
    description="Specializes in processing customer refund requests by verifying eligibility and executing the refund transaction using available tools.",
    llm=llm,
    custom_instruction=REFUND_SPECIALIST_SYSTEM_PROMPT,
    tools=[check_refund_eligibility, process_refund],
    agent_id="RefundSpecialist",  # for the `print_messages` utility function
)
# .. end-##_Specialist_agent

refund_specialist_agent.raise_exceptions = False # docs-skiprow

# .. start-##_Specialist_test
refund_conversation = refund_specialist_agent.start_conversation()
refund_conversation.append_user_message(
    "Please handle a refund request. Details: Order ID='123', Customer ID='CUST456', Reason='Item arrived damaged'."
    # "Please handle a refund request. Details: Order ID='999', Customer ID='CUST789', Reason='No longer needed'."
    # "Please handle a refund request. Details: Order ID='INVALID_ID', Customer ID='CUST101', Reason='Item defective'."
)
refund_conversation.execute()
print(f"{'-'*30}\nFULL CONVERSATION:\n{'-'*30}\n")
print_messages(refund_conversation.get_messages())

# USER >>> Please handle a refund request. Details: Order ID='123', Customer ID='CUST456', Reason='Item arrived damaged'.
# TOOL_REQUEST (RefundSpecialist) >>> To process the refund request, we first need to check if the order is eligible for a refund based on company policy.
# [ToolRequest(name='check_refund_eligibility', args={'order_id': '123', 'customer_id': 'CUST456'}, tool_request_id='42d8f215-e80e-4426-b8d1-9c18d6d8059e')]
# TOOL_RESULT (RefundSpecialist) >>> {'eligible': True, 'max_refundable_amount': 50.0, 'reason': 'Within 30-day return window and item is returnable.'}
# TOOL_REQUEST (RefundSpecialist) >>> The order is eligible for a refund. Now, we need to process the refund for the maximum refundable amount.
# [ToolRequest(name='process_refund', args={'order_id': '123', 'amount': 50.0, 'reason': 'Item arrived damaged'}, tool_request_id='6b8f07eb-2caa-4551-9ea3-dcd2b53916b8')]
# TOOL_RESULT (RefundSpecialist) >>> {'success': True, 'refund_id': 'REF_1235000', 'message': 'Refund of $50.00 processed successfully.'}
# AGENT (RefundSpecialist) >>> Refund processed successfully. Refund ID: REF_1235000, Amount: $50.00
# .. end-##_Specialist_test

# .. start-##_Surveyor_tools
@tool
def record_survey_response(
    customer_id: Annotated[str, "The unique identifier for the customer."],
    satisfaction_score: Annotated[
        Optional[int], "The customer's satisfaction rating (e.g., 1-5), if provided."
    ] = None,
    comments: Annotated[
        Optional[str], "Any additional comments provided by the customer, if provided."
    ] = None,
) -> Dict[str, Union[bool, str]]:
    """
    Records the customer's satisfaction survey response.

    Returns:
        A dictionary confirming the recording status.
        Example: {"success": True, "message": "Survey response recorded."}
                 {"success": False, "message": "Failed to record survey response."}
    """
    # Simulate storing the response (e.g., writing to a database or logging system)
    # In a real system, this would persist the feedback data.
    if customer_id:
        return {"success": True, "message": "Survey response recorded successfully."}
    else:
        return {"success": False, "message": "Customer ID is required to record response."}


# .. end-##_Surveyor_tools

# .. start-##_Surveyor_prompt
SURVEYOR_SYSTEM_PROMPT = """
You are a Satisfaction Surveyor agent tasked with collecting customer feedback about their recent service experience in a friendly manner.

# Instructions
- Receive the trigger to conduct a survey from the 'CustomerServiceManager', including context like the customer ID and the nature of the interaction if provided.
- Politely ask the customer if they have a moment to provide feedback on their recent interaction.
- If the customer agrees, ask 1-2 concise questions about their satisfaction (e.g., "On a scale of 1 to 5, where 5 is highly satisfied, how satisfied were you with the resolution provided today?", "Is there anything else you'd like to share about your experience?").
- Use the `record_survey_response` tool to log the customer's feedback, including the satisfaction score and any comments provided. Ensure you pass the correct customer ID.
- If the customer declines to participate, thank them for their time anyway. Do not pressure them. Use the `record_survey_response` tool to log the declination if possible (e.g., score=None, comments="Declined survey").
- Thank the customer for their participation if they provided feedback.
- Report back to the 'CustomerServiceManager' confirming that the survey was attempted and whether it was completed or declined.
""".strip()
# .. end-##_Surveyor_prompt

# .. start-##_Surveyor_agent
surveyor_agent = Agent(
    name="SatisfactionSurveyor",
    description="Conducts brief surveys to gather feedback on customer satisfaction following service interactions.",
    llm=llm,
    custom_instruction=SURVEYOR_SYSTEM_PROMPT,
    tools=[record_survey_response],
    agent_id="SatisfactionSurveyor",  # for the `print_messages` utility function
)
# .. end-##_Surveyor_agent

surveyor_agent.raise_exceptions = False # docs-skiprow

# .. start-##_Surveyor_test
surveyor_conversation = surveyor_agent.start_conversation()
surveyor_conversation.append_user_message(
    "Engage customer for feedback. Details: Customer ID='CUST456', Context='Recent successful refund'."
)
surveyor_conversation.execute()
print_messages([surveyor_conversation.get_last_message()])
# AGENT (SatisfactionSurveyor) >>> Hi there, I'm reaching out on behalf of our Customer Service team. We're glad to hear that your recent refund was successful. If you have a moment, we'd greatly appreciate any feedback you can share about your experience. It will help us improve our services. Would you be willing to answer a couple of quick questions?
surveyor_conversation.append_user_message("yes")
surveyor_conversation.execute()
print_messages([surveyor_conversation.get_last_message()])
# AGENT (SatisfactionSurveyor) >>> On a scale of 1 to 5, where 5 is highly satisfied, how satisfied were you with the resolution provided today?
surveyor_conversation.append_user_message("5")
surveyor_conversation.execute()
print_messages([surveyor_conversation.get_last_message()])
# AGENT (SatisfactionSurveyor) >>> Is there anything else you'd like to share about your experience?
surveyor_conversation.append_user_message("Very quick!")
surveyor_conversation.execute()
print(f"{'-'*30}\nFULL CONVERSATION:\n{'-'*30}\n")
print_messages(surveyor_conversation.get_messages())
# USER >>> Engage customer for feedback. Details: Customer ID='CUST456', Context='Recent successful refund'.
# AGENT (SatisfactionSurveyor) >>> Hi there, I'm reaching out on behalf of our Customer Service team. We're glad to hear that your recent refund was successful. If you have a moment, we'd greatly appreciate any feedback you can share about your experience. It will help us improve our services. Would you be willing to answer a couple of quick questions?
# USER >>> yes
# AGENT (SatisfactionSurveyor) >>> On a scale of 1 to 5, where 5 is highly satisfied, how satisfied were you with the resolution provided today?
# USER >>> 5
# AGENT (SatisfactionSurveyor) >>> Is there anything else you'd like to share about your experience?
# USER >>> Very quick!
# TOOL_REQUEST (SatisfactionSurveyor) >>> Now that we have the customer's feedback, we can record it using the record_survey_response tool.
# [ToolRequest(name='record_survey_response', args={'customer_id': 'CUST456', 'satisfaction_score': 5, 'comments': 'Very quick!'}, tool_request_id='3d7ad387-13b0-465c-a425-42b50b7cfdd4')]
# TOOL_RESULT (SatisfactionSurveyor) >>> {'success': True, 'message': 'Survey response recorded successfully.'}
# TOOL_REQUEST (SatisfactionSurveyor) >>> Now that we have the customer's feedback, we can record it using the record_survey_response tool.
# [ToolRequest(name='record_survey_response', args={'customer_id': 'CUST456', 'satisfaction_score': 5, 'comments': 'Very quick!'}, tool_request_id='e1d00a28-ecbe-4c6f-91fc-a75c13e2e467')]
# TOOL_RESULT (SatisfactionSurveyor) >>> {'success': True, 'message': 'Survey response recorded successfully.'}
# AGENT (SatisfactionSurveyor) >>> Thank you so much for taking the time to share your feedback with us! Your input is invaluable in helping us improve our services. Have a great day!
# .. end-##_Surveyor_test

# .. start-##_Manager_prompt
MANAGER_SYSTEM_PROMPT = """
You are a Customer Service Manager agent tasked with handling incoming customer interactions and orchestrating the resolution process efficiently.

# Instructions
- Greet the customer politely and acknowledge their message.
- Analyze the customer's message to understand their core need (e.g., refund request, general query, feedback).
- Answer common informational questions (e.g., about shipping times, return policy basics) directly if you have the knowledge, before delegating.
- If the request is clearly about a refund, gather necessary details (like Order ID) if missing, and then assign the task to the 'RefundSpecialist' agent. Provide all relevant context.
- If the interaction seems successfully concluded (e.g., refund processed, query answered) and requesting feedback is appropriate, assign the task to the 'SatisfactionSurveyor' agent. Provide customer context.
- For general queries you cannot handle directly and that don't fit the specialist agents, state your limitations clearly and politely.
- Await responses or status updates from specialist agents you have assigned to.
- Summarize the final outcome or confirmation for the customer based on specialist agent reports.
- Maintain a helpful, empathetic, and professional tone throughout the interaction.

# Additional Context
Customer ID: {{customer_id}}
Company policies: {{company_policy_info}}
""".strip()
# .. end-##_Manager_prompt

# .. start-##_Manager_agent
customer_service_manager = Agent(
    name="CustomerServiceManager",
    description="Acts as the primary contact point for customer inquiries, analyzes the request, routes tasks to specialized agents (Refund Specialist, Satisfaction Surveyor), and ensures resolution.",
    llm=llm,
    custom_instruction=MANAGER_SYSTEM_PROMPT,
    agent_id="CustomerServiceManager",  # for the `print_messages` utility function
)
# .. end-##_Manager_agent

# .. start-##_Managerworkers_pattern
from wayflowcore.managerworkers import ManagerWorkers

group = ManagerWorkers(
    group_manager=customer_service_manager,
    workers=[refund_specialist_agent, surveyor_agent],
)
# .. end-##_Managerworkers_pattern

# .. start-##_Managerworkers_answers_without_expert
main_conversation = group.start_conversation(
    inputs={
        "customer_id": "CUST456",
        "company_policy_info": "Shipping times: 3-5 business days in the US",
    }
)
main_conversation.append_user_message(
    "Hi, I was wondering what your standard shipping times are for orders within the US?"
)
main_conversation.execute()
"""
last_message = main_conversation.get_last_message()
print(f"{last_message.message_type} >>> {last_message.content or last_message.tool_requests}")
# AGENT >>> Hello! Thank you for reaching out to us. Our standard shipping times for orders within the US are 3-5 business days. Is there anything else I can help you with?
main_conversation.append_user_message("Okay, thanks! Does that include weekends?")
main_conversation.execute()
last_message = main_conversation.get_last_message()
print(f"{last_message.message_type} >>> {last_message.content or last_message.tool_requests}")
# AGENT >>> Our standard shipping times of 3-5 business days are for weekdays only (Monday through Friday). Weekends and holidays are not included in that timeframe. If you have any other questions or need further assistance, feel free to ask!
print(f"{'-'*30}\nFULL CONVERSATION:\n{'-'*30}\n")
print_messages(main_conversation.get_messages())
# USER >>> Hi, I was wondering what your standard shipping times are for orders within the US?
# AGENT >>> Hello! Thank you for reaching out to us. Our standard shipping times for orders within the US are 3-5 business days. Is there anything else I can help you with?
# USER >>> Okay, thanks! Does that include weekends?
# AGENT >>> Our standard shipping times of 3-5 business days are for weekdays only (Monday through Friday). Weekends and holidays are not included in that timeframe. If you have any other questions or need further assistance, feel free to ask!
"""
# .. end-##_Managerworkers_answers_without_expert

# .. start-##_Managerworkers_answers_with_expert
main_conversation = group.start_conversation(inputs={
    "customer_id": "CUST456",
    "company_policy_info": "Shipping times: 3-5 business days in the US"
})
main_conversation.execute()
"""
print_messages([main_conversation.get_last_message()])

main_conversation.append_user_message("Thank you")
main_conversation.execute()

print(f"{'-'*30}\nFULL CONVERSATION:\n{'-'*30}\n")
print_messages(main_conversation.get_messages())
# ------------------------------
# FULL CONVERSATION:
# ------------------------------
# USER >>> Hi, I need to request a refund for order #123. The item wasn't what I expected.
# TOOL_REQUEST (CustomerServiceManager) >>> The user is requesting a refund for order #123 because the item did not meet their expectations. I will forward this request to the Refund Specialist to verify the eligibility and process the refund accordingly.
# [ToolRequest(name='send_message', args={'message': 'A customer is requesting a refund for order #123 due to the item not meeting their expectations. Please verify the eligibility for the refund and proceed with the necessary steps.', 'recipient': 'RefundSpecialist'}, tool_request_id='19c3cad0-683f-4aa5-9047-57f446405932')]
# TOOL_RESULT (None) >>> The refund for order #123 has been processed successfully. The refund amount is $50.00. Refund ID: REF_789XYZ
# AGENT (CustomerServiceManager) >>> Your refund for order #123 has been processed successfully. The refund amount of $50.00 has been issued to you. If there's anything else you need, please feel free to ask!
# USER >>> Thank you
# TOOL_REQUEST (CustomerServiceManager) >>> --- MESSAGE: From: CustomerServiceManager ---
# I will now initiate a brief satisfaction survey with the user regarding their refund experience to ensure complete service quality.
# [ToolRequest(name='send_message', args={'message': 'Please conduct a brief satisfaction survey with the customer regarding their recent refund experience for order #123.', 'recipient': 'SatisfactionSurveyor'}, tool_request_id='b2368dd2-4bab-447d-9bf3-a6483b403beb')]
# TOOL_RESULT (None) >>> Hi there, I hope you’re doing well. My name is John, and I’m a Satisfaction Surveyor. I’m reaching out because you recently had a refund experience with us for order #123. I wanted to take a moment to thank you for being our customer, and I was wondering if you might have a moment to provide some feedback on that experience. Would you be willing to answer a couple of quick questions about your recent interaction?
# AGENT (CustomerServiceManager) >>> Hi there, I hope you’re doing well. My name is John, and I’m a Satisfaction Surveyor. I’m reaching out because you recently had a refund experience with us for order #123. I wanted to take a moment to thank you for being our customer, and I was wondering if you might have a moment to provide some feedback on that experience. Would you be willing to answer a couple of quick questions about your recent interaction?

# ... can continue similarly to the example above with the satisfaction surveyor
"""
# .. end-##_Managerworkers_answers_with_expert

# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_group = AgentSpecExporter().to_yaml(group)
# .. end-##_Export_config_to_Agent_Spec

# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {
    "record_survey_response": record_survey_response,
    "check_refund_eligibility": check_refund_eligibility,
    "process_refund": process_refund,
}

deserialized_group: ManagerWorkers = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_yaml(serialized_group)
# .. end-##_Load_Agent_Spec_config

# .. start-##_Using_ManagerWorkers_within_a_Flow
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep, CallerInputMode
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.property import StringProperty

# Example of using a ManagerWorkers within a Flow in non-conversational mode
def managerworkers_in_flow():
    customer_id = StringProperty(name="customer_id", default_value="")
    company_policy_info = StringProperty(name="company_policy_info", default_value="")
    refunds_days = StringProperty(name="refunds_days", default_value="", description='Number of days before getting back the refund.')
    managerworkers = ManagerWorkers(
        group_manager=customer_service_manager,
        workers=[refund_specialist_agent, surveyor_agent],
        input_descriptors=[customer_id, company_policy_info],
        output_descriptors=[refunds_days],
        caller_input_mode=CallerInputMode.NEVER
    )
    agent_step = AgentExecutionStep(
        name="agent_step",
        agent=managerworkers
    )
    output_step = OutputMessageStep(name="output_step", message_template="{{refunds_days}}")

    flow = Flow(
        begin_step=agent_step,
        control_flow_edges=[
            ControlFlowEdge(source_step=agent_step, destination_step=output_step),
            ControlFlowEdge(source_step=output_step, destination_step=None),
        ],
        data_flow_edges=[DataFlowEdge(agent_step, "refunds_days", output_step, "refunds_days")],
    )
    return flow
# .. end-##_Using_ManagerWorkers_within_a_Flow

# .. start-##_Run_ManagerWorkers_within_a_Flow
flow = managerworkers_in_flow()
conversation = flow.start_conversation(inputs={
    "customer_id": "CUST456",
})
conversation.append_user_message("Hi, I need to request a refund for order #123. The item wasn't what I expected. In how many days will I expect a refund?")
status = conversation.execute()
print(status.output_values["output_message"])
# .. end-##_Run_ManagerWorkers_within_a_Flow

# .. start-##_Export_config_to_Agent_Spec2
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_yaml(flow)
# .. end-##_Export_config_to_Agent_Spec2

# .. start-##_Load_Agent_Spec_config2
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {
    "record_survey_response": record_survey_response,
    "check_refund_eligibility": check_refund_eligibility,
    "process_refund": process_refund,
}
flow: Flow = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_yaml(serialized_flow)
# .. end-##_Load_Agent_Spec_config2
