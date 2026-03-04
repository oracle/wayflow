# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to use MessageTransform
# ------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_long_context.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


import logging

logging.basicConfig(level=logging.INFO)


# %%[markdown]
## Define LLMS

# %%
from wayflowcore.models import VllmModel

summarization_llm = VllmModel(
    model_id="SMALL_LLAMA_MODEL_ID",
    host_port="SMALL_LLAMA_API_URL",
)
agent_llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)


# %%[markdown]
## Create MessageSummarizationTransform

# %%
from wayflowcore.transforms import MessageSummarizationTransform


transform = MessageSummarizationTransform(
    llm=summarization_llm,
    max_message_size=10000,
    summarized_message_template="Summarized result:\n{{summary}}"
)



# %%[markdown]
## Create Agent

# %%
from wayflowcore import Agent, Message, tool

@tool
def read_logs_tool() -> str:
    """Return logs from the system"""
    return (
        "Starting long processing\n"
        + "Waiting for process ...\n" * 2_000
        + "Found error: Missing credentials for user kurt_andrews."
        + " Please pass the correct credentials.\n"
    )

agent = Agent(
    llm=agent_llm,
    tools=[read_logs_tool],
    transforms=[transform],
)


# %%[markdown]
## Create Token Event Listener

# %%
from wayflowcore.events.eventlistener import EventListener
from wayflowcore.events.event import LlmGenerationResponseEvent
from wayflowcore.events import register_event_listeners
from wayflowcore.tokenusage import TokenUsage

class TokenListener(EventListener):
    def __init__(self):
        self.usage = TokenUsage()
    def __call__(self, event):
        if isinstance(event, LlmGenerationResponseEvent):
            self.usage += event.completion.token_usage


# %%[markdown]
## Run Agent With MessageSummarizationTransform

# %%
listener_with_transform = TokenListener()
with register_event_listeners([listener_with_transform]):
    from wayflowcore.executors.executionstatus import UserMessageRequestStatus

    conversation = agent.start_conversation()
    conversation.append_user_message("Can you explain the error in the system?")
    status = conversation.execute()
    if isinstance(status, UserMessageRequestStatus):
        print(status.message.content)
        # The error is likely due to a missing credential for
        # a user named kurt_andrews. Please ensure the credentials
        # are provided correctly for kurt_andrews to resolve the issue.
    print(f"Token usage with MessageSummarizationTransform after 1 user message: {listener_with_transform.usage.total_tokens} tokens")
    # Token usage with MessageSummarizationTransform after 1 user message: 8854 tokens

    conversation.append_user_message('What is the exact message repeated in a loop? Do not recall the tool')
    status = conversation.execute()
    if isinstance(status, UserMessageRequestStatus):
        print(status.message.content)
        # The tool is stuck in an infinite loop, repeatedly displaying the message "Waiting for process" until it encounters an error due to missing credentials for user "kurt_andrews".
    print(f"Token usage with MessageSummarizationTransform after 2 user messages: {listener_with_transform.usage.total_tokens} tokens")# .. start-##_Create_Token_Event_Listener
    # Token usage with MessageSummarizationTransform after 2 user messages: 9314 tokens





# %%[markdown]
## Create Agent Without Transform

# %%
agent_no_transform = Agent(
    llm=agent_llm,
    tools=[read_logs_tool],
    transforms=[],  # no transforms
)

listener_no_transform = TokenListener()
with register_event_listeners([listener_no_transform]):
    conversation = agent_no_transform.start_conversation()
    conversation.append_user_message("Can you explain the error in the system?")
    status = conversation.execute()
    if isinstance(status, UserMessageRequestStatus):
        print(status.message.content)

    # ... (same conversation as above)

    print(f"Token usage without MessageSummarizationTransform after 1 user message: {listener_no_transform.usage.total_tokens} tokens")
    # Token usage without MessageSummarizationTransform after 1 user message: 12757 tokens


    conversation.append_user_message('What is the exact message repeated in a loop? Do not recall the tool')
    status = conversation.execute()
    if isinstance(status, UserMessageRequestStatus):
        print(status.message.content)

    print(f"Token usage without MessageSummarizationTransform after 2 user messages: {listener_no_transform.usage.total_tokens} tokens")# .. start-##_Create_Token_Event_Listener
    # Token usage without MessageSummarizationTransform after 2 user messages: 25224 tokens





