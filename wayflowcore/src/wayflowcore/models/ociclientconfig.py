# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import os
import warnings
from abc import ABC
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Dict, Optional, Union

from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.warnings import SecurityWarning

logger = logging.getLogger(__name__)


class _OCIAuthType(str, Enum):
    API_KEY = "API_KEY"
    SECURITY_TOKEN = "SECURITY_TOKEN"  # nosec
    INSTANCE_PRINCIPAL = "INSTANCE_PRINCIPAL"
    RESOURCE_PRINCIPAL = "RESOURCE_PRINCIPAL"


@dataclass
class OCIClientConfig(SerializableObject, ABC):
    """Base abstract class for OCI client config"""

    _can_be_referenced: ClassVar[bool] = False

    service_endpoint: str
    auth_type: _OCIAuthType
    compartment_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.compartment_id:
            warnings.warn(
                "Usage of ``compartment_id`` is deprecated from 25.3, and will be removed in 25.5. "
                "Please pass this field to ``OCIGenAIModel`` instead.",
                DeprecationWarning,
            )

    def to_dict(self) -> Dict[str, Union[str, Dict[str, Any]]]:
        return {
            "service_endpoint": self.service_endpoint,
            "compartment_id": self.compartment_id or "",
            "auth_type": self.auth_type.name,
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        return cls.from_dict(input_dict)

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_dict(cls, input_dict: Dict[str, Union[str, Dict[str, str]]]) -> "OCIClientConfig":
        config: Dict[str, Any] = deepcopy(input_dict)
        auth_type = config.pop("auth_type")
        if auth_type == _OCIAuthType.API_KEY:
            return OCIClientConfig._create_api_key_config(config)
        elif auth_type == _OCIAuthType.SECURITY_TOKEN:
            return OCIClientConfigWithSecurityToken(**config)
        elif auth_type == _OCIAuthType.INSTANCE_PRINCIPAL:
            return OCIClientConfigWithInstancePrincipal(**config)
        elif auth_type == _OCIAuthType.RESOURCE_PRINCIPAL:
            return OCIClientConfigWithResourcePrincipal(**config)
        else:
            raise ValueError(
                "Error occured during deserialization. Please make sure the `auth_type` ",
                "is correctly passed.",
            )

    @staticmethod
    def _create_api_key_config(config: Dict[str, Any]) -> "OCIClientConfig":
        if "user_config" in config:
            if isinstance(config["user_config"], dict):
                config["user_config"] = OCIUserAuthenticationConfig.from_dict(config["user_config"])
            elif not isinstance(config["user_config"], OCIUserAuthenticationConfig):
                raise TypeError(
                    f"'user_config' should be either a dictionary or an OCIUserAuthenticationConfig object. "
                    f"Got type {type(config['user_config'])} instead."
                )
            return OCIClientConfigWithUserAuthentication(**config)
        else:
            return OCIClientConfigWithApiKey(**config)


class OCIClientConfigWithApiKey(OCIClientConfig):
    def __init__(
        self,
        service_endpoint: str,
        compartment_id: Optional[str] = None,
        auth_profile: Optional[str] = None,
        _auth_file_location: Optional[str] = None,  # not supported yet
    ) -> None:
        """
        OCI client config class for authentication using API_KEY.

        Parameters
        ----------
        service_endpoint:
            the endpoint of the OCI GenAI service.
        compartment_id:
            compartment id to use.
        auth_profile:
            name of the profile to use in the config file. Defaults to "DEFAULT".
        """
        self.auth_profile = auth_profile or "DEFAULT"
        self.auth_file_location = _auth_file_location or "~/.oci/config"
        super().__init__(service_endpoint, _OCIAuthType.API_KEY, compartment_id=compartment_id)

    def to_dict(self) -> Dict[str, Union[str, Dict[str, str]]]:
        base_config = super().to_dict()
        base_config.update(
            {
                "auth_profile": self.auth_profile,
                "_auth_file_location": self.auth_file_location,
            }
        )
        return base_config


class OCIClientConfigWithSecurityToken(OCIClientConfig):
    def __init__(
        self,
        service_endpoint: str,
        compartment_id: Optional[str] = None,
        auth_profile: Optional[str] = None,
        _auth_file_location: Optional[str] = None,  # not supported yet
    ) -> None:
        """
        OCI client config class for authentication using SECURITY_TOKEN.

        Parameters
        ----------
        service_endpoint:
            the endpoint of the OCI GenAI service.
        compartment_id:
            compartment id to use.
        auth_profile:
            name of the profile to use in the config file. Defaults to "DEFAULT".
        """
        self.auth_profile = auth_profile or "DEFAULT"
        self.auth_file_location = _auth_file_location or "~/.oci/config"
        super().__init__(
            service_endpoint, _OCIAuthType.SECURITY_TOKEN, compartment_id=compartment_id  # nosec
        )

    def to_dict(self) -> Dict[str, Union[str, Dict[str, str]]]:
        base_config = super().to_dict()
        base_config.update(
            {
                "auth_profile": self.auth_profile,
                "_auth_file_location": self.auth_file_location,
            }
        )
        return base_config


class OCIClientConfigWithInstancePrincipal(OCIClientConfig):
    def __init__(self, service_endpoint: str, compartment_id: Optional[str] = None) -> None:
        """
        OCI client config class for authentication using INSTANCE_PRINCIPAL.

        Parameters
        ----------
        service_endpoint:
            the endpoint of the OCI GenAI service.
        compartment_id:
            compartment id to use.
        """
        super().__init__(
            service_endpoint, _OCIAuthType.INSTANCE_PRINCIPAL, compartment_id=compartment_id
        )


class OCIClientConfigWithResourcePrincipal(OCIClientConfig):
    def __init__(self, service_endpoint: str, compartment_id: Optional[str] = None) -> None:
        """
        OCI client config class for authentication using RESOURCE_PRINCIPAL.

        Parameters
        ----------
        service_endpoint:
            the endpoint of the OCI GenAI service.
        compartment_id:
            compartment id to use.
        """
        super().__init__(
            service_endpoint, _OCIAuthType.RESOURCE_PRINCIPAL, compartment_id=compartment_id
        )


class OCIUserAuthenticationConfig:
    def __init__(
        self, user: str, key_content: str, fingerprint: str, tenancy: str, region: str
    ) -> None:
        """
        Create an OCI user authentication config, which can be passed to the OCIClientConfigWithUserAuthentication class in order to authenticate the OCI service.

        This class provides a way to authenticate the OCI service without relying on a config file.
        In other words, it is equivalent to saving the config in a file and passing the file using OCIClientConfigWithApiKey class.

        Parameters
        ----------
        user:
            user OCID
        key_content:
            content of the private key
        fingerprint:
            fingerprint of your public key
        tenancy:
            tenancy OCID
        region:
            OCI region

        .. warning::
            This class contains sensitive information. Please make sure that the contents are not printed or logged.
        """
        self.user = user
        self.key_content = key_content
        self.fingerprint = fingerprint
        self.tenancy = tenancy
        self.region = region

        # validate the config
        import oci  # type: ignore

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=SecurityWarning)
            oci.config.validate_config(self._get_config())

    def to_dict(self) -> Dict[str, str]:
        warnings.warn(
            "OCIUserAuthenticationConfig is a security sensitive configuration object, and cannot be serialized.",
            SecurityWarning,
        )
        return {}

    @classmethod
    def from_dict(cls, client_config: Dict[str, str]) -> "OCIUserAuthenticationConfig":
        raise ValueError(
            "OCIUserAuthenticationConfig is a security sensitive configuration object, and cannot be deserialized."
        )

    def _get_config(self) -> Dict[str, Optional[str]]:
        warnings.warn(
            (
                "'_get_config()' method of OCIUserAuthenticationConfig will return sensitive information. "
                "Please make sure the content is not leaked."
            ),
            SecurityWarning,
        )
        return {
            "user": self.user,
            "key_content": self.key_content,
            "fingerprint": self.fingerprint,
            "tenancy": self.tenancy,
            "region": self.region,
        }


