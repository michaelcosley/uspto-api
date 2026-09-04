# Request Pacing and Retries

## Defaults

Both clients serialize requests within the current Python process. Open Data
Portal calls sharing the same base URL and API key share a coordinator;
Assignment Center clients sharing the same base URL share a separate
coordinator.

- Ordinary API calls: minimum 0.010 seconds (10 ms) between starts.
- Serial downloads: minimum 0.050 seconds (50 ms) between starts.
- Automatic retries: disabled.

Configure pacing explicitly:

```python
from uspto_client import PacingConfig, UsptoClient

client = UsptoClient(
    api_key="...",
    pacing_config=PacingConfig(
        request_interval_seconds=0.025,
        download_interval_seconds=0.100,
    ),
)
```

Zero disables the corresponding minimum interval. Process-local coordination
cannot prevent collisions with another process or machine using the same key.

## Opt-in retries

```python
from uspto_client import RetryConfig, UsptoClient

client = UsptoClient(
    api_key="...",
    retry_config=RetryConfig(
        retry_on_429=True,
        retry_on_5xx=True,
        retry_on_transport_error=True,
        max_attempts=3,
        backoff_initial_seconds=0.5,
        backoff_multiplier=2.0,
        backoff_max_seconds=30.0,
    ),
)
```

For HTTP 429, the wait is at least five seconds and honors a longer numeric
`Retry-After` value. HTTP 5xx and transport failures use bounded exponential
backoff. HTTP 404 is never retried or converted to an empty result; it remains
a `UsptoNotFoundError`. In particular, some PTAB searches return 404 when no
records match.
