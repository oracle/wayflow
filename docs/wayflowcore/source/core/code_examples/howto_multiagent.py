# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

import logging
import os
import warnings
from typing import Annotated, Dict, Optional, Union

from wayflowcore.agent import Agent
from wayflowcore.models import VllmModel
from wayflowcore.templates import REACT_AGENT_TEMPLATE
from wayflowcore.tools import tool

logging.basicConfig(level=logging.CRITICAL)
warnings.filterwarnings("ignore")

llm = VllmModel(
    model_id="/storage/models/Llama-3.3-70B-Instruct",
    host_port=os.environ["VLLM_HOST_PORT"],
)
llm.agent_template = REACT_AGENT_TEMPLATE


# .. start-helpermethod:
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


# .. end-helpermethod
# .. start-specialisttools:
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


# .. end-specialisttools
# .. start-specialistprompt:
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
# .. end-specialistprompt
# .. start-specialistagent:
from wayflowcore.agent import Agent

refund_specialist_agent = Agent(
    name="RefundSpecialist",
    description="Specializes in processing customer refund requests by verifying eligibility and executing the refund transaction using available tools.",
    llm=llm,
    custom_instruction=REFUND_SPECIALIST_SYSTEM_PROMPT,
    tools=[check_refund_eligibility, process_refund],
    agent_id="RefundSpecialist",  # for the `print_messages` utility function
)
# .. end-specialistagent
# .. start-specialisttest:
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
# .. end-specialisttest
# .. start-surveyortools:
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