class OCIClientConfigWithUserAuthentication(OCIClientConfig):
    def __init__(
        self,
        service_endpoint: str,
        user_config: OCIUserAuthenticationConfig,
        compartment_id: Optional[str] = None,
    ) -> None:
        if not isinstance(user_config, OCIUserAuthenticationConfig):
            raise TypeError("'user_config' must be an OCIUserAuthenticationConfig object.")
        self.user_config = user_config
        super().__init__(service_endpoint, _OCIAuthType.API_KEY, compartment_id=compartment_id)

    def to_dict(self) -> Dict[str, Union[str, Dict[str, Any]]]:
        base_config = super().to_dict()
        base_config.update(
            {
                "user_config": self.user_config.to_dict(),  # currently returns an empty dict
            }
        )
        return base_config


def _client_config_to_oci_client_kwargs(client_config: OCIClientConfig) -> Dict[str, Any]:
    import oci

    client_kwargs = dict(
        service_endpoint=client_config.service_endpoint,
        retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY,
        timeout=(10, 240),
        config={},
    )

    if isinstance(client_config, OCIClientConfigWithUserAuthentication):
        # retry_strategy and timeout are set as the same value as in the langchain wrapper
        # so that we have the same behavior in both option 1 and option 2
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=SecurityWarning)
            client_user_config = client_config.user_config._get_config()

        client_kwargs["config"] = client_user_config
    elif isinstance(client_config, OCIClientConfigWithApiKey):
        client_kwargs["config"] = oci.config.from_file(
            file_location=client_config.auth_file_location,
            profile_name=client_config.auth_profile,
        )
    elif isinstance(client_config, OCIClientConfigWithSecurityToken):
        oci_config = oci.config.from_file(
            file_location=client_config.auth_file_location,
            profile_name=client_config.auth_profile,
        )
        pk = oci.signer.load_private_key_from_file(oci_config.get("key_file"), None)
        with open(oci_config.get("security_token_file"), encoding="utf-8") as f:
            st_string = f.read()

        client_kwargs["config"] = oci_config
        client_kwargs["signer"] = oci.auth.signers.SecurityTokenSigner(st_string, pk)
    elif isinstance(client_config, OCIClientConfigWithInstancePrincipal):
        client_kwargs["signer"] = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    elif isinstance(client_config, OCIClientConfigWithResourcePrincipal):
        client_kwargs["signer"] = oci.auth.signers.get_resource_principals_signer()
    return client_kwargs


