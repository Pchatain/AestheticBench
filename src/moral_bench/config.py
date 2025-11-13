"""Configuration management for MoralBench."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Configuration for MoralBench."""

    api_key: str
    base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    http_referer: str = "https://github.com/moralbench"
    x_title: str = "MoralBench"
    health_check_timeout: int = 30
    request_timeout: int = 60
    max_workers: int = 10

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
        max_workers_str = os.getenv("MORALBENCH_WORKERS", "10")
        try:
            max_workers = int(max_workers_str)
            if max_workers < 0:
                raise ValueError("MORALBENCH_WORKERS must be >= 0")
        except ValueError as e:
            raise ValueError(
                f"Invalid MORALBENCH_WORKERS value '{max_workers_str}': {e}"
            )

        return cls(
            api_key=api_key,
            max_workers=max_workers,
        )
