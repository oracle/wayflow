<a id="top-howtomanagerworkers"></a>

# How to Build a Manager-Workers of Agents![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[ManagerWorkers how-to script](../end_to_end_code_examples/howto_managerworkers.py)

#### Prerequisites
This guide assumes familiarity with [Agents](../tutorials/basic_agent.md).

With the advent of increasingly powerful Large Language Models (LLMs), multi-agent systems are becoming more relevant
and are expected to be particularly valuable in scenarios requiring high-levels of autonomy and/or processing
of diverse sources of information.

There are various types of multi-agent systems, each serving different purposes and applications.
Some notable examples include hierarchical structures, agent swarms, and mixtures of agents.

This guide demonstrates an example of a hierarchical multi-agent system (also known as manager-workers pattern) and will show you how to:

- Build expert agents equipped with tools and a manager agent;
- Test the expert agents individually;
- Build a ManagerWorkers using the defined agents;
- Execute the ManagerWorkers of agents;

![Example of a multi-agent system](core/_static/howto/howto_multiagent.svg)

**Diagram:** Multi-agent system shown in this how-to guide, comprising a manager agent
(customer service agent) and two expert agents equipped with tools (refund specialist
and satisfaction surveyor).

#### SEE ALSO
To access short code snippets demonstrating how to use other agentic patterns in WayFlow,
refer to the [Reference Sheet](../misc/reference_sheet.md).

To follow this guide, you need an LLM. WayFlow supports several LLM API providers.
Select an LLM from the options below:




OCI GenAI

```python
from wayflowcore.models import OCIGenAIModel, OCIClientConfigWithApiKey

llm = OCIGenAIModel(
    model_id="provider.model-id",
    compartment_id="compartment-id",
    client_config=OCIClientConfigWithApiKey(
        service_endpoint="https://url-to-service-endpoint.com",
    ),
)
```

vLLM

```python
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)
```

Ollama

```python
from wayflowcore.models import OllamaModel

llm = OllamaModel(
    model_id="model-id",
)
```

## Building and testing expert Agents

In this guide you will use the following helper function to print
messages:

```python
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


```

