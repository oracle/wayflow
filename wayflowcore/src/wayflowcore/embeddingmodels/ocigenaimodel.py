# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import warnings
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.async_helpers import run_sync_in_thread
from wayflowcore._utils.lazy_loader import LazyLoader
from wayflowcore.embeddingmodels.embeddingmodel import EmbeddingModel
from wayflowcore.models.ociclientconfig import OCIClientConfig, _client_config_to_oci_client_kwargs
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject

if TYPE_CHECKING:
    # Important: do not move this import out of the TYPE_CHECKING block so long as oci is an optional dependency.
    # Otherwise, importing the module when they are not installed would lead to an import error.
    import oci  # type: ignore
else:
    oci = LazyLoader("oci")


class OCIGenAIEmbeddingModel(EmbeddingModel, SerializableObject):
    """Embedding model for Oracle OCI Generative AI service.

    Parameters
    ----------
    model_id
        The model identifier (e.g., 'cohere.embed-english-light-v3.0').
    config
        OCI client configuration with authentication details.
    compartment_id:
        The compartment OCID

    Examples
    --------
    The following examples show how to configure the OCIGenAIEmbeddingModel.
    In actual use, replace the placeholder values with your real credentials.

    # Option 1: User Authentication Config
    >>> from wayflowcore.models.ociclientconfig import OCIUserAuthenticationConfig, OCIClientConfigWithUserAuthentication  # doctest: +SKIP
    >>> oci_user_config = OCIUserAuthenticationConfig(  # doctest: +SKIP
    ...     user="<my_user_ocid>",
    ...     key_content="<my_key_content>",
    ...     fingerprint="<fingerprint_of_my_public_key>",
    ...     tenancy="<my_tenancy_ocid>",
    ...     region="<my_oci_region>",
    ... )
    >>> client_config = OCIClientConfigWithUserAuthentication(  # doctest: +SKIP
    ...     service_endpoint="https://inference.generativeai.us-<your key's region>.oci.oraclecloud.com",
    ...     compartment_id="<Please read the 'Using the API_KEY authentication method' subsection in the 'How to Use LLM from Different LLM Sources/Providers' how-to guide>",
    ...     user_config=oci_user_config
    ... )

    # Option 2: Instance Principal
    >>> from wayflowcore.models.ociclientconfig import OCIClientConfigWithInstancePrincipal  # doctest: +SKIP
    >>> client_config = OCIClientConfigWithInstancePrincipal(  # doctest: +SKIP
    ...     service_endpoint="https://inference.generativeai.us-<your key's region>.oci.oraclecloud.com",
    ...     compartment_id="<Please read the 'Using the API_KEY authentication method' subsection in the 'How to Use LLM from Different LLM Sources/Providers' how-to guide>",
    ... )

    # Option 3: API Key from the default config file
    >>> from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey  # doctest: +SKIP
    >>> client_config = OCIClientConfigWithApiKey(  # doctest: +SKIP
    ...     service_endpoint="https://inference.generativeai.us-<your key's region>.oci.oraclecloud.com",
    ...     compartment_id="<Please read the 'Using the API_KEY authentication method' subsection in the 'How to Use LLM from Different LLM Sources/Providers' how-to guide>",
    ... )

    # Using the configured client with the embedding model
    >>> from wayflowcore.embeddingmodels.ocigenaimodel import OCIGenAIEmbeddingModel
    >>> model = OCIGenAIEmbeddingModel(  # doctest: +SKIP
    ...     model_id="cohere.embed-english-light-v3.0",
    ...     config=client_config,  # Use whichever client_config option you prefer
    ... )
    >>> embeddings = model.embed(["WayFlow is a framework to develop and run LLM-based assistants."])  # doctest: +SKIP

    Notes
    -----
    The OCI SDK must be installed.
    For generating the OCI config file, please follow the WayFlow documentation.

    Available embedding models: https://docs.oracle.com/en-us/iaas/Content/generative-ai/pretrained-models.htm
    """

    def __init__(
        self,
        model_id: str,
        config: "OCIClientConfig",
        compartment_id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        super().__init__(
            __metadata_info__=__metadata_info__, id=id, name=name, description=description
        )

        # There are two ways to initialize the ocigenai model:
        # Option (1) Pass OCIClientConfigWithUserAuthentication
        #    This way, we use configuration provided directly through the user_config object
        #    rather than depending on local configuration files. The required authentication
        #    parameters (user, key_content, fingerprint, tenancy, region) are passed directly
        #    in the OCIUserAuthenticationConfig object. This option is useful when you want to
        #    authenticate using API_KEY but don't want to rely on local config files.
        #
        # Option (2) Pass other types of OCIClientConfig
        #    For OCIClientConfigWithInstancePrincipal:
        #      Uses instance principal authentication which is ideal for applications running
        #      on OCI instances. No config file is needed, as the authentication is based on
        #      the instance's identity.
        #
        #    For OCIClientConfigWithApiKey:
        #      Uses API key authentication by loading credentials from a config file. By default,
        #      it reads from "~/.oci/config" with the "DEFAULT" profile, but these can be
        #      customized through the auth_file_location and auth_profile attributes.
        #
        #    In both cases of Option 2, an OCI client is created directly within this class
        #    with appropriate authentication settings.

        self.service_endpoint = config.service_endpoint
        self.oci_client_kwargs = _client_config_to_oci_client_kwargs(config)
        self._config = self.oci_client_kwargs["config"]

        if compartment_id:
            self.compartment_id = compartment_id
        elif config.compartment_id:
            warnings.warn(
                "Passing `compartment_id` to the client config is deprecated. "
                "Please pass the id to the `OCIGenAIEmbeddingModel` instead.",
                DeprecationWarning,
            )
            self.compartment_id = config.compartment_id
        else:
            raise ValueError("Compartment id should not be ``None``.")

        self._model_id = model_id

        # The client is set in a lazy manner to prevent the model from crashing before being
        # used in case the configuration is not valid for some reason.
        self._lazy_client = None
        self.config = config

    def _set_client(self) -> None:
        """Sets the GenerativeAiInferenceClient if it's not set already."""
        if not self._lazy_client:
            self._lazy_client = oci.generative_ai_inference.GenerativeAiInferenceClient(
                **self.oci_client_kwargs
            )

    @property
    def _client(self) -> "oci.generative_ai_inference.GenerativeAiInferenceClient":
        self._set_client()
        return self._lazy_client

    def embed(self, data: List[str]) -> List[List[float]]:
        embed_text_details = oci.generative_ai_inference.models.EmbedTextDetails(
            inputs=data,
            compartment_id=self.compartment_id,
            serving_mode=oci.generative_ai_inference.models.OnDemandServingMode(
                model_id=self._model_id
            ),
        )
        response = self._client.embed_text(embed_text_details=embed_text_details)
        # Cast the embeddings to the expected return type (mainly for mypy)
        return cast(List[List[float]], response.data.embeddings)

    async def embed_async(self, data: List[str]) -> List[List[float]]:
        return await run_sync_in_thread(self.embed, data)

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        # Store minimal information needed to recreate the embedding model
        # avoiding sensitive authentication details
        serialized_dict: Dict[str, Optional[str]] = {
            "model_id": self._model_id,
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }

        # For the config, handle different types differently
        # while avoiding directly serializing sensitive information
        if isinstance(self._config, dict) and "compartment_id" in self._config:
            serialized_dict["compartment_id"] = self._config["compartment_id"]

        # Store information about what type of configuration this is
        # Store service endpoint from client
        serialized_dict["service_endpoint"] = self._client.base_client.endpoint

        # Determine config type
        if isinstance(self._config, dict) and "user" in self._config:
            serialized_dict["config_type"] = "user_authentication"
        elif (
            isinstance(self._config, dict)
            and len(self._config) == 1
            and "compartment_id" in self._config
        ):
            serialized_dict["config_type"] = "instance_principal"
        else:
            serialized_dict["config_type"] = "api_key"

        return serialized_dict

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        model_id = input_dict.get("model_id")
        if not model_id:
            raise ValueError("Missing required 'model_id' in serialized data")

        compartment_id = input_dict.get("compartment_id")
        service_endpoint = input_dict.get("service_endpoint")
        config_type = input_dict.get("config_type")
        id = input_dict.get("id", None)
        name = input_dict.get("name", None)
        description = input_dict.get("description", None)

        if not service_endpoint or not compartment_id:
            raise ValueError(
                "Deserialization requires 'service_endpoint' and 'compartment_id' to be present. "
                "These should be provided through runtime configuration."
            )

        # Create the appropriate config object based on the saved config_type
        if config_type == "instance_principal":
            from wayflowcore.models.ociclientconfig import OCIClientConfigWithInstancePrincipal

            config: OCIClientConfig = OCIClientConfigWithInstancePrincipal(
                service_endpoint=service_endpoint
            )
        elif config_type == "user_authentication":
            # For user authentication, external configuration must be provided
            # This is a security measure to avoid storing sensitive credentials
            raise ValueError(
                "User authentication configuration cannot be automatically deserialized. "
                "Please provide an OCIClientConfigWithUserAuthentication instance at runtime."
            )
        else:  # Default to API key from config file
            from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey

            config = OCIClientConfigWithApiKey(service_endpoint=service_endpoint)

        return cls(
            model_id=model_id,
            config=config,
            compartment_id=compartment_id,
            id=id,
            name=name,
            description=description,
        )
