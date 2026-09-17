"""Package init: wire logfire before anything imports the library."""

from importlib.metadata import version

import logfire

from .cli import main
from .config.settings import get_settings

__version__ = version("schemai-builder")
settings = get_settings()

# ARCHITECTURE DECISION: distributed_tracing=False is required for Google Cloud Run deployments.
# Cloud Run injects 'X-Cloud-Trace-Context' headers. If distributed_tracing is enabled,
# Logfire will try to use these external trace IDs as parents, resulting in "orphaned"
# root traces in the Logfire UI since the parent span doesn't exist in our system.
logfire.configure(
    token=settings.logfire.token_value,
    send_to_logfire="if-token-present",
    distributed_tracing=False,
    environment=settings.environment,
    service_name=settings.project,
    service_version=__version__,
    scrubbing=False if settings.debug else None,
)

logfire.instrument_pydantic_ai()
logfire.instrument_httpx()

__all__ = ["main"]
