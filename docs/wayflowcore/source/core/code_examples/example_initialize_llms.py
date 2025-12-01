# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

# .. oci-start
from wayflowcore.models import OCIGenAIModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey

if __name__ == "__main__":

    # Get the list of available models from:
    # https://docs.oracle.com/en-us/iaas/Content/generative-ai/deprecating.htm#
    # under the "Model Retirement Dates (On-Demand Mode)" section.
    OCIGENAI_MODEL_ID = "cohere.command-r-plus-08-2024"
    # e.g. <oci region> can be "us-chicago-1" and can also be found in your ~/.oci/config file
    OCIGENAI_ENDPOINT = "https://inference.generativeai.<oci region>.oci.oraclecloud.com"
    # <compartment_id> can be obtained from your personal OCI account (not the key config file).
    # Please find it under "Identity > Compartments" on the OCI console website after logging in to your user account.
    COMPARTMENT_ID = compartment_id = ("ocid1.compartment.oc1..<compartment_id>",)

    generation_config = LlmGenerationConfig(max_tokens=256, temperature=0.8, top_p=0.95)

    llm = OCIGenAIModel(
        model_id=OCIGENAI_MODEL_ID,
        client_config=OCIClientConfigWithApiKey(
            service_endpoint=OCIGENAI_ENDPOINT,
            compartment_id=COMPARTMENT_ID,
        ),
        generation_config=generation_config,
    )
# .. oci-end

# .. oci-llmfactory-start
if __name__ == "__main__":
    COHERE_CONFIG = {
        "model_type": "ocigenai",
        "model_id": OCIGENAI_MODEL_ID,
        "client_config": {
            "service_endpoint": OCIGENAI_ENDPOINT,
            "compartment_id": COMPARTMENT_ID,
            "auth_type": "API_KEY",
        },
    }

    llm = LlmModelFactory.from_config(COHERE_CONFIG)
# .. oci-llmfactory-end

# .. vllm-start
from wayflowcore.models import VllmModel

if __name__ == "__main__":

    VLLM_MODEL_ID = "/storage/models/Llama-3.1-70B-Instruct"

    generation_config = LlmGenerationConfig(max_tokens=512, temperature=1.0, top_p=1.0)

    llm = VllmModel(
        model_id=VLLM_MODEL_ID,
        host_port=os.environ["VLLM_HOST_PORT"],
        generation_config=generation_config,
    )
# .. vllm-end

# .. vllm-llmfactory-start
if __name__ == "__main__":
    VLLM_CONFIG = {
        "model_type": "vllm",
        "host_port": VLLM_HOST_PORT,
        "model_id": VLLM_MODEL_ID,
    }

    llm = LlmModelFactory.from_config(VLLM_CONFIG)
# .. vllm-llmfactory-end


# export OPENAI_API_KEY=<a_valid_open_ai_key>
# For the sake of this example, we use a dummy key
import os

# .. openai-start
from wayflowcore.models import OpenAIModel, OpenAIAPIType

if __name__ == "__main__":

    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "DUMMY_OPENAI_KEY")

    # supported models "gpt-4o", "gpt-4o-mini".
    # We currently do not support gpt-o1 and gpt-o3 models.
    OPENAI_MODEL_ID = "gpt-5"

    generation_config = LlmGenerationConfig(max_tokens=256, temperature=0.7, top_p=0.9)

    api_type = OpenAIAPIType.RESPONSES

    llm = OpenAIModel(
        model_id=OPENAI_MODEL_ID,
        generation_config=generation_config,
        api_type=api_type,
    )
# .. openai-end

# .. openai-llmfactory-start
if __name__ == "__main__":
    OPENAI_CONFIG = {
        "model_type": "openai",
        "model_id": OPENAI_MODEL_ID,
        "generation_config": {"max_tokens": 256, "temperature": 0.7, "top_p": 0.9},
    }

    llm = LlmModelFactory.from_config(OPENAI_CONFIG)
# .. openai-llmfactory-end

# .. ollama-start
from wayflowcore.models import OllamaModel

if __name__ == "__main__":

    OLLAMA_MODEL_ID = "llama2-7b"
    OLLAMA_HOST_PORT = "localhost:11434"  # default is 11434 if omitted

    generation_config = LlmGenerationConfig(max_tokens=512, temperature=0.9, top_p=0.9)

    llm = OllamaModel(
        model_id=OLLAMA_MODEL_ID, host_port=OLLAMA_HOST_PORT, generation_config=generation_config
    )
# .. ollama-end

# .. ollama-llmfactory-start
if __name__ == "__main__":
    OLLAMA_CONFIG = {
        "model_type": "ollama",
        "model_id": OLLAMA_MODEL_ID,
        "host_port": OLLAMA_HOST_PORT,
        "generation_config": {"max_tokens": 512, "temperature": 0.9, "top_p": 0.9},
    }

    llm = LlmModelFactory.from_config(OLLAMA_CONFIG)
# .. ollama-llmfactory-end

# .. recap:
from wayflowcore.models import OCIGenAIModel, OllamaModel, OpenAIModel, VllmModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig

OCIGENAI_MODEL_ID = "cohere.command-r-plus"
OCIGENAI_ENDPOINT = "<YOUR_SERVICE_ENDPOINT>"
COMPARTMENT_ID = "<YOUR_COMPARTMENT_ID>"

if __name__ == "__main__":

    generation_config = LlmGenerationConfig(max_tokens=256, temperature=0.8, top_p=0.95)

    llm = OCIGenAIModel(
        model_id=OCIGENAI_MODEL_ID,
        client_config=OCIClientConfigWithApiKey(
            service_endpoint=OCIGENAI_ENDPOINT,
            compartment_id=COMPARTMENT_ID,
        ),
        generation_config=generation_config,
    )

    VLLM_MODEL_ID = "/storage/models/Llama-3.1-70B-Instruct"
    VLLM_HOST_PORT = "lVLLM_HOST_PORT"

    generation_config = LlmGenerationConfig(max_tokens=512, temperature=1.0, top_p=1.0)

    llm = VllmModel(
        model_id=VLLM_MODEL_ID,
        host_port=VLLM_HOST_PORT,
        generation_config=generation_config,
    )

    # export OPENAI_API_KEY=<a_valid_open_ai_key>
    # supported models "gpt-4o", "gpt-4o-mini".
    # We currently do not support gpt-o1 and gpt-o3 models.
    OPENAI_MODEL_ID = "gpt-4o"

    generation_config = LlmGenerationConfig(max_tokens=256, temperature=0.7, top_p=0.9)

    llm = OpenAIModel(
        model_id=OPENAI_MODEL_ID,
        generation_config=generation_config,
    )

    OLLAMA_MODEL_ID = "llama2-7b"
    OLLAMA_HOST_PORT = "localhost:11434"  # default is 11434 if omitted

    generation_config = LlmGenerationConfig(max_tokens=512, temperature=0.9, top_p=0.9)

    llm = OllamaModel(
        model_id=OLLAMA_MODEL_ID, host_port=OLLAMA_HOST_PORT, generation_config=generation_config
    )
# .. end-recap:
