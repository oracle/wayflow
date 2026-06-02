# Retries

This page presents the API related to retry configuration for remote components in WayFlow.

## Retry Policy

<a id="retrypolicy"></a>

### *class* wayflowcore.retrypolicy.RetryPolicy(max_attempts=2, request_timeout=600.0, initial_retry_delay=1.0, max_retry_delay=8.0, backoff_factor=2.0, jitter=RetryJitter.FULL_AND_EQUAL_FOR_THROTTLE, service_error_retry_on_any_5xx=True, recoverable_statuses=<factory>)

Provider-agnostic retry policy.

### Notes

- `max_attempts` is the maximum number of retries (does not include the initial attempt).
- `initial_retry_delay`/`max_retry_delay` apply to the sleep between attempts.

* **Parameters:**
  * **max_attempts** (*int*)
  * **request_timeout** (*float*)
  * **initial_retry_delay** (*float*)
  * **max_retry_delay** (*float*)
  * **backoff_factor** (*float*)
  * **jitter** ([*RetryJitter*](#wayflowcore.retrypolicy.RetryJitter) *|* *None*)
  * **service_error_retry_on_any_5xx** (*bool*)
  * **recoverable_statuses** (*Dict* *[**str* *,* *List* *[**str* *]* *]*)

#### backoff_factor *: float* *= 2.0*

Multiplier applied between retry delays during exponential backoff.

#### initial_retry_delay *: float* *= 1.0*

Base delay in seconds used to compute exponential backoff.

#### jitter *: Optional[RetryJitter]* *= 'full_and_equal_for_throttle'*

Randomization strategy applied to the computed backoff delay.

#### max_attempts *: int* *= 2*

Maximum number of retry attempts after the initial request.

#### max_retry_delay *: float* *= 8.0*

Upper bound in seconds for the delay between two retry attempts.

#### recoverable_statuses *: Dict[str, List[str]]*

Additional HTTP statuses to treat as retryable.

The dictionary key is the numeric HTTP status code encoded as a string.
The value is a list of textual service error codes to match for that status.
An empty list means the numeric status code alone is enough to retry.
A non-empty list means both the numeric status code and one of the textual
codes must match before the request is retried.

#### request_timeout *: float* *= 600.0*

Maximum allowed time (in seconds) for a single request attempt.

This is a per-attempt timeout. When set, runtimes should pass this value to the
underlying HTTP client / SDK timeout configuration. Values are expressed in
seconds and may be fractional (e.g., `0.5` means 500 milliseconds).

#### service_error_retry_on_any_5xx *: bool* *= True*

Whether retryable 5xx responses except 501 should be retried.

#### *property* total_attempts *: int*

## Retry Jitter

### *class* wayflowcore.retrypolicy.RetryJitter(value, names=<not given>, \*values, module=None, qualname=None, type=None, start=1, boundary=None)

Supported jitter strategies for retry backoff.

#### DECORRELATED *= 'decorrelated'*

#### EQUAL *= 'equal'*

#### FULL *= 'full'*

#### FULL_AND_EQUAL_FOR_THROTTLE *= 'full_and_equal_for_throttle'*