# %%[markdown]
## Create ConversationSummarizationTransform

# %%
from wayflowcore.transforms import ConversationSummarizationTransform

transform = ConversationSummarizationTransform(
    llm=summarization_llm,
    max_num_messages=5,
    min_num_messages=2
)


# %%[markdown]
## Run Agent With ConversationSummarizationTransform

# %%

agent = Agent(
    llm=agent_llm,
    tools=[],
    transforms=[transform],
)

conversation = agent.start_conversation()
conversation.append_user_message("What is the capital of Switzerland?")
conversation.execute()
conversation.append_user_message("Tell me a fun fact about it.")
conversation.execute()
conversation.append_user_message("What is the population?")
conversation.execute()
conversation.append_user_message("What is the area?")
conversation.execute()
conversation.append_user_message("What languages are spoken there?")
conversation.execute()
# The conversation will be summarized when it exceeds 5 messages



# %%[markdown]
## Create Both Transforms

# %%
transforms = [
    MessageSummarizationTransform(
        llm=summarization_llm,
        max_message_size=10000,
        summarized_message_template="Summarized content:\n{{summary}}"
    ),
    ConversationSummarizationTransform(
        llm=summarization_llm,
        max_num_messages=5,
        min_num_messages=2
    )
]


# %%[markdown]
## Run Agent With Both Transforms

# %%
agent = Agent(
    llm=summarization_llm,
    tools=[read_logs_tool],
    transforms=transforms,
)

conversation = agent.start_conversation()

