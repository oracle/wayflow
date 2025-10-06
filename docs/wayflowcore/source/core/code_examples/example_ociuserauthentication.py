# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

def get_oci_genai_credentials():
    return {
        "user": "ocid1.user.oc1..aaaaaaaa",
        "key_content": "dummy_key_content",
        "fingerprint": "aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa",
        "tenancy": "ocid1.tenancy.oc1..aaaaaaaa",
        "compartment_id": "ocid1.compartment.oc1..aaaaaaaa",
        "region": "us-chicago-1",
    }


# .. start-userauthenticationconfig:
from wayflowcore.models.ociclientconfig import (
    OCIClientConfigWithUserAuthentication,
    OCIUserAuthenticationConfig,
)

# Assume we have an API to get credentials
oci_genai_cred = get_oci_genai_credentials()

user_config = OCIUserAuthenticationConfig(
    user=oci_genai_cred["user"],
    key_content=oci_genai_cred["key_content"],
    fingerprint=oci_genai_cred["fingerprint"],
    tenancy=oci_genai_cred["tenancy"],
    region=oci_genai_cred["region"],
)
# .. end-userauthenticationconfig:

# .. start-clientconfig:
client_config = OCIClientConfigWithUserAuthentication(
    service_endpoint="my_service_endpoint",  # replace it with your endpoint
    compartment_id=oci_genai_cred["compartment_id"],
    user_config=user_config,
)
# .. end-clientconfig:

# .. start-ocigenaimodel:
from wayflowcore.models.ocigenaimodel import OCIGenAIModel

llm = OCIGenAIModel(
    model_id="cohere.command-r-plus-08-2024",
    client_config=client_config,
)
# .. end-ocigenaimodel:

# .. start-llmmodelfactory:
from wayflowcore.models import LlmModelFactory

COHERE_CONFIG = {
    "model_type": "ocigenai",
    "model_id": "cohere.command-r-plus-08-2024",
    "client_config": client_config,
}
llm = LlmModelFactory.from_config(COHERE_CONFIG)
# .. end-llmmodelfactory