def _convert_arguments_into_client_config(
    compartment_id: Optional[str],
    service_endpoint: Optional[str],
    auth_type: Optional[str],
    auth_profile: Optional[str],
) -> OCIClientConfig:
    compartment_id = compartment_id or os.getenv("OCI_GENAI_COMPARTMENT")
    if not (service_endpoint and auth_type and compartment_id):
        raise ValueError(
            "Either client config (recommeded) or service_endpoint, auth_type, "
            "and compartment_id arguments need to specified (deprecated)."
        )

    if auth_type == _OCIAuthType.API_KEY:
        return OCIClientConfigWithApiKey(
            service_endpoint=service_endpoint,
            compartment_id=compartment_id,
            auth_profile=auth_profile,
        )
    elif auth_type == _OCIAuthType.SECURITY_TOKEN:
        return OCIClientConfigWithSecurityToken(
            service_endpoint=service_endpoint,
            compartment_id=compartment_id,
            auth_profile=auth_profile,
        )
    elif auth_type == _OCIAuthType.INSTANCE_PRINCIPAL:
        return OCIClientConfigWithInstancePrincipal(
            service_endpoint=service_endpoint, compartment_id=compartment_id
        )
    elif auth_type == _OCIAuthType.RESOURCE_PRINCIPAL:
        return OCIClientConfigWithResourcePrincipal(
            service_endpoint=service_endpoint, compartment_id=compartment_id
        )
    else:
        raise ValueError(
            "Given `auth_type` is not supported. Valid options are: API_KEY, ",
            "SECURITY_TOKEN, INSTANCE_PRINCIPAL, RESOURCE_PRINCIPAL.",
        )