LONG_CONVERSATION = [
    {"role": "user", "content": "Hi! Can you tell me something interesting about dolphins?"},
    {
        "role": "assistant",
        "content": "Absolutely! Dolphins are fascinating creatures, famous for their intelligence and complex behavior. For example, they have been observed using tools, such as covering their snouts with sponges to protect themselves while foraging on the seafloor. Dolphins also display strong social bonds and have been known to help injured individuals within their pods. Communication among dolphins is advanced; they use a series of clicks, whistles, and body movements to convey information, and some species even have distinctive signature whistles that function like names.",
    },
    {"role": "user", "content": "Wow, I didn’t know that. Do dolphins have good memory?"},
    {
        "role": "assistant",
        "content": "Dolphins possess remarkable memories, particularly when it comes to their social groups and vocal communication. Researchers have discovered that dolphins can remember the unique signature whistles of other dolphins for over 20 years, which is the longest social memory recorded in non-human animals. This ability highlights their sophisticated cognitive abilities and the importance of long-term relationships in dolphin societies. Memory also plays a crucial role in their navigation and hunting skills, as dolphins migrate and follow paths in the oceans over great distances. In addition, their keen memory supports learning from one another, enhancing the social structure of their pods.",
    },
    {
        "role": "user",
        "content": "That’s impressive. Are there other animals with similar intelligence?",
    },
    {
        "role": "assistant",
        "content": "Indeed, there are several other animals that exhibit forms of intelligence comparable to dolphins. Great apes, such as chimpanzees and orangutans, have been observed making and using tools, solving puzzles, and displaying empathy and self-awareness. Elephants show emotional intelligence and have complex social relationships, including mourning their dead and helping injured companions. Crows and parrots, members of the bird family, demonstrate advanced problem-solving, mimicry, and even the ability to plan for future events. These examples across different branches of the animal kingdom show that intelligence has evolved in diverse and fascinating ways.",
    },
    {"role": "user", "content": "Can elephants recognize themselves in a mirror like dolphins?"},
    {
        "role": "assistant",
        "content": "Yes, elephants are among the elite group of species known to pass the mirror self-recognition test, an experiment generally considered evidence of self-awareness. In these experiments, elephants explore themselves in mirrors and investigate marks on their bodies they otherwise couldn’t see. Notably, this test has only been passed by a few species, including certain great apes, dolphins, magpies, and elephants. Such ability hints at a deep cognitive capacity, suggesting they have a mental representation of themselves, which is foundational for empathy and understanding the experiences of others. This self-recognition is just one of the many amazing aspects of elephant intelligence that continue to be studied.",
    },
    {"role": "user", "content": "What is the mirror test?"},
    {
        "role": "assistant",
        "content": "The mirror test, also known as the mark test, is a behavioral technique designed to assess self-awareness in animals. In the test, an animal is marked with an odorless dye in a place it cannot see without a mirror. The animal is then given access to a mirror, and researchers observe whether it investigates or tries to touch the mark on its own body, indicating recognition of its reflection as itself, not another animal. Passing the mirror test suggests a level of self-concept, which is considered an advanced cognitive trait. However, not all intelligent animals pass the mirror test, and failing it doesn’t necessarily mean an animal lacks self-awareness – it might simply not care about the mark or not rely on visual cues.",
    },
    {
        "role": "user",
        "content": "Besides animals, what’s another field where recognition is important?",
    },
    {
        "role": "assistant",
        "content": "Recognition is vitally important in many human technologies, notably in the field of artificial intelligence. Facial recognition technology is widely used for security purposes, such as unlocking smartphones or monitoring public spaces. In social media, these algorithms help automatically tag friends in photos, organizing vast amounts of visual data. Additionally, recognition systems are applied in retail, for personalized marketing, and in health care, for patient identification and monitoring. However, these powerful tools also raise important questions around privacy and data security, sparking ongoing debates about their regulation and ethical use.",
    },
    {"role": "user", "content": "Is facial recognition always accurate?"},
    {
        "role": "assistant",
        "content": "Facial recognition technology has improved significantly over recent years, but it is not flawless and its accuracy can vary depending on several factors. Lighting, angle, image quality, and the diversity of data used to train the algorithms all influence performance. Notably, many studies have shown that facial recognition systems can have higher error rates when identifying people with darker skin tones or from underrepresented demographics, leading to concerns about bias and discrimination. This has prompted researchers and policymakers to push for better training data, algorithmic transparency, and stricter oversight. As the technology becomes more widespread, ensuring fairness and accuracy is an essential focus for developers and regulators alike.",
    },
    {"role": "user", "content": "What are some other ethical concerns in AI?"},
    {
        "role": "assistant",
        "content": "Ethical challenges in AI are numerous and complex, reflecting the far-reaching impact of these technologies on society. Privacy concerns are paramount, as AI systems often require large amounts of personal data, raising questions about consent and data protection. Bias in algorithms is another major issue, as AI can inadvertently reinforce existing societal prejudices if not carefully monitored and tested. Transparency is crucial, because many AI systems, especially those using deep learning, can behave as 'black boxes'—making decisions in ways that aren’t easily understandable to humans. Additionally, there are fears around job displacement, as automation could replace roles faster than new opportunities are created, necessitating careful consideration and retraining initiatives.",
    },
    {
        "role": "user",
        "content": "Job displacement is interesting. Which jobs are most at risk from AI?",
    },
    {
        "role": "assistant",
        "content": "Jobs that involve repetitive, predictable tasks are currently considered the most vulnerable to automation by AI. For example, data entry clerks, assembly line workers, and certain types of customer service representatives face a high likelihood of being replaced or augmented by machines. Even within fields like transportation, we’re seeing the rise of autonomous vehicles that could impact truck drivers and delivery personnel. On the other hand, roles that require creativity, complex decision-making, emotional intelligence, or physical dexterity in unpredictable environments—such as healthcare providers, artists, and skilled trades—are less susceptible for now. To manage this transition, many experts recommend investing in retraining programs and encouraging adaptability in the workforce.",
    },
    {"role": "user", "content": "On a lighter note, do you know any fun space facts?"},
    {
        "role": "assistant",
        "content": "Absolutely, space offers an endless trove of fascinating discoveries. For example, Venus has a very unusual rotation: a single day on Venus (one rotation on its axis) is actually longer than its year (one complete orbit around the Sun) due to its slow spin. There are also diamond rains on planets like Neptune and Uranus, caused by extreme pressure turning carbon into solid diamonds. You might be surprised to learn that there are more stars in the observable universe than grains of sand on all the Earth’s beaches combined. Finally, if you were to fall into a black hole, the laws of physics as we understand them break down at the singularity—a phenomenon still not fully explained by scientists.",
    },
    {"role": "user", "content": "That’s fascinating! How hot does it get on Venus?"},
    {
        "role": "assistant",
        "content": "Venus is the hottest planet in our solar system, even outpacing Mercury, which is closer to the Sun. The average surface temperature on Venus can reach an astonishing 465 degrees Celsius, or about 869 degrees Fahrenheit. This is hot enough to melt lead, and it creates an extremely inhospitable environment for life as we know it. The intense heat is largely due to the planet’s dense atmosphere, composed mostly of carbon dioxide, which traps heat through a runaway greenhouse effect. In addition to being scorching, Venus’s atmosphere features thick clouds of sulfuric acid that make its surface perpetually shrouded and acidic.",
    },
    {"role": "user", "content": "Why is Venus hotter than Mercury?"},
    {
        "role": "assistant",
        "content": "Despite being the second planet from the Sun, Venus is hotter than Mercury primarily because of its thick, carbon dioxide-rich atmosphere. This atmosphere acts as a blanket, trapping incoming solar radiation and preventing heat from escaping, leading to the planet's infamous runaway greenhouse effect. Meanwhile, Mercury has only a thin exosphere, which allows heat to escape into space quickly, resulting in dramatic temperature swings between day and night. The conditions on Venus are so extreme that even spacecraft sent to the surface survive only a few hours before being destroyed by the temperature and pressure. In effect, Venus offers a dramatic example of how atmospheric composition can significantly influence planetary climates.",
    },
    {"role": "user", "content": "Are there any missions planned to Venus soon?"},
    {
        "role": "assistant",
        "content": "Yes, the next decade promises to be exciting for Venus exploration, with both NASA and the European Space Agency planning new missions. NASA has announced the VERITAS and DAVINCI+ missions, aiming to study Venus’s geology, atmosphere, and history, with launches expected later this decade. ESA is preparing its own mission called EnVision, which will investigate Venus's surface and atmosphere using advanced radar and spectrometry. These missions hope to resolve key questions, such as whether Venus ever had oceans, what processes led to its intense greenhouse state, and if volcanic activity is still ongoing. Renewed interest in Venus stems from its potential to teach us about planetary evolution, including factors that affect habitability.",
    },
    {"role": "user", "content": "Cool! Back to Earth, what's the largest living structure here?"},
    {
        "role": "assistant",
        "content": "The largest living structure on Earth is the Great Barrier Reef, stretching more than 2,300 kilometers along Australia’s northeastern coast. This massive coral system is so large it can be seen from space, and it comprises thousands of individual reefs and hundreds of islands built by billions of tiny coral polyps. The reef supports an extraordinary diversity of marine life, hosting over 1,500 fish species, turtles, sea snakes, and countless invertebrates. It also plays a crucial ecological role, protecting coastlines from storms and supporting local economies through tourism and fishing. Unfortunately, despite its size and importance, the Great Barrier Reef faces significant threats from climate change, particularly coral bleaching and ocean acidification.",
    },
    {"role": "user", "content": "Is it in danger?"},
    {
        "role": "assistant",
        "content": "Sadly, the Great Barrier Reef is indeed at risk due to multiple environmental pressures. One of the most severe challenges is coral bleaching, which occurs when higher sea temperatures stress corals, causing them to expel the symbiotic algae they rely on for food and color. Repeated bleaching events in recent years have resulted in large-scale loss of coral cover, and the recovery process can be slow or incomplete. Additional threats include poor water quality from agricultural runoff, overfishing, cyclones, and outbreaks of crown-of-thorns starfish, which prey on corals. Conservation efforts are underway, but reducing global carbon emissions is crucial to ensuring the reef’s long-term survival.",
    },
    {"role": "user", "content": "Can coral reefs recover from bleaching?"},
    {
        "role": "assistant",
        "content": "Reef recovery after bleaching is possible, but it depends on the severity of the event and the time between subsequent stress episodes. Corals can regain their symbiotic algae and recover their vibrant colors if water temperatures return to normal quickly enough. However, back-to-back bleaching events—such as those in recent years—inhibit full recovery and can lead to widespread coral death. The resilience of a reef also depends on the health of its local ecosystem, water quality, and the diversity of coral species present. Active restoration efforts, like coral gardening and selective breeding for heat-tolerant corals, are being explored to help boost reef recovery in the face of a warming climate.",
    },
    {"role": "user", "content": "Are there artificial reefs?"},
    {
        "role": "assistant",
        "content": "Yes, artificial reefs have been employed worldwide as a means to enhance marine habitats and promote biodiversity. These structures can be made from a variety of materials, including concrete blocks, purpose-built modules, and even deliberately sunken ships or decommissioned military vehicles. When placed on the ocean floor, artificial reefs provide surfaces for corals to attach to and develop, which in turn attract fish and other marine species seeking food and shelter. Over time, these reefs can become thriving ecosystems, sometimes rivaling their natural counterparts in productivity. Besides ecological benefits, artificial reefs are also used to create tourist attractions for diving and help reduce pressure on natural reefs by diverting fishing and recreational activity.",
    },
    {"role": "user", "content": "Do fish immediately move into new artificial reefs?"},
    {
        "role": "assistant",
        "content": "Fish and other marine organisms often begin exploring and colonizing new artificial reefs quite quickly—sometimes within just a few weeks of their deployment. The structures offer instant shelter from predators and new feeding opportunities, which attract small fish and invertebrates first. Over several months, larger predatory species may start appearing as the new reef becomes established as a hunting and breeding ground. The colonization process is further accelerated if the surrounding water already hosts healthy marine life populations. Eventually, the artificial reef can develop complex food webs, supporting a community of organisms similar to that of natural reefs, though full ecosystem development takes several years.",
    },
    {
        "role": "user",
        "content": "I love learning these facts. Can you tell me one more surprising animal fact?",
    },
    {
        "role": "assistant",
        "content": "Of course! One particularly astonishing animal fact concerns the octopus: these remarkable creatures possess not one, but three hearts. Two of the hearts are responsible for pumping blood through the gills, where it picks up oxygen, while the third pumps oxygenated blood throughout the rest of the body. Octopuses also have blue blood, a consequence of their use of a copper-rich protein called hemocyanin instead of hemoglobin, which is based on iron and gives human blood its red color. The blue blood is more efficient at transporting oxygen in the cold, low-oxygen conditions of the ocean, making it especially advantageous for the octopus’s varied habitats. In addition to their unique circulatory system, octopuses are also known for their high intelligence, problem-solving abilities, and incredible camouflage skills.",
    },
    {"role": "user", "content": "That’s wild. Why do they have blue blood?"},
    {
        "role": "assistant",
        "content": "The blue color of octopus blood is due to the presence of hemocyanin, a copper-based molecule that binds with oxygen for transport throughout the body. This adaptation is particularly effective in the cold, low-oxygen environments found in many parts of the oceans where octopuses live. Hemocyanin is more efficient than hemoglobin (the iron-based molecule in red blood) under these conditions, which helps octopuses thrive in diverse and sometimes extreme marine settings. The evolution of blue blood is an example of the many unique physiological characteristics that have enabled cephalopods to become such successful marine invertebrates. It’s remarkable how life develops specialized solutions to meet the challenges of different environments.",
    },
]

for msg in LONG_CONVERSATION:
    conversation.append_message(
        Message(content=msg["content"], role=msg["role"])  # type: ignore
    )

conversation.append_user_message("What tool do dolphins sometimes use when foraging on the seafloor, and why?")
conversation.execute()
