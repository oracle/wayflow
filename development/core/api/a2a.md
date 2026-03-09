# A2A related classes

### *class* wayflowcore.a2a.a2aagent.A2AConnectionConfig(timeout=600.0, headers=None, verify=True, key_file=None, cert_file=None, ssl_ca_cert=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>, name='', description=None)

Configuration settings for establishing a connection in agent-to-agent (A2A) communication.

This class encapsulates the necessary parameters to set up HTTP connections with a remote server,
including timeout settings and security configurations for SSL/TLS.

* **Parameters:**
  * **timeout** (`float`) – The maximum time in seconds to wait for HTTP requests to complete before timing out.
    Defaults to 600.0 seconds.
  * **headers** (`Optional`[`Dict`[`str`, `str`]]) – A dictionary of HTTP headers to include in requests sent to the server.
    Defaults to None, meaning no additional headers are sent.
  * **verify** (`bool`) – Determines whether the client verifies the server’s SSL certificate, enabling HTTPS.
    If True, the client will verify the server’s identity using the provided ssl_ca_cert.
    If False, disables SSL verification (not recommended for production environments).
  * **key_file** (`Optional`[`str`]) – Path to the client’s private key file in PEM format, used for mTLS authentication.
    If None, mTLS cannot be performed. Defaults to None.
  * **cert_file** (`Optional`[`str`]) – Path to the client’s certificate chain file in PEM format, used for mTLS authentication.
    If None, mTLS cannot be performed. Defaults to None.
  * **ssl_ca_cert** (`Optional`[`str`]) – Path to the trusted CA certificate file in PEM format, used to verify the server’s identity.
    If None, the system’s certificate store is used. Defaults to None.
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)

#### cert_file *: `Optional`[`str`]* *= None*

#### headers *: `Optional`[`Dict`[`str`, `str`]]* *= None*

#### key_file *: `Optional`[`str`]* *= None*

#### ssl_ca_cert *: `Optional`[`str`]* *= None*

#### timeout *: `float`* *= 600.0*

#### verify *: `bool`* *= True*

### *class* wayflowcore.a2a.a2aagent.A2ASessionParameters(timeout=60.0, poll_interval=2.0, max_retries=5)

Configuration parameters for an A2A session, controlling polling timeout and retry behavior.

This class defines the settings used during agent-to-agent communication sessions,
particularly for polling and timeout behavior when waiting for responses from a remote server.

* **Parameters:**
  * **timeout** (`float`) – The maximum time in seconds to wait for a response before considering the session timed out.
    Defaults to 60.0 seconds.
  * **poll_interval** (`float`) – The time interval in seconds between polling attempts to check for a response from the server.
    Defaults to 2.0 seconds.
  * **max_retries** (`int`) – The maximum number of retry attempts to establish a connection or receive a response before
    giving up. Defaults to 5 retries.

#### max_retries *: `int`* *= 5*

#### poll_interval *: `float`* *= 2.0*

#### timeout *: `float`* *= 60.0*

## A2A Agent

refer [A2AAgent](agent.md#a2aagent)
