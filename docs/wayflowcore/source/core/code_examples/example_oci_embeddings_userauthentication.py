# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

from wayflowcore.embeddingmodels.ocigenaimodel import OCIGenAIEmbeddingModel
from wayflowcore.models.ociclientconfig import (
    OCIClientConfigWithUserAuthentication,
    OCIUserAuthenticationConfig,
)


def get_oci_genai_credentials():
    return {
        "user": "ocid1.user.oc1..aaaaaaaa",
        "key_content": "dummy_key_content",  # This is the content between the ---BEGIN/END--- lines of the key
        "fingerprint": "aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa",
        "tenancy": "ocid1.tenancy.oc1..aaaaaaaa",
        "compartment_id": "ocid1.compartment.oc1..aaaaaaaa",
        "region": "us-chicago-1",
    }


# .. start-embeddings-userauthenticationconfig:
# Assume we have an API to get credentials
oci_genai_cred = get_oci_genai_credentials()

user_config = OCIUserAuthenticationConfig(
    user=oci_genai_cred["user"],
    key_content=oci_genai_cred["key_content"],
    fingerprint=oci_genai_cred["fingerprint"],
    tenancy=oci_genai_cred["tenancy"],
    region=oci_genai_cred["region"],
)
# .. end-embeddings-userauthenticationconfig

# .. start-embeddings-clientconfig:
# Create client configuration with user authentication
client_config = OCIClientConfigWithUserAuthentication(
    service_endpoint="my_service_endpoint",  # replace it with your endpoint
    compartment_id=oci_genai_cred["compartment_id"],
    user_config=user_config,
)
# .. end-embeddings-clientconfig

# .. start-ocigenaiembeddingmodel:
# Create the OCIGenAIEmbeddingModel with the client configuration
oci_embedding_model = OCIGenAIEmbeddingModel(
    model_id="cohere.embed-english-light-v3.0",
    config=client_config,
)

# Generate embeddings
text_list = [
    "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
]
# embeddings = oci_embedding_model.embed(text_list)
# .. end-ocigenaiembeddingmodel