API Reference: [MessageType](../api/conversation.md#messagetype)

### Refund specialist agent

The refund specialist agent is equipped with two tools.

```python
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

```

API Reference: [tool](../api/tools.md#tooldecorator)

The first tool is used to check whether a given order is eligible for a refund,
while the second is used to process the specific refund.

#### System prompt
```python
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
```

#### IMPORTANT
The quality of the system prompt is paramount to ensuring proper behaviour of the multi-agent
system, because slight deviations in the behaviour can lead to cascading
unintended effects as the number of agents scales up.

#### Building the Agent
```python
from wayflowcore.agent import Agent

refund_specialist_agent = Agent(
    name="RefundSpecialist",
    description="Specializes in processing customer refund requests by verifying eligibility and executing the refund transaction using available tools.",
    llm=llm,
    custom_instruction=REFUND_SPECIALIST_SYSTEM_PROMPT,
    tools=[check_refund_eligibility, process_refund],
    agent_id="RefundSpecialist",  # for the `print_messages` utility function
)
```

API Reference: [Agent](../api/agent.md#agent)

#### Testing the Agent
```python
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
```

Test the agents individually to ensure they perform as expected.

### Statisfaction surveyor agent

#### Tools

The statisfaction surveyor agent is equipped with one tool.

```python
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


```

The `record_survey_response` tool is simulating the recording of
user feedback data.

#### System prompt
```python
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
```

#### Building the Agent
```python
surveyor_agent = Agent(
    name="SatisfactionSurveyor",
    description="Conducts brief surveys to gather feedback on customer satisfaction following service interactions.",
    llm=llm,
    custom_instruction=SURVEYOR_SYSTEM_PROMPT,
    tools=[record_survey_response],
    agent_id="SatisfactionSurveyor",  # for the `print_messages` utility function
)
```

#### Testing the Agent
```python
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
```

Again, the expert agent behaves as intended.

### Manager Agent

In the our built-in ManagerWorkers component, we allow passing an Agent
as the group manager. Therefore, we just need to define an agent as usual.

In this example, our manager agent will be a Customer Service Manager.

#### System prompt
```python
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
```

#### Building the manager Agent
```python
customer_service_manager = Agent(
    name="CustomerServiceManager",
    description="Acts as the primary contact point for customer inquiries, analyzes the request, routes tasks to specialized agents (Refund Specialist, Satisfaction Surveyor), and ensures resolution.",
    llm=llm,
    custom_instruction=MANAGER_SYSTEM_PROMPT,
    agent_id="CustomerServiceManager",  # for the `print_messages` utility function
)
```

## Building and testing ManagerWorkers of Agents

### Building the ManagerWorkers of Agents
```python
from wayflowcore.managerworkers import ManagerWorkers

group = ManagerWorkers(
    group_manager=customer_service_manager,
    workers=[refund_specialist_agent, surveyor_agent],
)
```

API Reference: [ManagerWorkers](../api/agent.md#managerworkers)

The ManagerWorkers has two main parameters:

- `group_manager`
  This can be either an Agent or an LLM.
  - If an LLM is provided, a manager agent will automatically be created using that LLM along with the default `custom_instruction` for group managers.
  - In this example, we explicitly pass an Agent (the *Customer Service Manager Agent*) so we can use our own defined `custom_instruction`.
- `workers` - List of Agents
  These agents serve as the workers within the group and are coordinated by the manager agent.
  - Worker agents cannot interact with the end user directly.
  - When invoked, each worker can leverage its equipped tools to complete the assigned task and report the result back to the group manager.

### Executing the ManagerWorkers

The power of mult-agent systems is their high adaptiveness.
In the following example, it is demonstrated how the manager can decide
not to call the expert agents for simple user queries.

```python
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
```

However, the manager is explicitly prompted to assign to the specialized agents for more complex tasks.
This is demonstrated in the following example.

```python
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
```

### Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_group = AgentSpecExporter().to_yaml(group)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
    "component_type": "ManagerWorkers",
    "id": "3a3ac4d1-5b2e-4f5d-8e8e-2ef3f447651c",
    "name": "managerworkers_a4ce9181__auto",
    "description": "",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [],
    "outputs": [],
    "group_manager": {
        "component_type": "Agent",
        "id": "CustomerServiceManager",
        "name": "CustomerServiceManager",
        "description": "Acts as the primary contact point for customer inquiries, analyzes the request, routes tasks to specialized agents (Refund Specialist, Satisfaction Surveyor), and ensures resolution.",
        "metadata": {
            "__metadata_info__": {}
        },
        "inputs": [
            {
                "description": "\"customer_id\" input variable for the template",
                "type": "string",
                "title": "customer_id"
            },
            {
                "description": "\"company_policy_info\" input variable for the template",
                "type": "string",
                "title": "company_policy_info"
            }
        ],
        "outputs": [],
        "llm_config": {
            "$component_ref": "8ac9179d-eec5-45da-bb77-500265cb830f"
        },
        "system_prompt": "You are a Customer Service Manager agent tasked with handling incoming customer interactions and orchestrating the resolution process efficiently.\n\n# Instructions\n- Greet the customer politely and acknowledge their message.\n- Analyze the customer's message to understand their core need (e.g., refund request, general query, feedback).\n- Answer common informational questions (e.g., about shipping times, return policy basics) directly if you have the knowledge, before delegating.\n- If the request is clearly about a refund, gather necessary details (like Order ID) if missing, and then assign the task to the 'RefundSpecialist' agent. Provide all relevant context.\n- If the interaction seems successfully concluded (e.g., refund processed, query answered) and requesting feedback is appropriate, assign the task to the 'SatisfactionSurveyor' agent. Provide customer context.\n- For general queries you cannot handle directly and that don't fit the specialist agents, state your limitations clearly and politely.\n- Await responses or status updates from specialist agents you have assigned to.\n- Summarize the final outcome or confirmation for the customer based on specialist agent reports.\n- Maintain a helpful, empathetic, and professional tone throughout the interaction.\n\n# Additional Context\nCustomer ID: {{customer_id}}\nCompany policies: {{company_policy_info}}",
        "tools": []
    },
    "workers": [
        {
            "component_type": "Agent",
            "id": "RefundSpecialist",
            "name": "RefundSpecialist",
            "description": "Specializes in processing customer refund requests by verifying eligibility and executing the refund transaction using available tools.",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
            "outputs": [],
            "llm_config": {
                "$component_ref": "8ac9179d-eec5-45da-bb77-500265cb830f"
            },
            "system_prompt": "You are a Refund Specialist agent whose objective is to process customer refund requests accurately and efficiently based on company policy.\n\n# Instructions\n- Receive the refund request details (e.g., order ID, customer ID, reason) from the 'CustomerServiceManager'.\n- Use the `check_refund_eligibility` tool to verify if the request meets the refund policy criteria using the provided order and customer IDs.\n- If the check indicates eligibility, determine the correct refund amount (up to the maximum allowed from the eligibility check).\n- If eligible, use the `process_refund` tool to execute the refund for the determined amount, providing order ID and reason.\n- If ineligible based on the check, clearly note the reason provided by the tool.\n- Report the final outcome (e.g., \"Refund processed successfully, Refund ID: [ID], Amount: [Amount]\", or \"Refund denied: [Reason from eligibility check]\") back to the 'CustomerServiceManager'.\n- Do not engage in general conversation; focus solely on the refund process.",
            "tools": [
                {
                    "component_type": "ServerTool",
                    "id": "89a5b809-f66f-4206-83d3-ab46debb83c2",
                    "name": "check_refund_eligibility",
                    "description": "Checks if a given order is eligible for a refund based on company policy.\n\nReturns:\n    A dictionary containing eligibility status and details.\n    Example: {\"eligible\": True, \"max_refundable_amount\": 50.00, \"reason\": \"Within return window\"}\n             {\"eligible\": False, \"reason\": \"Order past 30-day return window\"}",
                    "metadata": {
                        "__metadata_info__": {}
                    },
                    "inputs": [
                        {
                            "description": "The unique identifier for the order.",
                            "type": "string",
                            "title": "order_id"
                        },
                        {
                            "description": "The unique identifier for the customer.",
                            "type": "string",
                            "title": "customer_id"
                        }
                    ],
                    "outputs": [
                        {
                            "type": "object",
                            "additionalProperties": {
                                "anyOf": [
                                    {
                                        "type": "boolean"
                                    },
                                    {
                                        "type": "number"
                                    },
                                    {
                                        "type": "string"
                                    }
                                ]
                            },
                            "title": "tool_output"
                        }
                    ]
                },
                {
                    "component_type": "ServerTool",
                    "id": "958dfe5b-7124-4186-a2ac-0687e09db652",
                    "name": "process_refund",
                    "description": "Processes a refund for a specific order and amount.\n\nReturns:\n    A dictionary confirming the refund status.\n    Example: {\"success\": True, \"refund_id\": \"REF_789XYZ\", \"message\": \"Refund processed successfully.\"}\n             {\"success\": False, \"message\": \"Refund processing failed due to payment gateway error.\"}",
                    "metadata": {
                        "__metadata_info__": {}
                    },
                    "inputs": [
                        {
                            "description": "The unique identifier for the order to be refunded.",
                            "type": "string",
                            "title": "order_id"
                        },
                        {
                            "description": "The amount to be refunded.",
                            "type": "number",
                            "title": "amount"
                        },
                        {
                            "description": "The reason for the refund.",
                            "type": "string",
                            "title": "reason"
                        }
                    ],
                    "outputs": [
                        {
                            "type": "object",
                            "additionalProperties": {
                                "anyOf": [
                                    {
                                        "type": "boolean"
                                    },
                                    {
                                        "type": "string"
                                    }
                                ]
                            },
                            "title": "tool_output"
                        }
                    ]
                }
            ]
        },
        {
            "component_type": "Agent",
            "id": "SatisfactionSurveyor",
            "name": "SatisfactionSurveyor",
            "description": "Conducts brief surveys to gather feedback on customer satisfaction following service interactions.",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
            "outputs": [],
            "llm_config": {
                "$component_ref": "8ac9179d-eec5-45da-bb77-500265cb830f"
            },
            "system_prompt": "You are a Satisfaction Surveyor agent tasked with collecting customer feedback about their recent service experience in a friendly manner.\n\n# Instructions\n- Receive the trigger to conduct a survey from the 'CustomerServiceManager', including context like the customer ID and the nature of the interaction if provided.\n- Politely ask the customer if they have a moment to provide feedback on their recent interaction.\n- If the customer agrees, ask 1-2 concise questions about their satisfaction (e.g., \"On a scale of 1 to 5, where 5 is highly satisfied, how satisfied were you with the resolution provided today?\", \"Is there anything else you'd like to share about your experience?\").\n- Use the `record_survey_response` tool to log the customer's feedback, including the satisfaction score and any comments provided. Ensure you pass the correct customer ID.\n- If the customer declines to participate, thank them for their time anyway. Do not pressure them. Use the `record_survey_response` tool to log the declination if possible (e.g., score=None, comments=\"Declined survey\").\n- Thank the customer for their participation if they provided feedback.\n- Report back to the 'CustomerServiceManager' confirming that the survey was attempted and whether it was completed or declined.",
            "tools": [
                {
                    "component_type": "ServerTool",
                    "id": "95652709-278d-4f78-9ecf-dcf47d095b2d",
                    "name": "record_survey_response",
                    "description": "Records the customer's satisfaction survey response.\n\nReturns:\n    A dictionary confirming the recording status.\n    Example: {\"success\": True, \"message\": \"Survey response recorded.\"}\n             {\"success\": False, \"message\": \"Failed to record survey response.\"}",
                    "metadata": {
                        "__metadata_info__": {}
                    },
                    "inputs": [
                        {
                            "description": "The unique identifier for the customer.",
                            "type": "string",
                            "title": "customer_id"
                        },
                        {
                            "description": "The customer's satisfaction rating (e.g., 1-5), if provided.",
                            "anyOf": [
                                {
                                    "type": "integer"
                                },
                                {
                                    "type": "null"
                                }
                            ],
                            "title": "satisfaction_score",
                            "default": null
                        },
                        {
                            "description": "Any additional comments provided by the customer, if provided.",
                            "anyOf": [
                                {
                                    "type": "string"
                                },
                                {
                                    "type": "null"
                                }
                            ],
                            "title": "comments",
                            "default": null
                        }
                    ],
                    "outputs": [
                        {
                            "type": "object",
                            "additionalProperties": {
                                "anyOf": [
                                    {
                                        "type": "boolean"
                                    },
                                    {
                                        "type": "string"
                                    }
                                ]
                            },
                            "title": "tool_output"
                        }
                    ]
                }
            ]
        }
    ],
    "$referenced_components": {
        "8ac9179d-eec5-45da-bb77-500265cb830f": {
            "component_type": "VllmConfig",
            "id": "8ac9179d-eec5-45da-bb77-500265cb830f",
            "name": "llm_65f5df68__auto",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "default_generation_parameters": null,
            "url": "VLLM_HOST_PORT",
            "model_id": "model-id"
        }
    },
    "agentspec_version": "25.4.2"
}
```

YAML

```yaml
component_type: ManagerWorkers
id: 92d09dcd-0eb4-43d7-8626-e9879a7e0ec2
name: managerworkers_ec2b1679__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
group_manager:
  component_type: Agent
  id: CustomerServiceManager
  name: CustomerServiceManager
  description: Acts as the primary contact point for customer inquiries, analyzes
    the request, routes tasks to specialized agents (Refund Specialist, Satisfaction
    Surveyor), and ensures resolution.
  metadata:
    __metadata_info__: {}
  inputs:
  - description: '"customer_id" input variable for the template'
    type: string
    title: customer_id
  - description: '"company_policy_info" input variable for the template'
    type: string
    title: company_policy_info
  outputs: []
  llm_config:
    $component_ref: 6cc05856-534f-4684-bbd0-b9c98021ab8b
  system_prompt: 'You are a Customer Service Manager agent tasked with handling incoming
    customer interactions and orchestrating the resolution process efficiently.


    # Instructions

    - Greet the customer politely and acknowledge their message.

    - Analyze the customer''s message to understand their core need (e.g., refund
    request, general query, feedback).

    - Answer common informational questions (e.g., about shipping times, return policy
    basics) directly if you have the knowledge, before delegating.

    - If the request is clearly about a refund, gather necessary details (like Order
    ID) if missing, and then assign the task to the ''RefundSpecialist'' agent. Provide
    all relevant context.

    - If the interaction seems successfully concluded (e.g., refund processed, query
    answered) and requesting feedback is appropriate, assign the task to the ''SatisfactionSurveyor''
    agent. Provide customer context.

    - For general queries you cannot handle directly and that don''t fit the specialist
    agents, state your limitations clearly and politely.

    - Await responses or status updates from specialist agents you have assigned to.

    - Summarize the final outcome or confirmation for the customer based on specialist
    agent reports.

    - Maintain a helpful, empathetic, and professional tone throughout the interaction.


    # Additional Context

    Customer ID: {{customer_id}}

    Company policies: {{company_policy_info}}'
  tools: []
workers:
- component_type: Agent
  id: RefundSpecialist
  name: RefundSpecialist
  description: Specializes in processing customer refund requests by verifying eligibility
    and executing the refund transaction using available tools.
  metadata:
    __metadata_info__: {}
  inputs: []
  outputs: []
  llm_config:
    $component_ref: 6cc05856-534f-4684-bbd0-b9c98021ab8b
  system_prompt: 'You are a Refund Specialist agent whose objective is to process
    customer refund requests accurately and efficiently based on company policy.


    # Instructions

    - Receive the refund request details (e.g., order ID, customer ID, reason) from
    the ''CustomerServiceManager''.

    - Use the `check_refund_eligibility` tool to verify if the request meets the refund
    policy criteria using the provided order and customer IDs.

    - If the check indicates eligibility, determine the correct refund amount (up
    to the maximum allowed from the eligibility check).

    - If eligible, use the `process_refund` tool to execute the refund for the determined
    amount, providing order ID and reason.

    - If ineligible based on the check, clearly note the reason provided by the tool.

    - Report the final outcome (e.g., "Refund processed successfully, Refund ID: [ID],
    Amount: [Amount]", or "Refund denied: [Reason from eligibility check]") back to
    the ''CustomerServiceManager''.

    - Do not engage in general conversation; focus solely on the refund process.'
  tools:
  - component_type: ServerTool
    id: 7df19064-1b82-4e9e-9168-2edd052b07ad
    name: check_refund_eligibility
    description: "Checks if a given order is eligible for a refund based on company\
      \ policy.\n\nReturns:\n    A dictionary containing eligibility status and details.\n\
      \    Example: {\"eligible\": True, \"max_refundable_amount\": 50.00, \"reason\"\
      : \"Within return window\"}\n             {\"eligible\": False, \"reason\":\
      \ \"Order past 30-day return window\"}"
    metadata:
      __metadata_info__: {}
    inputs:
    - description: The unique identifier for the order.
      type: string
      title: order_id
    - description: The unique identifier for the customer.
      type: string
      title: customer_id
    outputs:
    - type: object
      additionalProperties:
        anyOf:
        - type: boolean
        - type: number
        - type: string
      title: tool_output
  - component_type: ServerTool
    id: 4fe2caf8-eacf-40b6-853c-6763477748d3
    name: process_refund
    description: "Processes a refund for a specific order and amount.\n\nReturns:\n\
      \    A dictionary confirming the refund status.\n    Example: {\"success\":\
      \ True, \"refund_id\": \"REF_789XYZ\", \"message\": \"Refund processed successfully.\"\
      }\n             {\"success\": False, \"message\": \"Refund processing failed\
      \ due to payment gateway error.\"}"
    metadata:
      __metadata_info__: {}
    inputs:
    - description: The unique identifier for the order to be refunded.
      type: string
      title: order_id
    - description: The amount to be refunded.
      type: number
      title: amount
    - description: The reason for the refund.
      type: string
      title: reason
    outputs:
    - type: object
      additionalProperties:
        anyOf:
        - type: boolean
        - type: string
      title: tool_output
- component_type: Agent
  id: SatisfactionSurveyor
  name: SatisfactionSurveyor
  description: Conducts brief surveys to gather feedback on customer satisfaction
    following service interactions.
  metadata:
    __metadata_info__: {}
  inputs: []
  outputs: []
  llm_config:
    $component_ref: 6cc05856-534f-4684-bbd0-b9c98021ab8b
  system_prompt: 'You are a Satisfaction Surveyor agent tasked with collecting customer
    feedback about their recent service experience in a friendly manner.


    # Instructions

    - Receive the trigger to conduct a survey from the ''CustomerServiceManager'',
    including context like the customer ID and the nature of the interaction if provided.

    - Politely ask the customer if they have a moment to provide feedback on their
    recent interaction.

    - If the customer agrees, ask 1-2 concise questions about their satisfaction (e.g.,
    "On a scale of 1 to 5, where 5 is highly satisfied, how satisfied were you with
    the resolution provided today?", "Is there anything else you''d like to share
    about your experience?").

    - Use the `record_survey_response` tool to log the customer''s feedback, including
    the satisfaction score and any comments provided. Ensure you pass the correct
    customer ID.

    - If the customer declines to participate, thank them for their time anyway. Do
    not pressure them. Use the `record_survey_response` tool to log the declination
    if possible (e.g., score=None, comments="Declined survey").

    - Thank the customer for their participation if they provided feedback.

    - Report back to the ''CustomerServiceManager'' confirming that the survey was
    attempted and whether it was completed or declined.'
  tools:
  - component_type: ServerTool
    id: b25b7b4b-a880-47f2-af61-68cf232841a8
    name: record_survey_response
    description: "Records the customer's satisfaction survey response.\n\nReturns:\n\
      \    A dictionary confirming the recording status.\n    Example: {\"success\"\
      : True, \"message\": \"Survey response recorded.\"}\n             {\"success\"\
      : False, \"message\": \"Failed to record survey response.\"}"
    metadata:
      __metadata_info__: {}
    inputs:
    - description: The unique identifier for the customer.
      type: string
      title: customer_id
    - description: The customer's satisfaction rating (e.g., 1-5), if provided.
      anyOf:
      - type: integer
      - type: 'null'
      title: satisfaction_score
      default: null
    - description: Any additional comments provided by the customer, if provided.
      anyOf:
      - type: string
      - type: 'null'
      title: comments
      default: null
    outputs:
    - type: object
      additionalProperties:
        anyOf:
        - type: boolean
        - type: string
      title: tool_output
$referenced_components:
  6cc05856-534f-4684-bbd0-b9c98021ab8b:
    component_type: VllmConfig
    id: 6cc05856-534f-4684-bbd0-b9c98021ab8b
    name: llm_9112faef__auto
    description: null
    metadata:
      __metadata_info__: {}
    default_generation_parameters: null
    url: VLLM_HOST_PORT
    model_id: model-id
agentspec_version: 25.4.2
```

</details>

You can load it back using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {
    "record_survey_response": record_survey_response,
    "check_refund_eligibility": check_refund_eligibility,
    "process_refund": process_refund,
}

deserialized_group: ManagerWorkers = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_yaml(serialized_group)
```

## Using ManagerWorkers within a Flow

The `Manager-Workers` pattern can be integrated into a [Flow](../api/flows.md#flow) using the [AgentExecutionStep](../api/flows.md#agentexecutionstep).

Here’s an example of how to integrate a manager-workers system into a flow:

```python
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
```

You can run the flow with:

```python
flow = managerworkers_in_flow()
conversation = flow.start_conversation(inputs={
    "customer_id": "CUST456",
})
conversation.append_user_message("Hi, I need to request a refund for order #123. The item wasn't what I expected. In how many days will I expect a refund?")
status = conversation.execute()
print(status.output_values["output_message"])
```

### Agent Spec Exporting/Loading

You can export the flow configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_yaml(flow)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
    "component_type": "Flow",
    "id": "0823fc83-1baa-44bb-a192-531d34921e30",
    "name": "flow_52727579__auto",
    "description": "",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [
        {
            "type": "string",
            "title": "customer_id",
            "default": ""
        },
        {
            "type": "string",
            "title": "company_policy_info",
            "default": ""
        }
    ],
    "outputs": [
        {
            "description": "Number of days before getting back the refund.",
            "type": "string",
            "title": "refunds_days",
            "default": ""
        },
        {
            "description": "the message added to the messages list",
            "type": "string",
            "title": "output_message"
        }
    ],
    "start_node": {
        "$component_ref": "bba3ce84-0ab7-4a19-86dc-93eddaf18d9d"
    },
    "nodes": [
        {
            "$component_ref": "c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb"
        },
        {
            "$component_ref": "3d7ce624-3b69-4195-9e10-8c0082436d89"
        },
        {
            "$component_ref": "bba3ce84-0ab7-4a19-86dc-93eddaf18d9d"
        },
        {
            "$component_ref": "79c3ae52-6e18-4c95-9a21-cbe6f88a158f"
        }
    ],
    "control_flow_connections": [
        {
            "component_type": "ControlFlowEdge",
            "id": "38d403c7-cfd7-4610-92a5-807e6ed3df97",
            "name": "agent_step_to_output_step_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "3d7ce624-3b69-4195-9e10-8c0082436d89"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "55450cd7-7564-4a00-8ad8-029934026f56",
            "name": "__StartStep___to_agent_step_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "bba3ce84-0ab7-4a19-86dc-93eddaf18d9d"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "ce02118a-c0e8-48cd-8219-3363626a923a",
            "name": "output_step_to_None End node_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "3d7ce624-3b69-4195-9e10-8c0082436d89"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "79c3ae52-6e18-4c95-9a21-cbe6f88a158f"
            }
        }
    ],
    "data_flow_connections": [
        {
            "component_type": "DataFlowEdge",
            "id": "76476327-669a-4398-983b-83bddc8d46ed",
            "name": "agent_step_refunds_days_to_output_step_refunds_days_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb"
            },
            "source_output": "refunds_days",
            "destination_node": {
                "$component_ref": "3d7ce624-3b69-4195-9e10-8c0082436d89"
            },
            "destination_input": "refunds_days"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "76d2b096-0fcd-4d45-a644-dc1dd57e8738",
            "name": "__StartStep___customer_id_to_agent_step_customer_id_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "bba3ce84-0ab7-4a19-86dc-93eddaf18d9d"
            },
            "source_output": "customer_id",
            "destination_node": {
                "$component_ref": "c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb"
            },
            "destination_input": "customer_id"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "e0cf2705-c6d2-40ed-b862-6c38021794b9",
            "name": "__StartStep___company_policy_info_to_agent_step_company_policy_info_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "bba3ce84-0ab7-4a19-86dc-93eddaf18d9d"
            },
            "source_output": "company_policy_info",
            "destination_node": {
                "$component_ref": "c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb"
            },
            "destination_input": "company_policy_info"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "15515102-d9fb-4265-972f-8c2eaa39a988",
            "name": "agent_step_refunds_days_to_None End node_refunds_days_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb"
            },
            "source_output": "refunds_days",
            "destination_node": {
                "$component_ref": "79c3ae52-6e18-4c95-9a21-cbe6f88a158f"
            },
            "destination_input": "refunds_days"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "03bb2f10-2c37-4bfe-9646-cd6d4562c3bd",
            "name": "output_step_output_message_to_None End node_output_message_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "3d7ce624-3b69-4195-9e10-8c0082436d89"
            },
            "source_output": "output_message",
            "destination_node": {
                "$component_ref": "79c3ae52-6e18-4c95-9a21-cbe6f88a158f"
            },
            "destination_input": "output_message"
        }
    ],
    "$referenced_components": {
        "c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb": {
            "component_type": "AgentNode",
            "id": "c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb",
            "name": "agent_step",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "type": "string",
                    "title": "customer_id",
                    "default": ""
                },
                {
                    "type": "string",
                    "title": "company_policy_info",
                    "default": ""
                }
            ],
            "outputs": [
                {
                    "description": "Number of days before getting back the refund.",
                    "type": "string",
                    "title": "refunds_days",
                    "default": ""
                }
            ],
            "branches": [
                "next"
            ],
            "agent": {
                "component_type": "ManagerWorkers",
                "id": "550d2a94-ad12-4e36-8138-3a1246a09b0a",
                "name": "managerworkers_153290a1__auto",
                "description": "",
                "metadata": {
                    "__metadata_info__": {}
                },
                "inputs": [
                    {
                        "type": "string",
                        "title": "customer_id",
                        "default": ""
                    },
                    {
                        "type": "string",
                        "title": "company_policy_info",
                        "default": ""
                    }
                ],
                "outputs": [
                    {
                        "description": "Number of days before getting back the refund.",
                        "type": "string",
                        "title": "refunds_days",
                        "default": ""
                    }
                ],
                "group_manager": {
                    "component_type": "ExtendedAgent",
                    "id": "CustomerServiceManager",
                    "name": "CustomerServiceManager",
                    "description": "Acts as the primary contact point for customer inquiries, analyzes the request, routes tasks to specialized agents (Refund Specialist, Satisfaction Surveyor), and ensures resolution.",
                    "metadata": {
                        "__metadata_info__": {}
                    },
                    "inputs": [
                        {
                            "description": "\"customer_id\" input variable for the template",
                            "type": "string",
                            "title": "customer_id"
                        },
                        {
                            "description": "\"company_policy_info\" input variable for the template",
                            "type": "string",
                            "title": "company_policy_info"
                        }
                    ],
                    "outputs": [],
                    "llm_config": {
                        "$component_ref": "bd13304e-265e-4f7f-aa48-d8242ba347c6"
                    },
                    "system_prompt": "You are a Customer Service Manager agent tasked with handling incoming customer interactions and orchestrating the resolution process efficiently.\n\n# Instructions\n- Greet the customer politely and acknowledge their message.\n- Analyze the customer's message to understand their core need (e.g., refund request, general query, feedback).\n- Answer common informational questions (e.g., about shipping times, return policy basics) directly if you have the knowledge, before delegating.\n- If the request is clearly about a refund, gather necessary details (like Order ID) if missing, and then assign the task to the 'RefundSpecialist' agent. Provide all relevant context.\n- If the interaction seems successfully concluded (e.g., refund processed, query answered) and requesting feedback is appropriate, assign the task to the 'SatisfactionSurveyor' agent. Provide customer context.\n- For general queries you cannot handle directly and that don't fit the specialist agents, state your limitations clearly and politely.\n- Await responses or status updates from specialist agents you have assigned to.\n- Summarize the final outcome or confirmation for the customer based on specialist agent reports.\n- Maintain a helpful, empathetic, and professional tone throughout the interaction.\n\n# Additional Context\nCustomer ID: {{customer_id}}\nCompany policies: {{company_policy_info}}",
                    "tools": [],
                    "toolboxes": [],
                    "human_in_the_loop": true,
                    "transforms": [],
                    "context_providers": null,
                    "can_finish_conversation": false,
                    "raise_exceptions": false,
                    "max_iterations": 10,
                    "initial_message": "Hi! How can I help you?",
                    "caller_input_mode": "always",
                    "agents": [],
                    "flows": [],
                    "agent_template": null,
                    "component_plugin_name": "AgentPlugin",
                    "component_plugin_version": "26.2.0.dev0"
                },
                "workers": [
                    {
                        "component_type": "ExtendedAgent",
                        "id": "RefundSpecialist",
                        "name": "RefundSpecialist",
                        "description": "Specializes in processing customer refund requests by verifying eligibility and executing the refund transaction using available tools.",
                        "metadata": {
                            "__metadata_info__": {}
                        },
                        "inputs": [],
                        "outputs": [],
                        "llm_config": {
                            "$component_ref": "bd13304e-265e-4f7f-aa48-d8242ba347c6"
                        },
                        "system_prompt": "You are a Refund Specialist agent whose objective is to process customer refund requests accurately and efficiently based on company policy.\n\n# Instructions\n- Receive the refund request details (e.g., order ID, customer ID, reason) from the 'CustomerServiceManager'.\n- Use the `check_refund_eligibility` tool to verify if the request meets the refund policy criteria using the provided order and customer IDs.\n- If the check indicates eligibility, determine the correct refund amount (up to the maximum allowed from the eligibility check).\n- If eligible, use the `process_refund` tool to execute the refund for the determined amount, providing order ID and reason.\n- If ineligible based on the check, clearly note the reason provided by the tool.\n- Report the final outcome (e.g., \"Refund processed successfully, Refund ID: [ID], Amount: [Amount]\", or \"Refund denied: [Reason from eligibility check]\") back to the 'CustomerServiceManager'.\n- Do not engage in general conversation; focus solely on the refund process.",
                        "tools": [
                            {
                                "component_type": "ServerTool",
                                "id": "cff39d54-c852-4114-871d-873e8f52c121",
                                "name": "check_refund_eligibility",
                                "description": "Checks if a given order is eligible for a refund based on company policy.\n\nReturns:\n    A dictionary containing eligibility status and details.\n    Example: {\"eligible\": True, \"max_refundable_amount\": 50.00, \"reason\": \"Within return window\"}\n             {\"eligible\": False, \"reason\": \"Order past 30-day return window\"}",
                                "metadata": {
                                    "__metadata_info__": {}
                                },
                                "inputs": [
                                    {
                                        "description": "The unique identifier for the order.",
                                        "type": "string",
                                        "title": "order_id"
                                    },
                                    {
                                        "description": "The unique identifier for the customer.",
                                        "type": "string",
                                        "title": "customer_id"
                                    }
                                ],
                                "outputs": [
                                    {
                                        "type": "object",
                                        "additionalProperties": {
                                            "anyOf": [
                                                {
                                                    "type": "string"
                                                },
                                                {
                                                    "type": "number"
                                                },
                                                {
                                                    "type": "boolean"
                                                }
                                            ]
                                        },
                                        "title": "tool_output"
                                    }
                                ],
                                "requires_confirmation": false
                            },
                            {
                                "component_type": "ServerTool",
                                "id": "1c876021-49eb-408b-90f6-d5dc3e13346b",
                                "name": "process_refund",
                                "description": "Processes a refund for a specific order and amount.\n\nReturns:\n    A dictionary confirming the refund status.\n    Example: {\"success\": True, \"refund_id\": \"REF_789XYZ\", \"message\": \"Refund processed successfully.\"}\n             {\"success\": False, \"message\": \"Refund processing failed due to payment gateway error.\"}",
                                "metadata": {
                                    "__metadata_info__": {}
                                },
                                "inputs": [
                                    {
                                        "description": "The unique identifier for the order to be refunded.",
                                        "type": "string",
                                        "title": "order_id"
                                    },
                                    {
                                        "description": "The amount to be refunded.",
                                        "type": "number",
                                        "title": "amount"
                                    },
                                    {
                                        "description": "The reason for the refund.",
                                        "type": "string",
                                        "title": "reason"
                                    }
                                ],
                                "outputs": [
                                    {
                                        "type": "object",
                                        "additionalProperties": {
                                            "anyOf": [
                                                {
                                                    "type": "boolean"
                                                },
                                                {
                                                    "type": "string"
                                                }
                                            ]
                                        },
                                        "title": "tool_output"
                                    }
                                ],
                                "requires_confirmation": false
                            }
                        ],
                        "toolboxes": [],
                        "human_in_the_loop": true,
                        "transforms": [],
                        "context_providers": null,
                        "can_finish_conversation": false,
                        "raise_exceptions": false,
                        "max_iterations": 10,
                        "initial_message": "Hi! How can I help you?",
                        "caller_input_mode": "always",
                        "agents": [],
                        "flows": [],
                        "agent_template": null,
                        "component_plugin_name": "AgentPlugin",
                        "component_plugin_version": "26.2.0.dev0"
                    },
                    {
                        "component_type": "ExtendedAgent",
                        "id": "SatisfactionSurveyor",
                        "name": "SatisfactionSurveyor",
                        "description": "Conducts brief surveys to gather feedback on customer satisfaction following service interactions.",
                        "metadata": {
                            "__metadata_info__": {}
                        },
                        "inputs": [],
                        "outputs": [],
                        "llm_config": {
                            "$component_ref": "bd13304e-265e-4f7f-aa48-d8242ba347c6"
                        },
                        "system_prompt": "You are a Satisfaction Surveyor agent tasked with collecting customer feedback about their recent service experience in a friendly manner.\n\n# Instructions\n- Receive the trigger to conduct a survey from the 'CustomerServiceManager', including context like the customer ID and the nature of the interaction if provided.\n- Politely ask the customer if they have a moment to provide feedback on their recent interaction.\n- If the customer agrees, ask 1-2 concise questions about their satisfaction (e.g., \"On a scale of 1 to 5, where 5 is highly satisfied, how satisfied were you with the resolution provided today?\", \"Is there anything else you'd like to share about your experience?\").\n- Use the `record_survey_response` tool to log the customer's feedback, including the satisfaction score and any comments provided. Ensure you pass the correct customer ID.\n- If the customer declines to participate, thank them for their time anyway. Do not pressure them. Use the `record_survey_response` tool to log the declination if possible (e.g., score=None, comments=\"Declined survey\").\n- Thank the customer for their participation if they provided feedback.\n- Report back to the 'CustomerServiceManager' confirming that the survey was attempted and whether it was completed or declined.",
                        "tools": [
                            {
                                "component_type": "ServerTool",
                                "id": "7c1caf2c-6809-4509-a7a3-5d79887dd231",
                                "name": "record_survey_response",
                                "description": "Records the customer's satisfaction survey response.\n\nReturns:\n    A dictionary confirming the recording status.\n    Example: {\"success\": True, \"message\": \"Survey response recorded.\"}\n             {\"success\": False, \"message\": \"Failed to record survey response.\"}",
                                "metadata": {
                                    "__metadata_info__": {}
                                },
                                "inputs": [
                                    {
                                        "description": "The unique identifier for the customer.",
                                        "type": "string",
                                        "title": "customer_id"
                                    },
                                    {
                                        "description": "The customer's satisfaction rating (e.g., 1-5), if provided.",
                                        "anyOf": [
                                            {
                                                "type": "integer"
                                            },
                                            {
                                                "type": "null"
                                            }
                                        ],
                                        "title": "satisfaction_score",
                                        "default": null
                                    },
                                    {
                                        "description": "Any additional comments provided by the customer, if provided.",
                                        "anyOf": [
                                            {
                                                "type": "string"
                                            },
                                            {
                                                "type": "null"
                                            }
                                        ],
                                        "title": "comments",
                                        "default": null
                                    }
                                ],
                                "outputs": [
                                    {
                                        "type": "object",
                                        "additionalProperties": {
                                            "anyOf": [
                                                {
                                                    "type": "boolean"
                                                },
                                                {
                                                    "type": "string"
                                                }
                                            ]
                                        },
                                        "title": "tool_output"
                                    }
                                ],
                                "requires_confirmation": false
                            }
                        ],
                        "toolboxes": [],
                        "human_in_the_loop": true,
                        "transforms": [],
                        "context_providers": null,
                        "can_finish_conversation": false,
                        "raise_exceptions": false,
                        "max_iterations": 10,
                        "initial_message": "Hi! How can I help you?",
                        "caller_input_mode": "always",
                        "agents": [],
                        "flows": [],
                        "agent_template": null,
                        "component_plugin_name": "AgentPlugin",
                        "component_plugin_version": "26.2.0.dev0"
                    }
                ],
                "$referenced_components": {
                    "bd13304e-265e-4f7f-aa48-d8242ba347c6": {
                        "component_type": "VllmConfig",
                        "id": "bd13304e-265e-4f7f-aa48-d8242ba347c6",
                        "name": "llm_0fbe0307__auto",
                        "description": null,
                        "metadata": {
                            "__metadata_info__": {}
                        },
                        "default_generation_parameters": null,
                        "url": "VLLM_HOST_PORT",
                        "model_id": "model-id",
                        "api_type": "chat_completions",
                        "api_key": null
                    }
                }
            }
        },
        "3d7ce624-3b69-4195-9e10-8c0082436d89": {
            "component_type": "PluginOutputMessageNode",
            "id": "3d7ce624-3b69-4195-9e10-8c0082436d89",
            "name": "output_step",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "description": "\"refunds_days\" input variable for the template",
                    "type": "string",
                    "title": "refunds_days"
                }
            ],
            "outputs": [
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                }
            ],
            "branches": [
                "next"
            ],
            "message": "{{refunds_days}}",
            "input_mapping": {},
            "output_mapping": {},
            "message_type": "AGENT",
            "rephrase": false,
            "llm_config": null,
            "expose_message_as_output": true,
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "26.2.0.dev0"
        },
        "bba3ce84-0ab7-4a19-86dc-93eddaf18d9d": {
            "component_type": "StartNode",
            "id": "bba3ce84-0ab7-4a19-86dc-93eddaf18d9d",
            "name": "__StartStep__",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "type": "string",
                    "title": "customer_id",
                    "default": ""
                },
                {
                    "type": "string",
                    "title": "company_policy_info",
                    "default": ""
                }
            ],
            "outputs": [
                {
                    "type": "string",
                    "title": "customer_id",
                    "default": ""
                },
                {
                    "type": "string",
                    "title": "company_policy_info",
                    "default": ""
                }
            ],
            "branches": [
                "next"
            ]
        },
        "79c3ae52-6e18-4c95-9a21-cbe6f88a158f": {
            "component_type": "EndNode",
            "id": "79c3ae52-6e18-4c95-9a21-cbe6f88a158f",
            "name": "None End node",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "description": "Number of days before getting back the refund.",
                    "type": "string",
                    "title": "refunds_days",
                    "default": ""
                },
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                }
            ],
            "outputs": [
                {
                    "description": "Number of days before getting back the refund.",
                    "type": "string",
                    "title": "refunds_days",
                    "default": ""
                },
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                }
            ],
            "branches": [],
            "branch_name": "next"
        }
    },
    "agentspec_version": "26.2.0"
}
```

YAML

```yaml
component_type: Flow
id: 0823fc83-1baa-44bb-a192-531d34921e30
name: flow_52727579__auto
description: ''
metadata:
  __metadata_info__: {}
