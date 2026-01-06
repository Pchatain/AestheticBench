"""OpenRouter API client using httpx."""

import httpx
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from tqdm import tqdm
from typing import Callable, Optional

from .config import Config


@dataclass
class BatchStats:
    """Statistics for a batch operation."""
    total: int = 0
    completed: int = 0
    failed: int = 0
    retries: int = 0
    rate_limited: int = 0
    current_concurrency: int = 64
    
    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "retries": self.retries,
            "rate_limited": self.rate_limited,
            "current_concurrency": self.current_concurrency,
        }


class OpenRouterClient:
    """Client for interacting with OpenRouter API."""

    def __init__(self, config: Config):
        """Initialize the OpenRouter client.

        Args:
            config: Configuration object containing API credentials and settings.
        """
        self.config = config
        self._client = httpx.Client(
            headers=config.headers,
            timeout=config.request_timeout,
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close the client."""
        self.close()

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def get_available_models(self) -> Optional[list[dict]]:
        """Fetch list of available models from OpenRouter.

        Returns:
            List of model dictionaries if successful, None otherwise.
        """
        try:
            response = self._client.get(
                "https://openrouter.ai/api/v1/models",
                timeout=self.config.health_check_timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            else:
                print(f"✗ Failed to fetch models: {response.status_code}")
                return None

        except httpx.HTTPError as e:
            print(f"✗ Error fetching models: {e}")
            return None

    def get_model_info(self, model_name: str) -> Optional[dict]:
        """Get detailed information about a specific model.

        Args:
            model_name: The model ID to look up (e.g., "openai/gpt-4o").

        Returns:
            Dictionary with model information including pricing, or None if not found.
        """
        models = self.get_available_models()
        if models is None:
            return None

        for model in models:
            if model.get("id") == model_name:
                return model

        return None

    def verify_model(self, model_name: str, verbose: bool = True) -> bool:
        """Verify that a model exists in OpenRouter's available models.

        Args:
            model_name: The model ID to verify (e.g., "openai/gpt-4o").
            verbose: Whether to print verification messages.

        Returns:
            True if the model exists, False otherwise.
        """
        if verbose:
            print(f"Verifying model: {model_name}...")

        models = self.get_available_models()
        if models is None:
            if verbose:
                print("✗ Could not fetch available models")
            return False

        # Check if model exists
        model_ids = [model.get("id") for model in models]
        if model_name in model_ids:
            if verbose:
                print(f"✓ Model '{model_name}' is available")
            return True
        else:
            if verbose:
                print(f"✗ Model '{model_name}' not found")
                print(f"  Available models: {len(model_ids)} total")
                # Show similar models if any
                similar = [m for m in model_ids if model_name.split("/")[0] in m]
                if similar:
                    print(f"  Similar models: {', '.join(similar[:5])}")
            return False

    def health_check(self) -> bool:
        """Verify OpenRouter API connection with a simple test request.

        Returns:
            True if the connection is successful, False otherwise.
        """
        print("Testing OpenRouter API connection...")

        try:
            response = self._client.post(
                self.config.base_url,
                json={
                    "model": "openai/gpt-4o",
                    "messages": [
                        {"role": "user", "content": "Say 'OK' if you can read this."}
                    ],
                },
                timeout=self.config.health_check_timeout,
            )

            if response.status_code == 200:
                print("✓ OpenRouter API connection successful")
                return True
            else:
                print(f"✗ API request failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                return False

        except httpx.HTTPError as e:
            print(f"✗ Connection error: {e}")
            return False

    def chat_completion(
        self,
        message: str,
        model: str = "openai/gpt-4o",
        timeout: Optional[int] = None,
    ) -> str:
        """Send a single chat completion request.

        Args:
            message: The message to send to the model.
            model: The model to use for the completion.
            timeout: Optional timeout override for this request.

        Returns:
            The model's response text.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        response = self._client.post(
            self.config.base_url,
            json={"model": model, "messages": [{"role": "user", "content": message}]},
            timeout=timeout or self.config.request_timeout,
        )

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def batch_chat_completions(
        self,
        messages: list[str],
        model: str = "openai/gpt-4o",
        max_workers: Optional[int] = None,
        on_status: Optional[Callable[[BatchStats], None]] = None,
    ) -> list[tuple[int, str, Optional[str]]]:
        """Send multiple chat completion requests in parallel with adaptive rate limiting.

        Args:
            messages: List of messages to send to the model.
            model: The model to use for completions.
            max_workers: Initial number of concurrent workers. If 0, run sequentially.
                        If None, use config.max_workers (default 64).
            on_status: Optional callback for status updates (rate limits, backoffs).

        Returns:
            List of tuples (index, message, response) where response is None if error occurred.
        """
        if max_workers is None:
            max_workers = self.config.max_workers

        results: list[tuple[int, str, Optional[str]]] = []
        stats = BatchStats(total=len(messages), current_concurrency=max_workers)
        
        # Thread-safe state for adaptive concurrency
        lock = threading.Lock()
        current_workers = max_workers
        backoff_until = 0.0

        # Sequential mode when max_workers is 0
        if max_workers == 0:
            for i, message in tqdm(
                enumerate(messages),
                total=len(messages),
                desc="Processing prompts",
                unit="prompt",
                leave=True,
            ):
                try:
                    response = self.chat_completion(message, model)
                    results.append((i, message, response))
                    stats.completed += 1
                except Exception as e:
                    tqdm.write(f"  ✗ Error: {e}")
                    results.append((i, message, None))
                    stats.failed += 1
            return results

        def process_with_retry(index: int, message: str) -> tuple[int, str, Optional[str]]:
            """Process a single message with retries and exponential backoff."""
            nonlocal current_workers, backoff_until
            
            max_retries = self.config.max_retries
            backoff = self.config.initial_backoff
            
            for attempt in range(max_retries + 1):
                # Check if we need to wait for backoff
                with lock:
                    wait_time = backoff_until - time.time()
                if wait_time > 0:
                    time.sleep(wait_time)
                
                try:
                    response = self.chat_completion(message, model)
                    return (index, message, response)
                    
                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code
                    
                    # Rate limit (429) or server overload (529)
                    if status_code in (429, 529):
                        with lock:
                            stats.rate_limited += 1
                            # Reduce concurrency on rate limit
                            new_workers = max(4, current_workers // 2)
                            if new_workers < current_workers:
                                current_workers = new_workers
                                stats.current_concurrency = current_workers
                                tqdm.write(f"  ⚠ Rate limited, reducing concurrency to {current_workers}")
                            
                            # Set global backoff
                            retry_after = float(e.response.headers.get("Retry-After", backoff))
                            backoff_until = time.time() + retry_after
                        
                        if on_status:
                            on_status(stats)
                        
                        if attempt < max_retries:
                            stats.retries += 1
                            # Exponential backoff with jitter
                            sleep_time = backoff * (2 ** attempt) + random.uniform(0, 1)
                            sleep_time = min(sleep_time, self.config.max_backoff)
                            tqdm.write(f"  ⏳ Retrying {index} in {sleep_time:.1f}s (attempt {attempt + 1}/{max_retries})")
                            time.sleep(sleep_time)
                            continue
                    
                    # Other HTTP errors - don't retry
                    tqdm.write(f"  ✗ HTTP {status_code} for message {index}: {e}")
                    return (index, message, None)
                    
                except httpx.TimeoutException:
                    if attempt < max_retries:
                        stats.retries += 1
                        tqdm.write(f"  ⏳ Timeout for {index}, retrying (attempt {attempt + 1}/{max_retries})")
                        time.sleep(backoff * (2 ** attempt))
                        continue
                    tqdm.write(f"  ✗ Timeout for message {index} after {max_retries} retries")
                    return (index, message, None)
                    
                except Exception as e:
                    tqdm.write(f"  ✗ Error processing message {index}: {e}")
                    return (index, message, None)
            
            return (index, message, None)

        # Parallel mode with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(process_with_retry, i, msg): i
                for i, msg in enumerate(messages)
            }

            with tqdm(
                total=len(messages),
                desc=f"Processing ({max_workers} workers)",
                unit="prompt",
                leave=True,
            ) as pbar:
                for future in as_completed(future_to_index):
                    result = future.result()
                    results.append(result)
                    
                    if result[2] is not None:
                        stats.completed += 1
                    else:
                        stats.failed += 1
                    
                    # Update progress bar description with current concurrency
                    with lock:
                        if stats.current_concurrency != max_workers:
                            pbar.set_description(f"Processing ({stats.current_concurrency} workers)")
                    
                    pbar.update(1)
                    
                    if on_status:
                        on_status(stats)

        # Sort results by original index to maintain order
        results.sort(key=lambda x: x[0])
        
        # Final status report
        if stats.rate_limited > 0:
            tqdm.write(f"  ℹ Rate limits hit: {stats.rate_limited}, Total retries: {stats.retries}")
        
        return results
