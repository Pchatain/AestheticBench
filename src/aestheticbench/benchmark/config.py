"""Configuration management for AestheticBench."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Configuration for AestheticBench."""

    api_key: str
    base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    http_referer: str = "https://github.com/aestheticbench"
    x_title: str = "AestheticBench"
    health_check_timeout: int = 30
    request_timeout: int = 120
    max_workers: int = 64
    max_retries: int = 5
    initial_backoff: float = 1.0
    max_backoff: float = 60.0

    @property
    def headers(self) -> dict[str, str]:
        """Return the HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.http_referer,
            "X-Title": self.x_title,
        }

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not found in environment variables. "
                "Please run setup.sh to configure your API key."
            )

        # Allow customizing max_workers via environment variable
        max_workers_str = os.getenv("AESTHETICBENCH_WORKERS", "64")
        try:
            max_workers = int(max_workers_str)
            if max_workers < 0:
                raise ValueError("AESTHETICBENCH_WORKERS must be >= 0")
        except ValueError as e:
            raise ValueError(
                f"Invalid AESTHETICBENCH_WORKERS value '{max_workers_str}': {e}"
            )

        return cls(
            api_key=api_key,
            max_workers=max_workers,
        )

    def with_workers(self, max_workers: int) -> "Config":
        """Return a copy of config with different max_workers."""
        return Config(
            api_key=self.api_key,
            base_url=self.base_url,
            http_referer=self.http_referer,
            x_title=self.x_title,
            health_check_timeout=self.health_check_timeout,
            request_timeout=self.request_timeout,
            max_workers=max_workers,
            max_retries=self.max_retries,
            initial_backoff=self.initial_backoff,
            max_backoff=self.max_backoff,
        )