inputs:
- type: string
  title: customer_id
  default: ''
- type: string
  title: company_policy_info
  default: ''
outputs:
- description: Number of days before getting back the refund.
  type: string
  title: refunds_days
  default: ''
- description: the message added to the messages list
  type: string
  title: output_message
start_node:
  $component_ref: bba3ce84-0ab7-4a19-86dc-93eddaf18d9d
nodes:
- $component_ref: c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb
- $component_ref: 3d7ce624-3b69-4195-9e10-8c0082436d89
- $component_ref: bba3ce84-0ab7-4a19-86dc-93eddaf18d9d
- $component_ref: 79c3ae52-6e18-4c95-9a21-cbe6f88a158f
control_flow_connections:
- component_type: ControlFlowEdge
  id: 38d403c7-cfd7-4610-92a5-807e6ed3df97
  name: agent_step_to_output_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb
  from_branch: null
  to_node:
    $component_ref: 3d7ce624-3b69-4195-9e10-8c0082436d89
- component_type: ControlFlowEdge
  id: 55450cd7-7564-4a00-8ad8-029934026f56
  name: __StartStep___to_agent_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: bba3ce84-0ab7-4a19-86dc-93eddaf18d9d
  from_branch: null
  to_node:
    $component_ref: c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb
- component_type: ControlFlowEdge
  id: ce02118a-c0e8-48cd-8219-3363626a923a
  name: output_step_to_None End node_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 3d7ce624-3b69-4195-9e10-8c0082436d89
  from_branch: null
  to_node:
    $component_ref: 79c3ae52-6e18-4c95-9a21-cbe6f88a158f
