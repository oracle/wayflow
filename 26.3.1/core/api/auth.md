# Auth

This page presents all APIs and classes related to WayFlow Auth configuration components.

## Auth classes

<a id="authconfig"></a>

### *class* wayflowcore.auth.auth.AuthConfig(\_\_metadata_info_\_=None, id=None)

Base class for Auth configurations.

* **Parameters:**
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str* *|* *None*)

<a id="oauthendpoints"></a>

### *class* wayflowcore.auth.auth.OAuthEndpoints(authorization_endpoint, token_endpoint, refresh_endpoint=None, revocation_endpoint=None, userinfo_endpoint=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Explicit OAuth endpoint configuration.

Use this component when endpoint discovery is not available or not desired.
This groups the relevant endpoints required to execute OAuth authorization
code flows and token refresh.

* **Parameters:**
  * **authorization_endpoint** (*str*)
  * **token_endpoint** (*str*)
  * **refresh_endpoint** (*str* *|* *None*)
  * **revocation_endpoint** (*str* *|* *None*)
  * **userinfo_endpoint** (*str* *|* *None*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### authorization_endpoint *: `str`*

Authorization endpoint where the user agent is redirected for login and consent.

#### refresh_endpoint *: `Optional`[`str`]* *= None*

Optional endpoint for refresh token requests.

#### revocation_endpoint *: `Optional`[`str`]* *= None*

Optional endpoint for token revocation.

#### token_endpoint *: `str`*

Token endpoint where authorization codes are exchanged for access tokens.

#### userinfo_endpoint *: `Optional`[`str`]* *= None*

Optional OIDC UserInfo endpoint.

<a id="pkcemethod"></a>

### *class* wayflowcore.auth.auth.PKCEMethod(value)

An enumeration.

#### PLAIN *= 'plain'*

Code challenge is equal to code verifier.

#### S256 *= 'S256'*

Code verifier is hashed using SHA-256. Recommended over the `plain` method

<a id="pkcepolicy"></a>

### *class* wayflowcore.auth.auth.PKCEPolicy(required=True, method=PKCEMethod.S256, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Policy configuration for Proof Key for Code Exchange (PKCE).

PKCE mitigates authorization code interception and injection attacks in
authorization code flows. Some protocols (such as MCP OAuth) require PKCE.

* **Parameters:**
  * **required** (*bool*)
  * **method** ([*PKCEMethod*](#wayflowcore.auth.auth.PKCEMethod))
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### method *: [`PKCEMethod`](#wayflowcore.auth.auth.PKCEMethod)* *= 'S256'*

PKCE challenge method (e.g., `"S256"`). Defaults to `"S256"`.

#### required *: `bool`* *= True*

If True, the connection must be refused if PKCE cannot be used or
cannot be validated as supported by the authorization server.
Defaults to `True`.

<a id="oauthclientconfig"></a>

### *class* wayflowcore.auth.auth.OAuthClientConfig(type, client_id=None, client_secret=None, token_endpoint_auth_method=None, client_id_metadata_url=None, registration_endpoint=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

OAuth client identity / registration configuration.

This configuration describes the OAuth client identity to use
with the authorization server. It supports:
- Pre-registered clients (static client_id/client_secret)
- Client ID Metadata Documents (URL-formatted client_id)
- Dynamic client registration (RFC 7591)

* **Parameters:**
  * **type** (*Literal* *[* *'pre_registered'* *,*  *'client_id_metadata_document'* *,*  *'dynamic_registration'* *]*)
  * **client_id** (*str* *|* *None*)
  * **client_secret** (*str* *|* *None*)
  * **token_endpoint_auth_method** (*str* *|* *None*)
  * **client_id_metadata_url** (*str* *|* *None*)
  * **registration_endpoint** (*str* *|* *None*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### client_id *: `Optional`[`str`]* *= None*

OAuth client identifier (used for pre-registered clients).

#### client_id_metadata_url *: `Optional`[`str`]* *= None*

HTTPS URL used as the OAuth `client_id` for Client ID Metadata Documents.

#### client_secret *: `Optional`[`str`]* *= None*

OAuth client secret (used for confidential pre-registered clients).

#### registration_endpoint *: `Optional`[`str`]* *= None*

Optional dynamic registration endpoint. If omitted, may be obtained
from authorization server discovery metadata when available.

#### token_endpoint_auth_method *: `Optional`[`str`]* *= None*

Token endpoint authentication method (e.g., `"client_secret_basic"`,
`"client_secret_post"`, `"private_key_jwt"`, or `"none"`).

#### type *: `Literal`[`'pre_registered'`, `'client_id_metadata_document'`, `'dynamic_registration'`]*

Strategy used to obtain client identity.

<a id="oauthconfig"></a>

### *class* wayflowcore.auth.auth.OAuthConfig(issuer=None, endpoints=None, client=<factory>, redirect_uri=<factory>, scopes=None, scope_policy=None, pkce=None, resource=None, callback_timeout_seconds=300.0, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Configure OAuth-based authentication for a tool or transport.

OAuthConfig is a generic configuration that can be used for both MCP servers
and non-MCP remote API tools. It supports discovery-based configuration (via
`issuer`) and explicit endpoints (via `endpoints`).

* **Parameters:**
  * **issuer** (*str* *|* *None*)
  * **endpoints** ([*OAuthEndpoints*](#wayflowcore.auth.auth.OAuthEndpoints) *|* *None*)
  * **client** ([*OAuthClientConfig*](#wayflowcore.auth.auth.OAuthClientConfig))
  * **redirect_uri** (*str*)
  * **scopes** (*str* *|* *List* *[**str* *]*  *|* *None*)
  * **scope_policy** (*Literal* *[* *'use_challenge_or_supported'* *,*  *'fixed'* *]*  *|* *None*)
  * **pkce** ([*PKCEPolicy*](#wayflowcore.auth.auth.PKCEPolicy) *|* *None*)
  * **resource** (*str* *|* *None*)
  * **callback_timeout_seconds** (*float*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### callback_timeout_seconds *: `float`* *= 300.0*

Maximum time to wait for the OAuth callback/challenge results to be received before timing out.

#### client *: [`OAuthClientConfig`](#wayflowcore.auth.auth.OAuthClientConfig)*

OAuth client identity / registration configuration.

#### endpoints *: `Optional`[[`OAuthEndpoints`](#wayflowcore.auth.auth.OAuthEndpoints)]* *= None*

Explicit OAuth endpoints. When provided, these endpoints should be used
directly instead of discovery.

#### issuer *: `Optional`[`str`]* *= None*

Authorization server issuer URL used for discovery (e.g., OIDC discovery
or RFC 8414).

#### pkce *: `Optional`[[`PKCEPolicy`](#wayflowcore.auth.auth.PKCEPolicy)]* *= None*

PKCE policy. For authorization code flows, this should typically be set
to required with method `S256`.

#### redirect_uri *: `str`*

Redirect (callback) URI registered with the authorization server.

#### resource *: `Optional`[`str`]* *= None*

Optional resource indicator value (RFC 8707). If set, this should be
includeed with relevant authorization and token requests when applicable.

#### scope_policy *: `Optional`[`Literal`[`'use_challenge_or_supported'`, `'fixed'`]]* *= None*

How the scopes are selected.

* `"use_challenge_or_supported"`: may prefer scopes indicated by
  : challenges/metadata.
* `"fixed"`: requests exactly the provided scopes.

#### scopes *: `Union`[`str`, `List`[`str`], `None`]* *= None*

Requested scopes, either as a space-delimited string or a list of scope
strings.

## Auth-related Classes

<a id="authchallengerequest"></a>

### *class* wayflowcore.auth.auth.AuthChallengeRequest(resource_uri, issuer, authorization_url, \_conversation_id=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Dataclass to store auth challenge request data to
present to the client/app to complete an auth flow.

* **Parameters:**
  * **resource_uri** (*str* *|* *None*)
  * **issuer** (*list* *[**str* *]*  *|* *None*)
  * **authorization_url** (*str*)
  * **\_conversation_id** (*str* *|* *None*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### authorization_url *: `str`*

The authorization endpoint URL to which the user agent should be directed
to authenticate and grant consent.

#### issuer *: `Optional`[`list`[`str`]]*

The OAuth/OIDC authorization server issuer identifier (typically a URL).
May be omitted if discovery is not used or issuer is unknown.

#### resource_uri *: `Optional`[`str`]*

The protected resource being accessed (e.g., MCP server URL or API base URL).
May be omitted if not known or not applicable.

<a id="authchallengeresult"></a>

### *class* wayflowcore.auth.auth.AuthChallengeResult(code=None, state=None, error=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Dataclass to store OAuth challenge result information.

The auth `code` and `state` are then exchanged with the OAuth tokens.

* **Parameters:**
  * **code** (*str* *|* *None*)
  * **state** (*str* *|* *None*)
  * **error** (*Exception* *|* *None*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### code *: `Optional`[`str`]* *= None*

OAuth 2.0 authorization code returned to the redirect URI, if the user
successfully authenticated/consented.

#### error *: `Optional`[`Exception`]* *= None*

Exception describing failure to complete the challenge (e.g., user
cancelled, redirect contained an error parameter, network/timeout).

#### state *: `Optional`[`str`]* *= None*

Opaque value originally provided in the authorization request and returned
in the callback. Used to correlate/validate the response.