# .. end-surveyortools
# .. start-surveyorprompt:
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
# .. end-surveyorprompt
# .. start-surveyoragent:
surveyor_agent = Agent(
    name="SatisfactionSurveyor",
    description="Conducts brief surveys to gather feedback on customer satisfaction following service interactions.",
    llm=llm,
    custom_instruction=SURVEYOR_SYSTEM_PROMPT,
    tools=[record_survey_response],
    agent_id="SatisfactionSurveyor",  # for the `print_messages` utility function
)
# .. end-surveyoragent
# .. start-surveyortest:
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
# .. end-surveyortest
# .. start-managerprompt:
MANAGER_SYSTEM_PROMPT = """
You are a Customer Service Manager agent tasked with handling incoming customer interactions and orchestrating the resolution process efficiently.

# Instructions
- Greet the customer politely and acknowledge their message.
- Analyze the customer's message to understand their core need (e.g., refund request, general query, feedback).
- Answer common informational questions (e.g., about shipping times, return policy basics) directly if you have the knowledge, before delegating.
- If the request is clearly about a refund, gather necessary details (like Order ID) if missing, and then delegate the task to the 'RefundSpecialist' agent. Provide all relevant context.
- If the interaction seems successfully concluded (e.g., refund processed, query answered) and requesting feedback is appropriate, delegate the task to the 'SatisfactionSurveyor' agent. Provide customer context.
- For general queries you cannot handle directly and that don't fit the specialist agents, state your limitations clearly and politely.
- Await responses or status updates from specialist agents you have delegated to.
- Summarize the final outcome or confirmation for the customer based on specialist agent reports.
- Maintain a helpful, empathetic, and professional tone throughout the interaction.

# Additional Context
Customer ID: {{customer_id}}
Company policies:
{% for item in company_policy_info -%}
- {{ item }}
{% endfor -%}
""".strip()
# .. end-managerprompt
# .. start-manageragent:
customer_service_manager = Agent(
    name="CustomerServiceManager",
    description="Acts as the primary contact point for customer inquiries, analyzes the request, routes tasks to specialized agents (Refund Specialist, Satisfaction Surveyor), and ensures resolution.",
    llm=llm,
    custom_instruction=MANAGER_SYSTEM_PROMPT,
    agents=[refund_specialist_agent, surveyor_agent],
    agent_id="CustomerServiceManager",  # for the `print_messages` utility function
)
# .. end-manageragent
"""
# .. start-managertest_noexpert:
main_conversation = customer_service_manager.start_conversation(
    inputs={
        "customer_id": "CUST456",
        "company_policy_info": ["Shipping times: 3-5 business days in the US"],
    }
)
main_conversation.append_user_message(
    "Hi, I was wondering what your standard shipping times are for orders within the US?"
)
main_conversation.execute()
last_message = main_conversation.get_last_message()
print(f"{last_message.message_type} >>> {last_message.content or last_message.tool_requests}")
# AGENT >>> Hello! Thank you for reaching out to us. Our standard shipping times for orders within the US are 3-5 business days. Is there anything else I can help you with?
main_conversation.append_user_message("Okay, thanks! Does that include weekends?")
main_conversation.execute()
last_message = main_conversation.get_last_message()
print(f"{last_message.message_type} >>> {last_message.content or last_message.tool_requests}")
# AGENT >>> Our standard shipping times of 3-5 business days are for weekdays only (Monday through Friday). Weekends and holidays are not included in that timeframe. If you have any other questions or need further assistance, feel free to ask!
print(f"{'-'*30}\nFULL CONVERSATION:\n{'-'*30}\n")
print(
    *[
        f"{message.message_type} >>> {message.content or message.tool_requests}"
        for message in main_conversation.get_messages()
    ],
    sep="\n",
)
# USER >>> Hi, I was wondering what your standard shipping times are for orders within the US?
# AGENT >>> Hello! Thank you for reaching out to us. Our standard shipping times for orders within the US are 3-5 business days. Is there anything else I can help you with?
# USER >>> Okay, thanks! Does that include weekends?
# AGENT >>> Our standard shipping times of 3-5 business days are for weekdays only (Monday through Friday). Weekends and holidays are not included in that timeframe. If you have any other questions or need further assistance, feel free to ask!
# .. end-managertest_noexpert
# .. start-managertest_withexpert:
main_conversation = customer_service_manager.start_conversation(inputs={
    "customer_id": "CUST456",
    "company_policy_info": ["Shipping times: 3-5 business days in the US"]
})
main_conversation.append_user_message(
    "Hi, I need to request a refund for order #123. The item wasn't what I expected."
)
main_conversation.execute()
print_messages([main_conversation.get_last_message()])

main_conversation.append_user_message("Thank you")
main_conversation.execute()
# ... can continue similarly to the example above with the satisfaction surveyor

print(f"{'-'*30}\nFULL CONVERSATION:\n{'-'*30}\n")
print_messages(main_conversation.get_messages())
# ------------------------------
# FULL CONVERSATION:
# ------------------------------
# USER >>> Hi, I need to request a refund for order #123. The item wasn't what I expected.
# TOOL_REQUEST (CustomerServiceManager) >>> The customer is requesting a refund for order #123 due to the item not meeting their expectations. We should delegate this task to the RefundSpecialist agent to process the refund.
# [ToolRequest(name='RefundSpecialist', args={'context': "Customer CUST456 is requesting a refund for order #123 as the item wasn't what they expected. Please verify eligibility and process the refund."}, tool_request_id='20a31c10-f000-4053-935b-bb2c5ed38c2e')]
# AGENT (CustomerServiceManager) >>> Customer CUST456 is requesting a refund for order #123 as the item wasn't what they expected. Please verify eligibility and process the refund.
# TOOL_REQUEST (RefundSpecialist) >>> To verify the refund eligibility, we need to check if the order meets the company's refund policy criteria. We have the order ID and customer ID, so we can use the `check_refund_eligibility` tool.
# [ToolRequest(name='check_refund_eligibility', args={'order_id': '#123', 'customer_id': 'CUST456'}, tool_request_id='2bb26c7c-9467-4eb4-94f0-e47afc838535')]
# TOOL_RESULT (RefundSpecialist) >>> {'eligible': True, 'max_refundable_amount': 50.0, 'reason': 'Within 30-day return window and item is returnable.'}
# TOOL_REQUEST (RefundSpecialist) >>> Since the order is eligible for a refund and the maximum refundable amount is $50.00, we should process the refund for this amount.
# [ToolRequest(name='process_refund', args={'order_id': '#123', 'amount': 50.0, 'reason': 'Item not as expected'}, tool_request_id='b5f6de16-1530-4b63-b180-92764b728714')]
# TOOL_RESULT (RefundSpecialist) >>> {'success': True, 'refund_id': 'REF_#125000', 'message': 'Refund of $50.00 processed successfully.'}
# AGENT (RefundSpecialist) >>> Refund processed successfully, Refund ID: REF_#125000, Amount: $50.00.
# TOOL_RESULT (CustomerServiceManager) >>> Refund processed successfully, Refund ID: REF_#125000, Amount: $50.00.
# AGENT (CustomerServiceManager) >>> I've processed your refund for order #123. You will receive $50.00 back. Your refund ID is REF_#125000.
# USER >>> Thank you
# TOOL_REQUEST (CustomerServiceManager) >>> The interaction seems successfully concluded, so I will request feedback from the customer.
# [ToolRequest(name='SatisfactionSurveyor', args={'context': 'Customer CUST456 had a refund processed for order #123 and expressed gratitude.'}, tool_request_id='fa5bf287-3c20-4838-9693-58681f98fd07')]
# AGENT (CustomerServiceManager) >>> Customer CUST456 had a refund processed for order #123 and expressed gratitude.
# AGENT (SatisfactionSurveyor) >>> Hi there, thank you for choosing our service. I'd love to hear about your recent experience with us. Do you have a moment to provide some quick feedback?
# TOOL_RESULT (CustomerServiceManager) >>> Hi there, thank you for choosing our service. I'd love to hear about your recent experience with us. Do you have a moment to provide some quick feedback?
# AGENT (CustomerServiceManager) >>> How was your experience with the refund process?
# ...
# .. end-managertest_withexpert
"""