data_flow_connections:
- component_type: DataFlowEdge
  id: 76476327-669a-4398-983b-83bddc8d46ed
  name: agent_step_refunds_days_to_output_step_refunds_days_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb
  source_output: refunds_days
  destination_node:
    $component_ref: 3d7ce624-3b69-4195-9e10-8c0082436d89
  destination_input: refunds_days
- component_type: DataFlowEdge
  id: 76d2b096-0fcd-4d45-a644-dc1dd57e8738
  name: __StartStep___customer_id_to_agent_step_customer_id_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: bba3ce84-0ab7-4a19-86dc-93eddaf18d9d
  source_output: customer_id
  destination_node:
    $component_ref: c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb
  destination_input: customer_id
- component_type: DataFlowEdge
  id: e0cf2705-c6d2-40ed-b862-6c38021794b9
  name: __StartStep___company_policy_info_to_agent_step_company_policy_info_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: bba3ce84-0ab7-4a19-86dc-93eddaf18d9d
  source_output: company_policy_info
  destination_node:
    $component_ref: c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb
  destination_input: company_policy_info
- component_type: DataFlowEdge
  id: 15515102-d9fb-4265-972f-8c2eaa39a988
  name: agent_step_refunds_days_to_None End node_refunds_days_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb
  source_output: refunds_days
  destination_node:
    $component_ref: 79c3ae52-6e18-4c95-9a21-cbe6f88a158f
  destination_input: refunds_days
- component_type: DataFlowEdge
  id: 03bb2f10-2c37-4bfe-9646-cd6d4562c3bd
  name: output_step_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 3d7ce624-3b69-4195-9e10-8c0082436d89
  source_output: output_message
  destination_node:
    $component_ref: 79c3ae52-6e18-4c95-9a21-cbe6f88a158f
  destination_input: output_message
$referenced_components:
  c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb:
    component_type: AgentNode
    id: c48a82be-fb4c-4e7b-acfd-5b6dd5a80fcb
    name: agent_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: string
      title: customer_id
      default: ''
    - type: string
      title: company_policy_info
      default: ''
    outputs:
    - description: Number of days before getting back the refund.
      type: string
      title: refunds_days
      default: ''
    branches:
    - next
    agent:
      component_type: ManagerWorkers
      id: 550d2a94-ad12-4e36-8138-3a1246a09b0a
      name: managerworkers_153290a1__auto
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - type: string
        title: customer_id
        default: ''
      - type: string
        title: company_policy_info
        default: ''
      outputs:
      - description: Number of days before getting back the refund.
        type: string
        title: refunds_days
        default: ''
      group_manager:
        component_type: ExtendedAgent
        id: CustomerServiceManager
        name: CustomerServiceManager
        description: Acts as the primary contact point for customer inquiries, analyzes
          the request, routes tasks to specialized agents (Refund Specialist, Satisfaction
          Surveyor), and ensures resolution.
        metadata:
          __metadata_info__: {}
        inputs:
        - description: '"customer_id" input variable for the template'
          type: string
          title: customer_id
        - description: '"company_policy_info" input variable for the template'
          type: string
          title: company_policy_info
        outputs: []
        llm_config:
          $component_ref: bd13304e-265e-4f7f-aa48-d8242ba347c6
        system_prompt: 'You are a Customer Service Manager agent tasked with handling
          incoming customer interactions and orchestrating the resolution process
          efficiently.


          # Instructions

          - Greet the customer politely and acknowledge their message.

          - Analyze the customer''s message to understand their core need (e.g., refund
          request, general query, feedback).

          - Answer common informational questions (e.g., about shipping times, return
          policy basics) directly if you have the knowledge, before delegating.

          - If the request is clearly about a refund, gather necessary details (like
          Order ID) if missing, and then assign the task to the ''RefundSpecialist''
          agent. Provide all relevant context.

          - If the interaction seems successfully concluded (e.g., refund processed,
          query answered) and requesting feedback is appropriate, assign the task
          to the ''SatisfactionSurveyor'' agent. Provide customer context.

          - For general queries you cannot handle directly and that don''t fit the
          specialist agents, state your limitations clearly and politely.

          - Await responses or status updates from specialist agents you have assigned
          to.

          - Summarize the final outcome or confirmation for the customer based on
          specialist agent reports.

          - Maintain a helpful, empathetic, and professional tone throughout the interaction.


          # Additional Context

          Customer ID: {{customer_id}}

          Company policies: {{company_policy_info}}'
        tools: []
        toolboxes: []
        human_in_the_loop: true
        transforms: []
        context_providers: null
        can_finish_conversation: false
        raise_exceptions: false
        max_iterations: 10
        initial_message: Hi! How can I help you?
        caller_input_mode: always
        agents: []
        flows: []
        agent_template: null
        component_plugin_name: AgentPlugin
        component_plugin_version: 26.2.0.dev0
      workers:
      - component_type: ExtendedAgent
        id: RefundSpecialist
        name: RefundSpecialist
        description: Specializes in processing customer refund requests by verifying
          eligibility and executing the refund transaction using available tools.
        metadata:
          __metadata_info__: {}
        inputs: []
        outputs: []
        llm_config:
          $component_ref: bd13304e-265e-4f7f-aa48-d8242ba347c6
        system_prompt: 'You are a Refund Specialist agent whose objective is to process
          customer refund requests accurately and efficiently based on company policy.


          # Instructions

          - Receive the refund request details (e.g., order ID, customer ID, reason)
          from the ''CustomerServiceManager''.

          - Use the `check_refund_eligibility` tool to verify if the request meets
          the refund policy criteria using the provided order and customer IDs.

          - If the check indicates eligibility, determine the correct refund amount
          (up to the maximum allowed from the eligibility check).

          - If eligible, use the `process_refund` tool to execute the refund for the
          determined amount, providing order ID and reason.

          - If ineligible based on the check, clearly note the reason provided by
          the tool.

          - Report the final outcome (e.g., "Refund processed successfully, Refund
          ID: [ID], Amount: [Amount]", or "Refund denied: [Reason from eligibility
          check]") back to the ''CustomerServiceManager''.

          - Do not engage in general conversation; focus solely on the refund process.'
        tools:
        - component_type: ServerTool
          id: cff39d54-c852-4114-871d-873e8f52c121
          name: check_refund_eligibility
          description: "Checks if a given order is eligible for a refund based on\
            \ company policy.\n\nReturns:\n    A dictionary containing eligibility\
            \ status and details.\n    Example: {\"eligible\": True, \"max_refundable_amount\"\
            : 50.00, \"reason\": \"Within return window\"}\n             {\"eligible\"\
            : False, \"reason\": \"Order past 30-day return window\"}"
          metadata:
            __metadata_info__: {}
          inputs:
          - description: The unique identifier for the order.
            type: string
            title: order_id
          - description: The unique identifier for the customer.
            type: string
            title: customer_id
          outputs:
          - type: object
            additionalProperties:
              anyOf:
              - type: string
              - type: number
              - type: boolean
            title: tool_output
          requires_confirmation: false
        - component_type: ServerTool
          id: 1c876021-49eb-408b-90f6-d5dc3e13346b
          name: process_refund
          description: "Processes a refund for a specific order and amount.\n\nReturns:\n\
            \    A dictionary confirming the refund status.\n    Example: {\"success\"\
            : True, \"refund_id\": \"REF_789XYZ\", \"message\": \"Refund processed\
            \ successfully.\"}\n             {\"success\": False, \"message\": \"\
            Refund processing failed due to payment gateway error.\"}"
          metadata:
            __metadata_info__: {}
          inputs:
          - description: The unique identifier for the order to be refunded.
            type: string
            title: order_id
          - description: The amount to be refunded.
            type: number
            title: amount
          - description: The reason for the refund.
            type: string
            title: reason
          outputs:
          - type: object
            additionalProperties:
              anyOf:
              - type: boolean
              - type: string
            title: tool_output
          requires_confirmation: false
        toolboxes: []
        human_in_the_loop: true
        transforms: []
        context_providers: null
        can_finish_conversation: false
        raise_exceptions: false
        max_iterations: 10
        initial_message: Hi! How can I help you?
        caller_input_mode: always
        agents: []
        flows: []
        agent_template: null
        component_plugin_name: AgentPlugin
        component_plugin_version: 26.2.0.dev0
      - component_type: ExtendedAgent
        id: SatisfactionSurveyor
        name: SatisfactionSurveyor
        description: Conducts brief surveys to gather feedback on customer satisfaction
          following service interactions.
        metadata:
          __metadata_info__: {}
        inputs: []
        outputs: []
        llm_config:
          $component_ref: bd13304e-265e-4f7f-aa48-d8242ba347c6
        system_prompt: 'You are a Satisfaction Surveyor agent tasked with collecting
          customer feedback about their recent service experience in a friendly manner.


          # Instructions

          - Receive the trigger to conduct a survey from the ''CustomerServiceManager'',
          including context like the customer ID and the nature of the interaction
          if provided.

          - Politely ask the customer if they have a moment to provide feedback on
          their recent interaction.

          - If the customer agrees, ask 1-2 concise questions about their satisfaction
          (e.g., "On a scale of 1 to 5, where 5 is highly satisfied, how satisfied
          were you with the resolution provided today?", "Is there anything else you''d
          like to share about your experience?").

          - Use the `record_survey_response` tool to log the customer''s feedback,
          including the satisfaction score and any comments provided. Ensure you pass
          the correct customer ID.

          - If the customer declines to participate, thank them for their time anyway.
          Do not pressure them. Use the `record_survey_response` tool to log the declination
          if possible (e.g., score=None, comments="Declined survey").

          - Thank the customer for their participation if they provided feedback.

          - Report back to the ''CustomerServiceManager'' confirming that the survey
          was attempted and whether it was completed or declined.'
        tools:
        - component_type: ServerTool
          id: 7c1caf2c-6809-4509-a7a3-5d79887dd231
          name: record_survey_response
          description: "Records the customer's satisfaction survey response.\n\nReturns:\n\
            \    A dictionary confirming the recording status.\n    Example: {\"success\"\
            : True, \"message\": \"Survey response recorded.\"}\n             {\"\
            success\": False, \"message\": \"Failed to record survey response.\"}"
          metadata:
            __metadata_info__: {}
          inputs:
          - description: The unique identifier for the customer.
            type: string
            title: customer_id
          - description: The customer's satisfaction rating (e.g., 1-5), if provided.
            anyOf:
            - type: integer
            - type: 'null'
            title: satisfaction_score
            default: null
          - description: Any additional comments provided by the customer, if provided.
            anyOf:
            - type: string
            - type: 'null'
            title: comments
            default: null
          outputs:
          - type: object
            additionalProperties:
              anyOf:
              - type: boolean
              - type: string
            title: tool_output
          requires_confirmation: false
        toolboxes: []
        human_in_the_loop: true
        transforms: []
        context_providers: null
        can_finish_conversation: false
        raise_exceptions: false
        max_iterations: 10
        initial_message: Hi! How can I help you?
        caller_input_mode: always
        agents: []
        flows: []
        agent_template: null
        component_plugin_name: AgentPlugin
        component_plugin_version: 26.2.0.dev0
      $referenced_components:
        bd13304e-265e-4f7f-aa48-d8242ba347c6:
          component_type: VllmConfig
          id: bd13304e-265e-4f7f-aa48-d8242ba347c6
          name: llm_0fbe0307__auto
          description: null
          metadata:
            __metadata_info__: {}
          default_generation_parameters: null
          url: VLLM_HOST_PORT
          model_id: model-id
          api_type: chat_completions
          api_key: null
  3d7ce624-3b69-4195-9e10-8c0082436d89:
    component_type: PluginOutputMessageNode
    id: 3d7ce624-3b69-4195-9e10-8c0082436d89
    name: output_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"refunds_days" input variable for the template'
      type: string
      title: refunds_days
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    branches:
    - next
    message: '{{refunds_days}}'
    input_mapping: {}
    output_mapping: {}
    message_type: AGENT
    rephrase: false
    llm_config: null
    expose_message_as_output: true
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.2.0.dev0
  bba3ce84-0ab7-4a19-86dc-93eddaf18d9d:
    component_type: StartNode
    id: bba3ce84-0ab7-4a19-86dc-93eddaf18d9d
    name: __StartStep__
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: string
      title: customer_id
      default: ''
    - type: string
      title: company_policy_info
      default: ''
    outputs:
    - type: string
      title: customer_id
      default: ''
    - type: string
      title: company_policy_info
      default: ''
    branches:
    - next
  79c3ae52-6e18-4c95-9a21-cbe6f88a158f:
    component_type: EndNode
    id: 79c3ae52-6e18-4c95-9a21-cbe6f88a158f
    name: None End node
    description: null
    metadata:
      __metadata_info__: {}
    inputs:
    - description: Number of days before getting back the refund.
      type: string
      title: refunds_days
      default: ''
    - description: the message added to the messages list
      type: string
      title: output_message
    outputs:
    - description: Number of days before getting back the refund.
      type: string
      title: refunds_days
      default: ''
    - description: the message added to the messages list
      type: string
      title: output_message
    branches: []
    branch_name: next
agentspec_version: 26.2.0
```

</details>

You can then load the configuration back to a flow using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {
    "record_survey_response": record_survey_response,
    "check_refund_eligibility": check_refund_eligibility,
    "process_refund": process_refund,
}
flow: Flow = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_yaml(serialized_flow)
```

## Next steps

Now that you have learned how to define a ManagerWorkers, you may proceed to [Build a Swarm of Agents](howto_swarm.md).

## Full code

Click on the card at the [top of this page](#top-howtomanagerworkers) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - Build a ManagerWorkers of Agents
# -----------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_managerworkers.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Annotated, Dict, Optional, Union

from wayflowcore.agent import Agent
from wayflowcore.models import VllmModel
from wayflowcore.tools import tool

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)



# %%[markdown]
## Helper method for printing conversation messages

# %%
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




# %%[markdown]
## Specialist tools

# %%
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



# %%[markdown]
## Specialist prompt

# %%
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


# %%[markdown]
## Specialist agent

# %%
from wayflowcore.agent import Agent

refund_specialist_agent = Agent(
    name="RefundSpecialist",
    description="Specializes in processing customer refund requests by verifying eligibility and executing the refund transaction using available tools.",
    llm=llm,
    custom_instruction=REFUND_SPECIALIST_SYSTEM_PROMPT,
    tools=[check_refund_eligibility, process_refund],
    agent_id="RefundSpecialist",  # for the `print_messages` utility function
)



# %%[markdown]
## Specialist test

# %%
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


# %%[markdown]
## Surveyor tools

# %%
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




# %%[markdown]
## Surveyor prompt

# %%
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


# %%[markdown]
## Surveyor agent

# %%
surveyor_agent = Agent(
    name="SatisfactionSurveyor",
    description="Conducts brief surveys to gather feedback on customer satisfaction following service interactions.",
    llm=llm,
    custom_instruction=SURVEYOR_SYSTEM_PROMPT,
    tools=[record_survey_response],
    agent_id="SatisfactionSurveyor",  # for the `print_messages` utility function
)



# %%[markdown]
## Surveyor test

# %%
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


# %%[markdown]
## Manager prompt

# %%
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


# %%[markdown]
## Manager agent

# %%
customer_service_manager = Agent(
    name="CustomerServiceManager",
    description="Acts as the primary contact point for customer inquiries, analyzes the request, routes tasks to specialized agents (Refund Specialist, Satisfaction Surveyor), and ensures resolution.",
    llm=llm,
    custom_instruction=MANAGER_SYSTEM_PROMPT,
    agent_id="CustomerServiceManager",  # for the `print_messages` utility function
)


# %%[markdown]
## Managerworkers pattern

# %%
from wayflowcore.managerworkers import ManagerWorkers

group = ManagerWorkers(
    group_manager=customer_service_manager,
    workers=[refund_specialist_agent, surveyor_agent],
)


# %%[markdown]
## Managerworkers answers without expert

# %%
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


# %%[markdown]
## Managerworkers answers with expert

# %%
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


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_group = AgentSpecExporter().to_yaml(group)


# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {
    "record_survey_response": record_survey_response,
    "check_refund_eligibility": check_refund_eligibility,
    "process_refund": process_refund,
}

deserialized_group: ManagerWorkers = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_yaml(serialized_group)


# %%[markdown]
## Using ManagerWorkers within a Flow

# %%
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


# %%[markdown]
## Run ManagerWorkers within a Flow

# %%
flow = managerworkers_in_flow()
conversation = flow.start_conversation(inputs={
    "customer_id": "CUST456",
})
conversation.append_user_message("Hi, I need to request a refund for order #123. The item wasn't what I expected. In how many days will I expect a refund?")
status = conversation.execute()
print(status.output_values["output_message"])


# %%[markdown]
## Export config to Agent Spec2

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_yaml(flow)


# %%[markdown]
## Load Agent Spec config2

# %%
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {
    "record_survey_response": record_survey_response,
    "check_refund_eligibility": check_refund_eligibility,
    "process_refund": process_refund,
}
flow: Flow = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_yaml(serialized_flow)
```
